import sys
import os
import sqlite3
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dataclasses import dataclass

# 直接读取数据库 settings 表
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'scene_chat.db')

def get_db_settings():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        settings = conn.execute('SELECT * FROM settings WHERE "default" = true').fetchone()
        return dict(settings) if settings else {}

db_settings = get_db_settings()

@dataclass
class APIConfig:
    """API 配置"""
    api_key: str = db_settings.get("api_key", "")
    model: str = db_settings.get("model_name", "")
    host: str = db_settings.get("host", "")
