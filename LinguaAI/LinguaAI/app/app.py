import asyncio
import base64
import os
import re
import sqlite3
import tempfile
import time
import io
import re
import traceback
from datetime import datetime, timedelta
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from audio.text_to_speech.kokoro import Kokoro
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Query
from fastapi import Response
import httpx
from LinguaAI.my_logging import logger
from LinguaAI.app.dialogue import DialogueAssistant
from LinguaAI.agent.PlanningAgent import PlanningAgent
from LinguaAI.database import TaskDatabase, ChatDatabase
from LinguaAI.prompts import COMPONENT_PROMPTS
import io
from LinguaAI.app.models import *
from LinguaAI.app.utils import *
logger.info("LinguaAI...")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()
static_path = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")
templates_path = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=templates_path)



# Initialize database
scene_db = ChatDatabase()
task_db = TaskDatabase()
db_settings = scene_db.get_settings()


manager = ConnectionManager()
# tts = Kokoro()
# from audio.speech_to_text.whisper import Whisper
# whisper = Whisper()
@dataclass
class RequestContext:
    is_disconnected: bool = False


# Create a context variable to track request state
request_context: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())

def get_db(mode: Optional[str] = None):
    if mode == "task_chat":
        return task_db
    return scene_db
@app.post("/dialogue/chat")
async def dialogue_chat(
    message: str = Form(...),
    conversation_id: str = Form(...),
):
    """
    用于和DialogueAssistant进行对话模拟
    """
    try:
        scene_assistant = await DialogueAssistant.create(conversation_id)
        response = await scene_assistant.chat(message)
        
        return response
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.post("/task_chat")
async def task_chat(
            message: str = Form(...),
            conversation_id: str = Form(...),
        ):
    """
    用于和PlanningAgent进行对话模拟
    """
    try:
        print('开始初始化')
        assistant = await PlanningAgent.create(conversation_id)
        print('assistant', assistant)
        response = await assistant.chat(message)
        
        return response
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
# 文本转语音
@app.post("/text_to_speech")
async def text_to_speech(text: str = Form(...)):
    is_english = not re.search(r'[\u4e00-\u9fff]', text)
    print('is_english', is_english)
    try:
        wav_bytes = await tts.generate_audio(text, is_english)
        return StreamingResponse(wav_bytes, media_type='audio/wav')
    except Exception as e:
        logger.error(f"text_to_speech error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/speech_to_text")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    接收音频数据并使用Whisper模型进行语音识别
    
    Args:
        audio (UploadFile): 上传的音频文件
        
    Returns:
        dict: 识别结果文本
    """
    try:

        # # Read the audio file
        audio_data = await audio.read()

        logger.info(f"Received audio data of size: {len(audio_data)} bytes")
        
        # Transcribe the audio directly using the audio bytes
        text = whisper.transcribe(audio_data, 'web')
        print('--------------开始语音识别----------------')
        print(text)
        return {"text": text}
    except Exception as e:
        logger.error(f"语音识别错误: {e}")
        raise HTTPException(status_code=500, detail="语音识别失败")
@app.get("/", response_class=HTMLResponse)
async def load_index(request: Request):
    """
    Serve the main application page.

    Args:
        request (Request): FastAPI request object

    Returns:
        TemplateResponse: Rendered HTML template
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )





@app.get("/conversations/{mode}")
async def get_conversations(mode: str):
    """
    Retrieve all conversations.

    Returns:
        dict: List of all conversations

    Raises:
        HTTPException: If database operation fails
    """
    try:
        db = get_db(mode)
        conversations = db.get_all_conversations()
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{mode}/{conversation_id}")
async def get_conversation(mode: str, conversation_id: str):
    """
    Retrieve a specific conversation's history.

    Args:
        conversation_id (str): ID of the conversation to retrieve

    Returns:
        dict: Conversation messages

    Raises:
        HTTPException: If conversation not found or operation fails
    """
    try:
        db = get_db(mode)
        history = db.get_conversation_history(conversation_id)
        if not history:
            raise HTTPException(status_code=404, detail="Conversation not found")
        # 处理每条消息的附件，图片类型转为base64
        for msg in history:
            attachments = msg.get("attachments", [])
            new_attachments = []
            for att in attachments:
                if att.get("type", "").startswith("image/") and att.get("path"):
                    try:
                        data = file_to_base64(att["path"], att["type"])
                    except Exception:
                        data = ""
                    new_attachments.append({
                        "name": att.get("name") or att.get("file_name"),
                        "type": att.get("type") or att.get("file_type"),
                        "data": data
                    })
                else:
                    new_attachments.append({
                        "name": att.get("name") or att.get("file_name"),
                        "type": att.get("type") or att.get("file_type"),
                        "data": ""
                    })
            msg["attachments"] = new_attachments
        return {"messages": history}
    except Exception as e:
        logger.error(f"get_conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create_conversation/{mode}")
async def create_conversation(mode: str):
    """
    Create a new conversation.

    Returns:
        dict: New conversation ID

    Raises:
        HTTPException: If creation fails
    """
    try:
        db = get_db(mode)
        conversation_id = db.create_conversation()
        await manager.broadcast({"type": "conversation_created", "conversation_id": conversation_id})
        return {"conversation_id": conversation_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/conversations/{mode}/{conversation_id}/messages")
async def add_message(mode: str, conversation_id: str, message: MessageInput):
    """
    Add a message to a conversation.

    Args:
        conversation_id (str): Target conversation ID
        message (MessageInput): Message data to add

    Returns:
        dict: Added message ID

    Raises:
        HTTPException: If operation fails
    """
    try:
        db = get_db(mode)
        message_id = db.add_message(
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
            content_type=message.content_type,
            attachments=message.attachments,
        )
        return {"message_id": message_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/messages/{mode}/{message_id}")
async def edit_message(mode: str, message_id: str, edit: MessageEdit):
    """
    Edit an existing message.

    Args:
        message_id (str): ID of the message to edit
        edit (MessageEdit): New message content

    Returns:
        dict: Operation status

    Raises:
        HTTPException: If message not found or edit not allowed
    """
    try:
        db = get_db(mode)
        success = db.edit_message(message_id, edit.content)
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")

        # Get message role to send in broadcast
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            msg = conn.execute("SELECT role FROM messages WHERE message_id = ?", (message_id,)).fetchone()

        # Broadcast update to all connected clients
        await manager.broadcast(
            {"type": "message_edited", "message_id": message_id, "content": edit.content, "role": msg["role"]}
        )

        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/messages/{mode}/{message_id}/raw")
async def get_raw_message(mode: str, message_id: str):
    """Get the raw content of a message.

    Args:
        message_id (str): ID of the message to retrieve

    Returns:
        dict: Message content

    Raises:
        HTTPException: If message not found
    """
    try:
        db = get_db(mode)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            message = conn.execute("SELECT content FROM messages WHERE message_id = ?", (message_id,)).fetchone()

            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            return {"content": message["content"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/conversations/{mode}/{conversation_id}")
async def delete_conversation(mode: str, conversation_id: str):
    """
    Delete a conversation.

    Args:
        conversation_id (str): ID of conversation to delete

    Returns:
        dict: Operation status

    Raises:
        HTTPException: If deletion fails
    """
    try:
        db = get_db(mode)
        db.delete_conversation(conversation_id)
        await manager.broadcast({"type": "conversation_deleted", "conversation_id": conversation_id})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save_settings")
async def save_settings(settings: SettingsInput):
    """Save AI model settings.

    Args:
        settings (SettingsInput): Settings to save

    Returns:
        dict: Operation status

    Raises:
        HTTPException: If save operation fails or name already exists
    """
    try:
        settings_dict = settings.model_dump()
        settings_dict["updated_at"] = time.time()  # Add timestamp
        settings_dict["created_at"] = time.time()  # Add creation timestamp for new settings
        scene_db.save_settings(settings_dict)
        return {"status": "success"}
    except sqlite3.IntegrityError as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="A settings configuration with this name already exists")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings")
async def get_settings():
    """
    Retrieve current default settings configuration.

    Returns:
        dict: Current default settings

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        settings = scene_db.get_settings()
        if not settings:
            raise HTTPException(status_code=404, detail="No default settings found")
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings")
async def create_settings(settings: SettingsInput):
    """Create a new settings configuration.

    Args:
        settings (SettingsInput): Settings data to create

    Returns:
        dict: Created settings ID and status

    Raises:
        HTTPException: If creation fails or name already exists
    """
    try:
        settings_dict = settings.model_dump()
        settings_dict["updated_at"] = time.time()  # Add timestamp
        settings_dict["created_at"] = time.time()  # Add creation timestamp
        settings_id = scene_db.add_settings(settings_dict)
        return {"status": "success", "id": settings_id}
    except sqlite3.IntegrityError as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="A settings configuration with this name already exists")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/settings/{settings_id}")
async def update_settings(settings_id: int, settings: SettingsInput):
    """
    Update an existing settings configuration.

    Args:
        settings_id (int): ID of settings to update
        settings (SettingsInput): New settings data

    Returns:
        dict: Operation status
    """
    try:
        settings_dict = settings.model_dump()
        settings_dict["id"] = settings_id
        settings_dict["updated_at"] = time.time()  # Add timestamp
        settings_dict["created_at"] = time.time()  # Add creation timestamp
        success = scene_db.save_settings(settings_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Settings not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings/{settings_id}/set_default")
async def set_default_settings(settings_id: int):
    """
    Mark a settings configuration as default.

    Args:
        settings_id (int): ID of settings to mark as default

    Returns:
        dict: Operation status
    """
    try:
        success = scene_db.set_default_settings(settings_id)
        if not success:
            raise HTTPException(status_code=404, detail="Settings not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings/all")
async def get_all_settings():
    """
    Get all settings configurations.

    Returns:
        dict: List of all settings configurations
    """
    try:
        settings = scene_db.get_all_settings()
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings/{settings_id}")
async def get_settings_by_id(settings_id: int):
    """
    Get settings by ID.

    Args:
        settings_id (int): ID of settings to retrieve

    Returns:
        dict: Settings configuration
    """
    try:
        settings = scene_db.get_settings_by_id(settings_id)
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/default_settings")
async def get_default_values():
    """
    Get default values for a new settings configuration.

    Returns:
        dict: Default settings values
    """
    return {
        "temperature": 1.0,
        "max_tokens": 4096,
        "top_p": 0.95,
        "host": "http://localhost:8000/v1",
        "model_name": "meta-llama/Llama-3.2-1B-Instruct",
        "api_key": "",
        "tavily_api_key": "",
    }



# 小组件请求
@app.post("/components/{mode}/{component_type}")
async def handle_component(
    mode: str,
    component_type: str, 
    text: str = Form(...),
    conversation_id: str = Form(...)
    ):
    """
    统一处理组件请求
    
    Args:
        component_type (str): 组件类型 (translate/grammar/speech-fix/smart-reply)
        text (str): 需要处理的文本
        
    Returns:
        dict: 包含处理结果的字典
    """
    db = get_db(mode)
    if component_type not in ["translate", "grammar", "speech-fix", "smart-reply"]:
        raise HTTPException(status_code=400, detail="Invalid component type")
    prompt = COMPONENT_PROMPTS[component_type]
    if "History" in prompt:
        history = db.get_conversation_history(conversation_id)
        history = history[-2:] if isinstance(history, list) else history
        formatted_prompt = prompt.format(text=text, history=history)
    else:
        formatted_prompt = prompt.format(text=text)
    
    formatted_msg = {"role": "user", "content": formatted_prompt}
   
    return await text_reply([formatted_msg])
   


@app.post("/regenerate_response", response_class=StreamingResponse)
async def chat_again(
    message: str = Form(...),
    system_prompt: str = Form(...),
    conversation_id: str = Form(...),
    message_id: str = Form(...),
    client_id: str = Form(...),  # Add client_id parameter
):
    """
    This endpoint is used to regenerate the response of a message in a conversation at any point in time.

    Args:
        message (str): User's message
        system_prompt (str): System instructions for the AI
        conversation_id (str): Unique identifier for the conversation
        message_id (str): ID of the message to regenerate. This message will be replaced with the new response.

    Returns:
        StreamingResponse: Server-sent events stream of AI responses

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(
            f"Regenerate request: message='{message}' conv_id={conversation_id} system_prompt='{system_prompt}'"
        )

        # Verify conversation exists
        history = db.get_conversation_history_upto_message_id(conversation_id, message_id)
        logger.info(history)

        if not history:
            logger.error("No conversation history found")
            raise HTTPException(status_code=404, detail="No conversation history found")

        system_role_messages = [m for m in history if m["role"] == "system"]
        last_system_message = system_role_messages[-1]["content"] if system_role_messages else ""
        if last_system_message != system_prompt:
            db.add_message(conversation_id=conversation_id, role="system", content=system_prompt)

        async def process_and_stream():
            """
            Inner generator function to process the chat and stream responses.

            Yields:
                str: Chunks of the AI response
            """
            full_response = ""
            async for chunk in text_streamer(history, client_id, manager):
                full_response += chunk
                yield chunk
                await asyncio.sleep(0)  # Ensure chunks are flushed immediately

            # Store the complete response
            db.edit_message(message_id, full_response)

            # Broadcast update after storing the response
            await manager.broadcast(
                {
                    "type": "message_added",
                    "conversation_id": conversation_id,
                }
            )

        return StreamingResponse(
            process_and_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
            },
        )

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversations/{mode}/{conversation_id}/summary")
async def update_conversation_summary(mode: str, conversation_id: str, summary: str = Form(...)):
    """
    Update the summary of a conversation.

    Args:
        conversation_id (str): ID of the conversation
        summary (str): New summary text

    Returns:
        dict: Operation status

    Raises:
        HTTPException: If update fails
    """
    try:
        db = get_db(mode)
        db.update_conversation_summary(conversation_id, summary)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "stop_generation":
                manager.set_generating(client_id, False)
                logger.info(f"Received stop signal for client {client_id}")
            else:
                # Handle other WebSocket messages
                pass
    except WebSocketDisconnect:
        manager.disconnect(client_id)


@app.get("/api/study-status")
async def get_study_status():
    """获取用户学习统计数据"""
    try:
        logger.info("开始获取学习统计数据")
        
        # 获取今天的日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 获取一周内的日期列表
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        dates.reverse()  # 按时间正序排列
        
        # 获取三个错题本的记录数
        listening_errors = get_error_count("listening_error_book.db", today)
        reading_errors = get_error_count("reading_error_book.db", today)
        writing_errors = get_error_count("writing_error_book.db", today)
        
        # 获取一周内每天的错题数量
        weekly_listening_errors = [get_error_count("listening_error_book.db", date) for date in dates]
        weekly_reading_errors = [get_error_count("reading_error_book.db", date) for date in dates]
        weekly_writing_errors = [get_error_count("writing_error_book.db", date) for date in dates]
        
        logger.info(f"今日错题统计 - 听力: {listening_errors}, 阅读: {reading_errors}, 写作: {writing_errors}")
        logger.info(f"一周错题统计 - 听力: {weekly_listening_errors}, 阅读: {weekly_reading_errors}, 写作: {weekly_writing_errors}")
        
        return JSONResponse({
            "study_duration": 37,  
            "error_counts": {
                "listening": listening_errors,
                "reading": reading_errors,
                "writing": writing_errors
            },
            "weekly_errors": {
                "dates": dates,
                "listening": weekly_listening_errors,
                "reading": weekly_reading_errors,
                "writing": weekly_writing_errors
            }
        })
        
    except Exception as e:
        logger.error(f"获取学习统计数据时出错: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/error_filter_options")
async def error_filter_options(book: str = Query(...)):
    db_path = None
    table = None
    
    db_path = 'data/' + book + "_error_book.db"
    table = book + "_error_records"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    filters = []

    # 错误类型
    error_types = conn.execute(f"SELECT DISTINCT error_type FROM {table} WHERE error_type IS NOT NULL AND error_type != ''").fetchall()
    filters.append({
        "name": "错误类型",
        "key": "error_type",
        "options": [{"value": "", "label": "全部"}] + [{"value": row["error_type"], "label": row["error_type"]} for row in error_types]
    })
    # 作文题目
    topics = conn.execute(f"SELECT DISTINCT topic FROM {table} WHERE topic IS NOT NULL AND topic != ''").fetchall()
    filters.append({
        "name": "作文题目",
        "key": "topic",
        "options": [{"value": "", "label": "全部"}] + [{"value": row["topic"], "label": row["topic"]} for row in topics]
    })
    # 复习次数
    filters.append({"name": "复习次数", "key": "review_count", "type": "number_range"})
    # 最后复习时间
    filters.append({"name": "最后复习时间", "key": "last_review_time", "type": "date_range"})
    conn.close()
    return JSONResponse({"filters": filters})

@app.get("/api/wrong_list")
async def wrong_list(
    book: str = Query(...),
    error_type: str = Query(None),
    topic: str = Query(None),
    review_count_min: int = Query(None, alias="review_count-min"),
    review_count_max: int = Query(None, alias="review_count-max"),
    last_review_time_start: float = Query(None, alias="last_review_time-start"),
    last_review_time_end: float = Query(None, alias="last_review_time-end")
):
    db_path = None
    table = None
    if book == "writing":
        db_path = "data/writing_error_book.db"
        table = "writing_error_records"
    else:
        return JSONResponse([])

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = f"SELECT * FROM {table} WHERE 1=1"
    params = []
    if error_type:
        sql += " AND error_type = ?"
        params.append(error_type)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if review_count_min is not None:
        sql += " AND review_count >= ?"
        params.append(review_count_min)
    if review_count_max is not None:
        sql += " AND review_count <= ?"
        params.append(review_count_max)
    if last_review_time_start is not None:
        sql += " AND last_review_time >= ?"
        params.append(last_review_time_start)
    if last_review_time_end is not None:
        sql += " AND last_review_time <= ?"
        params.append(last_review_time_end)
    sql += " ORDER BY last_review_time DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "question": row["topic"],
            "answer": row["model_essay"],
            "error_type": row["error_type"],
            "error_description": row["error_description"],
            "feedback": row["feedback"],
            "review_count": row["review_count"],
            "last_review_time": row["last_review_time"]
        })
    return JSONResponse(result)


@app.api_route("/word_learning/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_word_learning(request: Request, path: str):
    backend_url = f"http://localhost:5000/{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            request.method,
            backend_url,
            headers=request.headers.raw,
            content=await request.body()
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )