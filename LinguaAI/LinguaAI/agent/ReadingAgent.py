import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
from enum import Enum
from openai import OpenAI
from LinguaAI.error_books.reading_error_book import ReadingErrorBook
from LinguaAI.prompts.reading import READING_PROMPT
from LinguaAI.database import ChatDatabase
import random
scene_db = ChatDatabase()
db_settings = scene_db.get_settings()

class MaterialType(Enum):
    NEWS = "news"
    EXAM = "exam"
    ARTICLE = "article"

class ReadingAgent:
    """阅读代理类，用于处理英语文章阅读和理解评估"""
    
    def __init__(self, use_online_search: bool = True):
        """初始化阅读代理
        
        Args:
            use_online_search: 是否使用在线搜索
        """
        self.current_article = None
        self.current_sections = []
        self.user_summary = None
        self.use_online_search = use_online_search
        
        self.error_book = ReadingErrorBook()
        
        
        if use_online_search:
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=db_settings["tavily_api_key"])
            except ImportError:
                raise ImportError("请先安装 tavily-python 包：pip install tavily-python")
        
       
        self.client = OpenAI(
            api_key=db_settings["api_key"],
            base_url=db_settings["host"]
        )

    def search_articles(self, query: str, material_type: MaterialType = MaterialType.NEWS, 
                       max_results: int = 3) -> List[Dict[str, Any]]:
        """搜索英语学习相关文章
        
        Args:
            query: 搜索关键词
            material_type: 材料类型（新闻/考试/文章）
            max_results: 最大返回结果数
            
        Returns:
            List[Dict]: 文章列表，每个文章包含标题、URL和摘要
        """
        try:
            print(f"正在搜索: {query}")
            
            if self.use_online_search and hasattr(self, 'tavily_client'):
                # 根据材料类型和查询生成更具体的搜索关键词
                if material_type == MaterialType.EXAM:
                    search_query = f"IELTS reading {query}"
                elif material_type == MaterialType.NEWS:
                    search_query = f"news {query}"
                else:
                    search_query = query
                
                # 使用 Tavily 客户端进行搜索
                search_results = self.tavily_client.get_search_context(
                    query=search_query,
                    max_results=max_results,
                    search_depth="advanced"
                )
                
                # 如果返回的是字符串，尝试解析为JSON
                if isinstance(search_results, str):
                    try:
                        search_results = json.loads(search_results)
                    except json.JSONDecodeError:
                        return []
                
                # 如果返回的是列表
                if isinstance(search_results, list):
                    articles = []
                    for result in search_results:
                        if isinstance(result, dict):
                            # 检查内容是否为英文
                            content = result.get("content", "")
                            
                            if not self._is_english_content(content):
                                continue
                                
                            # 清理内容中的特殊字符和多余空格
                            content = re.sub(r'\s+', ' ', content)
                            content = re.sub(r'\[.*?\]', '', content)
                            content = re.sub(r'\^.*?:', '', content)  # 移除引用标记
                            content = content.strip()
                            
                            # 确保内容长度合适
                            if len(content) < 100:  # 降低最小长度要求
                                continue
                                
                            article = {
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "summary": content,
                                "source": result.get("source", "未知来源")
                            }
                            articles.append(article)
                    
                    if articles:
                        return articles
                
                # 如果搜索失败或没有找到合适的文章，尝试使用不同的搜索关键词
                alternative_queries = [
                    query,  # 直接使用原始查询
                    f"article {query}",  # 添加article关键词
                    f"text {query}",  # 添加text关键词
                    f"content {query}"  # 添加content关键词
                ]
                
                for alt_query in alternative_queries:
                    try:
                        alt_results = self.tavily_client.get_search_context(
                            query=alt_query,
                            max_results=max_results,
                            max_tokens=4000,
                            search_depth="advanced"
                        )
                        
                        if isinstance(alt_results, list):
                            articles = []
                            for result in alt_results:
                                if isinstance(result, dict):
                                    content = result.get("content", "")
                                    if self._is_english_content(content) and len(content) >= 100:
                                        content = re.sub(r'\s+', ' ', content)
                                        content = re.sub(r'\[.*?\]', '', content)
                                        content = re.sub(r'\^.*?:', '', content)
                                        content = content.strip()
                                        
                                        article = {
                                            "title": result.get("title", ""),
                                            "url": result.get("url", ""),
                                            "summary": content,
                                            "source": result.get("source", "未知来源")
                                        }
                                        articles.append(article)
                            
                            if articles:
                                return articles
                    except Exception:
                        continue
                
                return []
            
            return []
            
        except Exception as e:
            print(f"搜索文章时出错: {str(e)}")
            return []

    def _is_english_content(self, text: str) -> bool:
        """检查文本是否为英文内容
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否为英文内容
        """
        # 如果文本太短，直接返回False
        if len(text) < 30:
            return False
            
        # 计算英文字符的比例
        english_chars = sum(1 for c in text if ord(c) < 128)
        english_ratio = english_chars / len(text)
        
        # 检查是否包含常见的中文标点符号（只检查中文特有的标点）
        chinese_punctuation = ['，', '。', '？', '！', '；', '：', '（', '）']
        has_chinese_punctuation = any(p in text for p in chinese_punctuation)
        
        # 如果英文字符比例低于60%或包含中文标点，则认为不是英文内容
        return english_ratio > 0.6 and not has_chinese_punctuation

    def extract_sections(self, url: str, max_sections: int = 6) -> List[str]:
        """从文章中提取关键片段
        
        Args:
            url: 文章URL
            max_sections: 最大提取片段数
            
        Returns:
            List[str]: 文章片段列表
        """
        try:
            if not self.current_article:
                return []
                
            # 获取文章内容
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除脚本、样式和导航元素
            for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
                element.decompose()
            
            # 提取正文内容
            content = soup.get_text()
            
            # 分段处理
            paragraphs = re.split(r'\n\s*\n', content)
            paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 50]
            
            # 过滤非英文段落
            english_paragraphs = [p for p in paragraphs if self._is_english_content(p)]
            
            # 选择最相关的段落
            sections = english_paragraphs[:max_sections]
            for section in sections:
                if len(section) < 100:
                    sections.remove(section)
            if not sections:
                # 如果没有找到合适的段落，使用文章摘要
                return [self.current_article.get("summary", "")]
            
            return sections
        except Exception as e:
            print(f"提取文章片段时出错: {str(e)}")
            # 如果提取失败，返回文章摘要
            return [self.current_article.get("summary", "")]

    def evaluate_understanding(self, user_summary: str, original_sections: List[str]) -> Dict[str, Any]:
        """评估用户对文章的理解程度
        
        Args:
            user_summary: 用户的总结
            original_sections: 原始文章片段
            
        Returns:
            Dict: 评估结果，包含理解程度和具体反馈
        """
        prompt = READING_PROMPT["evaluate_understanding"].format(
            content=chr(10).join(original_sections),
            user_summary=user_summary
        )
        for i in range(3):
            response = self.client.chat.completions.create(
                model=db_settings["model_name"],
                messages=[
                    {"role": "system", "content": "你是一位专业的英语阅读老师，擅长评估学生对英语文章的理解程度。当发现学生理解有误时，你会耐心地解释正确的理解，并帮助学生理解文章的真实含义。"},
                    {"role": "user", "content": prompt}
                ],
            )
        
            try:
                evaluation = json.loads(response.choices[0].message.content)
                return evaluation
            except json.JSONDecodeError:
                continue
        
        
            
        

    def format_sections_for_display(self, sections: List[str]) -> str:
        """格式化文章片段用于显示
        
        Args:
            sections: 文章片段列表
            
        Returns:
            str: 格式化后的文本
        """
        formatted_text = "请阅读以下英语文章片段：\n\n"
        for i, section in enumerate(sections, 1):
            formatted_text += f"片段 {i}:\n{section}\n\n"
        formatted_text += "请用中文或英文总结您对文章的理解"
        return formatted_text

    def process_reading_session(self, query: str, material_type: MaterialType = MaterialType.NEWS) -> Dict[str, Any]:
        """处理一次完整的阅读会话
        
        Args:
            query: 用户查询关键词
            material_type: 材料类型
            
        Returns:
            Dict: 会话结果
        """
        # 1. 搜索文章
        articles = self.search_articles(query, material_type)
        if not articles:
            return {"status": "error", "message": "未找到相关文章，请尝试其他关键词"}
            
        self.current_article = articles[random.randint(0, len(articles) - 1)]
        self.current_sections = self.extract_sections(self.current_article["url"])
        
        if not self.current_sections:
            return {"status": "error", "message": "无法提取文章内容，请尝试其他文章"}
        print('self.current_sections', self.current_sections)

        return {
            "status": "success",
            "article_title": self.current_article["title"],
            "article_source": self.current_article.get("source", "未知来源"),
            "reading_material": self.format_sections_for_display(self.current_sections)
        }

    def evaluate_user_summary(self, user_summary: str, content: str) -> Dict[str, Any]:
        """评估用户的总结
        
        Args:
            user_summary: 用户的总结文本
            
        Returns:
            Dict: 评估结果
        """
        self.user_summary = user_summary
        evaluation = self.evaluate_understanding(user_summary, content)

        if evaluation.get("understanding_score", 0) < 0.7:
            self.error_book.add_error(
                article_title=self.current_article["title"],
                article_content=content,
                user_summary=user_summary,
                correct_summary=evaluation.get("correct_understanding", ""),
                error_type="理解偏差" if evaluation.get("misunderstandings") else "遗漏要点",
                error_description="\n".join(evaluation.get("misunderstandings", [])),
                feedback=evaluation.get("detailed_feedback", "")
            )
        
        return evaluation

    def get_error_book(self) -> ReadingErrorBook:
        """获取错题本实例"""
        return self.error_book

