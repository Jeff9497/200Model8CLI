"""
Knowledge management tools for 200Model8CLI

Provides knowledge search, retrieval, and interactive learning capabilities.
"""

import asyncio
import json
import sqlite3
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import hashlib

import structlog

from .base import BaseTool, ToolResult, ToolCategory
from ..core.config import Config
from ..utils.security import SecurityValidator

logger = structlog.get_logger(__name__)


@dataclass
class KnowledgeEntry:
    """Knowledge entry data structure"""
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    created_at: str
    updated_at: str
    source: str
    metadata: Dict[str, Any]


class KnowledgeDatabase:
    """SQLite-based knowledge database"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize the knowledge database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON knowledge_entries(category)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tags ON knowledge_entries(tags)
            """)
            
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    id, title, content, category, tags, content=knowledge_entries
                )
            """)
            
            # Create triggers to keep FTS table in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert AFTER INSERT ON knowledge_entries
                BEGIN
                    INSERT INTO knowledge_fts(id, title, content, category, tags)
                    VALUES (new.id, new.title, new.content, new.category, new.tags);
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_update AFTER UPDATE ON knowledge_entries
                BEGIN
                    UPDATE knowledge_fts SET title=new.title, content=new.content, 
                           category=new.category, tags=new.tags WHERE id=new.id;
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_delete AFTER DELETE ON knowledge_entries
                BEGIN
                    DELETE FROM knowledge_fts WHERE id=old.id;
                END
            """)
    
    def add_entry(self, entry: KnowledgeEntry) -> bool:
        """Add a knowledge entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO knowledge_entries 
                    (id, title, content, category, tags, created_at, updated_at, source, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.id, entry.title, entry.content, entry.category,
                    json.dumps(entry.tags), entry.created_at, entry.updated_at,
                    entry.source, json.dumps(entry.metadata)
                ))
                return True
        except Exception as e:
            logger.error("Failed to add knowledge entry", error=str(e))
            return False
    
    def search_entries(self, query: str, category: Optional[str] = None, limit: int = 10) -> List[KnowledgeEntry]:
        """Search knowledge entries using FTS"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if category:
                    cursor = conn.execute("""
                        SELECT k.* FROM knowledge_entries k
                        JOIN knowledge_fts f ON k.id = f.id
                        WHERE knowledge_fts MATCH ? AND k.category = ?
                        ORDER BY rank LIMIT ?
                    """, (query, category, limit))
                else:
                    cursor = conn.execute("""
                        SELECT k.* FROM knowledge_entries k
                        JOIN knowledge_fts f ON k.id = f.id
                        WHERE knowledge_fts MATCH ?
                        ORDER BY rank LIMIT ?
                    """, (query, limit))
                
                entries = []
                for row in cursor.fetchall():
                    entry = KnowledgeEntry(
                        id=row[0], title=row[1], content=row[2], category=row[3],
                        tags=json.loads(row[4]), created_at=row[5], updated_at=row[6],
                        source=row[7], metadata=json.loads(row[8])
                    )
                    entries.append(entry)
                
                return entries
        except Exception as e:
            logger.error("Failed to search knowledge entries", error=str(e))
            return []
    
    def get_categories(self) -> List[str]:
        """Get all categories"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT DISTINCT category FROM knowledge_entries ORDER BY category")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error("Failed to get categories", error=str(e))
            return []


class KnowledgeSearchTool(BaseTool):
    """Tool for searching knowledge base"""
    
    name = "knowledge_search"
    description = "Search the knowledge base for information"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "category": {
                "type": "string",
                "description": "Category to search within (optional)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results",
                "default": 10
            }
        },
        "required": ["query"]
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.db = KnowledgeDatabase(config.config_dir / "knowledge.db")
    
    async def execute(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> ToolResult:
        try:
            entries = self.db.search_entries(query, category, limit)
            
            results = []
            for entry in entries:
                results.append({
                    "id": entry.id,
                    "title": entry.title,
                    "content": entry.content[:500] + "..." if len(entry.content) > 500 else entry.content,
                    "category": entry.category,
                    "tags": entry.tags,
                    "source": entry.source,
                    "created_at": entry.created_at
                })
            
            return ToolResult(
                success=True,
                result={
                    "query": query,
                    "category": category,
                    "results": results,
                    "total_found": len(results)
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Knowledge search failed: {str(e)}")


class AddKnowledgeTool(BaseTool):
    """Tool for adding knowledge to the knowledge base"""
    
    name = "add_knowledge"
    description = "Add new knowledge entry to the knowledge base"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Knowledge entry title"
            },
            "content": {
                "type": "string",
                "description": "Knowledge entry content"
            },
            "category": {
                "type": "string",
                "description": "Knowledge category"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for the knowledge entry"
            },
            "source": {
                "type": "string",
                "description": "Source of the knowledge",
                "default": "user_input"
            }
        },
        "required": ["title", "content", "category"]
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.db = KnowledgeDatabase(config.config_dir / "knowledge.db")
    
    async def execute(
        self,
        title: str,
        content: str,
        category: str,
        tags: Optional[List[str]] = None,
        source: str = "user_input"
    ) -> ToolResult:
        try:
            # Generate ID from title and content
            entry_id = hashlib.md5(f"{title}{content}".encode()).hexdigest()
            
            now = datetime.now().isoformat()
            
            entry = KnowledgeEntry(
                id=entry_id,
                title=title,
                content=content,
                category=category,
                tags=tags or [],
                created_at=now,
                updated_at=now,
                source=source,
                metadata={}
            )
            
            success = self.db.add_entry(entry)
            
            if success:
                return ToolResult(
                    success=True,
                    result={
                        "id": entry_id,
                        "title": title,
                        "category": category,
                        "tags": tags or [],
                        "message": "Knowledge entry added successfully"
                    }
                )
            else:
                return ToolResult(success=False, error="Failed to add knowledge entry")
            
        except Exception as e:
            return ToolResult(success=False, error=f"Add knowledge failed: {str(e)}")


class ListKnowledgeCategoriesTools(BaseTool):
    """Tool for listing knowledge categories"""
    
    name = "list_knowledge_categories"
    description = "List all knowledge categories"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.db = KnowledgeDatabase(config.config_dir / "knowledge.db")
    
    async def execute(self) -> ToolResult:
        try:
            categories = self.db.get_categories()
            
            return ToolResult(
                success=True,
                result={
                    "categories": categories,
                    "total_count": len(categories)
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"List categories failed: {str(e)}")


# Knowledge Tools registry
class KnowledgeTools:
    """Collection of knowledge management tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            KnowledgeSearchTool(config),
            AddKnowledgeTool(config),
            ListKnowledgeCategoriesTools(config),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all knowledge tools"""
        return self.tools
