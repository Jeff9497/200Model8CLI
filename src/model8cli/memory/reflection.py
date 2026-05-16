"""
Reflection Engine for 200Model8CLI

After every task, the agent reflects:
- Did it succeed?
- Were there unnecessary steps?
- What would it do differently?

Results are logged as lessons and used to refine skills.
"""

import json
import time
from typing import Dict, List, Optional
import structlog

from ..core.api import OpenRouterClient, Message
from ..core.config import Config
from ..memory.memory_store import MemoryStore

logger = structlog.get_logger(__name__)


class ReflectionEngine:
    """
    Lightweight post-task reflection. Runs after every task execution.
    Uses the model to score and narrate what happened, then logs it.
    """

    def __init__(self, config: Config, api_client: OpenRouterClient, memory: MemoryStore):
        self.config = config
        self.api_client = api_client
        self.memory = memory

    async def reflect(
        self,
        task_description: str,
        steps: List[Dict],
        outcome: str
    ) -> Dict:
        """
        Reflect on a completed task. Returns a reflection dict with:
        - score (0-10)
        - what_worked
        - what_failed
        - lesson (saved to memory if meaningful)
        """
        successful = [s for s in steps if s.get("success")]
        failed = [s for s in steps if not s.get("success")]

        prompt = f"""You are an AI agent reflecting on a task you just completed.

TASK: {task_description}
OUTCOME: {outcome}
SUCCESSFUL STEPS ({len(successful)}): {json.dumps([s.get('action') for s in successful])}
FAILED STEPS ({len(failed)}): {json.dumps([s.get('action') for s in failed])}

Reflect briefly. Return ONLY a JSON object:
{{
  "score": <0-10>,
  "what_worked": "one sentence",
  "what_failed": "one sentence or empty string",
  "lesson": "one actionable lesson or empty string",
  "could_be_skill": <true/false>
}}"""

        try:
            response = await self.api_client.chat_completion(
                messages=[Message(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=300
            )
            raw = response.choices[0]["message"]["content"]
            clean = raw.replace("```json", "").replace("```", "").strip()
            reflection = json.loads(clean)

            # Save lesson if meaningful
            lesson = reflection.get("lesson", "").strip()
            if lesson and reflection.get("score", 10) < 8:
                self.memory.save_lesson(
                    context=task_description,
                    fix=lesson,
                    error_type="performance",
                    tool=failed[0].get("action", "") if failed else ""
                )
                logger.info("Lesson saved from reflection", lesson=lesson[:80])

            logger.info(
                "Reflection complete",
                task=task_description[:60],
                score=reflection.get("score"),
                could_be_skill=reflection.get("could_be_skill")
            )

            return reflection

        except Exception as e:
            logger.error("Reflection failed", error=str(e))
            return {
                "score": 5,
                "what_worked": "Task attempted",
                "what_failed": str(e),
                "lesson": "",
                "could_be_skill": False
            }
