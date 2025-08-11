"""
Rich Formatting for 200Model8CLI

Provides rich terminal formatting for messages, code, and tool results.
"""

import json
import re
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from rich.json import JSON
import structlog

from ..core.config import Config
from ..utils.helpers import extract_code_blocks, detect_file_language

logger = structlog.get_logger(__name__)


class RichFormatter:
    """
    Rich terminal formatter for 200Model8CLI
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.console = Console()
        
        # Color scheme
        self.colors = {
            "user": "blue",
            "assistant": "green", 
            "system": "yellow",
            "tool": "cyan",
            "error": "red",
            "success": "green",
            "warning": "yellow",
            "info": "blue",
        }
    
    def display_user_message(self, content: str):
        """Display user message"""
        self.console.print(Panel(
            content,
            title="[bold blue]You[/bold blue]",
            border_style="blue",
            padding=(0, 1),
        ))
    
    def display_assistant_message(self, content: str):
        """Display 200model8CLI message with rich formatting"""
        if self.config.ui.rich_formatting:
            # Try to render as markdown first
            try:
                if self._contains_markdown(content):
                    markdown = Markdown(content)
                    self.console.print(Panel(
                        markdown,
                        title="[bold green]Assistant[/bold green]",
                        border_style="green",
                        padding=(0, 1),
                    ))
                    return
            except Exception:
                pass  # Fall back to plain text
        
        # Display as plain text
        self.console.print(Panel(
            content,
            title="[bold green]200model8CLI[/bold green]",
            border_style="green",
            padding=(0, 1),
        ))
    
    def display_system_message(self, content: str):
        """Display system message"""
        self.console.print(Panel(
            content,
            title="[bold yellow]System[/bold yellow]",
            border_style="yellow",
            padding=(0, 1),
        ))
    
    def display_tool_result(self, tool_name: str, result: Dict[str, Any]):
        """Display tool execution result"""
        try:
            formatted_result = self._format_tool_result(tool_name, result)
            
            self.console.print(Panel(
                formatted_result,
                title=f"[bold cyan]🔧 {tool_name}[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            ))
            
        except Exception as e:
            logger.warning("Failed to format tool result", tool=tool_name, error=str(e))
            # Fall back to JSON display
            self.console.print(Panel(
                JSON.from_data(result),
                title=f"[bold cyan]🔧 {tool_name}[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            ))
    
    def display_error(self, message: str, details: Optional[str] = None):
        """Display error message"""
        content = f"[red]{message}[/red]"
        if details:
            content += f"\n[dim]{details}[/dim]"
        
        self.console.print(Panel(
            content,
            title="[bold red]Error[/bold red]",
            border_style="red",
            padding=(0, 1),
        ))
    
    def display_warning(self, message: str):
        """Display warning message"""
        self.console.print(Panel(
            f"[yellow]{message}[/yellow]",
            title="[bold yellow]Warning[/bold yellow]",
            border_style="yellow",
            padding=(0, 1),
        ))
    
    def display_info(self, message: str):
        """Display info message"""
        self.console.print(Panel(
            f"[blue]{message}[/blue]",
            title="[bold blue]Info[/bold blue]",
            border_style="blue",
            padding=(0, 1),
        ))
    
    def display_success(self, message: str):
        """Display success message"""
        self.console.print(Panel(
            f"[green]{message}[/green]",
            title="[bold green]Success[/bold green]",
            border_style="green",
            padding=(0, 1),
        ))
    
    def display_code(self, code: str, language: str = "text", title: Optional[str] = None):
        """Display code with syntax highlighting"""
        if self.config.ui.syntax_highlighting:
            try:
                syntax = Syntax(
                    code,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                
                if title:
                    self.console.print(Panel(
                        syntax,
                        title=f"[bold]{title}[/bold]",
                        border_style="dim",
                    ))
                else:
                    self.console.print(syntax)
                return
            except Exception:
                pass  # Fall back to plain text
        
        # Display as plain text
        content = f"```{language}\n{code}\n```"
        if title:
            self.console.print(Panel(content, title=title))
        else:
            self.console.print(content)
    
    def display_file_tree(self, files: List[Dict[str, Any]], title: str = "Files"):
        """Display file tree structure"""
        tree = Tree(f"[bold]{title}[/bold]")
        
        # Group files by directory
        dirs = {}
        for file_info in files:
            path = file_info.get("path", "")
            parts = path.split("/")
            
            current = dirs
            for part in parts[:-1]:  # All but filename
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Add file
            filename = parts[-1] if parts else path
            current[filename] = file_info
        
        self._build_tree_recursive(tree, dirs)
        self.console.print(tree)
    
    def display_table(self, data: List[Dict[str, Any]], title: Optional[str] = None):
        """Display data as a table"""
        if not data:
            return
        
        # Get columns from first row
        columns = list(data[0].keys())
        
        table = Table(title=title)
        for col in columns:
            table.add_column(col.replace("_", " ").title())
        
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in columns])
        
        self.console.print(table)
    
    def _contains_markdown(self, text: str) -> bool:
        """Check if text contains markdown formatting"""
        markdown_patterns = [
            r'#{1,6}\s',  # Headers
            r'\*\*.*?\*\*',  # Bold
            r'\*.*?\*',  # Italic
            r'`.*?`',  # Inline code
            r'```.*?```',  # Code blocks
            r'\[.*?\]\(.*?\)',  # Links
            r'^\s*[-*+]\s',  # Lists
            r'^\s*\d+\.\s',  # Numbered lists
        ]
        
        for pattern in markdown_patterns:
            if re.search(pattern, text, re.MULTILINE | re.DOTALL):
                return True
        
        return False
    
    def _format_tool_result(self, tool_name: str, result: Dict[str, Any]) -> Any:
        """Format tool result based on tool type"""
        if tool_name == "read_file":
            return self._format_file_read_result(result)
        elif tool_name == "write_file":
            return self._format_file_write_result(result)
        elif tool_name == "search_files":
            return self._format_search_result(result)
        elif tool_name == "diff_files":
            return self._format_diff_result(result)
        else:
            # Generic formatting
            return self._format_generic_result(result)
    
    def _format_file_read_result(self, result: Dict[str, Any]) -> Any:
        """Format file read result"""
        content = result.get("content", "")
        path = result.get("path", "")
        language = result.get("language", "text")
        size = result.get("size_formatted", "")
        lines = result.get("line_count", 0)
        
        # Show file info
        info = f"[dim]Path: {path} | Size: {size} | Lines: {lines}[/dim]\n\n"
        
        # Show content with syntax highlighting
        if self.config.ui.syntax_highlighting and language != "text":
            try:
                syntax = Syntax(
                    content,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                return Text.from_markup(info) + syntax
            except Exception:
                pass
        
        return info + content
    
    def _format_file_write_result(self, result: Dict[str, Any]) -> str:
        """Format file write result"""
        path = result.get("path", "")
        size = result.get("size_formatted", "")
        backup = result.get("backup_path", "")
        
        text = f"✓ File written: [green]{path}[/green]\n"
        text += f"Size: {size}\n"
        
        if backup:
            text += f"Backup created: [dim]{backup}[/dim]"
        
        return text
    
    def _format_search_result(self, result: Dict[str, Any]) -> Any:
        """Format search result"""
        results = result.get("results", [])
        total = result.get("total_found", 0)
        directory = result.get("search_directory", "")
        
        if not results:
            return f"No results found in [dim]{directory}[/dim]"
        
        # Create table for results
        table = Table(title=f"Search Results ({total} found)")
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Size", justify="right")
        table.add_column("Details", style="dim")
        
        for item in results[:20]:  # Limit display
            details = ""
            if item.get("type") == "content_match":
                details = f"{item.get('total_matches', 0)} matches"
            
            table.add_row(
                item.get("type", "").replace("_", " ").title(),
                item.get("path", ""),
                item.get("size_formatted", ""),
                details
            )
        
        return table
    
    def _format_diff_result(self, result: Dict[str, Any]) -> str:
        """Format diff result"""
        file1 = result.get("file1", "")
        file2 = result.get("file2", "")
        diff = result.get("diff", "")
        additions = result.get("additions", 0)
        deletions = result.get("deletions", 0)
        identical = result.get("identical", False)
        
        if identical:
            return f"Files are identical:\n[dim]{file1}[/dim]\n[dim]{file2}[/dim]"
        
        header = f"Comparing:\n[dim]{file1}[/dim]\n[dim]{file2}[/dim]\n\n"
        header += f"[green]+{additions}[/green] additions, [red]-{deletions}[/red] deletions\n\n"
        
        # Format diff with syntax highlighting
        if self.config.ui.syntax_highlighting:
            try:
                syntax = Syntax(
                    diff,
                    "diff",
                    theme="monokai",
                    word_wrap=True,
                )
                return Text.from_markup(header) + syntax
            except Exception:
                pass
        
        return header + diff
    
    def _format_generic_result(self, result: Dict[str, Any]) -> Any:
        """Generic result formatting"""
        # Try to format as JSON with syntax highlighting
        if self.config.ui.syntax_highlighting:
            try:
                return JSON.from_data(result)
            except Exception:
                pass
        
        # Fall back to string representation
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    def _build_tree_recursive(self, parent_node, data: Dict[str, Any]):
        """Recursively build tree structure"""
        for name, value in data.items():
            if isinstance(value, dict) and not value.get("path"):
                # Directory
                branch = parent_node.add(f"[bold blue]{name}/[/bold blue]")
                self._build_tree_recursive(branch, value)
            else:
                # File
                if isinstance(value, dict):
                    size = value.get("size_formatted", "")
                    language = value.get("language", "")
                    file_display = f"[green]{name}[/green]"
                    if size:
                        file_display += f" [dim]({size})[/dim]"
                    if language and language != "text":
                        file_display += f" [cyan]{language}[/cyan]"
                    parent_node.add(file_display)
                else:
                    parent_node.add(f"[green]{name}[/green]")
