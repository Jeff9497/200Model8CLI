"""
Telegram Bot for 200Model8CLI

Talk to the agent from anywhere. Approve or reject code patches.
Receive the daily learning summary.

Setup:
  1. Create a bot via @BotFather on Telegram → get token
  2. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
  3. Run: 200model8cli bot --start
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Dict, List
import structlog

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from ..core.config import Config
from ..core.api import OpenRouterClient, Message
from ..memory.memory_store import MemoryStore
from ..memory.skill_engine import SkillEngine
from ..memory.self_improvement import SelfImprovementLoop
from ..memory.reflection import ReflectionEngine
from ..scheduler.scheduler import AgentScheduler
from ..agent.core import AdvancedAgent

logger = structlog.get_logger(__name__)


class AgentBot:
    """
    Telegram bot that exposes the full agent via chat.
    Pending patches are stored in memory until approved/rejected.
    """

    def __init__(self, config: Config):
        self.config = config
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.allowed_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN not set. Add it to your .env file.\n"
                "Get one from @BotFather on Telegram."
            )

        # Core components
        self.memory = MemoryStore()
        self.api_client = OpenRouterClient(config)
        self.skill_engine = SkillEngine(self.memory)
        self.improvement_loop = SelfImprovementLoop(config, self.api_client, self.memory)
        self.reflection_engine = ReflectionEngine(config, self.api_client, self.memory)
        self.agent = AdvancedAgent(config)

        # Pending patches waiting for approval
        self._pending_patches: Dict[str, Dict] = {}

        # Scheduler wired to send_message
        self.scheduler = AgentScheduler(
            memory=self.memory,
            notify_callback=self._send_to_user
        )

    # ------------------------------------------------------------------ #
    # Start
    # ------------------------------------------------------------------ #

    def run(self):
        """Start the bot. Blocks until interrupted."""
        app = Application.builder().token(self.token).build()

        # Commands
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("skills", self._cmd_skills))
        app.add_handler(CommandHandler("memory", self._cmd_memory))
        app.add_handler(CommandHandler("improve", self._cmd_improve))
        app.add_handler(CommandHandler("summary", self._cmd_summary))
        app.add_handler(CommandHandler("help", self._cmd_help))

        # Inline keyboard callbacks (approve/reject patches)
        app.add_handler(CallbackQueryHandler(self._handle_callback))

        # All other messages → agent
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Start scheduler
        self.scheduler.start()
        self.scheduler.restore_pending_tasks()

        logger.info("Telegram bot started")
        print(f"\nBot is running. Open Telegram and message your bot.")
        print(f"Chat ID restriction: {'yes' if self.allowed_chat_id else 'no (open to anyone)'}\n")

        app.run_polling(drop_pending_updates=True)

    # ------------------------------------------------------------------ #
    # Auth guard
    # ------------------------------------------------------------------ #

    def _is_allowed(self, update: Update) -> bool:
        if not self.allowed_chat_id:
            return True
        return str(update.effective_chat.id) == str(self.allowed_chat_id)

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return
        user_model = self.memory.get_user_model_summary()
        name = user_model.get("name", update.effective_user.first_name)
        await update.message.reply_text(
            f"Agent online, {name}.\n\n"
            "Just talk to me naturally. Commands:\n"
            "/skills — list saved skills\n"
            "/memory — show what I remember about you\n"
            "/improve — run self-improvement analysis\n"
            "/summary — today's learning summary\n"
            "/help — this message"
        )

    async def _cmd_skills(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return
        skills = self.skill_engine.list_skills()
        if not skills:
            await update.message.reply_text("No skills saved yet.")
            return
        lines = ["Saved skills:\n"]
        for s in skills:
            lines.append(f"• {s['name']} (used {s['use_count']}x)\n  {s['description'][:60]}")
        await update.message.reply_text("\n".join(lines))

    async def _cmd_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return
        user_model = self.memory.get_user_model_summary()
        lessons = self.memory.get_recent_lessons(5)
        lines = ["What I remember:\n"]
        if user_model:
            for k, v in user_model.items():
                lines.append(f"• {k}: {v}")
        if lessons:
            lines.append("\nRecent lessons:")
            for l in lessons:
                lines.append(f"• {l['context'][:60]} → {l['fix'][:60]}")
        if not user_model and not lessons:
            lines.append("Nothing stored yet — memory builds up as we work together.")
        await update.message.reply_text("\n".join(lines))

    async def _cmd_improve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return
        await update.message.reply_text("Running self-improvement analysis...")
        patches = await self.improvement_loop.run_analysis()
        if not patches:
            await update.message.reply_text("No issues found in error logs.")
            return
        for patch in patches:
            await self._send_patch_for_approval(update, patch)

    async def _cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return
        summary = self.memory.get_daily_summary()
        if summary["total_entries"] == 0:
            await update.message.reply_text("Nothing logged today yet.")
            return
        await self._send_daily_summary_message(update.effective_chat.id)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._cmd_start(update, context)

    # ------------------------------------------------------------------ #
    # Message handler — main agent loop
    # ------------------------------------------------------------------ #

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        user_input = update.message.text
        chat_id = update.effective_chat.id

        # Save user name if we don't know it
        if not self.memory.get_user_fact("name"):
            self.memory.set_user_fact("name", update.effective_user.first_name)

        # Save message to memory
        self.memory.save_message(
            session_id=str(chat_id),
            role="user",
            content=user_input
        )

        # Check if this is a time-based instruction
        scheduled = self.scheduler.parse_and_schedule(user_input)
        if scheduled:
            await update.message.reply_text(scheduled)
            return

        # Check for a matching skill first
        skill = self.skill_engine.find_matching_skill(user_input)
        if skill:
            await update.message.reply_text(
                f"I have a skill for this: {skill['name']}\nExecuting..."
            )

        # Send typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Get conversation context from memory
        recent = self.memory.get_recent_context(limit=15)

        try:
            # Build messages with memory context
            messages = []
            system = self._build_system_prompt()
            messages.append(Message(role="user", content=system))

            for msg in recent[:-1]:  # all but the last (which is current input)
                messages.append(Message(role=msg["role"], content=msg["content"]))

            messages.append(Message(role="user", content=user_input))

            # Run agent task
            result = await self.agent.execute_task(user_input)

            # Build response text
            if result.get("success"):
                exec_results = result.get("result", {}).get("execution_results", [])
                successful = [r for r in exec_results if r.get("success")]
                failed = [r for r in exec_results if not r.get("success")]

                response_parts = []
                for r in successful:
                    if r.get("result"):
                        response_parts.append(str(r["result"])[:400])

                response_text = "\n".join(response_parts) if response_parts else "Done."

                # Reflection
                reflection = await self.reflection_engine.reflect(
                    task_description=user_input,
                    steps=exec_results,
                    outcome="success" if successful else "partial"
                )

                # Capture skill if worthy
                if reflection.get("could_be_skill") and len(successful) >= 2:
                    skill_name = self.skill_engine.capture_skill(
                        task_description=user_input,
                        steps=exec_results,
                        outcome_summary=response_text[:80]
                    )
                    if skill_name:
                        response_text += f"\n\n(Saved as skill: {skill_name})"

            else:
                response_text = f"I ran into an issue: {result.get('error', 'unknown error')}"

            # Save response to memory
            self.memory.save_message(
                session_id=str(chat_id),
                role="assistant",
                content=response_text
            )

            await update.message.reply_text(response_text[:4000])

        except Exception as e:
            logger.error("Bot message handler failed", error=str(e))
            await update.message.reply_text(f"Error: {str(e)[:200]}")

    # ------------------------------------------------------------------ #
    # Patch approval flow
    # ------------------------------------------------------------------ #

    async def _send_patch_for_approval(self, update: Update, patch: Dict):
        """Send a patch diff with approve/reject buttons."""
        patch_id = f"patch_{int(asyncio.get_event_loop().time())}"
        self._pending_patches[patch_id] = patch

        diff_preview = patch["diff"][:800] if patch["diff"] else "No diff available"

        text = (
            f"Fix found in {patch['file']}\n\n"
            f"Error: {patch['error_type']}\n"
            f"Summary: {patch['summary']}\n\n"
            f"Diff:\n```\n{diff_preview}\n```\n\n"
            f"Explanation: {patch['explanation']}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{patch_id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{patch_id}"),
            ]
        ])

        await update.message.reply_text(
            text[:4000],
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle approve/reject button presses."""
        query = update.callback_query
        await query.answer()

        action, patch_id = query.data.split(":", 1)
        patch = self._pending_patches.get(patch_id)

        if not patch:
            await query.edit_message_text("Patch expired or already handled.")
            return

        if action == "approve":
            await query.edit_message_text("Applying patch...")
            success, message = await self.improvement_loop.apply_patch(patch)
            result_text = f"Applied: {message}" if success else f"Failed: {message}"
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=result_text
            )
        else:
            await query.edit_message_text("Patch rejected.")

        # Remove from pending
        self._pending_patches.pop(patch_id, None)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_system_prompt(self) -> str:
        user_model = self.memory.get_user_model_summary()
        skills = self.skill_engine.list_skills()
        lessons = self.memory.get_recent_lessons(5)

        parts = [
            "You are 200Model8CLI, a personal AI agent with persistent memory.",
            f"User profile: {json.dumps(user_model)}" if user_model else "",
            f"Available skills: {[s['name'] for s in skills]}" if skills else "",
            f"Recent lessons: {[l['fix'] for l in lessons]}" if lessons else "",
        ]
        return "\n".join(p for p in parts if p)

    async def _send_to_user(self, message: str):
        """Send a proactive message to the user (used by scheduler)."""
        if not self.allowed_chat_id:
            logger.warning("TELEGRAM_CHAT_ID not set — cannot send proactive message")
            return
        try:
            from telegram import Bot
            bot = Bot(token=self.token)
            await bot.send_message(chat_id=self.allowed_chat_id, text=message)
        except Exception as e:
            logger.error("Failed to send proactive message", error=str(e))

    async def _send_daily_summary_message(self, chat_id: int):
        """Build and send daily summary to a specific chat."""
        summary = self.memory.get_daily_summary()
        by_cat = summary["by_category"]
        lines = [f"End of day summary ({summary['date']}):\n"]

        if "skill" in by_cat:
            lines.append(f"Skills saved ({len(by_cat['skill'])}):")
            for s in by_cat["skill"]:
                lines.append(f"  - {s}")
        if "lesson" in by_cat:
            lines.append(f"\nLessons learned ({len(by_cat['lesson'])}):")
            for l in by_cat["lesson"]:
                lines.append(f"  - {l}")

        from telegram import Bot
        bot = Bot(token=self.token)
        await bot.send_message(chat_id=chat_id, text="\n".join(lines))


def start_bot(config: Config):
    """Entry point called from CLI."""
    bot = AgentBot(config)
    bot.run()
