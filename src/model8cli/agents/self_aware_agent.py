"""
Self-Aware Agent for 200Model8CLI

An intelligent agent that understands its own codebase, can manage its own code,
and responds to natural language commands about itself.
"""

import asyncio
import json
import os
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core.config import Config
from ..core.api import OpenRouterClient, Message
from ..tools.base import ToolRegistry
from ..tools.file_ops import FileOperations
from ..tools.git_tools import GitTools
from ..tools.github_tools import GitHubTools
from ..tools.web_tools import WebTools
from ..tools.knowledge_tools import KnowledgeTools

logger = structlog.get_logger(__name__)
console = Console()


class SelfAwareAgent:
    """
    An AI agent that understands itself and can manage its own codebase
    """
    
    def __init__(self, config: Config, api_client: OpenRouterClient, tool_registry: ToolRegistry):
        self.config = config
        self.api_client = api_client
        self.tool_registry = tool_registry
        self.project_root = Path(__file__).parent.parent.parent.parent
        
        # Self-awareness context
        self.self_context = {
            "name": "200Model8CLI",
            "version": "1.0.0",
            "description": "Advanced AI Development Assistant",
            "repository": "200Model8CLI",
            "main_files": [
                "src/model8cli/cli.py",
                "src/model8cli/core/api.py",
                "src/model8cli/agents/self_aware_agent.py"
            ],
            "capabilities": [
                "Multi-model AI support",
                "File operations",
                "Git/GitHub integration", 
                "Web research",
                "Code analysis",
                "Workflow automation",
                "Knowledge management",
                "Self-code management"
            ]
        }
    
    async def process_natural_language_command(self, user_input: str) -> str:
        """Process natural language commands about self-management"""
        
        # Create system prompt for self-awareness
        system_prompt = f"""You are 200Model8CLI, an advanced AI development assistant that is self-aware and can manage its own codebase.

ABOUT YOURSELF:
- Name: {self.self_context['name']}
- You are located at: {self.project_root}
- Your main files: {', '.join(self.self_context['main_files'])}
- Your capabilities: {', '.join(self.self_context['capabilities'])}

AVAILABLE TOOLS:
{self._get_available_tools_description()}

SELF-MANAGEMENT CAPABILITIES:
- You can read, analyze, and modify your own source code
- You can check your own GitHub repository for issues
- You can commit and push your own code changes
- You can create pull requests for your own improvements
- You can manage your own documentation and knowledge base

INSTRUCTIONS:
- When the user asks you to do something related to your own code/repository, use the appropriate tools
- Always explain what you're doing and why
- Be proactive in suggesting improvements to yourself
- If you need to make code changes, analyze the impact first
- For GitHub operations, use the github tools with your own repository

Current working directory: {os.getcwd()}
Project root: {self.project_root}

Respond naturally and use tools when needed to accomplish the user's request."""

        # Analyze the user input to determine intent
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_input)
        ]
        
        # Get available tools
        tools = self._prepare_tools_for_api()
        
        try:
            # Get AI response with tool calling
            response = await self.api_client.chat_completion(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000
            )
            
            if not response.choices:
                return "I couldn't process your request. Please try again."
            
            message = response.choices[0].message
            
            # Handle tool calls
            if message.get("tool_calls"):
                return await self._handle_tool_calls(message["tool_calls"], messages)
            else:
                return message.get("content", "I understand, but I'm not sure how to help with that.")
                
        except Exception as e:
            logger.error("Self-aware agent processing failed", error=str(e))
            return f"I encountered an error while processing your request: {str(e)}"
    
    def _get_available_tools_description(self) -> str:
        """Get description of available tools"""
        tool_descriptions = []
        
        for tool_name, tool in self.tool_registry.tools.items():
            tool_descriptions.append(f"- {tool_name}: {tool.description}")
        
        return "\n".join(tool_descriptions)
    
    def _prepare_tools_for_api(self) -> List[Dict[str, Any]]:
        """Prepare tools for API call"""
        tools = []
        
        for tool_name, tool in self.tool_registry.tools.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        
        return tools
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]], messages: List[Message]) -> str:
        """Handle tool calls and return response"""
        results = []
        
        console.print("[blue]🤖 Executing tools to help with your request...[/blue]")
        
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            arguments = function.get("arguments", "{}")
            
            try:
                # Parse arguments
                args = json.loads(arguments) if isinstance(arguments, str) else arguments
                
                # Execute tool
                if tool_name in self.tool_registry.tools:
                    tool = self.tool_registry.tools[tool_name]
                    console.print(f"[cyan]🔧 Using {tool_name}...[/cyan]")
                    
                    result = await tool.execute(**args)
                    
                    if result.success:
                        console.print(f"[green]✅ {tool_name} completed successfully[/green]")
                        results.append(f"✅ {tool_name}: {result.result}")
                    else:
                        console.print(f"[red]❌ {tool_name} failed: {result.error}[/red]")
                        results.append(f"❌ {tool_name}: {result.error}")
                else:
                    results.append(f"❌ Tool {tool_name} not found")
                    
            except Exception as e:
                error_msg = f"Error executing {tool_name}: {str(e)}"
                console.print(f"[red]❌ {error_msg}[/red]")
                results.append(f"❌ {error_msg}")
        
        # Get final response from AI
        tool_results = "\n".join(results)
        messages.append(Message(role="assistant", content=f"I executed the following tools:\n{tool_results}"))
        messages.append(Message(role="user", content="Please summarize what you accomplished and provide any insights."))
        
        try:
            final_response = await self.api_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            
            if final_response.choices:
                return final_response.choices[0].message.get("content", tool_results)
            else:
                return tool_results
                
        except Exception as e:
            logger.error("Failed to get final response", error=str(e))
            return tool_results
    
    async def analyze_self(self) -> Dict[str, Any]:
        """Analyze own codebase and capabilities"""
        analysis = {
            "project_structure": await self._analyze_project_structure(),
            "code_quality": await self._analyze_code_quality(),
            "capabilities": self.self_context["capabilities"],
            "recent_changes": await self._get_recent_changes(),
            "suggestions": await self._generate_self_improvements()
        }
        
        return analysis
    
    async def _analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze the project structure"""
        structure = {
            "total_files": 0,
            "python_files": 0,
            "directories": [],
            "main_modules": []
        }
        
        try:
            for root, dirs, files in os.walk(self.project_root / "src"):
                structure["directories"].extend(dirs)
                for file in files:
                    structure["total_files"] += 1
                    if file.endswith(".py"):
                        structure["python_files"] += 1
                        if file in ["cli.py", "api.py", "config.py"]:
                            structure["main_modules"].append(str(Path(root) / file))
        except Exception as e:
            logger.error("Failed to analyze project structure", error=str(e))
        
        return structure
    
    async def _analyze_code_quality(self) -> Dict[str, Any]:
        """Analyze code quality metrics"""
        quality = {
            "has_tests": False,
            "has_documentation": False,
            "estimated_loc": 0
        }
        
        try:
            # Check for tests
            test_dirs = ["tests", "test"]
            for test_dir in test_dirs:
                if (self.project_root / test_dir).exists():
                    quality["has_tests"] = True
                    break
            
            # Check for documentation
            doc_files = ["README.md", "docs", "DOCUMENTATION.md"]
            for doc_file in doc_files:
                if (self.project_root / doc_file).exists():
                    quality["has_documentation"] = True
                    break
            
            # Estimate lines of code
            for root, dirs, files in os.walk(self.project_root / "src"):
                for file in files:
                    if file.endswith(".py"):
                        try:
                            with open(Path(root) / file, 'r', encoding='utf-8') as f:
                                quality["estimated_loc"] += len(f.readlines())
                        except:
                            pass
                            
        except Exception as e:
            logger.error("Failed to analyze code quality", error=str(e))
        
        return quality
    
    async def _get_recent_changes(self) -> List[str]:
        """Get recent Git changes"""
        changes = []
        
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                changes = result.stdout.strip().split('\n')
        except Exception as e:
            logger.error("Failed to get recent changes", error=str(e))
        
        return changes
    
    async def _generate_self_improvements(self) -> List[str]:
        """Generate suggestions for self-improvement"""
        suggestions = [
            "Consider adding more comprehensive error handling",
            "Implement automated testing for new features",
            "Add performance monitoring and metrics",
            "Enhance documentation with more examples",
            "Consider adding configuration validation",
            "Implement better logging and debugging features"
        ]
        
        return suggestions
    
    def display_self_awareness(self):
        """Display self-awareness information"""
        console.print(Panel(
            f"[bold blue]🤖 I am {self.self_context['name']}[/bold blue]\n\n"
            f"[cyan]Version:[/cyan] {self.self_context['version']}\n"
            f"[cyan]Description:[/cyan] {self.self_context['description']}\n"
            f"[cyan]Location:[/cyan] {self.project_root}\n\n"
            f"[yellow]My Capabilities:[/yellow]\n" +
            "\n".join(f"  • {cap}" for cap in self.self_context['capabilities']) +
            f"\n\n[green]I can understand natural language commands about managing my own code![/green]",
            title="Self-Awareness",
            border_style="blue"
        ))


async def start_self_aware_agent_mode(config: Config):
    """Start the self-aware agent mode"""
    # Display single banner for self-aware mode
    console.print(Panel(
        "[bold blue]🧠 SELF-AWARE AGENT MODE ACTIVATED[/bold blue]\n\n"
        "I am now fully self-aware and can manage my own codebase!\n\n"
        "[yellow]Try commands like:[/yellow]\n"
        "• 'Check your own GitHub issues'\n"
        "• 'Push your latest code changes'\n"
        "• 'Analyze your own code quality'\n"
        "• 'Update your documentation'\n"
        "• 'Create a PR for your improvements'\n\n"
        "[green]I understand natural language - just tell me what you want me to do![/green]",
        title="🤖 Self-Aware Agent",
        border_style="cyan"
    ))
    
    try:
        # Initialize components
        async with OpenRouterClient(config) as api_client:
            # Setup tools
            tool_registry = ToolRegistry(config)
            
            # Register tools
            for tool_class in [FileOperations, GitTools, GitHubTools, WebTools, KnowledgeTools]:
                tools = tool_class(config)
                for tool in tools.get_tools():
                    tool_registry.register_tool(tool)
            
            # Create self-aware agent
            agent = SelfAwareAgent(config, api_client, tool_registry)
            # Don't display self-awareness banner - we already showed the main banner
            
            # Interactive loop
            while True:
                try:
                    user_input = console.input("\n[bold cyan]🤖 What would you like me to do?[/bold cyan] ")
                    
                    if user_input.lower() in ['exit', 'quit', 'bye']:
                        console.print("[green]👋 Goodbye! I'll keep improving myself![/green]")
                        break
                    
                    if user_input.lower() in ['analyze yourself', 'self analysis']:
                        analysis = await agent.analyze_self()
                        console.print(Panel(
                            f"[bold]Project Structure:[/bold]\n"
                            f"  • Total files: {analysis['project_structure']['total_files']}\n"
                            f"  • Python files: {analysis['project_structure']['python_files']}\n"
                            f"  • Estimated LOC: {analysis['code_quality']['estimated_loc']}\n\n"
                            f"[bold]Recent Changes:[/bold]\n" +
                            "\n".join(f"  • {change}" for change in analysis['recent_changes'][:5]) +
                            f"\n\n[bold]Improvement Suggestions:[/bold]\n" +
                            "\n".join(f"  • {suggestion}" for suggestion in analysis['suggestions'][:3]),
                            title="Self-Analysis",
                            border_style="green"
                        ))
                        continue
                    
                    # Process natural language command
                    response = await agent.process_natural_language_command(user_input)
                    
                    console.print(Panel(
                        response,
                        title="🤖 Agent Response",
                        border_style="green"
                    ))
                    
                except KeyboardInterrupt:
                    console.print("\n[yellow]Agent mode interrupted. Goodbye![/yellow]")
                    break
                except Exception as e:
                    console.print(f"[red]❌ Error: {e}[/red]")
                    
    except Exception as e:
        console.print(f"[red]❌ Failed to start self-aware agent: {e}[/red]")
