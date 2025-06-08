from pydantic import BaseModel
from typing import Dict, List, Optional
from fastapi import WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # Use dict instead of list
        self.active_generations: Dict[str, bool] = {}  # Track active generations

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.active_generations[client_id] = False

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.active_generations:
            del self.active_generations[client_id]

    def set_generating(self, client_id: str, is_generating: bool):
        self.active_generations[client_id] = is_generating

    def should_stop(self, client_id: str) -> bool:
        return not self.active_generations.get(client_id, False)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except Exception:
                # If sending fails, we'll handle it in the main websocket route
                pass

class FileAttachment(BaseModel):
    """
    Pydantic model for handling file attachments in messages.

    Attributes:
        name (str): Name of the file
        type (str): MIME type of the file
        data (str): Base64 encoded file data
    """
    name: str
    type: str
    data: str

class MessageContent(BaseModel):
    """
    Pydantic model for message content including optional file attachments.

    Attributes:
        text (str): The text content of the message
        files (List[FileAttachment]): Optional list of file attachments
    """
    text: str
    files: Optional[List[FileAttachment]] = None

class ChatInput(BaseModel):
    """
    Pydantic model for chat input data.

    Attributes:
        message (str): The user's message content
        system_prompt (str): Instructions for the AI model
        conversation_id (str, optional): ID of the conversation
    """
    message: str
    system_prompt: str
    conversation_id: Optional[str] = None

class MessageInput(BaseModel):
    """
    Pydantic model for message input data.

    Attributes:
        role (str): The role of the message sender (e.g., 'user', 'assistant', 'system')
        content (str): The message content
        content_type (str): Type of content, defaults to "text"
        attachments (List[Dict], optional): List of file attachments
    """
    role: str
    content: str
    content_type: str = "text"
    attachments: Optional[List[Dict]] = None

class SettingsInput(BaseModel):
    """
    Pydantic model for AI model settings.

    Attributes:
        name (str): Name of the settings configuration
        temperature (float): Controls randomness in responses
        max_tokens (int): Maximum length of generated responses
        top_p (float): Controls diversity via nucleus sampling
        host (str): API endpoint URL
        model_name (str): Name of the AI model to use
        api_key (str): Authentication key for the API
        tavily_api_key (str): Authentication key for the Tavily API
    """
    name: str
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = 4096
    top_p: Optional[float] = 0.95
    host: Optional[str] = "http://localhost:8000/v1"
    model_name: Optional[str] = "meta-llama/Llama-3.2-1B-Instruct"
    api_key: Optional[str] = ""
    tavily_api_key: Optional[str] = ""

class PromptInput(BaseModel):
    """
    Pydantic model for system prompt input.

    Attributes:
        name (str): Name of the prompt
        text (str): The prompt text content
    """
    name: str
    text: str

class MessageEdit(BaseModel):
    """
    Pydantic model for message edit requests.

    Attributes:
        content (str): New message content
    """
    content: str 