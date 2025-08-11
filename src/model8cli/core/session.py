"""
Session Management for 200Model8CLI

Handles persistent conversation history, context management, and multi-session support.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import asyncio

import structlog
import tiktoken

from .api import Message
from .config import Config

logger = structlog.get_logger(__name__)


@dataclass
class SessionMessage:
    """Message in a session with metadata"""
    id: str
    role: str
    content: str
    timestamp: float
    model: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    tokens: Optional[int] = None
    cost: Optional[float] = None


@dataclass
class SessionMetadata:
    """Session metadata"""
    id: str
    name: str
    created_at: float
    updated_at: float
    model: str
    total_messages: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    tags: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Session:
    """Complete session with messages and metadata"""
    metadata: SessionMetadata
    messages: List[SessionMessage] = field(default_factory=list)
    context_summary: Optional[str] = None


class SessionManager:
    """
    Manages conversation sessions with persistent storage and context management
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.sessions_dir = Path(config.config_dir) / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)
        
        # Current session
        self.current_session: Optional[Session] = None
        
        # Token encoder for context management
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoder = None
            logger.warning("Failed to load tiktoken encoder")
        
        logger.info("Session manager initialized", sessions_dir=str(self.sessions_dir))
    
    def create_session(
        self,
        name: Optional[str] = None,
        model: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Session:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        if not name:
            name = f"Session {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M')}"
        
        if not model:
            model = self.config.default_model
        
        metadata = SessionMetadata(
            id=session_id,
            name=name,
            created_at=current_time,
            updated_at=current_time,
            model=model,
            tags=tags or [],
            description=description,
        )
        
        session = Session(metadata=metadata)
        self.current_session = session
        
        # Save session
        self._save_session(session)
        
        logger.info("Session created", session_id=session_id, name=name)
        return session
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a session by ID"""
        session_file = self.sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            logger.warning("Session not found", session_id=session_id)
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Parse metadata
            metadata = SessionMetadata(**data["metadata"])
            
            # Parse messages
            messages = []
            for msg_data in data.get("messages", []):
                message = SessionMessage(**msg_data)
                messages.append(message)
            
            session = Session(
                metadata=metadata,
                messages=messages,
                context_summary=data.get("context_summary"),
            )
            
            self.current_session = session
            logger.info("Session loaded", session_id=session_id, message_count=len(messages))
            return session
            
        except Exception as e:
            logger.error("Failed to load session", session_id=session_id, error=str(e))
            return None
    
    def save_current_session(self):
        """Save the current session"""
        if self.current_session:
            self._save_session(self.current_session)
    
    def _save_session(self, session: Session):
        """Save a session to disk"""
        session_file = self.sessions_dir / f"{session.metadata.id}.json"
        
        try:
            # Update metadata
            session.metadata.updated_at = time.time()
            session.metadata.total_messages = len(session.messages)
            session.metadata.total_tokens = sum(
                msg.tokens or 0 for msg in session.messages
            )
            session.metadata.total_cost = sum(
                msg.cost or 0.0 for msg in session.messages
            )
            
            # Prepare data for serialization
            data = {
                "metadata": asdict(session.metadata),
                "messages": [asdict(msg) for msg in session.messages],
                "context_summary": session.context_summary,
            }
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug("Session saved", session_id=session.metadata.id)
            
        except Exception as e:
            logger.error("Failed to save session", session_id=session.metadata.id, error=str(e))
    
    def list_sessions(self) -> List[SessionMetadata]:
        """List all available sessions"""
        sessions = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                metadata = SessionMetadata(**data["metadata"])
                sessions.append(metadata)
                
            except Exception as e:
                logger.warning("Failed to load session metadata", file=str(session_file), error=str(e))
        
        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session_file = self.sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return False
        
        try:
            session_file.unlink()
            
            # Clear current session if it's the one being deleted
            if self.current_session and self.current_session.metadata.id == session_id:
                self.current_session = None
            
            logger.info("Session deleted", session_id=session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete session", session_id=session_id, error=str(e))
            return False
    
    def add_message(
        self,
        role: str,
        content: str,
        model: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
    ) -> SessionMessage:
        """Add a message to the current session"""
        if not self.current_session:
            self.create_session()

        # Validate role to prevent API errors
        valid_roles = {"user", "assistant", "system", "tool"}
        if role not in valid_roles:
            logger.warning(f"Invalid role '{role}', converting to 'assistant'", role=role)
            role = "assistant"

        message_id = str(uuid.uuid4())
        tokens = self._count_tokens(content) if self.encoder else None
        
        message = SessionMessage(
            id=message_id,
            role=role,
            content=content,
            timestamp=time.time(),
            model=model,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tokens=tokens,
        )
        
        self.current_session.messages.append(message)
        
        # Auto-save after adding message
        self._save_session(self.current_session)
        
        logger.debug("Message added to session", role=role, tokens=tokens)
        return message
    
    def get_context_messages(
        self,
        max_tokens: Optional[int] = None,
        include_system: bool = True,
    ) -> List[Message]:
        """Get messages for API context with token limit management"""
        if not self.current_session:
            return []
        
        if not max_tokens:
            max_tokens = self.config.ui.max_context_length
        
        messages = []
        current_tokens = 0
        
        # Process messages in reverse order (most recent first)
        for session_msg in reversed(self.current_session.messages):
            # Skip system messages if not requested
            if not include_system and session_msg.role == "system":
                continue
            
            msg_tokens = session_msg.tokens or self._count_tokens(session_msg.content)
            
            # Check if adding this message would exceed token limit
            if current_tokens + msg_tokens > max_tokens and messages:
                break
            
            message = Message(
                role=session_msg.role,
                content=session_msg.content,
                tool_calls=session_msg.tool_calls,
                tool_call_id=session_msg.tool_call_id,
            )
            
            messages.insert(0, message)  # Insert at beginning to maintain order
            current_tokens += msg_tokens
        
        logger.debug("Context messages prepared", count=len(messages), tokens=current_tokens)
        return messages
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if not self.encoder:
            # Rough estimation: ~4 characters per token
            return len(text) // 4
        
        try:
            return len(self.encoder.encode(text))
        except Exception:
            return len(text) // 4
    
    def summarize_context(self, max_messages: int = 10) -> Optional[str]:
        """Create a summary of older messages to preserve context"""
        if not self.current_session or len(self.current_session.messages) <= max_messages:
            return None
        
        # Get older messages for summarization
        older_messages = self.current_session.messages[:-max_messages]
        
        if not older_messages:
            return None
        
        # Create a simple summary
        summary_parts = []
        for msg in older_messages:
            if msg.role == "user":
                summary_parts.append(f"User asked: {msg.content[:100]}...")
            elif msg.role == "assistant":
                summary_parts.append(f"Assistant responded: {msg.content[:100]}...")
        
        summary = "Previous conversation summary:\n" + "\n".join(summary_parts)
        
        # Update session with summary
        self.current_session.context_summary = summary
        
        # Remove older messages to save space
        self.current_session.messages = self.current_session.messages[-max_messages:]
        
        logger.info("Context summarized", older_messages=len(older_messages))
        return summary
    
    def search_sessions(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[SessionMetadata]:
        """Search sessions by name, description, or tags"""
        all_sessions = self.list_sessions()
        matching_sessions = []
        
        query_lower = query.lower()
        
        for session in all_sessions:
            score = 0
            
            # Check name
            if query_lower in session.name.lower():
                score += 3
            
            # Check description
            if query_lower in session.description.lower():
                score += 2
            
            # Check tags
            if tags:
                matching_tags = set(tags) & set(session.tags)
                score += len(matching_tags)
            
            if score > 0:
                matching_sessions.append((score, session))
        
        # Sort by score and return top results
        matching_sessions.sort(key=lambda x: x[0], reverse=True)
        return [session for _, session in matching_sessions[:limit]]
    
    def export_session(self, session_id: str, format: str = "json") -> Optional[str]:
        """Export session in specified format"""
        session = self.load_session(session_id)
        if not session:
            return None
        
        if format == "json":
            return json.dumps(asdict(session), indent=2, ensure_ascii=False)
        elif format == "markdown":
            return self._export_as_markdown(session)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_as_markdown(self, session: Session) -> str:
        """Export session as markdown"""
        lines = [
            f"# {session.metadata.name}",
            f"",
            f"**Created:** {datetime.fromtimestamp(session.metadata.created_at)}",
            f"**Model:** {session.metadata.model}",
            f"**Messages:** {session.metadata.total_messages}",
            f"**Tokens:** {session.metadata.total_tokens}",
            f"",
        ]
        
        if session.metadata.description:
            lines.extend([f"**Description:** {session.metadata.description}", ""])
        
        if session.metadata.tags:
            lines.extend([f"**Tags:** {', '.join(session.metadata.tags)}", ""])
        
        lines.append("## Conversation")
        lines.append("")
        
        for msg in session.messages:
            timestamp = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S")
            lines.append(f"### {msg.role.title()} ({timestamp})")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
        
        return "\n".join(lines)
