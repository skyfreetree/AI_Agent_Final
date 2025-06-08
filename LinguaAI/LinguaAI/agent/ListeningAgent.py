import sys
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
from enum import Enum
from openai import OpenAI
from LinguaAI.error_books.listening_error_book import ListeningErrorBook, ListeningMode as ErrorBookMode
from LinguaAI.prompts.listening import LISTENING_PROMPT
from tavily import TavilyClient
from LinguaAI.database.scene_db import ChatDatabase
db = ChatDatabase()
db_settings = db.get_settings()

class ListeningMode(Enum):
    EXTENSIVE = "extensive"  # 泛听模式
    INTENSIVE = "intensive"  # 精听模式

class MaterialType(Enum):
    NEWS = "news"
    CONVERSATION = "conversation"
    STORY = "story"

class ListeningAgent:
    """听力练习代理类，用于处理英语听力练习和评估"""
    
    def __init__(self, use_online_search: bool = True):
        """初始化听力练习代理
        
        Args:
            use_online_search: 是否使用在线搜索
            api_key: Tavily API key（如果使用在线搜索）
            openai_api_key: OpenAI API key（用于评估用户理解）
        """
        self.current_material = None
        self.current_sections = []
        self.user_response = None
        self.use_online_search = use_online_search
        
        self.error_book = ListeningErrorBook()
        
        self.client = OpenAI(
            api_key=db_settings["api_key"],
            base_url=db_settings["host"]
        )
        self.tavily_client = TavilyClient(api_key=db_settings["tavily_api_key"])

    def _get_complete_sentences(self, text: str, max_length: int) -> str:
        """获取指定长度内的完整句子
        
        Args:
            text: 原始文本
            max_length: 最大长度限制
            
        Returns:
            str: 完整的句子
        """
        # 分割句子（考虑常见的句子结束标点）
        sentences = re.split(r'(?<=[.!?])\s+', text)
        result = []
        current_length = 0
        
        for sentence in sentences:
            # 如果添加这个句子会超出长度限制，就停止
            if current_length + len(sentence) > max_length:
                break
            result.append(sentence)
            current_length += len(sentence)
        
        return ' '.join(result)

    def _clean_news_content(self, content: str) -> str:
        """清理新闻内容，只保留主体部分
        
        Args:
            content: 原始新闻内容
            
        Returns:
            str: 清理后的内容
        """
        # 移除常见的新闻元数据
        patterns_to_remove = [
            r'^\s*[A-Z\s]+\s*\d+h?\s*ago\s*',  # 时间戳
            r'^\s*[A-Z\s]+\s*NEWS\s*',  # 新闻来源标记
            r'^\s*[A-Z\s]+\s*U\.S\.\s*NEWS\s*',  # 美国新闻标记
            r'^\s*[A-Z\s]+\s*[A-Z\s]+\s*',  # 全大写标题
            r'[-=]{3,}',  # 分隔线
            r'Top stories from around the country\.',  # 常见新闻网站标记
            r'[A-Z\s]+Office\s*$',  # 办公室署名
            r'[A-Z][a-z]+\s+[A-Z]\.\s*$',  # 作者署名
        ]
        
        # 应用清理规则
        cleaned_content = content
        for pattern in patterns_to_remove:
            cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.MULTILINE)
        
        # 移除多余的空行和空格
        cleaned_content = re.sub(r'\n\s*\n', '\n', cleaned_content)
        cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
        cleaned_content = cleaned_content.strip()
        
        return cleaned_content

    def search_materials(self, query: str, material_type: MaterialType = MaterialType.NEWS, 
                        mode: ListeningMode = ListeningMode.EXTENSIVE,
                        max_results: int = 3) -> List[Dict[str, Any]]:
        """搜索英语听力材料
        
        Args:
            query: 搜索关键词
            material_type: 材料类型（新闻/对话/故事）
            mode: 听力模式（泛听/精听）
            max_results: 最大返回结果数
            
        Returns:
            List[Dict]: 材料列表，每个材料包含标题、内容和来源
        """
        try:
            print(f"正在搜索: {query}")
            
            if self.use_online_search and hasattr(self, 'tavily_client'):
                # 根据材料类型和模式生成搜索关键词
                if mode == ListeningMode.EXTENSIVE:
                    search_query = f"news article {query}"
                else:
                    search_query = f"short conversation {query}"
                
                search_results = self.tavily_client.get_search_context(
                    query=search_query,
                    max_results=max_results,
                    max_tokens=4000,
                    search_depth="advanced"
                )
                
                if isinstance(search_results, str):
                    try:
                        search_results = json.loads(search_results)
                    except json.JSONDecodeError:
                        return []
                
                if isinstance(search_results, list):
                    materials = []
                    for result in search_results:
                        if isinstance(result, dict):
                            content = result.get("content", "")
                            
                            if not self._is_english_content(content):
                                continue
                            
                            # 清理新闻内容
                            if material_type == MaterialType.NEWS:
                                content = self._clean_news_content(content)
                            
                            content = re.sub(r'\s+', ' ', content)
                            content = re.sub(r'\[.*?\]', '', content)
                            content = re.sub(r'\^.*?:', '', content)
                            content = content.strip()
                            
                            # 根据模式调整内容长度，确保句子完整
                            if mode == ListeningMode.EXTENSIVE:
                                # 泛听模式：使用较长的材料（300-500字）
                                if len(content) < 300:
                                    continue
                                content = self._get_complete_sentences(content, 500)
                            else:
                                # 精听模式：使用较短的材料（100-200字）
                                if len(content) < 100:
                                    continue
                                content = self._get_complete_sentences(content, 200)
                                
                            material = {
                                "title": result.get("title", ""),
                                "content": content,
                                "source": result.get("source", "未知来源"),
                                "type": material_type
                            }
                            materials.append(material)
                    
                    if materials:
                        return materials
            
            return []
            
        except Exception as e:
            print(f"搜索材料时出错: {str(e)}")
            return []

    def _is_english_content(self, text: str) -> bool:
        """检查文本是否为英文内容"""
        if len(text) < 30:
            return False
            
        english_chars = sum(1 for c in text if ord(c) < 128)
        english_ratio = english_chars / len(text)
        
        chinese_punctuation = ['，', '。', '？', '！', '；', '：', '（', '）']
        has_chinese_punctuation = any(p in text for p in chinese_punctuation)
        
        return english_ratio > 0.6 and not has_chinese_punctuation

 

    def evaluate_extensive_listening(self, user_summary: str, original_content: str) -> Dict[str, Any]:
        """评估泛听理解
        
        Args:
            user_summary: 用户的总结
            original_content: 原始内容
            
        Returns:
            Dict: 评估结果
        """

        prompt = LISTENING_PROMPT["evaluate_extensive"].format(original_content=original_content, user_summary=user_summary)

        
        for i in range(3):
            response = self.client.chat.completions.create(
                model=db_settings["model_name"],
                messages=[
                    {"role": "system", "content": "你是一位专业的英语听力老师，擅长评估学生对英语听力材料的理解程度。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            try:
                evaluation = json.loads(response.choices[0].message.content)

                if evaluation["understanding_score"] < 70:
                    self.error_book.add_error(
                        material_title=self.current_material["title"],
                        material_content=original_content,
                        user_response=user_summary,
                        correct_response=evaluation["correct_understanding"],
                        listening_mode=ErrorBookMode.EXTENSIVE,
                        error_type="理解偏差",
                        error_description=", ".join(evaluation["misunderstandings"]),
                        feedback=evaluation["detailed_feedback"]
                    )
                print('evaluation', evaluation)
                return evaluation
            except Exception as e:
                continue
        return None
            
        

    def evaluate_intensive_listening(self, user_transcript: str, original_content: str) -> Dict[str, Any]:
        """评估精听听写
        
        Args:
            user_transcript: 用户的听写内容
            original_content: 原始内容
            
        Returns:
            Dict: 评估结果
        """
        try:
            # 清理文本
            user_transcript = re.sub(r'\s+', ' ', user_transcript).strip().lower()
            original_content = re.sub(r'\s+', ' ', original_content).strip().lower()
            
            # 计算相似度
            prompt = LISTENING_PROMPT["evaluate_intensive"].format(original_content=original_content, user_transcript=user_transcript)

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一位专业的英语听力老师，擅长评估学生的听写内容。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            try:
                evaluation = json.loads(response.choices[0].message.content)
                
                # 如果准确度分数低于0.7，记录到错题本
                if evaluation["accuracy_score"] < 0.7:
                    self.error_book.add_error(
                        material_title=self.current_material["title"],
                        material_content=original_content,
                        user_response=user_transcript,
                        correct_response=original_content,
                        listening_mode=ErrorBookMode.INTENSIVE,
                        error_type="听写错误",
                        error_description=f"拼写错误: {', '.join(evaluation['spelling_errors'])}; 漏听内容: {', '.join(evaluation['missing_content'])}",
                        feedback=evaluation["detailed_feedback"]
                    )
                
            except json.JSONDecodeError:
                evaluation = {
                    "accuracy_score": 0.5,
                    "spelling_errors": ["无法解析评估结果"],
                    "grammar_errors": [],
                    "missing_content": [],
                    "suggestions": ["请重试"],
                    "detailed_feedback": response.choices[0].message.content
                }
            
            return evaluation
            
        except Exception as e:
            print(f"评估听写时出错: {str(e)}")
            return {
                "accuracy_score": 0,
                "spelling_errors": ["评估过程出错"],
                "grammar_errors": [],
                "missing_content": [],
                "suggestions": ["请重试"],
                "detailed_feedback": f"评估过程出错: {str(e)}"
            }

    def process_listening_session(self, query: str, mode: ListeningMode = ListeningMode.EXTENSIVE,
                                material_type: MaterialType = MaterialType.NEWS) -> Dict[str, Any]:
        """处理一次完整的听力会话
        
        Args:
            query: 用户查询关键词
            mode: 听力模式
            material_type: 材料类型
            
        Returns:
            Dict: 会话结果
        """
        # 1. 搜索材料
        materials = self.search_materials(query, material_type, mode)
        if not materials:
            return {"status": "error", "message": "未找到相关材料，请尝试其他关键词"}
            

        feedback = materials[0]['content']
        if mode == ListeningMode.EXTENSIVE:
            feedback += '\n请描述您听到的主要内容：'
        elif mode == ListeningMode.INTENSIVE:
            feedback += '\n请写下您听到的内容：'
        else:
            pass
        return feedback

    def evaluate_user_response(self, user_response: str, mode: ListeningMode, content: str) -> Dict[str, Any]:
        """评估用户的回答
        
        Args:
            user_response: 用户的回答
            mode: 听力模式
            
        Returns:
            Dict: 评估结果
        """

        self.user_response = user_response
        
        if mode == ListeningMode.EXTENSIVE:
            # 泛听模式：评估整体理解
            evaluation = self.evaluate_extensive_listening(user_response, content)
        else:
            # 精听模式：评估听写准确性
            evaluation = self.evaluate_intensive_listening(user_response, content)
        
        return {
            "status": "success",
            "evaluation": evaluation
        }

    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错题统计信息"""
        return self.error_book.get_error_statistics()

    def get_review_items(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取需要复习的错题"""
        return self.error_book.get_review_items(days)

    def format_review_item(self, item: Dict[str, Any]) -> str:
        """格式化复习项显示"""
        return self.error_book.format_review_item(item)

    def update_review_status(self, error_id: str):
        """更新错题复习状态"""
        self.error_book.update_review_status(error_id)

    def mark_error_corrected(self, error_id: str) -> bool:
        """标记错题为已改正"""
        return self.error_book.mark_error_corrected(error_id)


