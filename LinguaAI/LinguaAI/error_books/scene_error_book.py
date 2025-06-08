import os
import sqlite3
import json
from datetime import datetime
import uuid
from typing import List, Dict, Any, Optional
import time

class SceneErrorBook:
    """错题本管理类，使用SQLite数据库存储错题记录"""
    
    _DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS error_records (
        error_id TEXT PRIMARY KEY,
        scene_id TEXT NOT NULL,  -- 新增场景ID字段
        scene TEXT NOT NULL,  -- JSON格式存储场景信息
        conversation_context TEXT NOT NULL,  -- JSON格式存储对话上下文
        user_error_input TEXT NOT NULL,
        correct_response TEXT NOT NULL,
        error_type TEXT,  -- 错误类型：语法错误/主题偏离/回答不完整/用词不当
        error_description TEXT  -- 具体错误描述
    );
    """

    def __init__(self, path: str = 'data/scene_error_book.db'):
        """初始化错题本"""
        self._max_retries = 3
        self._retry_delay = 1  # 重试延迟（秒）
        self.db_path = path
        if not os.path.exists(path):
            self._init_db()
        


    def _get_connection(self):
        """获取数据库连接，带重试机制"""
        for attempt in range(self._max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)  # 增加超时时间
                conn.row_factory = sqlite3.Row
                return conn
            except sqlite3.Error as e:
                if attempt == self._max_retries - 1:  # 最后一次尝试
                    raise Exception(f"数据库连接失败: {str(e)}")
                time.sleep(self._retry_delay)
        return None

    def _init_db(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            # 删除旧表（如果存在）
            conn.execute("DROP TABLE IF EXISTS error_records")
            
            # 创建新表，增加 is_corrected 字段
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_records (
                    error_id TEXT PRIMARY KEY,
                    scene_id TEXT NOT NULL,  -- 场景ID
                    scene TEXT NOT NULL,  -- JSON格式存储场景信息
                    conversation_context TEXT NOT NULL,  -- JSON格式存储对话上下文
                    user_error_input TEXT NOT NULL,
                    correct_response TEXT NOT NULL,
                    error_type TEXT NOT NULL,  -- 错误类型：语法错误/主题偏离/回答不完整/用词不当
                    error_description TEXT NOT NULL,  -- 具体错误描述
                    created_at REAL NOT NULL,  -- 创建时间
                    review_count INTEGER DEFAULT 0,  -- 复习次数
                    last_review_time REAL,  -- 最后复习时间
                    is_corrected INTEGER DEFAULT 0  -- 是否已改正，0=未改正，1=已改正
                )
            """)
            # 为scene_id创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scene_id ON error_records(scene_id)")
            # 为created_at创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON error_records(created_at)")
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
                if attempt == self._max_retries - 1:  # 最后一次尝试
                    raise Exception(f"数据库操作失败: {str(e)}")
                time.sleep(self._retry_delay)
        return None

    def _generate_scene_id(self):
        """生成唯一的场景ID"""
        return f"scene_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

    def add_error(self, scene: dict, conversation_context: list, user_error_input: str, 
                 correct_response: str, error_type: str, error_description: str, scene_id: str) -> str:
        """添加错题记录
        
        Args:
            scene: 场景信息
            conversation_context: 对话上下文
            user_error_input: 用户错误输入
            correct_response: 正确答案
            error_type: 错误类型
            error_description: 错误描述
            scene_id: 场景ID，如果为None则生成新的场景ID
        
        Returns:
            str: 错题ID
        """
            
        error_id = f"err_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        created_at = datetime.now().timestamp()
        
        def _add_error(conn):
            conn.execute("""
                INSERT INTO error_records (
                    error_id, scene_id, scene, conversation_context, 
                    user_error_input, correct_response, error_type, 
                    error_description, created_at, is_corrected
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error_id, scene_id, json.dumps(scene, ensure_ascii=False),
                json.dumps(conversation_context, ensure_ascii=False),
                user_error_input, correct_response, error_type,
                error_description, created_at, 0  # 新增 is_corrected 字段，默认0
            ))
            return error_id
        
        return self._execute_with_retry(_add_error)

    def get_errors_by_scene(self, scene_id: str) -> list:
        """获取指定场景的所有错题
        
        Args:
            scene_id: 场景ID
            
        Returns:
            list: 错题记录列表
        """
        def _get_errors(conn):
            cursor = conn.execute("""
                SELECT * FROM error_records 
                WHERE scene_id = ? 
                ORDER BY created_at DESC
            """, (scene_id,))
            return [dict(row) for row in cursor.fetchall()]
        
        return self._execute_with_retry(_get_errors)

    def get_review_items(self, days: int = 7) -> list:
        """获取需要复习的错题
        
        Args:
            days: 最近多少天内的错题需要复习
            
        Returns:
            list: 需要复习的错题列表
        """
        def _get_review_items(conn):
            cursor = conn.execute("""
                SELECT * FROM error_records 
                WHERE review_count < 3 
                AND created_at > ? 
                AND is_corrected = 0
                ORDER BY review_count ASC, created_at DESC
            """, (datetime.now().timestamp() - days * 24 * 3600,))
            return [dict(row) for row in cursor.fetchall()]
        
        return self._execute_with_retry(_get_review_items)

    def update_review_status(self, error_id: str):
        """更新错题复习状态"""
        def _update_status(conn):
            conn.execute("""
                UPDATE error_records 
                SET review_count = review_count + 1,
                    last_review_time = ?
                WHERE error_id = ?
            """, (datetime.now().timestamp(), error_id))
        
        self._execute_with_retry(_update_status)

    def get_error_statistics(self) -> dict:
        """获取错题统计信息"""
        def _get_stats(conn):
            # 获取总错题数
            cursor = conn.execute("SELECT COUNT(*) as count FROM error_records")
            total_errors = cursor.fetchone()['count']
            
            # 获取最近7天的错题数
            seven_days_ago = datetime.now().timestamp() - 7 * 24 * 3600
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM error_records 
                WHERE created_at > ?
            """, (seven_days_ago,))
            recent_errors = cursor.fetchone()['count']
            
            # 获取平均复习次数
            cursor = conn.execute("SELECT AVG(review_count) as avg_count FROM error_records")
            avg_review = cursor.fetchone()['avg_count'] or 0
            
            # 获取各类型错题数量
            cursor = conn.execute("""
                SELECT error_type, COUNT(*) as count 
                FROM error_records 
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
        """格式化复习项"""
        # try:
        scene = json.loads(item['scene'])
        conversation = json.loads(item['conversation_context'])

        # 只获取最后一条AI消息作为上下文
        last_ai_msg = next((msg['content'] for msg in reversed(conversation) 
                            if msg['role'] == 'assistant'), '')
        print(last_ai_msg)

        return f"""场景：{scene['场景分析']['核心场景']}

                对话上下文：
                AI: {last_ai_msg}

                您的回答：{item['user_error_input']}

                错误类型：{item['error_type']}
                错误描述：{item['error_description']}

                请重新回答（输入"\skip"可以跳过此题）："""
        # except Exception as e:
        #     print(f"格式化复习项时出错: {str(e)}")
        #     return "抱歉，加载复习项时出错，请跳过此题。"

    def delete_error_by_id(self, error_id: str) -> bool:
        """根据 error_id 删除错题记录

        Args:
            error_id: 错题ID

        Returns:
            bool: 是否删除成功
        """
        def _delete_error(conn):
            cursor = conn.execute(
                "DELETE FROM error_records WHERE error_id = ?",
                (error_id,)
            )
            return cursor.rowcount > 0  # 返回是否有行被删除

        return self._execute_with_retry(_delete_error)

    def mark_error_corrected(self, error_id: str) -> bool:
        """将指定错题的已改正状态设为1

        Args:
            error_id: 错题ID

        Returns:
            bool: 是否更新成功
        """
        def _mark_corrected(conn):
            cursor = conn.execute(
                "UPDATE error_records SET is_corrected = 1 WHERE error_id = ? AND is_corrected = 0",
                (error_id,)
            )
            return cursor.rowcount > 0  # 返回是否有行被更新

        return self._execute_with_retry(_mark_corrected) 