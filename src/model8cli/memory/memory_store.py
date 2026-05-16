"""
Memory Store for 200Model8CLI

SQLite-backed persistent memory. Stores conversations, skills, lessons,
and a user model that builds up over time. Zero external dependencies
beyond stdlib sqlite3.
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import structlog

logger = structlog.get_logger(__name__)


class MemoryStore:
    """
    Persistent SQLite memory. One file, lives in ~/.200model8cli/memory.db
    Remembers everything across sessions.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_dir = Path.home() / ".200model8cli"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "memory.db"

        self.db_path = db_path
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._setup_tables()
        logger.info("Memory store initialized", path=str(self.db_path))

    def _setup_tables(self):
        """Create all tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                steps TEXT NOT NULL,
                use_count INTEGER DEFAULT 0,
                last_used REAL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT,
                context TEXT NOT NULL,
                fix TEXT NOT NULL,
                tool TEXT,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_model (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                run_at REAL NOT NULL,
                repeat_seconds INTEGER DEFAULT 0,
                action TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date TEXT NOT NULL,
                entry TEXT NOT NULL,
                category TEXT NOT NULL,
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_session
                ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_daily_log_date
                ON daily_log(log_date);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Conversations
    # ------------------------------------------------------------------ #

    def save_message(self, session_id: str, role: str, content: str):
        """Save a single conversation message."""
        self._conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?,?,?,?)",
            (session_id, role, content, time.time())
        )
        self._conn.commit()

    def get_recent_context(self, limit: int = 20) -> List[Dict[str, str]]:
        """
        Return the last N messages across all sessions as a list of
        {role, content} dicts — ready to inject into an API call.
        """
        rows = self._conn.execute(
            "SELECT role, content FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict]:
        """Full-text search across all conversation content."""
        rows = self._conn.execute(
            """SELECT session_id, role, content, timestamp
               FROM conversations
               WHERE content LIKE ?
               ORDER BY timestamp DESC LIMIT ?""",
            (f"%{query}%", limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Skills
    # ------------------------------------------------------------------ #

    def save_skill(self, name: str, description: str, steps: List[Dict]) -> bool:
        """Save or update a reusable skill."""
        try:
            self._conn.execute(
                """INSERT INTO skills (name, description, steps, created_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(name) DO UPDATE SET
                       description=excluded.description,
                       steps=excluded.steps""",
                (name, description, json.dumps(steps), time.time())
            )
            self._conn.commit()
            self._log_today(f"Saved skill: {name}", "skill")
            return True
        except Exception as e:
            logger.error("Failed to save skill", error=str(e))
            return False

    def get_skill(self, name: str) -> Optional[Dict]:
        """Load a skill by name and increment its use count."""
        row = self._conn.execute(
            "SELECT * FROM skills WHERE name=?", (name,)
        ).fetchone()
        if row:
            self._conn.execute(
                "UPDATE skills SET use_count=use_count+1, last_used=? WHERE name=?",
                (time.time(), name)
            )
            self._conn.commit()
            return {**dict(row), "steps": json.loads(row["steps"])}
        return None

    def find_skill(self, query: str) -> Optional[Dict]:
        """Find the most relevant skill for a query (simple keyword match)."""
        rows = self._conn.execute(
            """SELECT * FROM skills
               WHERE name LIKE ? OR description LIKE ?
               ORDER BY use_count DESC LIMIT 1""",
            (f"%{query}%", f"%{query}%")
        ).fetchone()
        if rows:
            return {**dict(rows), "steps": json.loads(rows["steps"])}
        return None

    def list_skills(self) -> List[Dict]:
        """List all saved skills."""
        rows = self._conn.execute(
            "SELECT name, description, use_count, created_at FROM skills ORDER BY use_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Lessons
    # ------------------------------------------------------------------ #

    def save_lesson(self, context: str, fix: str, error_type: str = "", tool: str = ""):
        """Log something the agent learned."""
        self._conn.execute(
            """INSERT INTO lessons (error_type, context, fix, tool, timestamp)
               VALUES (?,?,?,?,?)""",
            (error_type, context, fix, tool, time.time())
        )
        self._conn.commit()
        self._log_today(f"Lesson: {context[:80]}", "lesson")

    def get_recent_lessons(self, limit: int = 10) -> List[Dict]:
        """Get the most recent lessons."""
        rows = self._conn.execute(
            "SELECT * FROM lessons ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_lessons_for_tool(self, tool: str) -> List[Dict]:
        """Get all lessons associated with a specific tool."""
        rows = self._conn.execute(
            "SELECT * FROM lessons WHERE tool=? ORDER BY timestamp DESC", (tool,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # User model
    # ------------------------------------------------------------------ #

    def set_user_fact(self, key: str, value: Any):
        """Store something the agent learned about the user."""
        self._conn.execute(
            """INSERT INTO user_model (key, value, updated_at) VALUES (?,?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, json.dumps(value), time.time())
        )
        self._conn.commit()

    def get_user_fact(self, key: str) -> Optional[Any]:
        """Retrieve a stored user fact."""
        row = self._conn.execute(
            "SELECT value FROM user_model WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row["value"]) if row else None

    def get_user_model_summary(self) -> Dict[str, Any]:
        """Return the full user model as a dict."""
        rows = self._conn.execute("SELECT key, value FROM user_model").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # ------------------------------------------------------------------ #
    # Scheduled tasks
    # ------------------------------------------------------------------ #

    def schedule_task(self, label: str, run_at: float, action: str, repeat_seconds: int = 0):
        """Schedule a future task."""
        self._conn.execute(
            """INSERT INTO scheduled_tasks (label, run_at, repeat_seconds, action, created_at)
               VALUES (?,?,?,?,?)""",
            (label, run_at, repeat_seconds, action, time.time())
        )
        self._conn.commit()

    def get_due_tasks(self) -> List[Dict]:
        """Return all tasks that are due now and not done."""
        now = time.time()
        rows = self._conn.execute(
            "SELECT * FROM scheduled_tasks WHERE run_at<=? AND done=0", (now,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_task_done(self, task_id: int, reschedule_seconds: int = 0):
        """Mark a task done, optionally rescheduling it."""
        if reschedule_seconds > 0:
            next_run = time.time() + reschedule_seconds
            self._conn.execute(
                "UPDATE scheduled_tasks SET run_at=? WHERE id=?", (next_run, task_id)
            )
        else:
            self._conn.execute(
                "UPDATE scheduled_tasks SET done=1 WHERE id=?", (task_id,)
            )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Daily log
    # ------------------------------------------------------------------ #

    def _log_today(self, entry: str, category: str):
        """Internal: append to today's log."""
        today = date.today().isoformat()
        self._conn.execute(
            "INSERT INTO daily_log (log_date, entry, category, timestamp) VALUES (?,?,?,?)",
            (today, entry, category, time.time())
        )
        self._conn.commit()

    def get_daily_summary(self, log_date: Optional[str] = None) -> Dict:
        """
        Build today's (or a past date's) learning summary.
        Returns counts and entries per category.
        """
        target = log_date or date.today().isoformat()
        rows = self._conn.execute(
            "SELECT category, entry, timestamp FROM daily_log WHERE log_date=? ORDER BY timestamp",
            (target,)
        ).fetchall()

        summary: Dict[str, List[str]] = {}
        for r in rows:
            summary.setdefault(r["category"], []).append(r["entry"])

        return {
            "date": target,
            "total_entries": len(rows),
            "by_category": summary
        }

    def close(self):
        self._conn.close()
