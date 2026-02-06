"""
DNA Backend - WebSocket Chat with Claude
=========================================
Real-time chat with Claude AI assistant.
"""

import json
import logging
import uuid
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from anthropic import AsyncAnthropic

from .config import settings
from .database import get_db_pool

logger = logging.getLogger(__name__)


class ChatService:
    """Manages WebSocket chat connections with Claude."""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def handle_chat(self, websocket: WebSocket, user_id: int):
        """
        Handle WebSocket chat connection.
        
        Args:
            websocket: WebSocket connection
            user_id: Authenticated user ID
        """
        conversation_id = str(uuid.uuid4())
        logger.info(f"Chat session started for user {user_id}, conversation {conversation_id}")

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                user_message = message_data.get("message", message_data.get("content", ""))

                if not user_message:
                    continue

                # Store user message
                await self._store_message(conversation_id, user_id, "user", user_message)

                # Get conversation history
                history = await self._get_conversation_history(conversation_id)

                # Stream response from Claude
                assistant_message = ""
                async with self.client.messages.stream(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                    messages=history,
                    system="You are a helpful AI assistant for DNA ISO Certification Dashboard. Help users with ISO certification workflows, document completion, and customer management."
                ) as stream:
                    async for text in stream.text_stream:
                        assistant_message += text
                        # Stream response to client (using "token" type for frontend compatibility)
                        await websocket.send_json({
                            "type": "token",
                            "content": text
                        })

                # Store complete assistant message
                await self._store_message(conversation_id, user_id, "assistant", assistant_message)

                # Send completion signal (using "done" type for frontend compatibility)
                await websocket.send_json({
                    "type": "done",
                    "content": assistant_message,
                    "conversation_id": conversation_id
                })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id}")
        except Exception as e:
            logger.error(f"Chat error for user {user_id}: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "content": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
            except:
                pass

    async def _store_message(self, conversation_id: str, user_id: int, role: str, content: str):
        """Store message in database."""
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO dna_app.conversations (conversation_id, user_id, message_role, message_content, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                """, conversation_id, user_id, role, content)
        except Exception as e:
            logger.error(f"Failed to store message: {e}")

    async def _get_conversation_history(self, conversation_id: str, limit: int = 20):
        """Get conversation history for context."""
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT message_role, message_content
                    FROM dna_app.conversations
                    WHERE conversation_id = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                """, conversation_id, limit)

                history = []
                for row in rows:
                    history.append({
                        "role": row["message_role"],
                        "content": row["message_content"]
                    })

                return history

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []


# Global chat service instance
chat_service = ChatService()
