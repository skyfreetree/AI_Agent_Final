import os
import sqlite3
import time
import uuid
from typing import Dict, List, Optional

import json


_DB = """
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    created_at REAL DEFAULT (strftime('%s.%f', 'now')),
    updated_at REAL DEFAULT (strftime('%s.%f', 'now')),
    last_updated REAL DEFAULT (strftime('%s.%f', 'now')),
    task TEXT, 
    mode TEXT DEFAULT 'start',
    mode_start BOOLEAN DEFAULT TRUE,
    listening_mode TEXT DEFAULT 'None',
    summary TEXT
);

CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    role TEXT CHECK(role IN ('user', 'assistant', 'system')),
    content_type TEXT CHECK(content_type IN ('text', 'image', 'audio', 'video', 'file')),
    content TEXT,
    mode TEXT,
    created_at REAL DEFAULT (strftime('%s.%f', 'now')),
    updated_at REAL DEFAULT (strftime('%s.%f', 'now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);
CREATE TABLE attachments (
    attachment_id TEXT PRIMARY KEY,
    message_id TEXT,
    file_name TEXT,
    file_path TEXT,
    file_type TEXT,
    file_size INTEGER,
    extracted_text TEXT,
    created_at REAL DEFAULT (strftime('%s.%f', 'now')),
    updated_at REAL DEFAULT (strftime('%s.%f', 'now')),
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
);
"""


class TaskDatabase:
    """A class to manage chat-related database operations.

    This class handles all database interactions for conversations, messages,
    attachments, and settings using SQLite.

    Attributes:
        db_path (str): Path to the SQLite database file
    """

    def __init__(self, db_path: str = "data/task_chat.db"):
        """Initialize the database connection.

        Args:
            db_path (str, optional): Path to the SQLite database file. Defaults to "chatbot.db".
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema.

        Creates tables if they don't exist or if the database is new.
        Also handles schema migrations for existing databases.
        """
        db_exists = os.path.exists(self.db_path)

        with sqlite3.connect(self.db_path) as conn:
            if not db_exists:
                # Execute schema
                conn.executescript(_DB)

    def create_conversation(self) -> str:
        """Create a new conversation.

        Returns:
            str: Unique identifier for the created conversation.
        """
        conversation_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO conversations (conversation_id) VALUES (?)", (conversation_id,))
        return conversation_id

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        mode: str,
        content_type: str = "text",
        attachments: Optional[List[Dict]] = None,
    ) -> str:
        """Add a new message to a conversation.

        Args:
            conversation_id (str): ID of the conversation
            role (str): Role of the message sender ('user', 'assistant', or 'system')
            content (str): Content of the message
            content_type (str, optional): Type of content. Defaults to "text".
            attachments (Optional[List[Dict]], optional): List of attachment metadata. Defaults to None.

        Returns:
            str: Unique identifier for the created message
        """
        message_id = str(uuid.uuid4())
        current_time = time.time()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO messages
                   (message_id, conversation_id, role, content_type, content, created_at, mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (message_id, conversation_id, role, content_type, content, current_time, mode),
            )

            conn.execute(
                """UPDATE conversations
                   SET last_updated = ?
                   WHERE conversation_id = ?""",
                (current_time, conversation_id),
            )

            if attachments:
                for att in attachments:
                    conn.execute(
                        """INSERT INTO attachments
                           (attachment_id, message_id, file_name, file_path, file_type, file_size, extracted_text, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(uuid.uuid4()),
                            message_id,
                            att["name"],
                            att["path"],
                            att["type"],
                            att["size"],
                            att.get("extracted_text", ""),
                            current_time,
                        ),
                    )

        return message_id

    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Retrieve the full history of a conversation including attachments.

        Args:
            conversation_id (str): ID of the conversation

        Returns:
            List[Dict]: List of messages with their attachments in chronological order
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            messages = conn.execute(
                """SELECT m.*, a.attachment_id, a.file_name, a.file_path, a.file_type, a.file_size, a.extracted_text
                   FROM messages m
                   LEFT JOIN attachments a ON m.message_id = a.message_id
                   WHERE m.conversation_id = ?
                   ORDER BY m.created_at ASC""",
                (conversation_id,),
            ).fetchall()

        # Group attachments by message_id
        message_dict = {}
        for row in messages:
            message_id = row["message_id"]
            if message_id not in message_dict:
                message_dict[message_id] = {
                    key: row[key]
                    for key in ["message_id", "conversation_id", "role", "content_type", "content", "created_at"]
                }
                message_dict[message_id]["attachments"] = []

            if row["attachment_id"]:
                message_dict[message_id]["attachments"].append(
                    {
                        "attachment_id": row["attachment_id"],
                        "file_name": row["file_name"],
                        "file_path": row["file_path"],
                        "file_type": row["file_type"],
                        "file_size": row["file_size"],
                        "extracted_text": row["extracted_text"],
                    }
                )

        return list(message_dict.values())
    def get_task_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Retrieve the full history of a conversation including attachments up to but not including a message_id.

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            messages = conn.execute(
                """SELECT m.role, m.content, m.mode
                   FROM messages m
                   WHERE m.conversation_id = ?
                   ORDER BY m.created_at ASC""",
                (conversation_id,),
            ).fetchall()
            if messages:
                return [dict(row) for row in messages]
            else:
                return []

    def get_question(self, conversation_id: str, mode: str) -> str:
        """Retrieve the listening question of a conversation.

        Args:
            conversation_id (str): ID of the conversation

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            question = conn.execute(
               """SELECT m.content
                   FROM messages m
                   WHERE m.conversation_id = ? and m.role = 'assistant' and m.mode = ?
                   ORDER BY m.created_at ASC""",
                (conversation_id, mode),
            ).fetchone()
            return question[0] if question else None
    def get_conversation_history_upto_message_id(self, conversation_id: str, message_id: str) -> List[Dict]:
        """Retrieve the full history of a conversation including attachments up to but not including a message_id.

        Args:
            conversation_id (str): ID of the conversation
            message_id (str): ID of the message

        Returns:
            List[Dict]: List of messages with their attachments in chronological order
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            messages = conn.execute(
                """SELECT m.*, a.attachment_id, a.file_name, a.file_path, a.file_type, a.file_size
                   FROM messages m
                   LEFT JOIN attachments a ON m.message_id = a.message_id
                   WHERE m.conversation_id = ? AND m.created_at < (
                       SELECT created_at FROM messages WHERE message_id = ?
                   )
                   ORDER BY m.created_at ASC""",
                (conversation_id, message_id),
            ).fetchall()

        # Group attachments by message_id
        message_dict = {}
        for row in messages:
            message_id = row["message_id"]
            if message_id not in message_dict:
                message_dict[message_id] = {
                    key: row[key]
                    for key in ["message_id", "conversation_id", "role", "content_type", "content", "created_at"]
                }
                message_dict[message_id]["attachments"] = []

            if row["attachment_id"]:
                message_dict[message_id]["attachments"].append(
                    {
                        "attachment_id": row["attachment_id"],
                        "file_name": row["file_name"],
                        "file_path": row["file_path"],
                        "file_type": row["file_type"],
                        "file_size": row["file_size"],
                    }
                )

        return list(message_dict.values())
    def get_conversation_task(self, conversation_id: str) -> Dict:
        """Retrieve the task of a conversation.

        Args:
            conversation_id (str): ID of the conversation

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            task = conn.execute(
                """SELECT task FROM conversations WHERE conversation_id = ?""",
                (conversation_id,),
            ).fetchone()
            return json.loads(task[0]) if task[0] else None
    def get_conversation_mode(self, conversation_id: str) -> Dict:
        """Retrieve the mode of a conversation.

        Args:
            conversation_id (str): ID of the conversation

        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
            mode = conn.execute(
                """SELECT mode FROM conversations WHERE conversation_id = ?""",
                (conversation_id,),
            ).fetchone()
            return mode[0] if mode else None
        except Exception as e:
            print(f"Error getting conversation mode: {e}")
            return None
    def get_conversation_mode_start(self, conversation_id: str) -> bool:
        """Retrieve the mode_start of a conversation.

        Args:
            conversation_id (str): ID of the conversation

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            mode_start = conn.execute(
                """SELECT mode_start FROM conversations WHERE conversation_id = ?""",
                (conversation_id,),
            ).fetchone()
            
            return mode_start[0] if mode_start else None
    def get_conversation_listening_mode(self, conversation_id: str) -> str:
        """Retrieve the listening_mode of a conversation.

        Args:
            conversation_id (str): ID of the conversation

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            listening_mode = conn.execute(
                """SELECT listening_mode FROM conversations WHERE conversation_id = ?""",
                (conversation_id,),
            ).fetchone()
            return listening_mode[0] if listening_mode else None
    
    def update_conversation_mode(self, conversation_id: str, mode: str):
        """Update the mode of a conversation.

        Args:
            conversation_id (str): ID of the conversation
            mode (str): New mode for the conversation
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE conversations
                   SET mode = ?, updated_at = strftime('%s.%f', 'now')
                   WHERE conversation_id = ?""",
                (mode, conversation_id),
            )
    def update_conversation_mode_start(self, conversation_id: str, mode_start: bool):
        """Update the mode_start of a conversation.

        Args:
            conversation_id (str): ID of the conversation
            mode_start (bool): New mode_start for the conversation

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE conversations
                   SET mode_start = ?, updated_at = strftime('%s.%f', 'now')
                   WHERE conversation_id = ?""",
                (mode_start, conversation_id),
            )
    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its associated messages and attachments.

        Args:
            conversation_id (str): ID of the conversation to delete
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """DELETE FROM attachments
                   WHERE message_id IN (
                       SELECT message_id FROM messages WHERE conversation_id = ?
                   )""",
                (conversation_id,),
            )
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))

    def get_all_conversations(self) -> List[Dict]:
        """Retrieve all conversations with their message counts and last activity.

        Returns:
            List[Dict]: List of conversations with their metadata
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conversations = conn.execute(
                """SELECT c.*,
                   COUNT(m.message_id) as message_count,
                   MAX(m.created_at) as last_message_at
                   FROM conversations c
                   LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                   GROUP BY c.conversation_id
                   ORDER BY c.created_at ASC"""
            ).fetchall()

        return [dict(conv) for conv in conversations]

    

    def update_conversation_summary(self, conversation_id: str, summary: str):
        """Update the summary of a conversation.

        Args:
            conversation_id (str): ID of the conversation
            summary (str): New summary text for the conversation
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE conversations
                   SET summary = ?, updated_at = strftime('%s.%f', 'now')
                   WHERE conversation_id = ?""",
                (summary, conversation_id),
            )
    def update_conversation_task(self, conversation_id: str, task: str):
        """Update the summary of a conversation.

        Args:
            conversation_id (str): ID of the conversation
            task (str): New task text for the conversation
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE conversations
                   SET task = ?, updated_at = strftime('%s.%f', 'now')
                   WHERE conversation_id = ?""",
                (task, conversation_id),
            )
    def update_conversation_listening_mode(self, conversation_id: str, listening_mode: str):
        """Update the listening_mode of a conversation.

        Args:
            conversation_id (str): ID of the conversation
            listening_mode (str): New listening_mode for the conversation   
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """UPDATE conversations
                    SET listening_mode = ?, updated_at = strftime('%s.%f', 'now')
                    WHERE conversation_id = ?""",
                        (listening_mode, conversation_id),
                    )
        except Exception as e:
            print(f"Error updating conversation listening mode: {e}")
    def edit_message(self, message_id: str, new_content: str) -> bool:
        """Edit an existing message's content.

        Args:
            message_id (str): ID of the message to edit
            new_content (str): New message content

        Returns:
            bool: True if successful, False if message not found

        Raises:
            ValueError: If trying to edit a system message
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if message exists and isn't a system message
            message = conn.execute("SELECT role FROM messages WHERE message_id = ?", (message_id,)).fetchone()

            if not message:
                return False

            if message[0] == "system":
                raise ValueError("System messages cannot be edited")

            cursor = conn.execute(
                """UPDATE messages
                   SET content = ?, updated_at = strftime('%s.%f', 'now')
                   WHERE message_id = ?""",
                (new_content, message_id),
            )
            return cursor.rowcount > 0
