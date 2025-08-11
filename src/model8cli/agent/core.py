"""
Advanced Agent System for 200Model8CLI
Provides autonomous task execution with browser automation, file management, and more
"""
import asyncio
import json
import webbrowser
import subprocess
import platform
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass

from model8cli.core.config import Config
from model8cli.core.api import OpenRouterClient
from model8cli.core.models import ModelManager
from model8cli.tools.base import ToolRegistry
from model8cli.tools.file_ops import FileOperations
from model8cli.tools.web_tools import WebTools
from model8cli.tools.browser_tools import BrowserTools
from model8cli.tools.system_tools import SystemTools
from model8cli.tools.git_tools import GitTools
from model8cli.tools.code_tools import CodeTools
from model8cli.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentTask:
    """Represents a task for the agent to execute"""
    id: str
    description: str
    priority: int = 1
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AdvancedAgent:
    """Advanced autonomous agent with comprehensive capabilities"""
    
    def __init__(self, config: Config):
        self.config = config
        self.api_client = OpenRouterClient(config)
        self.model_manager = ModelManager(config, self.api_client)
        self.tool_registry = ToolRegistry(config)
        
        # Initialize all tool categories
        self._setup_tools()
        
        # Agent state
        self.tasks = []
        self.current_task = None
        self.session_context = {}
        self.browser_sessions = {}
        
    def _setup_tools(self):
        """Setup all available tools for the agent"""
        # File operations
        file_ops = FileOperations(self.config)
        for tool in file_ops.get_tools():
            self.tool_registry.register_tool(tool)
        
        # Web tools
        web_tools = WebTools(self.config)
        for tool in web_tools.get_tools():
            self.tool_registry.register_tool(tool)
        
        # Browser automation
        browser_tools = BrowserTools(self.config)
        for tool in browser_tools.get_tools():
            self.tool_registry.register_tool(tool)
        
        # System tools
        system_tools = SystemTools(self.config)
        for tool in system_tools.get_tools():
            self.tool_registry.register_tool(tool)
        
        # Git tools
        git_tools = GitTools(self.config)
        for tool in git_tools.get_tools():
            self.tool_registry.register_tool(tool)
        
        # Code tools
        code_tools = CodeTools(self.config)
        for tool in code_tools.get_tools():
            self.tool_registry.register_tool(tool)
    
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Execute a high-level task using AI planning and tool execution"""
        try:
            # Create task
            task = AgentTask(
                id=f"task_{len(self.tasks)}",
                description=task_description,
                status="in_progress"
            )
            self.tasks.append(task)
            self.current_task = task
            
            # Plan the task execution
            plan = await self._plan_task(task_description)
            
            # Execute the plan
            result = await self._execute_plan(plan)
            
            # Update task status
            task.status = "completed"
            task.result = result
            
            return {
                "success": True,
                "task_id": task.id,
                "result": result
            }
            
        except Exception as e:
            if self.current_task:
                self.current_task.status = "failed"
                self.current_task.error = str(e)
            
            logger.error("Agent task execution failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _plan_task(self, task_description: str) -> List[Dict[str, Any]]:
        """Use AI to plan task execution steps"""
        try:
            # Get available tools
            tools = self.tool_registry.get_tool_definitions()
            tool_descriptions = []
            
            for tool in tools:
                tool_descriptions.append(f"- {tool['function']['name']}: {tool['function']['description']}")
            
            # Create planning prompt
            planning_prompt = f"""
You are an advanced AI agent. Plan how to execute this task: "{task_description}"

Available tools:
{chr(10).join(tool_descriptions)}

Create a step-by-step plan as a JSON array. Each step should have:
- "action": tool name to use
- "parameters": parameters for the tool
- "description": what this step accomplishes

Example format:
[
  {{"action": "search_web", "parameters": {{"query": "example"}}, "description": "Search for information"}},
  {{"action": "open_browser", "parameters": {{"url": "https://example.com"}}, "description": "Open website"}}
]

Plan:
"""
            
            # Get AI response
            from model8cli.core.api import Message
            messages = [Message(role="user", content=planning_prompt)]
            response = await self.api_client.chat_completion(
                model=self.config.models.default,
                messages=messages,
                temperature=0.3
            )
            
            # Parse the plan
            plan_text = response.choices[0]["message"]["content"]
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', plan_text, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                return plan
            else:
                # Fallback: create simple plan
                return [{"action": "web_search", "parameters": {"query": task_description}, "description": "Search for information about the task"}]

        except Exception as e:
            logger.error("Task planning failed", error=str(e))
            # Return basic fallback plan
            return [{"action": "web_search", "parameters": {"query": task_description}, "description": "Search for information"}]
    
    async def _execute_plan(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute the planned steps"""
        results = []
        
        for i, step in enumerate(plan):
            try:
                action = step.get("action")
                parameters = step.get("parameters", {})
                description = step.get("description", "")
                
                logger.info(f"Executing step {i+1}: {description}")
                
                # Find and execute the tool
                tool = self.tool_registry.get_tool(action)
                if tool:
                    result = await tool.execute(**parameters)
                    results.append({
                        "step": i + 1,
                        "action": action,
                        "description": description,
                        "success": result.success,
                        "result": result.result if result.success else None,
                        "error": result.error if not result.success else None
                    })
                else:
                    results.append({
                        "step": i + 1,
                        "action": action,
                        "description": description,
                        "success": False,
                        "error": f"Tool '{action}' not found"
                    })
                    
            except Exception as e:
                results.append({
                    "step": i + 1,
                    "action": step.get("action", "unknown"),
                    "description": step.get("description", ""),
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "plan": plan,
            "execution_results": results,
            "total_steps": len(plan),
            "successful_steps": len([r for r in results if r["success"]]),
            "failed_steps": len([r for r in results if not r["success"]])
        }
    
    async def browser_search_and_analyze(self, query: str, browser: str = "default") -> Dict[str, Any]:
        """Advanced browser search with analysis"""
        try:
            # Search the web first
            web_tool = self.tool_registry.get_tool("web_search")
            search_result = await web_tool.execute(query=query, max_results=5)
            
            if not search_result.success:
                return {"success": False, "error": "Web search failed"}
            
            # Open browser with search results
            browser_tool = self.tool_registry.get_tool("search_browser")
            browser_result = await browser_tool.execute(
                query=query,
                search_engine="google",
                browser=browser
            )
            
            return {
                "success": True,
                "web_search": search_result.result,
                "browser_opened": browser_result.success,
                "query": query
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and capabilities"""
        return {
            "total_tools": len(self.tool_registry.tools),
            "available_tools": list(self.tool_registry.tools.keys()),
            "current_task": self.current_task.description if self.current_task else None,
            "total_tasks": len(self.tasks),
            "completed_tasks": len([t for t in self.tasks if t.status == "completed"]),
            "failed_tasks": len([t for t in self.tasks if t.status == "failed"]),
            "capabilities": [
                "Web search and analysis",
                "Browser automation (Chrome, Firefox, Edge, Brave)",
                "File and directory management",
                "Code execution and analysis",
                "Git repository operations",
                "System monitoring and commands",
                "Multi-step task planning",
                "Autonomous execution"
            ]
        }
