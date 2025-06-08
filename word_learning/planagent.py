import os
import json
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Boolean, DateTime, func, text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from openai import OpenAI
from config import APIConfig
import time
import stat

# 初始化 rich console
console = Console()

# 数据库设置
Base = declarative_base()
DB_PATH = 'word_plans.db'
engine = create_engine(f'sqlite:///{DB_PATH}')
Session = sessionmaker(bind=engine)

# 艾宾浩斯复习间隔（小时）：1天、2天、4天、7天、15天
REVIEW_INTERVALS = [ 24, 48, 96, 168, 360]

# 词库配置
DICTIONARIES = {
    'kaoyan': {
        'name': '考研词库',
        'file': 'data/kaoyan.json'
    },
    'level4': {
        'name': '专四词库',
        'file': 'data/level4.json'
    },
    'level8': {
        'name': '专八词库',
        'file': 'data/level8.json'
    },
    'ielts': {
        'name': '雅思词库',
        'file': 'data/ielts.json'
    },
    'toefl': {
        'name': '托福词库',
        'file': 'data/toefl.json'
    },
    'gre': {
        'name': 'GRE词库',
        'file': 'data/gre.json'
    },
    'it': {
        'name': '计算机专业英语',
        'file': 'data/it.json'
    },
    'ai': {
        'name': '人工智能词汇',
        'file': 'data/ai.json'
    },
    'test': {
        'name': '测试词库',
        'file': 'data/words_test.json'
    }
}

class StudyPlan(Base):
    """学习计划表"""
    __tablename__ = 'study_plans'
    
    id = Column(Integer, primary_key=True)
    exam_type = Column(String, nullable=False)  # 考试类型（如 GRE, CET4）
    start_date = Column(DateTime, nullable=False)   # 开始日期
    end_date = Column(DateTime, nullable=False)     # 结束日期
    total_words = Column(Integer, nullable=False)  # 总单词数
    daily_words = Column(Integer, nullable=False)  # 每天新学单词数
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联
    word_plans = relationship("WordPlan", back_populates="study_plan", cascade="all, delete-orphan")

class WordPlan(Base):
    """单词学习计划表"""
    __tablename__ = 'word_plans'
    
    id = Column(Integer, primary_key=True)
    study_plan_id = Column(Integer, ForeignKey('study_plans.id'))
    word = Column(String, nullable=False)           # 单词
    phonetic = Column(String)                       # 音标
    meaning = Column(String)                        # 释义
    example = Column(String)                        # 例句
    first_learn_date = Column(DateTime, nullable=False) # 首次学习日期
    is_learned = Column(Boolean, default=False)     # 是否已学习
    is_mastered = Column(Boolean, default=False)    # 是否已掌握
    
    # 关联
    study_plan = relationship("StudyPlan", back_populates="word_plans")
    review_dates = relationship("ReviewDate", back_populates="word_plan", cascade="all, delete-orphan")

class ReviewDate(Base):
    """复习日期表"""
    __tablename__ = 'review_dates'
    
    id = Column(Integer, primary_key=True)
    word_plan_id = Column(Integer, ForeignKey('word_plans.id'))
    review_date = Column(DateTime, nullable=False)  # 复习日期
    is_reviewed = Column(Boolean, default=False)  # 是否已复习
    
    # 关联
    word_plan = relationship("WordPlan", back_populates="review_dates")

class ReviewManager:
    """复习时间管理器，基于艾宾浩斯记忆曲线"""
    def __init__(self, start_date: datetime):
        self.start_date = start_date
        # 艾宾浩斯复习间隔（天）：1天、2天、4天、7天、15天
        self.intervals = [1, 2, 4, 7, 15]

    def get_review_dates(self, first_learn_date: datetime) -> List[datetime]:
        """获取一个单词的所有复习日期"""
        review_dates = []
        # 将时间转换为日期（去掉时分秒）
        first_learn = first_learn_date.date()
        
        for interval in self.intervals:
            # 计算下一次复习日期
            next_review = first_learn + timedelta(days=interval)
            # 转换回datetime，使用中午12点作为默认时间
            review_dates.append(datetime.combine(next_review, datetime.min.time().replace(hour=12)))
            
        return review_dates

    def get_daily_review_count(self, date: datetime, daily_words: int) -> int:
        """计算指定日期需要复习的单词数量"""
        # 计算从开始日期到指定日期的天数
        days_passed = (date.date() - self.start_date.date()).days
        
        if days_passed <= 0:
            return 0
            
        # 计算每天需要复习的单词数
        review_count = 0
        for interval in self.intervals:
            # 如果当前日期减去间隔天数大于等于开始日期，说明有单词需要复习
            if days_passed >= interval:
                review_count += daily_words
                
        return review_count

class WordPlanner:
    def __init__(self):
        """初始化计划生成器"""
        # 初始化 OpenAI 客户端
        api_config = APIConfig()
        self.client = OpenAI(
            api_key=api_config.api_key,
            base_url=api_config.host
        )
        self.model_name = api_config.model
        
        if not self.client.api_key or self.client.api_key == "YOUR_ACTUAL_API_KEY_HERE":
            raise ValueError("API 密钥未设置。请在 config.py 中填写您的密钥。")
    
    def _extract_info(self, user_input: str) -> Dict:
        """从用户输入中提取信息，如目标词库和考试日期"""
        # 获取支持的词库名称列表，用于提示 AI
        supported_dict_names = ", ".join([f"'{info['name']}' (ID: '{dict_id}')" for dict_id, info in DICTIONARIES.items()])

        prompt = f"""请分析以下用户输入，提取用户想要背诵的词库ID和他们的目标日期。
用户输入: {user_input}
支持的词库有: {supported_dict_names}
当前日期: {datetime.now().strftime('%Y-%m-%d')}

请仔细分析用户的表达，特别注意：
1. 考试类型（如：GRE、考研、四级、六级、雅思、托福等）
2. 时间表达（如："3天后"、"一个月后"、"30天后"、"下个月"等）
3. 每天学习时间（如果提到）

请以JSON格式返回以下信息：
{{
    "target_dict_id": "用户提到的词库对应的ID (例如 'gre', 'kaoyan', 'test')",
    "exam_date": "目标日期 (如果是明确日期，使用 yyyy-mm-dd 格式；如果是相对时间，请严格按照以下规则转换：
        - '3天后' -> 当前日期 + 3天
        - '一周后' -> 当前日期 + 7天
        - '一个月后' -> 当前日期 + 30天
        - '30天后' -> 当前日期 + 30天
        - '下个月' -> 当前日期的下个月1号
        - '三个月后' -> 当前日期 + 90天)",
    "daily_study_time": "用户提到的每天学习时间（分钟），如果未提及，设为 null",
    "confidence": {{
        "dict_id": "词库ID的置信度 (0-1)",
        "exam_date": "日期的置信度 (0-1)"
    }},
    "interpretation": {{
        "raw_input": "用户的原始输入",
        "dict_interpretation": "对词库选择的解释",
        "date_interpretation": "对日期的解释"
    }}
}}

注意：
1. 对于时间表达，请严格按照上述规则转换，不要自行推测
2. 对于考试类型，请匹配到对应的词库ID：
   - "GRE" -> "gre"
   - "考研" -> "kaoyan"
   - "四级" -> "level4"
   - "六级" -> "level6"
   - "雅思" -> "ielts"
   - "托福" -> "toefl"
   - "测试" -> "test"
3. 如果用户提到"计算机"或"IT"，使用"it"词库
4. 如果用户提到"AI"或"人工智能"，使用"ai"词库
5. 如果置信度低于0.6，请将对应字段设为null
6. 严格按照JSON格式返回，不要包含额外文字说明。"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的英语学习规划师，擅长理解用户的自然语言表达。请仔细分析用户的输入，提取关键信息。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            console.print(f"[dim]DEBUG: API 返回原始内容: {content}[/]")
            result = json.loads(content)
            
            # 检查置信度
            if result.get("confidence", {}).get("dict_id", 0) < 0.6:
                result["target_dict_id"] = None
            if result.get("confidence", {}).get("exam_date", 0) < 0.6:
                result["exam_date"] = None
                
            return result
        except Exception as e:
            raise ValueError(f"信息提取出错: {str(e)}")
    
    def _load_word_list(self, dict_id: str) -> List[Dict]:
        """加载指定词库的单词列表"""
        if dict_id not in DICTIONARIES:
            raise ValueError(f"错误：找不到词库ID '{dict_id}'")
        
        file_path = os.path.join(os.path.dirname(__file__), DICTIONARIES[dict_id]['file'])
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "words" in data:
                    return data["words"]
                else:
                    raise ValueError(f"词库文件格式不正确: {file_path}")
        except Exception as e:
            raise ValueError(f"加载词库文件时出错: {str(e)}")
    
    def _calculate_daily_words(self, total_words: int, days: int) -> int:
        """计算每天需要学习的单词数"""
        return (total_words + days - 1) // days  # 向上取整
    
    def generate_plan(self, user_input: str, progress=None, task_id=None) -> Dict:
        """根据用户输入生成学习计划"""
        # 1. 提取用户信息
        user_info = self._extract_info(user_input)
        if not user_info or not user_info.get("target_dict_id") or not user_info.get("exam_date"):
            raise ValueError("未能从输入中提取到所需的词库或日期信息")
        
        # 2. 加载词库
        words = self._load_word_list(user_info["target_dict_id"])
        total_words = len(words)
        
        # 3. 计算日期
        start_date = datetime.now().date()  # 从今天开始
        end_date = datetime.strptime(user_info["exam_date"], "%Y-%m-%d").date()  # 考试日期
        days = (end_date - start_date).days + 1
        
        if days <= 0:
            raise ValueError("结束日期必须晚于开始日期")
        
        # 4. 计算每天新学单词数（向上取整）
        daily_words = (total_words + days - 1) // days
        
        # 5. 重置数据库
        self.reset_db()
        
        # 6. 创建数据库会话
        session = Session()
        
        try:
            # 删除所有旧计划（由于设置了级联删除，这会同时删除相关的单词计划和复习日期）
            session.query(StudyPlan).delete()
            session.commit()
            
            # 创建新的学习计划
            study_plan = StudyPlan(
                exam_type=user_info["target_dict_id"],
                start_date=datetime.combine(start_date, datetime.min.time().replace(hour=12)),
                end_date=datetime.combine(end_date, datetime.min.time().replace(hour=12)),
                total_words=total_words,
                daily_words=daily_words
            )
            session.add(study_plan)
            session.flush()
            
            if progress and task_id is not None:
                progress.update(task_id, completed=20)  # 更新进度到20%
            
            # 6. 分配单词到每天
            # 计算每天应该学习的单词范围
            daily_ranges = []
            remaining_words = total_words
            for day in range(days):
                if day == days - 1:  # 最后一天，分配所有剩余单词
                    word_count = remaining_words
                else:
                    word_count = min(daily_words, remaining_words)
                daily_ranges.append((day, word_count))
                remaining_words -= word_count
            
            # 按日期分配单词
            current_word_index = 0
            for day, word_count in daily_ranges:
                # 设置今天的学习时间（中午12点）
                today_learn_time = datetime.combine(start_date + timedelta(days=day), 
                                                  datetime.min.time().replace(hour=12))
                
                # 为今天分配指定数量的单词
                for _ in range(word_count):
                    if current_word_index >= len(words):
                        break
                        
                    word_data = words[current_word_index]
                    current_word_index += 1
                    
                    # 处理释义，确保是字符串类型
                    meaning = word_data.get("meaning", word_data.get("trans", ""))
                    if isinstance(meaning, list):
                        meaning = "；".join(meaning)
                    
                    # 创建单词计划
                    word_plan = WordPlan(
                        study_plan_id=study_plan.id,
                        word=word_data.get("word", word_data.get("name", "")),
                        phonetic=word_data.get("phonetic", word_data.get("usphone", "")),
                        meaning=meaning,
                        example=word_data.get("example", ""),
                        first_learn_date=today_learn_time
                    )
                    session.add(word_plan)
                    session.flush()
                    
                    # 计算复习日期（1、2、4、7、15天）
                    review_intervals = [1, 2, 4, 7, 15]
                    for interval in review_intervals:
                        review_date = today_learn_time + timedelta(days=interval)
                        if review_date.date() <= end_date:  # 只添加在计划时间范围内的复习日期
                            review = ReviewDate(
                                word_plan_id=word_plan.id,
                                review_date=review_date
                            )
                            session.add(review)
                
                # 更新进度
                if progress and task_id is not None:
                    current_progress = 20 + (day * 60 // days)  # 20%到80%之间
                    progress.update(task_id, completed=current_progress)
            
            session.commit()
            
            # 在关闭会话前获取所需的所有属性
            plan_info = {
                "id": study_plan.id,
                "exam_type": study_plan.exam_type,
                "start_date": study_plan.start_date,
                "end_date": study_plan.end_date,
                "total_words": study_plan.total_words,
                "daily_words": study_plan.daily_words,
                "created_at": study_plan.created_at
            }
            
            if progress and task_id is not None:
                progress.update(task_id, completed=100)  # 完成
                
            return plan_info
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_daily_plan(self, date: datetime) -> Dict:
        """获取指定日期的学习计划"""
        session = Session()
        try:
            # 获取当前学习计划信息（通过created_at确保获取最新创建的计划）
            study_plan = session.query(StudyPlan).order_by(StudyPlan.created_at.desc()).first()
            
            if not study_plan:
                return {
                    "date": date.date(),
                    "new_words": [],
                    "review_words": []
                }
            
            # 获取当天需要新学的单词（首次学习日期是今天的）
            new_words = session.query(WordPlan).filter(
                WordPlan.study_plan_id == study_plan.id,  # 确保只获取当前计划的单词
                func.date(WordPlan.first_learn_date) == date.date(),
                WordPlan.is_learned == False
            ).order_by(WordPlan.id).all()
            
            # 获取当天需要复习的单词（复习日期是今天的）
            review_words = session.query(WordPlan).join(ReviewDate).filter(
                WordPlan.study_plan_id == study_plan.id,  # 确保只获取当前计划的单词
                func.date(ReviewDate.review_date) == date.date(),
                ReviewDate.is_reviewed == False,
                WordPlan.is_mastered == False
            ).order_by(WordPlan.id).all()
            
            return {
                "date": date.date(),
                "new_words": [{
                    "id": w.id,
                    "word": w.word,
                    "phonetic": w.phonetic,
                    "meaning": w.meaning,
                    "example": w.example,
                    "first_learn_date": w.first_learn_date
                } for w in new_words],
                "review_words": [{
                    "id": w.id,
                    "word": w.word,
                    "phonetic": w.phonetic,
                    "meaning": w.meaning,
                    "example": w.example,
                    "first_learn_date": w.first_learn_date
                } for w in review_words]
            }
        finally:
            session.close()

    def reset_db(self):
        """重置数据库"""
        session = Session()
        try:
            # 先删除所有数据
            session.query(StudyPlan).delete()
            session.query(WordPlan).delete()
            session.query(ReviewDate).delete()
            session.commit()
            
            # 检查sqlite_sequence表是否存在，如果存在则重置序列
            result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';")).fetchone()
            if result:
                session.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('study_plans', 'word_plans', 'review_dates');"))
                session.commit()
        finally:
            session.close()

def ensure_db_permissions():
    """确保数据库文件有正确的权限"""
    if os.path.exists(DB_PATH):
        # 确保文件有读写权限
        os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR)

def init_db():
    """初始化数据库"""
    # 先创建所有表
    Base.metadata.create_all(engine)
    # 确保数据库文件有正确的权限
    ensure_db_permissions()

def reset_db():
    """重置数据库"""
    # 确保数据库文件有正确的权限
    ensure_db_permissions()
    
    session = Session()
    try:
        # 先删除所有数据
        session.query(StudyPlan).delete()
        session.query(WordPlan).delete()
        session.query(ReviewDate).delete()
        session.commit()
        
        # 检查sqlite_sequence表是否存在，如果存在则重置序列
        result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';")).fetchone()
        if result:
            session.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('study_plans', 'word_plans', 'review_dates');"))
            session.commit()
    finally:
        session.close()

@click.group()
def cli():
    """单词学习计划生成器"""
    pass

@cli.command()
def plan():
    """根据自然语言输入生成学习计划"""
    console.print("\n[bold cyan]欢迎使用单词学习计划生成器！[/]")
    console.print("\n请描述您的学习需求，例如：")
    console.print("- [green]一个月后要考GRE[/]")
    console.print("- [green]30天后要考四级[/]")
    console.print("- [green]下个月要准备考研[/]")
    console.print("- [green]三个月后要考雅思[/]")
    console.print("- [green]准备计算机专业英语考试，两个月后[/]")
    console.print("\n请输入您的需求：")
    
    planner = WordPlanner()
    
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
            
            # 提取用户信息
            user_info = planner._extract_info(user_input)
            
            # 检查必要信息
            if not user_info.get("target_dict_id"):
                console.print("\n[yellow]抱歉，我无法确定您想学习哪个词库。[/]")
                console.print("请明确说明您要准备什么考试，例如：")
                console.print("- GRE考试")
                console.print("- 考研英语")
                console.print("- 四级考试")
                console.print("- 计算机专业英语")
                continue
                
            if not user_info.get("exam_date"):
                console.print("\n[yellow]抱歉，我无法确定您的目标日期。[/]")
                console.print("请明确说明您的目标时间，例如：")
                console.print("- 一个月后")
                console.print("- 30天后")
                console.print("- 下个月")
                console.print("- 2024年6月1日")
                continue
            
            # 显示提取的信息
            dict_name = DICTIONARIES[user_info["target_dict_id"]]["name"]
            console.print(f"\n[green]我理解您想：[/]")
            console.print(f"- 学习词库：[bold]{dict_name}[/]")
            console.print(f"- 目标日期：[bold]{user_info['exam_date']}[/]")
            if user_info.get("daily_study_time"):
                console.print(f"- 每天学习时间：[bold]{user_info['daily_study_time']}分钟[/]")
            
            # 确认信息
            if not click.confirm("\n这些信息是否正确？", default=True):
                console.print("\n[yellow]好的，请重新输入您的需求。[/]")
                continue
            
            # 生成计划
            with Progress() as progress:
                task_id = progress.add_task("[cyan]正在生成学习计划...", total=100)
                plan_info = planner.generate_plan(user_input, progress, task_id)
            
            # 显示计划概览
            console.print("\n[bold green]学习计划已生成！[/]")
            console.print(f"\n计划概览：")
            console.print(f"- 词库：[bold]{DICTIONARIES[plan_info['exam_type']]['name']}[/]")
            console.print(f"- 总单词数：[bold]{plan_info['total_words']}[/]")
            console.print(f"- 每天新学单词数：[bold]{plan_info['daily_words']}[/]")
            console.print(f"- 开始日期：[bold]{plan_info['start_date'].strftime('%Y-%m-%d')}[/]")
            console.print(f"- 结束日期：[bold]{plan_info['end_date'].strftime('%Y-%m-%d')}[/]")
            
            # 显示前三天的计划预览
            console.print("\n[bold]前三天的学习计划预览：[/]")
            for i in range(3):
                date = plan_info['start_date'] + timedelta(days=i)
                daily_plan = planner.get_daily_plan(date)
                
                console.print(f"\n[cyan]第 {i+1} 天 ({date.strftime('%Y-%m-%d')})：[/]")
                console.print(f"- 新学单词：{len(daily_plan['new_words'])} 个")
                console.print(f"- 复习单词：{len(daily_plan['review_words'])} 个")
                
                # 显示新学单词示例
                if daily_plan['new_words']:
                    console.print("\n新学单词示例：")
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("单词", style="dim")
                    table.add_column("音标")
                    table.add_column("释义")
                    
                    for word in daily_plan['new_words'][:3]:  # 只显示前3个
                        table.add_row(
                            word['word'],
                            word.get('phonetic', ''),
                            word.get('meaning', '')
                        )
                    console.print(table)
            
            console.print("\n[green]您可以使用以下命令查看详细计划：[/]")
            console.print("- [bold]python planagent.py view-plan --date YYYY-MM-DD[/] 查看某天的具体计划")
            console.print("- [bold]python planagent.py mark-word[/] 标记单词的学习状态")
            
            break
            
        except ValueError as e:
            console.print(f"\n[red]错误：{str(e)}[/]")
            console.print("请重新输入您的需求。")
        except Exception as e:
            console.print(f"\n[red]发生错误：{str(e)}[/]")
            console.print("请重新输入您的需求。")

@cli.command()
@click.option('--date', type=click.DateTime(), 
              prompt='请输入要查看的日期 (YYYY-MM-DD)', help='要查看的日期')
def view_plan(date: datetime):
    """查看指定日期的学习计划"""
    try:
        planner = WordPlanner()
        daily_plan = planner.get_daily_plan(date)
        
        console.print(f"\n[bold]{date.strftime('%Y-%m-%d')} 的学习计划:[/]")
        
        if daily_plan["new_words"]:
            console.print("\n[bold green]新学单词:[/]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID")
            table.add_column("单词")
            table.add_column("音标")
            table.add_column("释义")
            table.add_column("首次学习时间")
            for word in daily_plan["new_words"]:
                table.add_row(
                    str(word["id"]),
                    word["word"],
                    word["phonetic"],
                    word["meaning"],
                    word["first_learn_date"].strftime("%H:%M")
                )
            console.print(table)
        else:
            console.print("\n[bold green]今天没有新学单词[/]")
        
        if daily_plan["review_words"]:
            console.print("\n[bold yellow]复习单词:[/]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID")
            table.add_column("单词")
            table.add_column("音标")
            table.add_column("释义")
            table.add_column("首次学习时间")
            for word in daily_plan["review_words"]:
                table.add_row(
                    str(word["id"]),
                    word["word"],
                    word["phonetic"],
                    word["meaning"],
                    word["first_learn_date"].strftime("%H:%M")
                )
            console.print(table)
        else:
            console.print("\n[bold yellow]今天没有需要复习的单词[/]")
            
    except Exception as e:
        console.print(f"[bold red]错误:[/] {str(e)}")

@cli.command()
@click.option('--word-id', type=int, prompt='请输入单词ID', help='要标记的单词ID')
@click.option('--status', type=click.Choice(['learned', 'mastered', 'reviewed']), 
              prompt='请选择状态', help='要标记的状态')
def mark_word(word_id: int, status: str):
    """标记单词的学习状态"""
    try:
        session = Session()
        word_plan = session.query(WordPlan).get(word_id)
        if not word_plan:
            raise ValueError(f"找不到ID为 {word_id} 的单词")
        
        today = datetime.now()
        
        if status == "learned":
            word_plan.is_learned = True
        elif status == "mastered":
            word_plan.is_mastered = True
            # 如果单词已掌握，标记所有未完成的复习为已完成
            for review in word_plan.review_dates:
                if not review.is_reviewed and review.review_date >= today:
                    review.is_reviewed = True
        elif status == "reviewed":
            # 标记今天的复习为已完成
            for review in word_plan.review_dates:
                if review.review_date.date() == today.date():
                    review.is_reviewed = True
                    break
        
        session.commit()
        console.print(f"[bold green]成功标记单词状态![/]")
        
        # 显示今天的计划
        planner = WordPlanner()
        daily_plan = planner.get_daily_plan(today)
        
        console.print(f"\n[bold]{today.strftime('%Y-%m-%d')} 的剩余计划:[/]")
        
        if daily_plan["new_words"]:
            console.print("\n[bold green]待学习单词:[/]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID")
            table.add_column("单词")
            table.add_column("音标")
            table.add_column("释义")
            table.add_column("首次学习时间")
            for word in daily_plan["new_words"]:
                table.add_row(
                    str(word["id"]),
                    word["word"],
                    word["phonetic"],
                    word["meaning"],
                    word["first_learn_date"].strftime("%H:%M")
                )
            console.print(table)
        else:
            console.print("\n[bold green]今天没有待学习的单词了[/]")
        
        if daily_plan["review_words"]:
            console.print("\n[bold yellow]待复习单词:[/]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID")
            table.add_column("单词")
            table.add_column("音标")
            table.add_column("释义")
            table.add_column("首次学习时间")
            for word in daily_plan["review_words"]:
                table.add_row(
                    str(word["id"]),
                    word["word"],
                    word["phonetic"],
                    word["meaning"],
                    word["first_learn_date"].strftime("%H:%M")
                )
            console.print(table)
        else:
            console.print("\n[bold yellow]今天没有待复习的单词了[/]")
            
    except Exception as e:
        console.print(f"[bold red]错误:[/] {str(e)}")
    finally:
        session.close()

if __name__ == '__main__':
    init_db()
    cli() 