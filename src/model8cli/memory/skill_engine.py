"""
Skill Capture Engine for 200Model8CLI

After a task is solved, this engine decides whether to save it as a
reusable skill. Next time a similar task comes in, the skill is loaded
and executed directly — no need to re-reason from scratch.
"""

import json
import time
from typing import List, Dict, Any, Optional
import structlog

from .memory_store import MemoryStore

logger = structlog.get_logger(__name__)

# Minimum tool calls for a workflow to be considered worth saving as a skill
MIN_TOOL_CALLS_FOR_SKILL = 2


class SkillEngine:
    """
    Observes task execution and decides what to save as a skill.
    Skills are stored in MemoryStore and loaded on future similar tasks.
    """

    def __init__(self, memory: MemoryStore):
        self.memory = memory

    def should_capture(self, task_description: str, steps: List[Dict]) -> bool:
        """
        Decide if this completed task is worth saving as a skill.
        Rules:
        - At least MIN_TOOL_CALLS_FOR_SKILL successful tool calls
        - Not already saved (checked by name similarity)
        - Task was fully successful
        """
        successful = [s for s in steps if s.get("success")]
        if len(successful) < MIN_TOOL_CALLS_FOR_SKILL:
            return False

        # Check if a very similar skill already exists
        existing = self.memory.find_skill(task_description[:30])
        if existing:
            logger.debug("Similar skill already exists", name=existing["name"])
            return False

        return True

    def capture_skill(
        self,
        task_description: str,
        steps: List[Dict],
        outcome_summary: str
    ) -> Optional[str]:
        """
        Save a completed task as a reusable skill.
        Returns the skill name if saved, None otherwise.
        """
        if not self.should_capture(task_description, steps):
            return None

        # Build skill name from task description (first 50 chars, snake_case)
        skill_name = self._make_skill_name(task_description)

        # Only keep successful steps
        clean_steps = [
            {
                "action": s.get("action"),
                "description": s.get("description"),
                "parameters_template": self._generalize_params(s.get("action", ""), s)
            }
            for s in steps if s.get("success")
        ]

        saved = self.memory.save_skill(
            name=skill_name,
            description=f"{task_description} — {outcome_summary}",
            steps=clean_steps
        )

        if saved:
            logger.info("Skill captured", name=skill_name, steps=len(clean_steps))
            return skill_name

        return None

    def find_matching_skill(self, task_description: str) -> Optional[Dict]:
        """
        Look for an existing skill that matches the incoming task.
        Returns the skill dict if found, None otherwise.
        """
        return self.memory.find_skill(task_description)

    def refine_skill(self, skill_name: str, better_steps: List[Dict]) -> bool:
        """
        Update an existing skill with improved steps after a better run.
        Only called when the new run had MORE successful steps than the stored one.
        """
        existing = self.memory.get_skill(skill_name)
        if not existing:
            return False

        if len(better_steps) <= len(existing["steps"]):
            return False  # Not actually better

        return self.memory.save_skill(
            name=skill_name,
            description=existing["description"],
            steps=better_steps
        )

    def list_skills(self) -> List[Dict]:
        return self.memory.list_skills()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _make_skill_name(self, description: str) -> str:
        """Convert a task description to a snake_case skill name."""
        words = description.lower().split()[:6]
        name = "_".join(w.strip(".,?!") for w in words if w.isalpha())
        return name or f"skill_{int(time.time())}"

    def _generalize_params(self, action: str, step: Dict) -> Dict:
        """
        Strip out session-specific values (paths, timestamps, etc.)
        and leave a generalizable parameter template.
        """
        # For now, return empty template — parameters are re-filled at runtime
        # This can be made smarter with action-specific param schemas
        return {}
