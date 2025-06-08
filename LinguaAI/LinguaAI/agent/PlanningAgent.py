from typing import List, Dict, Any
import openai
import sys
import os
import json
import random
from LinguaAI.prompts import PLANNING_PROMPT, WRITING_PROMPTS
from LinguaAI.agent.ReadingAgent import ReadingAgent, MaterialType
from LinguaAI.agent.WritingAgent import WritingAgent
import json
from LinguaAI.agent.ListeningAgent import ListeningAgent, ListeningMode, MaterialType as ListeningMaterialType
from LinguaAI.database import TaskDatabase, ChatDatabase

db = TaskDatabase()
scene_db = ChatDatabase()
db_settings = scene_db.get_settings()
class PlanningAgent:
    """学习计划代理，用于管理和协调不同学习模块"""
    
    def __init__(self, conversation_id: str):
        """
        初始化计划代理
        
        """
        print('初始化开始')
        self.conversation_id = conversation_id
        print('conversation_id初始化成功')
        self.client = openai.OpenAI(
            api_key=db_settings["api_key"],
            base_url=db_settings["host"]
        )
        print('openai初始化成功')
        self.read_agent = ReadingAgent(use_online_search=True)
        print('reading初始化成功')
        self.listening_agent = ListeningAgent(use_online_search=True)
        print('listening初始化成功')
        self.writing_agent = WritingAgent()
        print('writing初始化成功')

    @classmethod
    async def create(cls, conversation_id):
        self = cls(conversation_id)
        print('基础初始化成功')
        await self.init_by_conversation_id()
        print('conversation_id初始化成功')
        return self
    async def init_by_conversation_id(self):
        print('conversation_id初始化开始')
        self.mode = db.get_conversation_mode(self.conversation_id)
        print('mode初始化成功')
        self.mode_start = db.get_conversation_mode_start(self.conversation_id)
        print('mode_start初始化成功')
        self.task = db.get_conversation_task(self.conversation_id)
        print('task初始化成功')
        if self.task:
            self.module_order = self.task.get("modules", [])
        else:
            self.module_order = None

    async def analyze_learning_needs(self, user_input: str) -> Dict[str, Any]:
        """分析用户的学习需求，确定需要使用的学习模块
        
        Args:
            user_input: 用户的学习需求描述
            
        Returns:
            Dict: 包含需要使用的学习模块和具体任务
        """
        print('analyze_learning_needs开始')
        prompt = PLANNING_PROMPT["analyze_needs"].format(user_input=user_input)
        for i in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=db_settings["model_name"],
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
            except Exception as e:
                print('error', e)
                continue
            try:
                print('response', response.choices[0].message.content)
                result = json.loads(response.choices[0].message.content)
                result['user_input'] = user_input
                self.task = result
                db.update_conversation_task(self.conversation_id, json.dumps(result))
                print('db更新成功')
                break
            except json.JSONDecodeError:
                print(f"解析失败，重试第{i + 1}次")
                continue
        if result is None:
            return "解析失败，请重试"
        # 生成自然语言描述
        modules = result.get("modules", [])
        tasks = result.get("tasks", {})
        module_names = "、".join(modules)
        task_descriptions = []
        for module in modules:
            desc = tasks.get(module, "")
            if desc:
                task_descriptions.append(f"{module}：{desc}")
        tasks_text = "；".join(task_descriptions)
        natural_text = f"根据您的需求，建议您重点学习以下模块：{module_names}。具体任务包括：{tasks_text}。"
        
        print('analyze_learning_needs结束')
        print('result', natural_text)
        return natural_text, result
        
    async def execute_learning_plan(self, user_input: str):
        """执行学习计划
        
        Args:
            user_input: 用户的学习需求描述
        """
        print('execute_learning_plan开始')
        idx = self.module_order.index(self.mode)
        listening_question = db.get_question(self.conversation_id, self.mode)
        if user_input.isdigit() and idx == len(self.module_order) - 1 and '听力练习' not in listening_question:
            if user_input == "1":
                self.mode_start = True
                return await self._handle_mode(self.mode, user_input)
            elif user_input == "2":
                db.update_conversation_mode(self.conversation_id, "start")
                return "本次学习结束啦"
        if user_input.isdigit() and self.mode_start and self.mode == "listening":
            return await self._handle_listening(user_input)
        if user_input.isdigit() and not self.mode_start:
            self.mode_start = True
            if user_input == "1":
                print('继续当前模块')
                if self.mode == "reading":
                    return await self._handle_reading(user_input)
                elif self.mode == "writing":
                    return await self._handle_writing(user_input)
                elif self.mode == "listening":
                    return await self._handle_listening(user_input)
                else:
                    return f"未知模块: {self.mode}"
            elif user_input == "2":
                print('进入下一个模块')
                try:
                    idx = self.module_order.index(self.mode)
                    next_mode = self.module_order[(idx + 1) % len(self.module_order)]
                    self.mode = next_mode
                    print('next_mode', next_mode)
                    db.update_conversation_mode(self.conversation_id, self.mode)
                    if self.mode == "reading":
                        return await self._handle_reading(user_input)
                    elif self.mode == "writing":
                        return await self._handle_writing(user_input)
                    elif self.mode == "listening":
                        return await self._handle_listening(user_input)
                except ValueError:
                    return f"当前模块 {self.mode} 不在模块顺序列表中"
        else:
            self.mode_start = False
            if self.mode == "reading":
                return await self._handle_reading(user_input)
            elif self.mode == "writing":
                return await self._handle_writing(user_input)
            elif self.mode == "listening":
                return await self._handle_listening(user_input)
        
    async def _handle_reading(self, user_input: str):
        """处理阅读练习"""
        print('------------handle_reading------------')
        if self.mode_start:
            material_type = MaterialType.NEWS
            if "考试" in self.task['tasks']['reading'] or "测试" in self.task['tasks']['reading']:
                material_type = MaterialType.EXAM
            elif "文章" in self.task['tasks']['reading']:
                material_type = MaterialType.ARTICLE

            prompt = PLANNING_PROMPT["generate_keywords_for_reading"].format(task=self.task['user_input'])
            
            for i in range(3):
                response = self.client.chat.completions.create(
                    model=db_settings["model_name"],
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.9
                )
                print('response', response.choices[0].message.content)
                content = response.choices[0].message.content.strip()
                try:
                    search_queries = json.loads(content)
                    break
                except json.JSONDecodeError:
                    print(f"解析失败，重试第{i + 1}次")
                    continue
            
            for query in search_queries:
                result = self.read_agent.process_reading_session(query, material_type)
                print('result', result)
                if result.get("status") != "error":
                    feedback = result['reading_material']
                    db.update_conversation_mode_start(self.conversation_id, False)
                    return feedback
        print('-------evaluate_user_summary------------')
        content = db.get_question(self.conversation_id, "reading")
        print('content', content)
        eval_result = self.read_agent.evaluate_user_summary(user_input, content)
        print('阅读evaluation', eval_result)
        feedback = "\n=== 评估结果 ===\n"
        feedback += f"理解准确度: {eval_result.get('understanding_score', 0):.2f}\n"
        feedback += "\n主要观点:\n"
        for point in eval_result.get("main_points", []):
            feedback += f"- {point}\n"
        feedback += "\n需要改进的地方:\n"
        for misunderstanding in eval_result.get("misunderstandings", []):
            feedback += f"- {misunderstanding}\n"
        feedback += "\n建议:\n"
        for suggestion in eval_result.get("suggestions", []):
            feedback += f"- {suggestion}\n"
        feedback += "\n详细反馈:\n"
        feedback += eval_result.get("detailed_feedback", "") + "\n"
        feedback += "\n=== 阅读练习完成 ===\n"
        return feedback
        
    async def _handle_writing(self, user_input: str):
        """处理写作练习"""
        if self.mode_start:
            print('self.task', self.task)
            feedback = self.writing_agent.generate_question(self.task['user_input'])
            feedback += "\n请根据上面的要点用英文写作："
            db.update_conversation_mode_start(self.conversation_id, False)
            print('writing feedback', feedback)
            return feedback
        else:
            question = db.get_question(self.conversation_id, "writing")
            print('question', question)
            feedback = "写作评估\n"
            feedback += "语法错误：\n"
            feedback += self.writing_agent.check_grammar(user_input)
            feedback += "写作评分：\n"
            feedback += self.writing_agent.review_and_score_writing(user_input, question)
            return feedback

    
    async def _handle_listening(self, user_input: str):
        """处理听力练习（调用ListeningAgent）"""
        print('------------handle_listening------------')
        if self.mode_start and not user_input.isdigit():
            feedback = "\n=== 听力练习 ===\n"
            feedback += "请选择听力模式：\n"
            feedback += "1. 泛听（Extensive Listening，整体理解）\n"
            feedback += "2. 精听（Intensive Listening，听写/细节）\n"
            feedback += "请输入模式编号(1/2，默认1):"
            return feedback
        if user_input.isdigit():
            mode = ListeningMode.EXTENSIVE if user_input != "2" else ListeningMode.INTENSIVE
            db.update_conversation_listening_mode(self.conversation_id, mode.value)
            prompt = PLANNING_PROMPT["generate_keywords_for_listening"].format(task=user_input)
            
            response = self.client.chat.completions.create(
                model=db_settings["model_name"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9  
            )
            
            for i in range(3):
                content = response.choices[0].message.content.strip()
                try:
                    search_queries = json.loads(content)
                    break
                except json.JSONDecodeError:
                    continue
            print('search_queries', search_queries)
            for query in search_queries:
                result = self.listening_agent.process_listening_session(query, mode)
                db.update_conversation_mode_start(self.conversation_id, False)
                return result
        else:
            mode = db.get_conversation_listening_mode(self.conversation_id)
            
            content = db.get_question(self.conversation_id, "listening")
            print('content', content)

            evaluation = self.listening_agent.evaluate_user_response(user_input, mode, content)
            if evaluation.get("status") == "success":
                eval_result = evaluation.get("evaluation", {})
                feedback = "\n=== 评估结果 ===\n"
                if mode == ListeningMode.EXTENSIVE:
                    feedback += f"理解准确度: {eval_result.get('understanding_score', 0):.2f}\n"
                    feedback += "\n主要观点:\n"
                    for point in eval_result.get("main_points", []):
                        feedback += f"- {point}\n"
                    feedback += "\n需要改进的地方:\n"
                    for misunderstanding in eval_result.get("misunderstandings", []):
                        feedback += f"- {misunderstanding}\n"
                    feedback += "\n建议:\n"
                    for suggestion in eval_result.get("suggestions", []):
                        feedback += f"- {suggestion}\n"
                    feedback += "\n详细反馈:\n"
                    feedback += eval_result.get("detailed_feedback", "") + "\n"
                else:
                    feedback += f"听写准确度: {eval_result.get('accuracy_score', 0):.2f}\n"
                    feedback += "\n拼写错误:\n"
                    for err in eval_result.get("spelling_errors", []):
                        feedback += f"- {err}\n"
                    feedback += "\n语法错误:\n"
                    for err in eval_result.get("grammar_errors", []):
                        feedback += f"- {err}\n"
                    feedback += "\n漏听内容:\n"
                    for miss in eval_result.get("missing_content", []):
                        feedback += f"- {miss}\n"
                    feedback += "\n建议:\n"
                    for suggestion in eval_result.get("suggestions", []):
                        feedback += f"- {suggestion}\n"
                    feedback += "\n详细反馈:\n"
                    feedback += eval_result.get("detailed_feedback", "") + "\n"
                feedback += "\n=== 听力练习完成 ===\n"
                db.update_conversation_mode_start(self.conversation_id, False)
                return feedback
            else:
                return f"评估出错: {evaluation.get('message', '未知错误')}"

    async def _handle_mode(self, mode: str, user_input: str = None):
        if mode == "reading":
            return await self._handle_reading(user_input)
        elif mode == "writing":
            return await self._handle_writing(user_input)
        elif mode == "listening":
            return await self._handle_listening(user_input)

    async def chat(self, message: str):
        """与用户进行对话"""

        user_input = message.strip()

        if self.mode == "start":
            first, result = await self.analyze_learning_needs(user_input)
            mode = result["modules"][0]
            second = await self._handle_mode(mode, user_input)
            db.update_conversation_mode(self.conversation_id, mode)
            db.add_message(self.conversation_id, "assistant", first + "\n" + second, mode)
            return first + "\n" + second
            
        else:
            response = await self.execute_learning_plan(user_input)
            if response == "本次学习结束啦":
                return response
            idx = self.module_order.index(self.mode)
            if not self.mode_start:
                if idx == len(self.module_order) - 1:
                    response += "\n请选择下一步操作："
                    response += "\n 继续当前模块（1）"
                    response += "\n 结束学习（2）"
                if self.mode_start == False and idx != len(self.module_order) - 1:
                    response += "\n请选择下一步操作："
                    response += "\n 继续当前模块（1）"
                    response += "\n 进入下一个模块（2）"
            db.add_message(self.conversation_id, "assistant", response, self.mode)
            return response

