"""
Self-Aware Agent for 200Model8CLI

The upgraded agent: persistent memory, skill capture, self-improvement loop,
reflection after every task, and user-commanded scheduling.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

import structlog
from rich.console import Console
from rich.panel import Panel

from ..core.config import Config
from ..core.api import OpenRouterClient, Message
from ..tools.base import ToolRegistry
from ..tools.file_ops import FileOperations
from ..tools.git_tools import GitTools
from ..tools.github_tools import GitHubTools
from ..tools.web_tools import WebTools
from ..tools.knowledge_tools import KnowledgeTools
from ..memory.memory_store import MemoryStore
from ..memory.skill_engine import SkillEngine
from ..memory.self_improvement import SelfImprovementLoop
from ..memory.reflection import ReflectionEngine
from ..scheduler.scheduler import AgentScheduler

logger = structlog.get_logger(__name__)
console = Console()


class SelfAwareAgent:
    """
    A personal AI agent that:
    - Remembers every session (SQLite)
    - Saves proven workflows as reusable skills
    - Reflects after every task and logs lessons
    - Analyses its own error logs and proposes code patches
    - Handles time-based instructions from the user
    - Sends an end-of-day learning summary
    """

    def __init__(self, config: Config, api_client: OpenRouterClient, tool_registry: ToolRegistry):
        self.config = config
        self.api_client = api_client
        self.tool_registry = tool_registry
        self.project_root = Path(__file__).parent.parent.parent.parent

        # --- Memory stack ---
        self.memory = MemoryStore()
        self.skill_engine = SkillEngine(self.memory)
        self.improvement_loop = SelfImprovementLoop(config, api_client, self.memory)
        self.reflection_engine = ReflectionEngine(config, api_client, self.memory)

        # --- Scheduler ---
        self.scheduler = AgentScheduler(
            memory=self.memory,
            notify_callback=self._cli_notify
        )
        self.scheduler.start()
        self.scheduler.restore_pending_tasks()

        import time
        self.session_id = f"session_{int(time.time())}"

    async def _cli_notify(self, message: str):
        console.print(Panel(message, title="Agent", border_style="cyan"))

    async def process(self, user_input: str) -> str:
        self.memory.save_message(self.session_id, "user", user_input)

        # Time-based instruction?
        scheduled = self.scheduler.parse_and_schedule(user_input)
        if scheduled:
            self.memory.save_message(self.session_id, "assistant", scheduled)
            return scheduled

        # Matching skill?
        skill = self.skill_engine.find_matching_skill(user_input)
        if skill:
            console.print(f"[cyan]Using saved skill: {skill['name']}[/cyan]")

        system_prompt = self._build_system_prompt()
        recent = self.memory.get_recent_context(limit=15)
        messages = [Message(role="user", content=system_prompt)]
        for msg in recent[:-1]:
            messages.append(Message(role=msg["role"], content=msg["content"]))
        messages.append(Message(role="user", content=user_input))

        tools = self._prepare_tools()

        try:
            response = await self.api_client.chat_completion(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000
            )

            if not response.choices:
                return "No response from model."

            message = response.choices[0].get("message", {})

            if message.get("tool_calls"):
                result_text, steps = await self._execute_tool_calls(message["tool_calls"], messages)
            else:
                result_text = message.get("content", "")
                steps = []

            if steps:
                reflection = await self.reflection_engine.reflect(
                    task_description=user_input,
                    steps=steps,
                    outcome=result_text[:200]
                )
                if reflection.get("could_be_skill") and len(steps) >= 2:
                    skill_name = self.skill_engine.capture_skill(
                        task_description=user_input,
                        steps=steps,
                        outcome_summary=result_text[:80]
                    )
                    if skill_name:
                        result_text += f"\n\n(Saved as skill: {skill_name})"

            self.memory.save_message(self.session_id, "assistant", result_text)
            return result_text

        except Exception as e:
            logger.error("Agent processing failed", error=str(e))
            return f"Error: {str(e)}"

    async def run_self_improvement(self) -> List[Dict]:
        console.print("[yellow]Analysing error logs...[/yellow]")
        return await self.improvement_loop.run_analysis()

    async def apply_patch_interactively(self, patch: Dict) -> bool:
        console.print(Panel(
            f"[bold]File:[/bold] {patch['file']}\n"
            f"[bold]Summary:[/bold] {patch['summary']}\n\n"
            f"[bold]Diff:[/bold]\n{patch['diff'][:1000]}\n\n"
            f"[bold]Explanation:[/bold] {patch['explanation']}",
            title="Proposed Fix",
            border_style="yellow"
        ))
        answer = console.input("[bold]Apply? (yes/no):[/bold] ").strip().lower()
        if answer in ("yes", "y"):
            success, msg = await self.improvement_loop.apply_patch(patch)
            console.print(f"[{'green' if success else 'red'}]{msg}[/{'green' if success else 'red'}]")
            return success
        console.print("[yellow]Rejected.[/yellow]")
        return False

    async def _execute_tool_calls(self, tool_calls: List[Dict], messages: List[Message]):
        steps = []
        console.print("[blue]Executing tools...[/blue]")

        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except Exception:
                args = {}

            if tool_name in self.tool_registry.tools:
                tool = self.tool_registry.tools[tool_name]
                console.print(f"[cyan]  {tool_name}[/cyan]")
                try:
                    result = await tool.execute(**args)
                    steps.append({
                        "action": tool_name,
                        "description": tool.description,
                        "success": result.success,
                        "result": str(result.result)[:300] if result.success else None,
                        "error": result.error if not result.success else None
                    })
                    console.print(f"[{'green' if result.success else 'red'}]  {'done' if result.success else result.error}[/{'green' if result.success else 'red'}]")
                except Exception as e:
                    steps.append({"action": tool_name, "success": False, "error": str(e)})
            else:
                steps.append({"action": tool_name, "success": False, "error": "Tool not found"})

        tool_summary = "\n".join(
            f"{'OK' if s['success'] else 'FAIL'} {s['action']}: {s.get('result') or s.get('error', '')}"
            for s in steps
        )
        messages.append(Message(role="assistant", content=f"Tool results:\n{tool_summary}"))
        messages.append(Message(role="user", content="Summarise what was accomplished."))

        try:
            final = await self.api_client.chat_completion(
                messages=messages, temperature=0.3, max_tokens=600
            )
            summary = final.choices[0].get("message", {}).get("content", tool_summary)
        except Exception:
            summary = tool_summary

        return summary, steps

    def _build_system_prompt(self) -> str:
        user_model = self.memory.get_user_model_summary()
        skills = self.skill_engine.list_skills()
        lessons = self.memory.get_recent_lessons(5)
        parts = [
            "You are 200Model8CLI, a self-aware personal AI agent.",
            "You have persistent memory, reusable skills, and can improve your own code.",
            "Always be concise and action-oriented.",
        ]
        if user_model:
            parts.append(f"User profile: {json.dumps(user_model)}")
        if skills:
            parts.append(f"Available skills: {[s['name'] for s in skills]}")
        if lessons:
            parts.append(f"Recent lessons: {[l['fix'] for l in lessons]}")
        return "\n".join(parts)

    def _prepare_tools(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for name, tool in self.tool_registry.tools.items()
        ]

    def display_status(self):
        skills = self.skill_engine.list_skills()
        lessons = self.memory.get_recent_lessons(3)
        user_model = self.memory.get_user_model_summary()
        console.print(Panel(
            f"[bold cyan]200Model8CLI — Self-Aware Agent[/bold cyan]\n\n"
            f"[yellow]Memory:[/yellow] {self.memory.db_path}\n"
            f"[yellow]Skills saved:[/yellow] {len(skills)}\n"
            f"[yellow]Recent lessons:[/yellow] {len(lessons)}\n"
            f"[yellow]User model keys:[/yellow] {list(user_model.keys())}\n\n"
            f"[green]Scheduler running:[/green] {self.scheduler.scheduler.running}\n\n"
            "Commands:\n"
            "  'improve'  — run self-improvement analysis\n"
            "  'skills'   — list saved skills\n"
            "  'summary'  — today's learning summary\n"
            "  'exit'     — quit",
            title="Agent Status",
            border_style="blue"
        ))


async def start_self_aware_agent_mode(config: Config):
    console.print(Panel(
        "[bold blue]SELF-AWARE AGENT — ONLINE[/bold blue]\n\n"
        "Memory: persistent (SQLite)\n"
        "Skills: auto-captured from solved tasks\n"
        "Improvement: type 'improve' to run self-analysis\n"
        "Scheduler: time-based instructions understood naturally\n\n"
        "[green]Just talk. Type 'exit' to quit.[/green]",
        title="200Model8CLI",
        border_style="cyan"
    ))

    async with OpenRouterClient(config) as api_client:
        tool_registry = ToolRegistry(config)
        for tool_class in [FileOperations, GitTools, GitHubTools, WebTools, KnowledgeTools]:
            tools_instance = tool_class(config)
            for tool in tools_instance.get_tools():
                tool_registry.register_tool(tool)

        agent = SelfAwareAgent(config, api_client, tool_registry)
        agent.display_status()

        while True:
            try:
                user_input = console.input("\n[bold cyan]>[/bold cyan] ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    console.print("[green]Goodbye.[/green]")
                    agent.scheduler.shutdown()
                    break
                if user_input.lower() == "improve":
                    patches = await agent.run_self_improvement()
                    if not patches:
                        console.print("[green]No issues found.[/green]")
                    else:
                        for patch in patches:
                            await agent.apply_patch_interactively(patch)
                    continue
                if user_input.lower() == "skills":
                    for s in agent.skill_engine.list_skills():
                        console.print(f"• [cyan]{s['name']}[/cyan] (used {s['use_count']}x)")
                    continue
                if user_input.lower() == "summary":
                    summary = agent.memory.get_daily_summary()
                    by_cat = summary.get("by_category", {})
                    lines = [f"Summary for {summary['date']}:"]
                    for cat, entries in by_cat.items():
                        lines.append(f"\n{cat.title()} ({len(entries)}):")
                        for e in entries:
                            lines.append(f"  - {e}")
                    console.print("\n".join(lines) if len(lines) > 1 else "Nothing logged today.")
                    continue

                response = await agent.process(user_input)
                console.print(Panel(response, border_style="green"))

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted.[/yellow]")
                agent.scheduler.shutdown()
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
