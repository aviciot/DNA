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
        self._client: AsyncAnthropic | None = None

    async def _get_client(self) -> AsyncAnthropic:
        """Resolve Anthropic client: env var first, then llm_providers table."""
        if settings.ANTHROPIC_API_KEY:
            return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        # Key not in env — fetch from llm_providers (stored encrypted)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT api_key FROM {settings.DATABASE_APP_SCHEMA}.llm_providers "
                    "WHERE name = 'claude' AND enabled = true LIMIT 1"
                )
            if row and row["api_key"]:
                raw = row["api_key"]
                if raw.startswith("enc:"):
                    import base64, hashlib
                    from cryptography.fernet import Fernet
                    fkey = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
                    raw = Fernet(fkey).decrypt(raw[4:].encode()).decode()
                return AsyncAnthropic(api_key=raw)
        except Exception as e:
            logger.warning(f"Could not load Anthropic key from DB: {e}")
        return AsyncAnthropic(api_key="")  # will fail with clear SDK error

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

                # Get conversation history; always ensure current message is included
                history = await self._get_conversation_history(conversation_id)
                if not history:
                    history = [{"role": "user", "content": user_message}]

                # Stream response from Claude
                client = await self._get_client()
                assistant_message = ""
                async with client.messages.stream(
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
