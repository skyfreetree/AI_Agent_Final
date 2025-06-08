import base64
import PyPDF2
import io
import docx
from fastapi import HTTPException
from openai import OpenAI
from typing import List, Dict
from LinguaAI import logger
from LinguaAI.database import ChatDatabase
import asyncio
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
import time
import re
from pathlib import Path
import os
import sqlite3
from datetime import datetime

# Initialize database
db = ChatDatabase()

TEMP_DIR = "LinguaAI_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)
def file_to_base64(path, content_type):
    """文件转base64"""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"

def extract_text_from_pdf(file_content: bytes) -> str:
    """从PDF文件中提取文本内容"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_text_from_docx(file_content: bytes) -> str:
    """从Word文档中提取文本内容"""
    try:
        docx_file = io.BytesIO(file_content)
        doc = docx.Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {str(e)}")
        return ""

async def text_reply(messages: List[Dict[str, str]]):
    print('---------------------------')
    print('text_reply')
    db_settings = db.get_settings()
    if not db_settings:
        raise HTTPException(status_code=404, detail="No default settings found")

    client = OpenAI(
        api_key=db_settings["api_key"] if db_settings["api_key"] != "" else "empty",
        base_url=db_settings["host"],
    )

    try:
        response = client.chat.completions.create(
            messages=messages,
            model=db_settings["model_name"],
            max_completion_tokens=db_settings["max_tokens"],
            temperature=db_settings["temperature"],
            top_p=db_settings["top_p"],
            stream=False,
        )
        print('---------------------------')
        print(response.choices[0].message.content)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in text_reply: {e}")
        raise
# 流式文本输出
async def text_streamer(messages: List[Dict[str, str]], client_id: str, manager):
    """Stream text responses from the AI model."""
    formatted_messages = []

    for msg in messages:
        formatted_msg = {"role": msg["role"]}
        attachments = msg.get("attachments", [])

        content = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})

        if attachments:
            for att in attachments:
                # 1. 先加提取的文本
                extracted_text = att.get("extracted_text")
                if extracted_text:
                    content.append({
                        "type": "text",
                        "text": f"文件 '{att.get('name', '')}' 的内容：\n{extracted_text}"
                    })

                # 2. 仅对图片、音频、视频加 base64
                file_type = att.get("file_type", "").split("/")[0]
                if file_type in ["image", "audio", "video"]:
                    with open(att["file_path"], "rb") as f:
                        file_data = base64.b64encode(f.read()).decode()

                    content_type_map = {"image": "image_url", "video": "video_url", "audio": "input_audio"}
                    url_key = content_type_map.get(file_type, "file_url")
                    content.append({"type": url_key, url_key: {"url": f"data:{att['file_type']};base64,{file_data}"}})

            formatted_msg["content"] = content
        else:
            formatted_msg["content"] = msg.get("content", "")

        formatted_messages.append(formatted_msg)
        # print('formatted_messages', formatted_messages)
    db_settings = db.get_settings()
    if not db_settings:
        raise HTTPException(status_code=404, detail="No default settings found")

    client = OpenAI(
        api_key=db_settings["api_key"] if db_settings["api_key"] != "" else "empty",
        base_url=db_settings["host"],
    )

    stream = None
    try:
        manager.set_generating(client_id, True)
        stream = client.chat.completions.create(
            messages=formatted_messages,
            model=db_settings["model_name"],
            max_completion_tokens=db_settings["max_tokens"],
            temperature=db_settings["temperature"],
            top_p=db_settings["top_p"],
            stream=True,
        )

        for message in stream:
            if manager.should_stop(client_id):
                logger.info(f"Stopping generation for client {client_id}")
                break

            if message.choices and len(message.choices) > 0:
                if message.choices[0].delta.content is not None:
                    yield message.choices[0].delta.content

    except Exception as e:
        logger.error(f"Error in text_streamer: {e}")
        raise

    finally:
        manager.set_generating(client_id, False)
        if stream and hasattr(stream, "response"):
            stream.response.close()
def generate_safe_filename(original_filename: str) -> str:
    """
    Generate a safe filename with timestamp to prevent collisions.

    Args:
        original_filename (str): Original filename to be sanitized

    Returns:
        str: Sanitized filename with timestamp
    """
    # Get timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # Get file extension
    ext = Path(original_filename).suffix

    # Get base name and sanitize it
    base = Path(original_filename).stem
    # Remove special characters and spaces
    base = re.sub(r"[^\w\-_]", "_", base)

    # Create new filename
    return f"{base}_{timestamp}{ext}"

def process_uploaded_files(files):
    """
    处理上传的文件，保存到目录，并根据类型提取文本内容。

    Args:
        files (List[UploadFile]): 上传的文件列表

    Returns:
        Tuple[List[dict], str]: 文件信息列表和可能追加了文件内容的消息
    """
    file_info_list = []

    for file in files:
        if file is None:
            continue

    contents = asyncio.run(file.read())
    file_size = len(contents)

    safe_filename = generate_safe_filename(file.filename)
    temp_file = TEMP_DIR + '/' + safe_filename

    try:
        with open(temp_file, "wb") as f:
            f.write(contents)
        
        # 根据文件类型处理内容
        extracted_text = ""
        if file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(contents)
        elif file.content_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            extracted_text = extract_text_from_docx(contents)
    
        file_info = {
            "name": file.filename,  # Original name for display
            "path": str(temp_file),  # Path to saved file
            "type": file.content_type,
            "size": file_size,
            "extracted_text": extracted_text, 
        }
        file_info_list.append(file_info)
        logger.info(f"Saved uploaded file: {temp_file} ({file_size} bytes)")
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded file: {str(e)}")
    return file_info_list

def get_error_count(db_name: str, date: str) -> int:
    """
    获取指定错题本数据库中指定日期的错题数量
    
    Args:
        db_name (str): 错题本数据库名称
        date (str): 日期，格式为 YYYY-MM-DD
        
    Returns:
        int: 错题数量
    """
    try:
        # 根据数据库名称确定表名
        table_name = {
            "listening_error_book.db": "listening_error_records",
            "reading_error_book.db": "reading_error_records",
            "writing_error_book.db": "writing_error_records"
        }.get(db_name)
        
        if not table_name:
            logger.error(f"未知的错题本数据库: {db_name}")
            return 0
        
        db_path = 'data/' + db_name
        # 连接数据库并查询
        start_timestamp = datetime.strptime(date, "%Y-%m-%d").timestamp() - 86400 * 10
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            end_timestamp = start_timestamp + 86400 * 10
            
            # 查询指定日期范围内的记录数
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE created_at >= ? AND created_at < ?
            """, (start_timestamp, end_timestamp))
            
            count = cursor.fetchone()[0]
            logger.info(f"数据库 {db_name} 在 {date} 有 {count} 条记录")
            return count
            
    except Exception as e:
        logger.error(f"获取错题数量失败: {str(e)}")
        return 0

def get_today_study_duration(self):
    """获取当天的学习时长（秒）
    
    Returns:
        int: 当天的学习时长（秒），如果没有数据则返回None
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT SUM(duration) as total_duration 
                    FROM study_sessions 
                    WHERE date(created_at, 'unixepoch') = ?""",
                (today,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
    except Exception as e:
        logger.error(f"获取当天学习时长失败: {str(e)}")
        return None