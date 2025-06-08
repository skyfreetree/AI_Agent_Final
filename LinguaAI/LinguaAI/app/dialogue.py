import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import asyncio
from openai import AsyncOpenAI
from enum import Enum
from LinguaAI.error_books import SceneErrorBook
from LinguaAI.prompts import *
from LinguaAI.database.scene_db import ChatDatabase


db = ChatDatabase()
db_settings = db.get_settings()


class DialogueAssistant:
    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.client = AsyncOpenAI(
            api_key=db_settings["api_key"],
            base_url=db_settings["host"]
        )
        self.model = db_settings["model_name"]
        self.error_book = SceneErrorBook()  # 初始化错题本
        self.current_scene_id = conversation_id  # 当前场景ID
        
    @classmethod
    async def create(cls, conversation_id):
        self = cls(conversation_id)
        await self.init_by_conversation_id()
        return self

    async def init_by_conversation_id(self):
        try:
            self.mode = db.get_conversation_mode(self.conversation_id)
            print('mode', self.mode)
            self.conversation_history = await self.get_conversation_history()
            print('conversation history', self.conversation_history)
            self.current_scene = db.get_conversation_scene(self.conversation_id)
            print('current scene', self.current_scene)
            if self.mode == "simulation":
                if self.current_scene:
                    if isinstance(self.current_scene['角色列表'], dict):
                        self.scene_context = SIMULATION_PROMPT["scene_context"].format(
                            role=self.current_scene['角色列表']['角色名称'],
                            scene=self.current_scene['场景分析']['核心场景']
                        )
            
        except Exception as e:
            print(f"初始化对话助手时发生错误: {str(e)}")
            raise e
    async def analyze_input(self, user_input: str) -> str:
        """Analyze user input and generate a structured scene description."""
        print('analyze input')
        prompt = SIMULATION_PROMPT["role_and_topic"].format(user_input=user_input)

        
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
                )
            print('response', response)
            scene_data = json.loads(response.choices[0].message.content)
            self.current_scene = scene_data
            print('scene data', scene_data)
            # Format output
            output = []
            output.append("## 场景分析 ")
            output.append(f"- 核心场景：{scene_data['场景分析']['核心场景']}")


            # 展示每个角色及其话题和建议补充
            output.append("## 角色与可能的话题：")
            
            for i, role in enumerate(scene_data['角色列表'], 1):
                output.append(f"- {i}. {role['角色名称']}（{role['角色描述']}）")
                if role.get('角色话题'):
                    for topic in role['角色话题']:
                        output.append(f"      - {topic}")
               
            output.append("\n以上是否有您想要对话的角色？如果有，您可以输入数字。如果没有，您可以完善场景/角色细节，重新生成。")
            formatted_analysis = "\n".join(output)
            # 最后更新db中的场景，确保场景格式正确
            db.update_conversation_scene(self.conversation_id, response.choices[0].message.content)
            db.add_message(self.conversation_id, "assistant", formatted_analysis, self.mode)
            return formatted_analysis

        except json.JSONDecodeError as e:
            return f"抱歉，场景分析出现错误。请重新描述您想要模拟的场景。"
    async def into_teaching_mode(self, user_input: str) -> str:
        """进入教学模式"""

        self.mode = "teaching"
        db.update_conversation_mode(self.conversation_id, "teaching")
        print('conversation history', self.conversation_history)
        last_ai_message = next((msg["content"] for msg in reversed(self.conversation_history) if msg["role"] == "assistant"), "")
        system_message = SIMULATION_PROMPT["teaching_context"].format(
            current_scene=self.current_scene['场景分析']['核心场景'],
        )
        teaching_prompt = SIMULATION_PROMPT["into_teaching"].format(
            role=self.current_scene['角色列表']['角色名称'],
            role_output=last_ai_message,
            user_input=user_input
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_message},
                      {"role": "user", "content": teaching_prompt}],
            response_format={"type": "json_object"}
        )
        
        teaching_response = response.choices[0].message.content

        data = json.loads(teaching_response)
        print('teaching_response解析成功')
        output = []
        if "语言困难分析" in data:
            output.append(f"【语言困难分析】\n{data['语言困难分析']}")
        if "用户回答修正示例" in data:
            output.append("【用户回答修正示例】")
            for example in data["用户回答修正示例"]:
                output.append(f"- {example}")
        if "表达技巧与词汇解释" in data:
            output.append(f"【表达技巧与词汇解释】\n{data['表达技巧与词汇解释']}")
        if "鼓励语" in data:
            output.append(f"\n{data['鼓励语']} 您要继续刚才的对话练习吗？(输入\\return退出教学模式)")
            
        db.add_message(self.conversation_id, "system", system_message, self.mode)
        db.add_message(self.conversation_id, "user", user_input, self.mode)
        db.add_message(self.conversation_id, "assistant", "\n\n".join(output), self.mode)
        return "\n\n".join(output)

    async def provide_teaching_help(self, user_input: str) -> str:
        """Provide teaching assistance when user is stuck."""
        # Get the last few conversation turns for context
        recent_conversation = self.conversation_history[-2:] if len(self.conversation_history) > 2 else self.conversation_history
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=recent_conversation + [{"role": "user", "content": user_input}],
        )
        
        teaching_response = response.choices[0].message.content
        return teaching_response
    async def make_a_scene(self, user_input: str) -> str:
        role_index = int(user_input) - 1
        self.current_scene['角色列表'] = self.current_scene['角色列表'][role_index]
        
        db.update_conversation_scene(self.conversation_id, json.dumps(self.current_scene))

        system_message = SIMULATION_PROMPT["scene_context"].format(
        role=self.current_scene['角色列表']['角色名称'],
        scene=self.current_scene['场景分析']['核心场景']
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_message}]
        )
        
        assistant_response = response.choices[0].message.content
        db.add_message(self.conversation_id, "assistant", assistant_response, self.mode)
        return assistant_response
    
    async def simulate_dialogue(self, user_input: str) -> str:
        """Simulate dialogue based on the current scene."""
            
        # Check for Chinese characters
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in user_input)

        if has_chinese:
            return await self.into_teaching_mode(user_input)

        else:
            self.conversation_history.append({"role": "user", "content": user_input})
            messages = [{"role": "system", "content": self.scene_context}]
            messages += self.conversation_history[-4:] if len(self.conversation_history) > 3 else self.conversation_history

            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages
                
            )
            assistant_response = response.choices[0].message.content
            db.add_message(self.conversation_id, "assistant", assistant_response, self.mode)
            return assistant_response

    async def analyze_error(self, user_input: str, ai_response: str) -> Optional[Dict[str, str]]:
        """分析用户输入是否存在明显错误
        
        Returns:
            Optional[Dict]: 如果存在错误，返回错误类型和描述；否则返回None
        """
        prompt = SIMULATION_PROMPT["error_analysis"].format(
            user_input=user_input,
            ai_response=ai_response
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            
            analysis = json.loads(response.choices[0].message.content)
            print('analysis', analysis)
            if analysis["has_error"] == 'true' or analysis["has_error"] == True:
                return {
                    "error_type": analysis["error_type"],
                    "error_description": analysis["error_description"]
                }
            return None
        except Exception as e:
            print(f"分析错误时发生异常: {str(e)}")
            return None


    async def main_chat(self, user_input: str) -> str:
        """Handle user input and return a response."""
        
        # Simulation mode
        if self.mode == "simulation":
            if not self.current_scene:
                return await self.analyze_input(user_input)
            
            # Handle user confirmation of the scene
            if user_input.isdigit():
                self.mode = "simulation"
                self.current_scene_id = self.conversation_id 
                return await self.make_a_scene(user_input)
            elif user_input == '\q':
                try:
                    stats = self.error_book.get_error_statistics()
                    
                    if stats['total_errors'] > 0:
                        stats_msg = "\n\n【错题统计】\n--------------------------------------------"
                        stats_msg += f"\n总错题数：{stats['total_errors']}"
                        stats_msg += f"\n最近7天新增：{stats['recent_errors']}"
                        stats_msg += f"\n平均复习次数：{stats['avg_review_count']:.1f}"
                        
                        if stats['error_types']:
                            stats_msg += "\n\n各类型错题数："
                            for error_type, count in stats['error_types'].items():
                                stats_msg += f"\n- {error_type}: {count}"
                        
                        return "再见！" + stats_msg
                    else:
                        return "再见！\n\n目前还没有记录任何错题。"
                except Exception as e:
                    return "再见！"
                

            # 检查是否需要记录错题
            if len(self.conversation_history) >= 2:
                last_ai_msg = self.conversation_history[-1]["content"]
                error_analysis = await self.analyze_error(user_input, last_ai_msg)
                
                if error_analysis:
                    print('用户出现错误回答')
                    print(error_analysis)
                    # 记录错题
                    self.error_book.add_error(
                        self.current_scene,
                        self.conversation_history[-2:] if len(self.conversation_history) > 2 else self.conversation_history,
                        user_input,
                        last_ai_msg,
                        error_analysis['error_type'],
                        error_analysis['error_description'],
                        self.current_scene_id  # 使用当前场景ID
                    )
                    return await self.into_teaching_mode(user_input)
            
            response = await self.simulate_dialogue(user_input)
            
            return response
        
        # Teaching mode after help request
        elif self.mode == "teaching":
            if user_input.lower() == '\\return':
                db.update_conversation_mode(self.conversation_id, "simulation")
                last_dialogue = db.get_last_dialogue(self.conversation_id)
                return "\n好的，让我们继续刚才的对话。\n" + last_dialogue
            else:
                return await self.provide_teaching_help(user_input)
    async def get_conversation_history(self):
        sim_conversation_history = []
        conversation_history = []
        for message in db.get_scene_conversation_history(self.conversation_id):
            new_message = {"role": message['role'], "content": message['content']}
            if message['mode'] == 'simulation':
                sim_conversation_history.append(new_message)
            conversation_history.append(new_message)
        if self.mode == "teaching":
            return conversation_history
        else:
            return sim_conversation_history
    async def chat(self, message: str):
        try:
            user_input = message.strip()

            if not user_input:  
                return "请输入有效内容。"
            else:

                db.add_message(self.conversation_id, "user", user_input, self.mode)
                print('user input:\t', user_input)
                response = await self.main_chat(user_input)

            print('response:\t', response)
            return response
            
        except Exception as e:
            print(f"\n系统错误: {str(e)}")
            print("请重试或输入 '\q' 退出。")

