import os
import sqlite3
import json
from datetime import datetime
import time
from typing import List, Dict, Any, Optional

class ReadingErrorBook:
    """阅读错题本管理类，使用SQLite数据库存储阅读错题记录"""
    
    _DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS reading_error_records (
        error_id TEXT PRIMARY KEY,
        article_title TEXT NOT NULL,  -- 文章标题
        article_content TEXT NOT NULL,  -- 文章内容
        user_summary TEXT NOT NULL,  -- 用户总结
        correct_summary TEXT NOT NULL,  -- 正确答案
        error_type TEXT NOT NULL,  -- 错误类型（理解偏差/遗漏要点/表达不清等）
        error_description TEXT NOT NULL,  -- 具体错误描述
        feedback TEXT,  -- AI详细评语
        created_at REAL NOT NULL,  -- 创建时间
        review_count INTEGER DEFAULT 0,  -- 复习次数
        last_review_time REAL,  -- 最后复习时间
        is_corrected INTEGER DEFAULT 0  -- 是否已改正，0=未改正，1=已改正
    );
    """

    def __init__(self, path: str = 'data/reading_error_book.db'):
        """初始化阅读错题本"""
        self._max_retries = 3
        self._retry_delay = 1  # 重试延迟（秒）
        self.db_path = path
        if not os.path.exists(path):
            self._init_db()

    def _get_connection(self):
        """获取数据库连接，带重试机制"""
        for attempt in range(self._max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                conn.row_factory = sqlite3.Row
                return conn
            except sqlite3.Error as e:
                if attempt == self._max_retries - 1:
                    raise Exception(f"数据库连接失败: {str(e)}")
                time.sleep(self._retry_delay)
        return None

    def _init_db(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            conn.execute("DROP TABLE IF EXISTS reading_error_records")
            conn.execute(self._DB_SCHEMA)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reading_created_at ON reading_error_records(created_at)")
            conn.commit()

    def _execute_with_retry(self, operation, *args, **kwargs):
        """执行数据库操作，带重试机制"""
        for attempt in range(self._max_retries):
            try:
                with self._get_connection() as conn:
                    result = operation(conn, *args, **kwargs)
                    conn.commit()
                    return result
            except sqlite3.Error as e:
                if attempt == self._max_retries - 1:
                    raise Exception(f"数据库操作失败: {str(e)}")
                time.sleep(self._retry_delay)
        return None

    def add_error(self, article_title: str, article_content: str, user_summary: str, 
                 correct_summary: str, error_type: str, error_description: str, 
                 feedback: str = "") -> str:
        """添加阅读错题记录
        
        Args:
            article_title: 文章标题
            article_content: 文章内容
            user_summary: 用户总结
            correct_summary: 正确答案
            error_type: 错误类型
            error_description: 错误描述
            feedback: AI详细评语
            
        Returns:
            str: 错题ID
        """
        error_id = f"err_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        created_at = datetime.now().timestamp()
        
        def _add_error(conn):
            conn.execute("""
                INSERT INTO reading_error_records (
                    error_id, article_title, article_content, user_summary, 
                    correct_summary, error_type, error_description, feedback, 
                    created_at, is_corrected
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error_id, article_title, article_content, user_summary,
                correct_summary, error_type, error_description, feedback,
                created_at, 0
            ))
            return error_id
            
        return self._execute_with_retry(_add_error)

    def get_all_errors(self) -> list:
        """获取所有阅读错题记录"""
        def _get_errors(conn):
            cursor = conn.execute("""
                SELECT * FROM reading_error_records 
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        return self._execute_with_retry(_get_errors)

    def get_review_items(self, days: int = 7) -> list:
        """获取需要复习的阅读错题
        
        Args:
            days: 最近多少天内的错题需要复习
            
        Returns:
            list: 需要复习的错题列表
        """
        def _get_review_items(conn):
            cursor = conn.execute("""
                SELECT * FROM reading_error_records 
                WHERE review_count < 3 
                AND created_at > ? 
                AND is_corrected = 0
                ORDER BY review_count ASC, created_at DESC
            """, (datetime.now().timestamp() - days * 24 * 3600,))
            return [dict(row) for row in cursor.fetchall()]
        return self._execute_with_retry(_get_review_items)

    def update_review_status(self, error_id: str):
        """更新阅读错题复习状态"""
        def _update_status(conn):
            conn.execute("""
                UPDATE reading_error_records 
                SET review_count = review_count + 1,
                    last_review_time = ?
                WHERE error_id = ?
            """, (datetime.now().timestamp(), error_id))
        self._execute_with_retry(_update_status)

    def get_error_statistics(self) -> dict:
        """获取阅读错题统计信息"""
        def _get_stats(conn):
            cursor = conn.execute("SELECT COUNT(*) as count FROM reading_error_records")
            total_errors = cursor.fetchone()['count']
            seven_days_ago = datetime.now().timestamp() - 7 * 24 * 3600
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM reading_error_records 
                WHERE created_at > ?
            """, (seven_days_ago,))
            recent_errors = cursor.fetchone()['count']
            cursor = conn.execute("SELECT AVG(review_count) as avg_count FROM reading_error_records")
            avg_review = cursor.fetchone()['avg_count'] or 0
            cursor = conn.execute("""
                SELECT error_type, COUNT(*) as count 
                FROM reading_error_records 
                GROUP BY error_type
            """)
            error_types = {row['error_type']: row['count'] for row in cursor.fetchall()}
            return {
                'total_errors': total_errors,
                'recent_errors': recent_errors,
                'avg_review_count': avg_review,
                'error_types': error_types
            }
        return self._execute_with_retry(_get_stats)

    def format_review_item(self, item: dict) -> str:
        """格式化阅读复习项"""
        return f"""文章标题：{item['article_title']}
\n文章内容：\n{item['article_content']}\n\n您的总结：\n{item['user_summary']}\n\n正确答案：\n{item['correct_summary']}\n\n错误类型：{item['error_type']}\n错误描述：{item['error_description']}\n\n请重新总结文章内容（输入"\\skip"可以跳过此题）："""

    def delete_error_by_id(self, error_id: str) -> bool:
        """根据 error_id 删除阅读错题记录"""
        def _delete_error(conn):
            cursor = conn.execute(
                "DELETE FROM reading_error_records WHERE error_id = ?",
                (error_id,)
            )
            return cursor.rowcount > 0
        return self._execute_with_retry(_delete_error)

    def mark_error_corrected(self, error_id: str) -> bool:
        """将指定阅读错题的已改正状态设为1"""
        def _mark_corrected(conn):
            cursor = conn.execute(
                "UPDATE reading_error_records SET is_corrected = 1 WHERE error_id = ? AND is_corrected = 0",
                (error_id,)
            )
            return cursor.rowcount > 0
        return self._execute_with_retry(_mark_corrected) 