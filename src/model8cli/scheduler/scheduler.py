"""
Scheduler for 200Model8CLI

Two jobs only:
1. User-commanded time tasks ("suggest a song in 3 hours")
2. End-of-day learning summary (sent once daily via Telegram)

Uses APScheduler. Lightweight, no daemon process required when running
in CLI mode — the scheduler runs in the same process.
"""

import asyncio
import time
import re
from datetime import datetime, timedelta
from typing import Callable, Optional, Awaitable
import structlog

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from ..memory.memory_store import MemoryStore

logger = structlog.get_logger(__name__)


class AgentScheduler:
    """
    Manages timed tasks commanded by the user and the daily summary job.
    """

    def __init__(self, memory: MemoryStore, notify_callback: Callable[[str], Awaitable[None]]):
        """
        notify_callback: async function that sends a message to the user.
        In CLI mode this prints to terminal. In bot mode it sends a Telegram message.
        """
        self.memory = memory
        self.notify = notify_callback
        self.scheduler = AsyncIOScheduler()
        self._setup_daily_summary()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # ------------------------------------------------------------------ #
    # Daily summary (always on)
    # ------------------------------------------------------------------ #

    def _setup_daily_summary(self):
        """Send an end-of-day summary every day at 21:00 local time."""
        self.scheduler.add_job(
            self._send_daily_summary,
            CronTrigger(hour=21, minute=0),
            id="daily_summary",
            replace_existing=True
        )
        logger.info("Daily summary scheduled for 21:00")

    async def _send_daily_summary(self):
        """Build and send the daily learning summary."""
        summary = self.memory.get_daily_summary()
        if summary["total_entries"] == 0:
            await self.notify("End of day — nothing new logged today.")
            return

        lines = [f"End of day summary ({summary['date']}):\n"]

        by_cat = summary["by_category"]

        if "skill" in by_cat:
            lines.append(f"Skills saved ({len(by_cat['skill'])}):")
            for s in by_cat["skill"]:
                lines.append(f"  - {s}")

        if "lesson" in by_cat:
            lines.append(f"\nLessons learned ({len(by_cat['lesson'])}):")
            for l in by_cat["lesson"]:
                lines.append(f"  - {l}")

        if "error" in by_cat:
            lines.append(f"\nErrors encountered ({len(by_cat['error'])}):")
            for e in by_cat["error"]:
                lines.append(f"  - {e}")

        await self.notify("\n".join(lines))

    # ------------------------------------------------------------------ #
    # User-commanded tasks
    # ------------------------------------------------------------------ #

    def parse_and_schedule(self, instruction: str) -> Optional[str]:
        """
        Parse a natural language time instruction and schedule it.
        Examples:
          "suggest a song in 3 hours"
          "remind me to check the EA logs in 2 hours"
          "in 30 minutes tell me to take a break"

        Returns a confirmation string or None if unparseable.
        """
        delta = self._parse_time_delta(instruction)
        if delta is None:
            return None

        run_at = datetime.now() + delta
        label = self._extract_label(instruction)

        self.scheduler.add_job(
            self._fire_user_task,
            DateTrigger(run_date=run_at),
            args=[label],
            id=f"user_task_{int(time.time())}",
            replace_existing=False
        )

        # Persist to memory too (survives restarts)
        self.memory.schedule_task(
            label=label,
            run_at=run_at.timestamp(),
            action=label
        )

        human_time = run_at.strftime("%H:%M")
        logger.info("User task scheduled", label=label, run_at=human_time)
        return f"Scheduled: '{label}' at {human_time}"

    async def _fire_user_task(self, label: str):
        """Called when a user-scheduled task fires."""
        await self.notify(f"Reminder: {label}")

    # ------------------------------------------------------------------ #
    # Restore persisted tasks on startup
    # ------------------------------------------------------------------ #

    def restore_pending_tasks(self):
        """
        On startup, re-register any tasks that were scheduled in a previous
        session and haven't fired yet.
        """
        due = self.memory.get_due_tasks()
        now = time.time()

        tasks = self.memory.get_due_tasks()
        # get ALL tasks (not just due ones) — fetch directly
        rows = self.memory._conn.execute(
            "SELECT * FROM scheduled_tasks WHERE done=0"
        ).fetchall()

        for row in rows:
            run_at_ts = row["run_at"]
            if run_at_ts <= now:
                # Already overdue — fire immediately
                asyncio.ensure_future(self._fire_user_task(row["action"]))
                self.memory.mark_task_done(row["id"])
            else:
                run_at = datetime.fromtimestamp(run_at_ts)
                self.scheduler.add_job(
                    self._fire_user_task,
                    DateTrigger(run_date=run_at),
                    args=[row["action"]],
                    id=f"restored_{row['id']}",
                    replace_existing=True
                )

    # ------------------------------------------------------------------ #
    # Time parsing helpers
    # ------------------------------------------------------------------ #

    def _parse_time_delta(self, text: str) -> Optional[timedelta]:
        """Extract a time delta from natural language."""
        text = text.lower()

        patterns = [
            (r'(\d+)\s*hour', lambda m: timedelta(hours=int(m.group(1)))),
            (r'(\d+)\s*hr', lambda m: timedelta(hours=int(m.group(1)))),
            (r'(\d+)\s*minute', lambda m: timedelta(minutes=int(m.group(1)))),
            (r'(\d+)\s*min', lambda m: timedelta(minutes=int(m.group(1)))),
            (r'(\d+)\s*second', lambda m: timedelta(seconds=int(m.group(1)))),
            (r'(\d+)\s*sec', lambda m: timedelta(seconds=int(m.group(1)))),
        ]

        for pattern, builder in patterns:
            m = re.search(pattern, text)
            if m:
                return builder(m)

        return None

    def _extract_label(self, instruction: str) -> str:
        """
        Extract the action label from the instruction.
        "suggest a song in 3 hours" → "suggest a song"
        "in 2 hours remind me to check logs" → "remind me to check logs"
        """
        # Remove time references
        cleaned = re.sub(
            r'\b(in\s+)?\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b',
            '', instruction, flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(" ,.")
        return cleaned or instruction
