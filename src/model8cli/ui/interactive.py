"""
Interactive Mode for 200Model8CLI

Provides a rich interactive terminal interface for conversing with AI models.
"""

import asyncio
from typing import Optional, List, Dict, Any
import json

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
import structlog

from ..core.config import Config
from ..core.api import OpenRouterClient, Message
from ..core.models import ModelManager
from ..core.session import SessionManager
from ..tools.base import ToolRegistry
from .formatting import RichFormatter

logger = structlog.get_logger(__name__)


class InteractiveMode:
    """
    Interactive terminal interface for 200Model8CLI
    """
    
    def __init__(
        self,
        config: Config,
        api_client: OpenRouterClient,
        model_manager: ModelManager,
        session_manager: SessionManager,
        tool_registry: ToolRegistry,
    ):
        self.config = config
        self.api_client = api_client
        self.model_manager = model_manager
        self.session_manager = session_manager
        self.tool_registry = tool_registry
        
        self.console = Console()
        self.formatter = RichFormatter(config)

        self.running = True
        self.current_session = None

        # Loop detection
        self.recent_messages = []
        self.max_recent_messages = 5
        self.loop_threshold = 3
        
    async def start(self):
        """Start interactive mode"""
        self.console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]")
        
        # Create or load session
        await self._setup_session()
        
        while self.running:
            try:
                # Get user input
                user_input = Prompt.ask(
                    f"[bold blue]200model8CLI[/bold blue]",
                    default=""
                )
                
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    await self._handle_command(user_input[1:])
                    continue
                
                # Process user message
                await self._process_user_message(user_input)
                
            except KeyboardInterrupt:
                if Confirm.ask("\n[yellow]Exit 200Model8CLI?[/yellow]"):
                    break
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                logger.error("Interactive mode error", error=str(e))
        
        self.console.print("[dim]Session saved. Goodbye![/dim]")
    
    async def _setup_session(self):
        """Setup or create a session"""
        # For now, create a new session
        # In a full implementation, this would allow loading existing sessions
        self.current_session = self.session_manager.create_session(
            name=f"Interactive Session",
            model=self.model_manager.current_model
        )

        # Add system message to make the assistant aware of its capabilities
        available_tools = list(self.tool_registry.tools.keys())
        system_prompt = f"""You are 200Model8CLI, an advanced AI assistant with comprehensive tool-calling capabilities. You can:

🔧 **Available Tools ({len(available_tools)} total):**
- **File Operations**: read_file, write_file, create_directory, list_directory, delete_file, copy_file, move_file
- **Web Search**: web_search (search the internet for information)
- **Browser Automation**: open_browser, search_browser (open URLs and search directly in browsers like Chrome, Firefox, Edge, Brave)
- **Git Operations**: git_status, git_add, git_commit, git_push, git_pull, git_branch, git_log
- **System Operations**: execute_command, get_system_info, list_processes
- **Code Analysis**: analyze_code, run_code, format_code, lint_code

🌐 **Browser Capabilities:**
- I CAN open browsers and search for information
- I CAN open specific URLs in different browsers (Chrome, Firefox, Edge, Brave)
- I CAN perform web searches directly in browsers
- I CAN search for current information like "top Netflix movies 2025"

💡 **How to use me:**
- Ask me to search for information: "search for Python tutorials"
- Ask me to open websites: "open Google in Chrome"
- Ask me to search in browser: "search for top Netflix movies 2025 in Brave"
- Ask me about files: "what files are in this directory?"
- Ask me to create/edit files: "create a Python hello world file"
- Ask me to run commands: "check system information"

I'm proactive and will use the appropriate tools to help you accomplish your tasks!"""

        self.session_manager.add_message("system", system_prompt)

        self.console.print(f"[dim]Started new session: {self.current_session.metadata.name}[/dim]")
    
    async def _handle_command(self, command: str):
        """Handle slash commands"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == "help":
            self._show_help()
        elif cmd == "exit" or cmd == "quit":
            self.running = False
        elif cmd == "model":
            await self._handle_model_command(args)
        elif cmd == "models":
            await self._list_models()
        elif cmd == "session":
            await self._handle_session_command(args)
        elif cmd == "sessions":
            await self._list_sessions()
        elif cmd == "tools":
            self._list_tools()
        elif cmd == "capabilities":
            self._show_capabilities()
        elif cmd == "clear":
            self.console.clear()
        elif cmd == "config":
            self._show_config()
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self._show_help()
    
    def _show_help(self):
        """Show help information"""
        help_text = """
[bold]Available Commands:[/bold]

[cyan]/help[/cyan]           - Show this help message
[cyan]/exit[/cyan]           - Exit the application
[cyan]/model <name>[/cyan]   - Switch to a different model
[cyan]/models[/cyan]         - List available models
[cyan]/session <cmd>[/cyan]  - Session management (save, load, new)
[cyan]/sessions[/cyan]       - List all sessions
[cyan]/tools[/cyan]          - List available tools
[cyan]/capabilities[/cyan]   - Show AI capabilities and examples
[cyan]/clear[/cyan]          - Clear the screen
[cyan]/config[/cyan]         - Show configuration

[bold green]AI Capabilities:[/bold green]
• Search the web and open browsers
• Create, read, and edit files
• Execute system commands
• Manage Git repositories
• Analyze and run code

[bold]Usage:[/bold]
- Type your message and press Enter to chat
- Use Ctrl+C to interrupt, then confirm to exit
- Messages are automatically saved to the current session
        """
        self.console.print(Panel(help_text.strip(), title="Help"))

    def _show_capabilities(self):
        """Show AI capabilities with examples"""
        available_tools = list(self.tool_registry.tools.keys())
        capabilities_text = f"""
[bold blue]🤖 200Model8CLI AI Capabilities[/bold blue]

[bold green]🔧 Available Tools ({len(available_tools)} total):[/bold green]

[yellow]🌐 Web & Browser:[/yellow]
• web_search - Search the internet for information
• open_browser - Open URLs in browsers (Chrome, Firefox, Edge, Brave)
• search_browser - Search directly in browsers

[yellow]📁 File Operations:[/yellow]
• read_file, write_file, create_directory, list_directory
• delete_file, copy_file, move_file

[yellow]⚙️ System Operations:[/yellow]
• execute_command - Run terminal commands
• get_system_info - Get system information
• list_processes - List running processes

[yellow]🔧 Git Operations:[/yellow]
• git_status, git_add, git_commit, git_push, git_pull
• git_branch, git_log

[yellow]💻 Code Analysis:[/yellow]
• analyze_code, run_code, format_code, lint_code

[bold cyan]💡 Example Commands:[/bold cyan]
• "search for top Netflix movies 2025"
• "open Brave and search for Python tutorials"
• "what files are in this directory?"
• "create a Python hello world file"
• "check system information"
• "run git status"

[bold red]🚀 I'm proactive and will use tools automatically to help you![/bold red]
        """
        self.console.print(Panel(capabilities_text.strip(), title="AI Capabilities"))

    async def _handle_model_command(self, args: List[str]):
        """Handle model switching"""
        if not args:
            self.console.print(f"Current model: [green]{self.model_manager.current_model}[/green]")
            return
        
        model_id = args[0]
        if self.model_manager.set_current_model(model_id):
            self.console.print(f"[green]✓[/green] Switched to model: {model_id}")
            
            # Update session model
            if self.current_session:
                self.current_session.metadata.model = model_id
                self.session_manager.save_current_session()
        else:
            self.console.print(f"[red]Model not found: {model_id}[/red]")
            await self._list_models()
    
    async def _list_models(self):
        """List available models"""
        models = self.model_manager.get_available_models()
        
        if not models:
            self.console.print("[yellow]No models available[/yellow]")
            return
        
        self.console.print("[bold]Available Models:[/bold]")
        for model in models:
            current = "→ " if model.info.id == self.model_manager.current_model else "  "
            capabilities = ", ".join([cap.value for cap in list(model.capabilities)[:3]])
            
            self.console.print(
                f"{current}[green]{model.info.id}[/green] - {model.info.name}"
            )
            self.console.print(f"    [dim]{capabilities}[/dim]")
    
    async def _handle_session_command(self, args: List[str]):
        """Handle session management"""
        if not args:
            if self.current_session:
                self.console.print(f"Current session: [green]{self.current_session.metadata.name}[/green]")
            else:
                self.console.print("[yellow]No active session[/yellow]")
            return
        
        cmd = args[0].lower()
        
        if cmd == "new":
            name = " ".join(args[1:]) if len(args) > 1 else None
            self.current_session = self.session_manager.create_session(
                name=name,
                model=self.model_manager.current_model
            )
            self.console.print(f"[green]✓[/green] Created new session: {self.current_session.metadata.name}")
        
        elif cmd == "save":
            if self.current_session:
                self.session_manager.save_current_session()
                self.console.print("[green]✓[/green] Session saved")
            else:
                self.console.print("[yellow]No active session to save[/yellow]")
        
        elif cmd == "load":
            if len(args) < 2:
                self.console.print("[red]Usage: /session load <session_id>[/red]")
                return
            
            session_id = args[1]
            session = self.session_manager.load_session(session_id)
            if session:
                self.current_session = session
                self.model_manager.set_current_model(session.metadata.model)
                self.console.print(f"[green]✓[/green] Loaded session: {session.metadata.name}")
            else:
                self.console.print(f"[red]Session not found: {session_id}[/red]")
        
        else:
            self.console.print(f"[red]Unknown session command: {cmd}[/red]")
            self.console.print("[dim]Available: new, save, load[/dim]")
    
    async def _list_sessions(self):
        """List all sessions"""
        sessions = self.session_manager.list_sessions()
        
        if not sessions:
            self.console.print("[yellow]No sessions found[/yellow]")
            return
        
        self.console.print("[bold]Available Sessions:[/bold]")
        for session in sessions[:10]:  # Show last 10 sessions
            current = "→ " if (self.current_session and 
                             session.id == self.current_session.metadata.id) else "  "
            
            from datetime import datetime
            updated = datetime.fromtimestamp(session.updated_at).strftime("%m/%d %H:%M")
            
            self.console.print(
                f"{current}[green]{session.id[:8]}[/green] - {session.name} "
                f"[dim]({session.total_messages} msgs, {updated})[/dim]"
            )
    
    def _list_tools(self):
        """List available tools"""
        tools = self.tool_registry.get_enabled_tools()
        
        if not tools:
            self.console.print("[yellow]No tools available[/yellow]")
            return
        
        self.console.print("[bold]Available Tools:[/bold]")
        
        # Group by category
        by_category = {}
        for tool in tools:
            category = tool.category.value
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tool)
        
        for category, category_tools in by_category.items():
            self.console.print(f"\n[cyan]{category.replace('_', ' ').title()}:[/cyan]")
            for tool in category_tools:
                dangerous = " [red]⚠[/red]" if tool.dangerous else ""
                confirmation = " [yellow]?[/yellow]" if tool.requires_confirmation else ""
                
                self.console.print(f"  • [green]{tool.name}[/green]{dangerous}{confirmation} - {tool.description}")
    
    def _show_config(self):
        """Show current configuration"""
        config_info = {
            "Model": self.model_manager.current_model,
            "Streaming": self.config.ui.streaming,
            "Syntax Highlighting": self.config.ui.syntax_highlighting,
            "File Operations": self.config.tools.file_operations_enabled,
            "Web Search": self.config.tools.web_search_enabled,
            "Git Operations": self.config.tools.git_operations_enabled,
        }
        
        self.console.print("[bold]Current Configuration:[/bold]")
        for key, value in config_info.items():
            color = "green" if value else "red" if isinstance(value, bool) else "blue"
            self.console.print(f"  {key}: [{color}]{value}[/{color}]")
    
    async def _process_user_message(self, user_input: str):
        """Process user message and get AI response"""
        try:
            # Check for loops
            if self._detect_loop(user_input):
                self.console.print("[yellow]⚠️ Loop detected! Trying a different approach...[/yellow]")
                user_input = f"Let me try a different approach: {user_input}"

            # Add to recent messages for loop detection
            self.recent_messages.append(user_input.lower().strip())
            if len(self.recent_messages) > self.max_recent_messages:
                self.recent_messages.pop(0)

            # Add user message to session
            self.session_manager.add_message("user", user_input)
            
            # Get context messages
            context_messages = self.session_manager.get_context_messages()
            
            # Get tool definitions (disable for Ollama models)
            current_model = self.config.models.default
            if current_model and current_model.startswith("ollama/"):
                # Disable tools for Ollama models as they don't support tool calling well
                tool_definitions = []
            else:
                tool_definitions = self.tool_registry.get_tool_definitions()
            
            # Show thinking indicator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task("Thinking...", total=None)
                
                # Make API call
                if self.config.ui.streaming:
                    await self._handle_streaming_response(
                        context_messages, tool_definitions, progress, task
                    )
                else:
                    await self._handle_non_streaming_response(
                        context_messages, tool_definitions, progress, task
                    )
        
        except Exception as e:
            self.console.print(f"[red]Failed to process message: {e}[/red]")
            logger.error("Message processing failed", error=str(e))

    def _detect_loop(self, message: str) -> bool:
        """Detect if user is repeating similar messages (indicating a loop)"""
        if len(self.recent_messages) < self.loop_threshold:
            return False

        normalized_message = message.lower().strip()

        # Count similar messages in recent history
        similar_count = 0
        for recent_msg in self.recent_messages[-self.loop_threshold:]:
            # Simple similarity check - could be improved with fuzzy matching
            if (normalized_message in recent_msg or
                recent_msg in normalized_message or
                len(set(normalized_message.split()) & set(recent_msg.split())) > len(normalized_message.split()) * 0.6):
                similar_count += 1

        return similar_count >= self.loop_threshold - 1
    
    async def _handle_streaming_response(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        progress: Progress,
        task_id: Any
    ):
        """Handle streaming response"""
        try:
            # For now, fall back to non-streaming to avoid async issues
            progress.update(task_id, description="Getting response...")

            response = await self.api_client.chat_completion(
                messages=messages,
                tools=tools if tools else None,
                stream=False  # Disable streaming for stability
            )

            progress.stop()

            # Handle response
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                message = choice.get("message", {}) if isinstance(choice, dict) else choice

                # Handle content
                if isinstance(message, dict) and message.get("content"):
                    response_text = message["content"]
                    self.formatter.display_assistant_message(response_text)
                    self.session_manager.add_message("assistant", response_text)

                # Handle tool calls if any
                if isinstance(message, dict) and message.get("tool_calls"):
                    await self._handle_tool_calls(message["tool_calls"])
        
        except Exception as e:
            progress.stop()
            raise e
    
    async def _handle_non_streaming_response(
        self, 
        messages: List[Message], 
        tools: List[Dict[str, Any]],
        progress: Progress,
        task_id: Any
    ):
        """Handle non-streaming response"""
        try:
            response = await self.api_client.chat_completion(
                messages=messages,
                tools=tools if tools else None,
                stream=False
            )
            
            progress.stop()
            
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                message = choice.get("message", {}) if isinstance(choice, dict) else choice

                # Handle content
                if isinstance(message, dict) and message.get("content"):
                    content = message["content"]
                    self.formatter.display_assistant_message(content)
                    self.session_manager.add_message("assistant", content)

                # Handle tool calls
                if isinstance(message, dict) and message.get("tool_calls"):
                    await self._handle_tool_calls(message["tool_calls"])
        
        except Exception as e:
            progress.stop()
            raise e
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """Handle tool calls from AI"""
        for tool_call in tool_calls:
            try:
                function = tool_call["function"]
                tool_name = function["name"]
                arguments = json.loads(function["arguments"])
                
                self.console.print(f"[dim]🔧 Calling tool: {tool_name}[/dim]")
                
                # Check if tool requires confirmation
                tool = self.tool_registry.get_tool(tool_name)
                if tool and tool.requires_confirmation:
                    if not Confirm.ask(f"[yellow]Execute {tool_name}?[/yellow]"):
                        self.console.print("[dim]Tool execution cancelled[/dim]")
                        continue
                
                # Execute tool
                result = await self.tool_registry.execute_tool(tool_name, **arguments)
                
                if result.success:
                    self.console.print(f"[green]✓[/green] Tool executed successfully")
                    if result.result:
                        self.formatter.display_tool_result(tool_name, result.result)
                else:
                    self.console.print(f"[red]✗[/red] Tool failed: {result.error}")
                
                # Add tool result to session
                self.session_manager.add_message(
                    "tool",
                    json.dumps(result.result if result.success else {"error": result.error}),
                    tool_call_id=tool_call["id"]
                )
                
            except Exception as e:
                self.console.print(f"[red]Tool execution error: {e}[/red]")
                logger.error("Tool execution failed", tool=tool_name, error=str(e))
