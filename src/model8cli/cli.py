"""
Main CLI interface for 200Model8CLI

Provides the command-line interface using Click framework with rich terminal UI.
"""

import asyncio
import sys
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core.config import Config
from .core.api import OpenRouterClient
from .core.models import ModelManager
from .core.session import SessionManager
from .tools.base import ToolRegistry
from .tools.file_ops import FileOperations
from .tools.web_tools import WebTools
from .tools.git_tools import GitTools
from .tools.github_tools import GitHubTools
from .tools.system_tools import SystemTools
from .tools.code_tools import CodeTools
from .tools.knowledge_tools import KnowledgeTools
from .tools.workflow_tools import WorkflowTools
from .tools.ollama_tools import OllamaTools
from .ui.interactive import InteractiveMode
from .ui.formatting import RichFormatter

# Initialize console and logger
console = Console()
logger = structlog.get_logger(__name__)


def setup_logging(level: str = "INFO"):
    """Setup structured logging"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@click.group(invoke_without_command=True)
@click.option('--config', '-c', type=click.Path(), help='Configuration file path')
@click.option('--model', '-m', help='Model to use for this session')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def main(ctx, config: Optional[str], model: Optional[str], verbose: bool, debug: bool):
    """200Model8CLI Agent

    A sophisticated command-line interface tool that supports multiple AI providers
    (OpenRouter, Ollama, Groq) with comprehensive tool calling capabilities.
    """
    import os

    # Setup logging
    log_level = "DEBUG" if debug else ("INFO" if verbose else "WARNING")
    setup_logging(log_level)

    # Check if we're setting an API key - if so, skip validation
    if ctx.invoked_subcommand == 'set-api-key':
        os.environ["SKIP_API_KEY_VALIDATION"] = "1"

    # Load configuration
    try:
        config_path = Path(config) if config else None
        app_config = Config(config_path)

        # Override model if specified
        if model:
            app_config.models.default = model

        ctx.ensure_object(dict)
        ctx.obj['config'] = app_config

    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)

    # If no subcommand, start interactive mode
    if ctx.invoked_subcommand is None:
        asyncio.run(start_interactive_mode(app_config))


@main.command()
@click.pass_context
def interactive(ctx):
    """Start interactive mode"""
    config = ctx.obj['config']
    # Skip API key validation for interactive mode if no key is set
    import os
    if not config.api.openrouter_key:
        os.environ["SKIP_API_KEY_VALIDATION"] = "1"
    try:
        asyncio.run(start_interactive_mode(config))
    finally:
        # Clean up the environment variable
        if "SKIP_API_KEY_VALIDATION" in os.environ:
            del os.environ["SKIP_API_KEY_VALIDATION"]


@main.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--encoding', default='utf-8', help='File encoding')
@click.pass_context
def read(ctx, path: str, encoding: str):
    """Read a file"""
    config = ctx.obj['config']
    asyncio.run(read_file_command(config, path, encoding))


@main.command()
@click.argument('path', type=click.Path())
@click.argument('content')
@click.option('--encoding', default='utf-8', help='File encoding')
@click.option('--backup/--no-backup', default=True, help='Create backup')
@click.pass_context
def write(ctx, path: str, content: str, encoding: str, backup: bool):
    """Write content to a file"""
    config = ctx.obj['config']
    asyncio.run(write_file_command(config, path, content, encoding, backup))


@main.command()
@click.argument('path', type=click.Path(exists=True))
@click.argument('changes')
@click.option('--backup/--no-backup', default=True, help='Create backup')
@click.pass_context
def edit(ctx, path: str, changes: str, backup: bool):
    """Edit a file with AI assistance"""
    config = ctx.obj['config']
    asyncio.run(edit_file_command(config, path, changes, backup))


@main.command()
@click.argument('path')
@click.option('--parents', is_flag=True, help='Create parent directories as needed')
@click.pass_context
def mkdir(ctx, path: str, parents: bool):
    """Create a directory"""
    import os
    try:
        if parents:
            os.makedirs(path, exist_ok=True)
        else:
            os.mkdir(path)
        click.echo(f"✅ Directory created: {path}")
    except FileExistsError:
        click.echo(f"❌ Directory already exists: {path}")
    except Exception as e:
        click.echo(f"❌ Failed to create directory: {e}")


@main.command()
@click.option('--directory', '-d', default='.', help='Directory to search')
@click.option('--pattern', '-p', help='File name pattern')
@click.option('--content', '-c', help='Content to search for')
@click.option('--recursive/--no-recursive', default=True, help='Recursive search')
@click.option('--case-sensitive', is_flag=True, help='Case sensitive search')
@click.option('--max-results', default=100, help='Maximum results')
@click.pass_context
def search(ctx, directory: str, pattern: Optional[str], content: Optional[str], 
          recursive: bool, case_sensitive: bool, max_results: int):
    """Search for files and content"""
    config = ctx.obj['config']
    asyncio.run(search_files_command(
        config, directory, pattern, content, recursive, case_sensitive, max_results
    ))


@main.command()
@click.pass_context
def models(ctx):
    """List available models"""
    config = ctx.obj['config']
    asyncio.run(list_models_command(config))


@main.command()
@click.argument('model_name')
@click.pass_context
def use_model(ctx, model_name: str):
    """Switch to a different model"""
    config = ctx.obj['config']
    asyncio.run(switch_model_command(config, model_name))


@main.command()
@click.pass_context
def sessions(ctx):
    """List conversation sessions"""
    config = ctx.obj['config']
    asyncio.run(list_sessions_command(config))


@main.command()
@click.pass_context
def config_info(ctx):
    """Show configuration information"""
    config = ctx.obj['config']
    show_config_info(config)


@main.command()
@click.argument('api_key')
@click.pass_context
def set_api_key(ctx, api_key: str):
    """Set and save OpenRouter API key"""
    import os
    # Skip API key validation when setting the key
    os.environ["SKIP_API_KEY_VALIDATION"] = "1"
    try:
        config = ctx.obj['config']
        asyncio.run(set_api_key_command(config, api_key))
    finally:
        # Clean up the environment variable
        if "SKIP_API_KEY_VALIDATION" in os.environ:
            del os.environ["SKIP_API_KEY_VALIDATION"]


@main.command()
@click.argument('api_key')
@click.pass_context
def set_groq_key(ctx, api_key: str):
    """Set and save Groq API key"""
    import os
    # Skip API key validation when setting the key
    os.environ["SKIP_API_KEY_VALIDATION"] = "1"
    try:
        config = ctx.obj['config']
        asyncio.run(set_groq_key_command(config, api_key))
    finally:
        # Clean up the environment variable
        if "SKIP_API_KEY_VALIDATION" in os.environ:
            del os.environ["SKIP_API_KEY_VALIDATION"]


@main.command()
@click.argument('token')
@click.pass_context
def set_github_token(ctx, token: str):
    """Set and save GitHub token"""
    import os
    # Skip API key validation when setting the token
    os.environ["SKIP_API_KEY_VALIDATION"] = "1"
    try:
        config = ctx.obj['config']
        asyncio.run(set_github_token_command(config, token))
    finally:
        # Clean up the environment variable
        if "SKIP_API_KEY_VALIDATION" in os.environ:
            del os.environ["SKIP_API_KEY_VALIDATION"]


@main.command()
@click.argument('code_or_file')
@click.option('--save', help='Save code to file before running')
@click.option('--file', is_flag=True, help='Treat argument as a file path')
@click.pass_context
def run_python(ctx, code_or_file: str, save: str = None, file: bool = False):
    """Run Python code directly or execute a Python file"""
    asyncio.run(run_python_command(code_or_file, save, file))


@main.command()
@click.argument('request', nargs=-1, required=True)
@click.pass_context
def ask(ctx, request):
    """Ask AI to do something in natural language"""
    config = ctx.obj['config']
    request_text = ' '.join(request)
    asyncio.run(ask_ai_command(config, request_text))


# Remove the problematic switch command - use python switch_model.py instead


@click.command()
@click.option('--free-only', is_flag=True, help='Show only free models')
@click.option('--update', is_flag=True, help='Update model list from OpenRouter')
def models_standalone(free_only, update):
    """List available models (standalone)"""
    asyncio.run(list_available_models_command(free_only, update))

# Add standalone models command to main
main.add_command(models_standalone, name="models")


@main.command()
@click.argument('task', nargs=-1, required=True)
@click.option('--browser', default='default', help='Browser to use for web tasks')
@click.option('--verbose', is_flag=True, help='Show detailed execution steps')
@click.pass_context
def agent(ctx, task, browser, verbose):
    """Advanced AI agent for autonomous task execution"""
    config = ctx.obj['config']
    task_description = ' '.join(task)
    asyncio.run(agent_command(config, task_description, browser, verbose))


@main.command()
@click.argument('query')
@click.pass_context
def search(ctx, query):
    """Quick web search"""
    config = ctx.obj['config']
    asyncio.run(quick_search_command(config, query))


@main.command()
@click.argument('command')
@click.pass_context
def cmd(ctx, command):
    """Execute a terminal command"""
    config = ctx.obj['config']
    asyncio.run(quick_command_execute(config, command))


@main.command()
@click.argument('task', nargs=-1, required=True)
@click.option('--browser', default='default', help='Browser to use for web tasks')
@click.option('--verbose', is_flag=True, help='Show detailed execution steps')
@click.pass_context
def agent(ctx, task, browser: str, verbose: bool):
    """Advanced AI agent for autonomous task execution"""
    config = ctx.obj['config']
    task_text = ' '.join(task)
    asyncio.run(agent_command(config, task_text, browser, verbose))


@main.command()
@click.pass_context
def self_aware(ctx):
    """Start self-aware agent mode - I can manage my own code!"""
    config = ctx.obj['config']
    asyncio.run(self_aware_agent_command(config))


@main.command()
@click.argument('github_token', required=True)
@click.option('--repo-name', default='200model8cli', help='Repository name')
@click.option('--private', is_flag=True, help='Create private repository')
@click.pass_context
def self_publish(ctx, github_token: str, repo_name: str, private: bool):
    """Create GitHub repo and publish the CLI itself"""
    asyncio.run(self_publish_command(ctx.obj['config'], github_token, repo_name, private))


@main.command()
@click.argument('github_token', required=True)
@click.option('--version', default='patch', help='Version bump type (patch, minor, major)')
@click.pass_context
def self_update(ctx, github_token: str, version: str):
    """Update and republish the CLI to GitHub and NPM"""
    asyncio.run(self_update_command(ctx.obj['config'], github_token, version))


@main.command()
@click.pass_context
def switch(ctx):
    """Switch to a different model (interactive)"""
    # Skip API key validation for model switching
    import os
    os.environ["SKIP_API_KEY_VALIDATION"] = "1"
    try:
        asyncio.run(interactive_switch_model_command(ctx.obj['config']))
    finally:
        # Clean up the environment variable
        if "SKIP_API_KEY_VALIDATION" in os.environ:
            del os.environ["SKIP_API_KEY_VALIDATION"]


@main.command()
@click.pass_context
def version(ctx):
    """Show version information"""
    show_version_info()


@main.command()
@click.option('--set', 'set_model', help='Set a local model as default')
@click.pass_context
def local(ctx, set_model: Optional[str]):
    """List and manage local Ollama models"""
    asyncio.run(local_models_command(ctx.obj['config'], set_model))


@main.group(invoke_without_command=True)
@click.pass_context
def ollama(ctx):
    """Ollama local model management and optimization"""
    if ctx.invoked_subcommand is None:
        console.print("[blue]Ollama Commands:[/blue]")
        console.print("  list       - List available local models")
        console.print("  switch     - Switch to an Ollama model (interactive)")
        console.print("  recommend  - Get model recommendations for tool calling")
        console.print("  test       - Test tool calling capabilities")
        console.print("  optimize   - Get optimization tips")


@ollama.command()
@click.pass_context
def list(ctx):
    """List available Ollama models"""
    asyncio.run(ollama_list_command(ctx.obj['config']))


@ollama.command()
@click.pass_context
def switch(ctx):
    """Switch to an Ollama model (interactive)"""
    asyncio.run(ollama_switch_command(ctx.obj['config']))


@ollama.command()
@click.option('--use-case', default='tool_calling',
              type=click.Choice(['tool_calling', 'coding', 'general', 'reasoning']),
              help='Use case for model selection')
@click.option('--size', 'size_preference', default='medium',
              type=click.Choice(['small', 'medium', 'large', 'any']),
              help='Model size preference')
@click.pass_context
def recommend(ctx, use_case: str, size_preference: str):
    """Get Ollama model recommendations"""
    asyncio.run(ollama_recommend_command(ctx.obj['config'], use_case, size_preference))


@ollama.command()
@click.argument('model')
@click.option('--test-type', default='basic',
              type=click.Choice(['basic', 'complex', 'multiple_tools']),
              help='Type of test to run')
@click.pass_context
def test(ctx, model: str, test_type: str):
    """Test tool calling capabilities of an Ollama model"""
    asyncio.run(ollama_test_command(ctx.obj['config'], model, test_type))


@ollama.command()
@click.option('--ram', type=float, help='System RAM in GB')
@click.option('--gpu/--no-gpu', default=None, help='Has GPU acceleration')
@click.option('--gpu-memory', type=float, help='GPU memory in GB')
@click.pass_context
def optimize(ctx, ram: float, gpu: bool, gpu_memory: float):
    """Get optimization tips for Ollama tool calling"""
    system_info = {}
    if ram:
        system_info['ram_gb'] = ram
    if gpu is not None:
        system_info['has_gpu'] = gpu
    if gpu_memory:
        system_info['gpu_memory_gb'] = gpu_memory

    asyncio.run(ollama_optimize_command(ctx.obj['config'], system_info if system_info else None))


@main.group(invoke_without_command=True)
@click.option('--set', 'set_model', help='Set a Groq model as default')
@click.pass_context
def groq(ctx, set_model: Optional[str]):
    """List and manage Groq models"""
    if ctx.invoked_subcommand is None:
        asyncio.run(groq_models_command(ctx.obj['config'], set_model))


@groq.command()
@click.pass_context
def switch(ctx):
    """Switch to a different Groq model (interactive)"""
    asyncio.run(groq_switch_command(ctx.obj['config']))


@main.group(invoke_without_command=True)
@click.pass_context
def github(ctx):
    """GitHub integration commands"""
    if ctx.invoked_subcommand is None:
        console.print("[blue]GitHub Integration Commands:[/blue]")
        console.print("  create-repo    - Create a new repository")
        console.print("  create-pr      - Create a pull request")
        console.print("  list-issues    - List repository issues")
        console.print("  create-issue   - Create a new issue")
        console.print("  list-prs       - List pull requests")
        console.print("  workflow       - Execute GitHub workflows")


@github.command()
@click.argument('name')
@click.option('--description', '-d', default='', help='Repository description')
@click.option('--private', is_flag=True, help='Create private repository')
@click.option('--gitignore', help='Gitignore template (e.g., Python, Node)')
@click.option('--license', help='License template (e.g., mit, apache-2.0)')
@click.pass_context
def create_repo(ctx, name: str, description: str, private: bool, gitignore: str, license: str):
    """Create a new GitHub repository"""
    asyncio.run(github_create_repo_command(ctx.obj['config'], name, description, private, gitignore, license))


@github.command()
@click.argument('owner')
@click.argument('repo')
@click.argument('title')
@click.argument('head')
@click.option('--body', '-b', default='', help='Pull request description')
@click.option('--base', default='main', help='Base branch')
@click.option('--draft', is_flag=True, help='Create as draft PR')
@click.pass_context
def create_pr(ctx, owner: str, repo: str, title: str, head: str, body: str, base: str, draft: bool):
    """Create a pull request"""
    asyncio.run(github_create_pr_command(ctx.obj['config'], owner, repo, title, head, body, base, draft))


@github.command()
@click.argument('owner')
@click.argument('repo')
@click.option('--state', default='open', help='Issue state (open, closed, all)')
@click.option('--labels', help='Comma-separated list of labels')
@click.option('--limit', default=30, help='Maximum number of issues')
@click.pass_context
def list_issues(ctx, owner: str, repo: str, state: str, labels: str, limit: int):
    """List repository issues"""
    asyncio.run(github_list_issues_command(ctx.obj['config'], owner, repo, state, labels, limit))


@github.command()
@click.argument('owner')
@click.argument('repo')
@click.argument('title')
@click.option('--body', '-b', default='', help='Issue description')
@click.option('--labels', help='Comma-separated list of labels')
@click.option('--assignees', help='Comma-separated list of assignees')
@click.pass_context
def create_issue(ctx, owner: str, repo: str, title: str, body: str, labels: str, assignees: str):
    """Create a new issue"""
    labels_list = labels.split(',') if labels else None
    assignees_list = assignees.split(',') if assignees else None
    asyncio.run(github_create_issue_command(ctx.obj['config'], owner, repo, title, body, labels_list, assignees_list))


@github.command()
@click.argument('owner')
@click.argument('repo')
@click.option('--state', default='open', help='PR state (open, closed, all)')
@click.option('--base', help='Base branch to filter by')
@click.option('--head', help='Head branch to filter by')
@click.option('--limit', default=30, help='Maximum number of PRs')
@click.pass_context
def list_prs(ctx, owner: str, repo: str, state: str, base: str, head: str, limit: int):
    """List pull requests"""
    asyncio.run(github_list_prs_command(ctx.obj['config'], owner, repo, state, base, head, limit))


@main.command()
@click.pass_context
def learn(ctx):
    """Start interactive learning mode"""
    config = ctx.obj['config']
    asyncio.run(learning_mode_command(config))


@main.group(invoke_without_command=True)
@click.pass_context
def knowledge(ctx):
    """Knowledge management commands"""
    if ctx.invoked_subcommand is None:
        console.print("[blue]Knowledge Management Commands:[/blue]")
        console.print("  search     - Search the knowledge base")
        console.print("  add        - Add new knowledge entry")
        console.print("  categories - List knowledge categories")


@knowledge.command()
@click.argument('query')
@click.option('--category', help='Category to search within')
@click.option('--limit', default=10, help='Maximum number of results')
@click.pass_context
def search(ctx, query: str, category: str, limit: int):
    """Search the knowledge base"""
    asyncio.run(knowledge_search_command(ctx.obj['config'], query, category, limit))


@knowledge.command()
@click.argument('title')
@click.argument('content')
@click.argument('category')
@click.option('--tags', help='Comma-separated tags')
@click.pass_context
def add(ctx, title: str, content: str, category: str, tags: str):
    """Add knowledge entry"""
    tags_list = tags.split(',') if tags else None
    asyncio.run(knowledge_add_command(ctx.obj['config'], title, content, category, tags_list))


@knowledge.command()
@click.pass_context
def categories(ctx):
    """List knowledge categories"""
    asyncio.run(knowledge_categories_command(ctx.obj['config']))


@main.group(invoke_without_command=True)
@click.pass_context
def workflow(ctx):
    """Workflow automation commands"""
    if ctx.invoked_subcommand is None:
        console.print("[blue]Workflow Automation Commands:[/blue]")
        console.print("  execute    - Execute a workflow or template")
        console.print("  list       - List available workflows and templates")
        console.print("  create     - Create a custom workflow")
        console.print("  template   - Get workflow template details")


@workflow.command()
@click.argument('workflow_id')
@click.option('--variables', help='JSON string of variables to pass')
@click.option('--template', is_flag=True, help='Execute as template')
@click.pass_context
def execute(ctx, workflow_id: str, variables: str, template: bool):
    """Execute a workflow or template"""
    variables_dict = {}
    if variables:
        try:
            variables_dict = json.loads(variables)
        except json.JSONDecodeError:
            console.print("[red]❌ Invalid JSON in variables[/red]")
            return

    asyncio.run(workflow_execute_command(ctx.obj['config'], workflow_id, variables_dict, template))


@workflow.command()
@click.option('--templates/--no-templates', default=True, help='Include templates')
@click.pass_context
def list(ctx, templates: bool):
    """List workflows and templates"""
    asyncio.run(workflow_list_command(ctx.obj['config'], templates))


@workflow.command()
@click.argument('workflow_id')
@click.argument('name')
@click.argument('description')
@click.option('--steps', help='JSON string of workflow steps')
@click.option('--variables', help='JSON string of default variables')
@click.option('--tags', help='Comma-separated tags')
@click.pass_context
def create(ctx, workflow_id: str, name: str, description: str, steps: str, variables: str, tags: str):
    """Create a custom workflow"""
    if not steps:
        console.print("[red]❌ Steps are required (use --steps with JSON)[/red]")
        return

    try:
        steps_list = json.loads(steps)
        variables_dict = json.loads(variables) if variables else {}
        tags_list = tags.split(',') if tags else []

        asyncio.run(workflow_create_command(
            ctx.obj['config'], workflow_id, name, description,
            steps_list, variables_dict, tags_list
        ))
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Invalid JSON: {e}[/red]")


@workflow.command()
@click.argument('template_name')
@click.pass_context
def template(ctx, template_name: str):
    """Get workflow template details"""
    asyncio.run(workflow_template_command(ctx.obj['config'], template_name))


# Command implementations

async def start_interactive_mode(config: Config):
    """Start interactive mode"""
    try:
        # Display the new ASCII banner
        from .ui.banner import display_welcome_banner
        from . import __version__
        display_welcome_banner(model=config.default_model, version=__version__)
        
        # Initialize components
        async with OpenRouterClient(config) as api_client:
            model_manager = ModelManager(config, api_client)
            session_manager = SessionManager(config)
            tool_registry = ToolRegistry(config)
            
            # Register all tools
            file_ops = FileOperations(config)
            for tool in file_ops.get_tools():
                tool_registry.register_tool(tool)

            if config.tools.web_search_enabled:
                web_tools = WebTools(config)
                for tool in web_tools.get_tools():
                    tool_registry.register_tool(tool)

                # Also register browser tools for web interaction
                from .tools.browser_tools import BrowserTools
                browser_tools = BrowserTools(config)
                for tool in browser_tools.get_tools():
                    tool_registry.register_tool(tool)

            if config.tools.git_operations_enabled:
                git_tools = GitTools(config)
                for tool in git_tools.get_tools():
                    tool_registry.register_tool(tool)

            if config.tools.system_operations_enabled:
                system_tools = SystemTools(config)
                for tool in system_tools.get_tools():
                    tool_registry.register_tool(tool)

            if config.tools.code_analysis_enabled:
                code_tools = CodeTools(config)
                for tool in code_tools.get_tools():
                    tool_registry.register_tool(tool)
            
            # Initialize model manager
            await model_manager.initialize()
            
            # Start interactive mode
            interactive_mode = InteractiveMode(
                config, api_client, model_manager, session_manager, tool_registry
            )
            
            await interactive_mode.start()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("Interactive mode failed", error=str(e))


async def read_file_command(config: Config, path: str, encoding: str):
    """Read file command"""
    try:
        tool_registry = ToolRegistry(config)
        file_ops = FileOperations(config)
        
        for tool in file_ops.get_tools():
            tool_registry.register_tool(tool)
        
        result = await tool_registry.execute_tool("read_file", path=path, encoding=encoding)
        
        if result.success:
            file_data = result.result
            console.print(Panel(
                file_data['content'],
                title=f"[green]{file_data['path']}[/green]",
                subtitle=f"Size: {file_data['size_formatted']} | Language: {file_data['language']} | Lines: {file_data['line_count']}"
            ))
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            
    except Exception as e:
        console.print(f"[red]Command failed: {e}[/red]")


async def write_file_command(config: Config, path: str, content: str, encoding: str, backup: bool):
    """Write file command"""
    try:
        tool_registry = ToolRegistry(config)
        file_ops = FileOperations(config)
        
        for tool in file_ops.get_tools():
            tool_registry.register_tool(tool)
        
        result = await tool_registry.execute_tool(
            "write_file", 
            path=path, 
            content=content, 
            encoding=encoding, 
            create_backup=backup
        )
        
        if result.success:
            file_data = result.result
            console.print(f"[green]✓[/green] File written: {file_data['path']}")
            console.print(f"  Size: {file_data['size_formatted']}")
            if file_data['backup_created']:
                console.print(f"  Backup: {file_data['backup_path']}")
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            
    except Exception as e:
        console.print(f"[red]Command failed: {e}[/red]")


async def edit_file_command(config: Config, path: str, changes: str, backup: bool):
    """Edit file command"""
    try:
        tool_registry = ToolRegistry(config)
        file_ops = FileOperations(config)
        
        for tool in file_ops.get_tools():
            tool_registry.register_tool(tool)
        
        result = await tool_registry.execute_tool(
            "edit_file", 
            path=path, 
            changes=changes, 
            create_backup=backup
        )
        
        if result.success:
            file_data = result.result
            console.print(f"[green]✓[/green] File edited: {file_data['path']}")
            console.print(f"  Changes: {file_data['changes_applied']}")
            console.print(f"  Size: {file_data['size_formatted']}")
            if file_data['backup_created']:
                console.print(f"  Backup: {file_data['backup_path']}")
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            
    except Exception as e:
        console.print(f"[red]Command failed: {e}[/red]")


async def search_files_command(
    config: Config, 
    directory: str, 
    pattern: Optional[str], 
    content: Optional[str],
    recursive: bool, 
    case_sensitive: bool, 
    max_results: int
):
    """Search files command"""
    try:
        tool_registry = ToolRegistry(config)
        file_ops = FileOperations(config)
        
        for tool in file_ops.get_tools():
            tool_registry.register_tool(tool)
        
        result = await tool_registry.execute_tool(
            "search_files",
            directory=directory,
            pattern=pattern,
            content=content,
            recursive=recursive,
            case_sensitive=case_sensitive,
            max_results=max_results
        )
        
        if result.success:
            search_data = result.result
            results = search_data['results']
            
            if not results:
                console.print("[yellow]No results found[/yellow]")
                return
            
            table = Table(title=f"Search Results ({len(results)} found)")
            table.add_column("Type", style="cyan")
            table.add_column("Path", style="green")
            table.add_column("Size", justify="right")
            table.add_column("Language", style="blue")
            table.add_column("Details", style="dim")
            
            for item in results:
                details = ""
                if item['type'] == 'content_match':
                    details = f"{item['total_matches']} matches"
                
                table.add_row(
                    item['type'].replace('_', ' ').title(),
                    item['path'],
                    item['size_formatted'],
                    item['language'],
                    details
                )
            
            console.print(table)
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            
    except Exception as e:
        console.print(f"[red]Command failed: {e}[/red]")


async def interactive_switch_model_command(config: Config):
    """Interactive model switching with all available free models"""
    try:
        import os
        import httpx
        from rich.prompt import Prompt

        console.print("🔍 Fetching all available models from OpenRouter...")

        # Check if API key is available
        if not config.api.openrouter_key:
            console.print("[red]❌ OpenRouter API key is required for model switching[/red]")
            console.print("[yellow]💡 Get a free API key at: https://openrouter.ai/keys[/yellow]")
            console.print("[yellow]💡 Then set it with: 200model8cli set-api-key YOUR_KEY[/yellow]")
            return

        headers = {
            "Authorization": f"Bearer {config.api.openrouter_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])

                # Filter for free models
                free_models = [m for m in models if m.get("pricing", {}).get("prompt", "0") == "0"]

                console.print(f"\n[green]✅ Found {len(free_models)} free models![/green]\n")

                # Show prioritized models first
                prioritized = [
                    "deepseek/deepseek-chat-v3-0324:free",
                    "deepseek/deepseek-chat:free",
                    "deepseek/deepseek-r1:free",
                    "google/gemma-3-27b-it:free",
                    "moonshotai/kimi-k2:free"
                ]

                console.print("[yellow]⭐ RECOMMENDED MODELS (Best tool calling):[/yellow]")
                for i, model_id in enumerate(prioritized, 1):
                    model_data = next((m for m in free_models if m["id"] == model_id), None)
                    if model_data:
                        name = model_data.get("name", "Unknown")
                        console.print(f"  {i:2d}. [green]{model_id}[/green] - {name}")

                console.print(f"\n[cyan]📋 ALL FREE MODELS ({len(free_models)} total):[/cyan]")
                for i, model in enumerate(free_models[:50], len(prioritized) + 1):
                    model_id = model.get("id", "Unknown")
                    name = model.get("name", "No description")
                    if model_id not in prioritized:
                        console.print(f"  {i:2d}. [cyan]{model_id}[/cyan] - {name}")

                if len(free_models) > 50:
                    console.print(f"[dim]... and {len(free_models) - 50} more models[/dim]")

                # Get user choice
                choice = Prompt.ask(
                    "\n[yellow]Enter model number or model ID[/yellow]",
                    default="1"
                )

                # Parse choice
                selected_model = None
                if choice.isdigit():
                    idx = int(choice) - 1
                    if idx < len(prioritized):
                        selected_model = prioritized[idx]
                    elif idx < len(prioritized) + len(free_models):
                        selected_model = free_models[idx - len(prioritized)]["id"]
                else:
                    # Direct model ID
                    selected_model = choice

                if selected_model:
                    # Update config
                    config.models.default = selected_model
                    config.save_config()
                    console.print(f"[green]✅ Switched to: {selected_model}[/green]")
                    console.print("[cyan]💡 Try: 200model8cli ask 'hello'[/cyan]")
                else:
                    console.print("[red]❌ Invalid selection[/red]")

            else:
                console.print(f"[red]❌ Error fetching models: HTTP {response.status_code}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


async def list_models_command(config: Config):
    """List available models"""
    try:
        async with OpenRouterClient(config) as api_client:
            model_manager = ModelManager(config, api_client)
            await model_manager.initialize()

            models = model_manager.get_available_models()

            table = Table(title="Available Models")
            table.add_column("Model ID", style="green")
            table.add_column("Name", style="blue")
            table.add_column("Context", justify="right")
            table.add_column("Capabilities", style="cyan")
            table.add_column("Recommended For", style="dim")

            for model in models:
                capabilities = ", ".join([cap.value for cap in model.capabilities])
                recommended = ", ".join(model.recommended_for)

                table.add_row(
                    model.info.id,
                    model.info.name,
                    f"{model.info.context_length:,}",
                    capabilities[:50] + "..." if len(capabilities) > 50 else capabilities,
                    recommended[:50] + "..." if len(recommended) > 50 else recommended
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to list models: {e}[/red]")


async def list_sessions_command(config: Config):
    """List conversation sessions"""
    try:
        session_manager = SessionManager(config)
        sessions = session_manager.list_sessions()
        
        if not sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return
        
        table = Table(title="Conversation Sessions")
        table.add_column("Name", style="green")
        table.add_column("Model", style="blue")
        table.add_column("Messages", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Created", style="dim")
        table.add_column("Updated", style="dim")
        
        for session in sessions:
            from datetime import datetime
            created = datetime.fromtimestamp(session.created_at).strftime("%Y-%m-%d %H:%M")
            updated = datetime.fromtimestamp(session.updated_at).strftime("%Y-%m-%d %H:%M")
            
            table.add_row(
                session.name,
                session.model,
                str(session.total_messages),
                f"{session.total_tokens:,}",
                created,
                updated
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Failed to list sessions: {e}[/red]")


def show_config_info(config: Config):
    """Show configuration information"""
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Config Path", str(config.config_path))
    table.add_row("Default Model", config.default_model)
    table.add_row("API Timeout", f"{config.api_timeout}s")
    table.add_row("Max Retries", str(config.max_retries))
    table.add_row("Streaming", str(config.ui.streaming))
    table.add_row("Syntax Highlighting", str(config.ui.syntax_highlighting))
    table.add_row("File Operations", str(config.tools.file_operations_enabled))
    table.add_row("Web Search", str(config.tools.web_search_enabled))
    table.add_row("Git Operations", str(config.tools.git_operations_enabled))
    
    console.print(table)


def show_version_info():
    """Show version information"""
    from . import __version__, __author__
    
    console.print(Panel.fit(
        f"[bold blue]200Model8CLI[/bold blue]\n"
        f"Version: [green]{__version__}[/green]\n"
        f"Author: [cyan]{__author__}[/cyan]\n"
        f"Python: [yellow]{sys.version.split()[0]}[/yellow]",
        title="Version Information"
    ))


async def switch_model_command(config: Config, model_name: str):
    """Switch to a different model"""
    try:
        # For free models, local models, or when validation is skipped, allow any model
        if (":free" in model_name or
            model_name.startswith("ollama/") or
            model_name in config.models.available):

            # Update config
            config.models.default = model_name
            config.save_config()
            console.print(f"[green]✅ Switched to model: {model_name}[/green]")
            console.print("[cyan]💡 Try: 200model8cli ask 'hello'[/cyan]")

        else:
            # For unknown models, warn but still allow
            console.print(f"[yellow]⚠️ Model '{model_name}' not in known list, but setting anyway[/yellow]")
            config.models.default = model_name
            config.save_config()
            console.print(f"[green]✅ Switched to model: {model_name}[/green]")
            console.print("[yellow]💡 If this model doesn't work, try: 200model8cli switch[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error switching model: {e}[/red]")


async def set_api_key_command(config: Config, api_key: str):
    """Set and save API key"""
    try:
        import os

        # Validate API key format
        if not api_key.startswith("sk-or-v1-"):
            console.print(f"[red]❌ Invalid API key format. Should start with 'sk-or-v1-'[/red]")
            return

        # Set environment variable to skip validation during save
        os.environ["SKIP_API_KEY_VALIDATION"] = "1"

        # Update config
        config.api.openrouter_key = api_key

        # Save to config file
        config._save_api_key_to_config(api_key)

        # Remove the skip flag
        if "SKIP_API_KEY_VALIDATION" in os.environ:
            del os.environ["SKIP_API_KEY_VALIDATION"]

        console.print(f"[green]✅ API key saved successfully![/green]")
        console.print(f"[green]✅ You can now use 200model8cli without setting the API key each time[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error saving API key: {e}[/red]")


async def set_groq_key_command(config: Config, api_key: str):
    """Set and save Groq API key"""
    try:
        import os

        # Validate API key format
        if not api_key.startswith("gsk_"):
            console.print("[red]❌ Invalid Groq API key format. Groq keys start with 'gsk_'[/red]")
            return

        # Set the API key in config
        config.api.groq_key = api_key

        # Save to config file
        config.save_config()

        # Also set environment variable for this session
        os.environ["GROQ_API_KEY"] = api_key

        console.print("[green]✅ Groq API key saved successfully![/green]")
        console.print("[cyan]💡 You can now use Groq models with: 200model8cli groq[/cyan]")
        console.print("[cyan]💡 Switch models with: 200model8cli groq switch[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error setting Groq API key: {e}[/red]")


async def run_python_command(code_or_file: str, save_file: str = None, is_file: bool = False):
    """Run Python code directly or execute a Python file"""
    try:
        import tempfile
        import subprocess
        from pathlib import Path

        # Check if it's a file path (either explicitly marked or has .py extension)
        if is_file or code_or_file.endswith('.py'):
            # Running an existing file
            file_path = Path(code_or_file)
            if not file_path.exists():
                console.print(f"[red]❌ File not found: {code_or_file}[/red]")
                return

            file_to_run = str(file_path)
            console.print(f"[blue]🐍 Running Python file: {file_to_run}[/blue]")

        else:
            # Running code as string
            if save_file:
                with open(save_file, 'w') as f:
                    f.write(code_or_file)
                console.print(f"[green]✅ Code saved to {save_file}[/green]")
                file_to_run = save_file
            else:
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code_or_file)
                    file_to_run = f.name

            console.print(f"[blue]🐍 Running Python code...[/blue]")

        # Execute the Python file
        result = subprocess.run(
            ["python", file_to_run],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Show results
        if result.stdout:
            console.print(f"[green]📤 Output:[/green]")
            console.print(result.stdout)

        if result.stderr:
            console.print(f"[red]❌ Error:[/red]")
            console.print(result.stderr)

        console.print(f"[blue]✅ Exit code: {result.returncode}[/blue]")

        # Clean up temp file if not saved and not an existing file
        if not save_file and not (is_file or code_or_file.endswith('.py')):
            import os
            os.unlink(file_to_run)

    except Exception as e:
        console.print(f"[red]❌ Error running Python: {e}[/red]")


async def ask_ai_command(config: Config, request: str):
    """Process a natural language request with AI"""
    try:
        from model8cli.ui.interactive import InteractiveMode
        from model8cli.ui.formatting import RichFormatter
        from model8cli.core.session import SessionManager
        from model8cli.core.api import OpenRouterClient
        from model8cli.core.models import ModelManager
        from model8cli.tools.base import ToolRegistry
        from model8cli.tools.file_ops import FileOperations
        from model8cli.tools.web_tools import WebTools
        from model8cli.tools.git_tools import GitTools
        from model8cli.tools.system_tools import SystemTools
        from model8cli.tools.code_tools import CodeTools

        # Create all required components
        api_client = OpenRouterClient(config)
        model_manager = ModelManager(config, api_client)
        session_manager = SessionManager(config)
        tool_registry = ToolRegistry(config)

        # Register ALL tools
        console.print(f"[blue]🔧 Registering tools...[/blue]")

        # File operations
        file_ops = FileOperations(config)
        for tool in file_ops.get_tools():
            tool_registry.register_tool(tool)

        # Web tools (for search)
        web_tools = WebTools(config)
        for tool in web_tools.get_tools():
            tool_registry.register_tool(tool)

        # Browser tools (for browser automation)
        from model8cli.tools.browser_tools import BrowserTools
        browser_tools = BrowserTools(config)
        for tool in browser_tools.get_tools():
            tool_registry.register_tool(tool)

        # Git tools
        git_tools = GitTools(config)
        for tool in git_tools.get_tools():
            tool_registry.register_tool(tool)

        # GitHub tools
        github_tools = GitHubTools(config)
        for tool in github_tools.get_tools():
            tool_registry.register_tool(tool)

        # Knowledge tools
        knowledge_tools = KnowledgeTools(config)
        for tool in knowledge_tools.get_tools():
            tool_registry.register_tool(tool)

        # Ollama tools
        ollama_tools = OllamaTools(config)
        for tool in ollama_tools.get_tools():
            tool_registry.register_tool(tool)

        # System tools (for terminal commands)
        system_tools = SystemTools(config)
        for tool in system_tools.get_tools():
            tool_registry.register_tool(tool)

        # Code tools
        code_tools = CodeTools(config)
        for tool in code_tools.get_tools():
            tool_registry.register_tool(tool)

        console.print(f"[green]✅ {len(tool_registry.tools)} tools registered[/green]")

        # Create interactive mode
        interactive = InteractiveMode(
            config=config,
            api_client=api_client,
            model_manager=model_manager,
            session_manager=session_manager,
            tool_registry=tool_registry
        )

        console.print(f"[blue]🤖 Processing request: {request}[/blue]")

        # Add system message to encourage tool use
        available_tools = list(tool_registry.tools.keys())
        system_prompt = f"""You are 200Model8CLI, an advanced AI assistant with comprehensive tool-calling capabilities. You have {len(available_tools)} tools available including:

• Web search (web_search)
• Browser automation (open_browser, search_browser) - You CAN open browsers and search
• File operations (read_file, write_file, create_directory, etc.)
• System operations (execute_command, get_system_info, etc.)
• Git operations (git_status, git_commit, etc.)
• Code analysis (analyze_code, run_code, etc.)

IMPORTANT: You should proactively use these tools to help users. When a user asks you to:
- Search for something: Use web_search or search_browser
- Open a browser: Use open_browser or search_browser
- Check files: Use list_directory or read_file
- Run commands: Use execute_command

Be helpful and use the appropriate tools to accomplish the user's request!"""

        session_manager.add_message("system", system_prompt)

        # Process the request
        await interactive._process_user_message(request)

    except Exception as e:
        console.print(f"[red]❌ Error processing request: {e}[/red]")


async def auto_switch_model_command(config: Config, list_models: bool = False):
    """Automatically switch to next available free model"""
    try:
        import os
        # Skip model validation during switching
        os.environ["SKIP_MODEL_VALIDATION"] = "true"

        # Use a simple list of known working models
        console.print("[blue]🔍 Using known working models...[/blue]")

        # Curated list of actually working free models
        working_free_models = [
            "deepseek/deepseek-r1:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "microsoft/phi-3-mini-4k-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free"
        ]

        if list_models:
            console.print("[blue]🔄 Available Free Models:[/blue]")
            for i, model in enumerate(working_free_models, 1):
                current = "← Current" if model == config.models.default else ""
                console.print(f"  {i}. {model} {current}")
            return

        # Find current model index
        current_model = config.models.default
        current_index = -1

        try:
            current_index = working_free_models.index(current_model)
        except ValueError:
            console.print(f"[yellow]⚠️ Current model '{current_model}' not in working list[/yellow]")

        # Switch to next model
        next_index = (current_index + 1) % len(working_free_models)
        next_model = working_free_models[next_index]

        # Update config file directly
        config_path = Path.home() / ".200model8cli" / "config.yaml"
        config_path.parent.mkdir(exist_ok=True)

        if config_path.exists():
            import yaml
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        else:
            config_data = {}

        if "models" not in config_data:
            config_data["models"] = {}
        config_data["models"]["default"] = next_model

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)

        console.print(f"[green]✅ Switched to: {next_model}[/green]")
        console.print(f"[blue]💡 Try: 200model8cli[/blue]")

        # Remove the skip flag
        if "SKIP_MODEL_VALIDATION" in os.environ:
            del os.environ["SKIP_MODEL_VALIDATION"]

    except Exception as e:
        console.print(f"[red]❌ Error switching model: {e}[/red]")
        # Remove the skip flag on error too
        if "SKIP_MODEL_VALIDATION" in os.environ:
            del os.environ["SKIP_MODEL_VALIDATION"]


async def simple_switch_model_command(list_models: bool = False):
    """Simple model switching without config validation"""
    try:
        from pathlib import Path
        import yaml

        # Curated list of actually working free models
        working_free_models = [
            "deepseek/deepseek-r1:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "microsoft/phi-3-mini-4k-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free"
        ]

        if list_models:
            console.print("[blue]🔄 Available Free Models:[/blue]")
            for i, model in enumerate(working_free_models, 1):
                console.print(f"  {i}. {model}")
            return

        # Get current model from config file
        config_path = Path.home() / ".200model8cli" / "config.yaml"
        current_model = None

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f) or {}
                current_model = config_data.get("models", {}).get("default")
            except:
                pass

        # Find current model index
        current_index = -1
        if current_model:
            try:
                current_index = working_free_models.index(current_model)
            except ValueError:
                console.print(f"[yellow]⚠️ Current model '{current_model}' not in working list[/yellow]")

        # Switch to next model
        next_index = (current_index + 1) % len(working_free_models)
        next_model = working_free_models[next_index]

        # Update config file
        config_path.parent.mkdir(exist_ok=True)

        if config_path.exists():
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        else:
            config_data = {}

        if "models" not in config_data:
            config_data["models"] = {}
        config_data["models"]["default"] = next_model

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)

        console.print(f"[green]✅ Switched to: {next_model}[/green]")
        console.print(f"[blue]💡 Try: 200model8cli[/blue]")

    except Exception as e:
        console.print(f"[red]❌ Error switching model: {e}[/red]")


async def list_available_models_command(free_only: bool = False, update: bool = False):
    """List available models from OpenRouter"""
    try:
        import httpx
        import os
        from pathlib import Path

        console.print("[blue]🔍 Fetching models from OpenRouter...[/blue]")

        # Get API key from environment or config
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            # Try to get from config file
            config_path = Path.home() / ".200model8cli" / "config.yaml"
            if config_path.exists():
                import yaml
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f) or {}
                api_key = config_data.get("api", {}).get("openrouter_key")

        if not api_key:
            console.print("[red]❌ No API key found. Set with: 200model8cli set-api-key YOUR_KEY[/red]")
            return

        # Fetch models from OpenRouter
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()

            models_data = response.json()
            models = models_data.get("data", [])

        # Filter models
        if free_only:
            free_models = [model for model in models if model.get("pricing", {}).get("prompt", "0") == "0"]
            models = free_models

        # Display models
        console.print(f"[green]✅ Found {len(models)} models[/green]")

        if free_only:
            console.print("[blue]🆓 Free Models:[/blue]")
        else:
            console.print("[blue]📋 All Models:[/blue]")

        for i, model in enumerate(models[:50], 1):  # Limit to first 50
            model_id = model.get("id", "unknown")
            name = model.get("name", "Unknown")
            pricing = model.get("pricing", {})
            prompt_price = pricing.get("prompt", "unknown")

            if prompt_price == "0":
                price_info = "[green]FREE[/green]"
            else:
                price_info = f"[yellow]${prompt_price}/1K tokens[/yellow]"

            console.print(f"  {i:2d}. {model_id} - {name} ({price_info})")

        if len(models) > 50:
            console.print(f"[dim]... and {len(models) - 50} more models[/dim]")

        # Update working models list if requested
        if update and free_only:
            free_model_ids = [model["id"] for model in models if model.get("pricing", {}).get("prompt", "0") == "0"]
            console.print(f"[blue]💡 Found {len(free_model_ids)} free models to add to switcher[/blue]")

            # Update the switch_model.py file
            update_switch_model_list(free_model_ids[:10])  # Use top 10 free models

    except Exception as e:
        console.print(f"[red]❌ Error fetching models: {e}[/red]")


def update_switch_model_list(model_ids):
    """Update the switch_model.py file with new model list"""
    try:
        switch_file = Path("switch_model.py")
        if switch_file.exists():
            content = switch_file.read_text()

            # Create new model list
            new_list = "        working_free_models = [\n"
            for model_id in model_ids:
                new_list += f'            "{model_id}",\n'
            new_list += "        ]"

            # Replace the old list
            import re
            pattern = r'working_free_models = \[.*?\]'
            new_content = re.sub(pattern, new_list.strip(), content, flags=re.DOTALL)

            switch_file.write_text(new_content)
            console.print("[green]✅ Updated switch_model.py with new free models[/green]")

    except Exception as e:
        console.print(f"[yellow]⚠️ Could not update switch_model.py: {e}[/yellow]")


async def quick_search_command(config: Config, query: str):
    """Quick web search without full AI interaction"""
    try:
        from model8cli.tools.web_tools import WebTools

        console.print(f"[blue]🔍 Searching for: {query}[/blue]")

        # Create web search tool
        web_search_tool = WebTools(config).get_tools()[0]  # Get the search tool
        result = await web_search_tool.execute(query, max_results=5)

        if result.success:
            console.print(f"[green]✅ Search Results:[/green]")
            console.print(result.result)
        else:
            console.print(f"[red]❌ Search failed: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error searching: {e}[/red]")


async def self_publish_command(config: Config, github_token: str, repo_name: str, private: bool):
    """Create GitHub repo and publish the CLI"""
    try:
        import requests
        import json
        import os
        import subprocess

        console.print(f"[blue]🚀 Publishing {repo_name} to GitHub...[/blue]")

        # Create GitHub repository
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        repo_data = {
            'name': repo_name,
            'description': '200Model8CLI - Advanced AI CLI with browser automation and tool calling',
            'private': private,
            'auto_init': False
        }

        response = requests.post('https://api.github.com/user/repos',
                               headers=headers, json=repo_data)

        if response.status_code == 201:
            repo_info = response.json()
            clone_url = repo_info['clone_url']
            console.print(f"[green]✅ Repository created: {repo_info['html_url']}[/green]")

            # Initialize git and push code
            cwd = os.getcwd()

            # Git commands
            commands = [
                ['git', 'init'],
                ['git', 'add', '.'],
                ['git', 'commit', '-m', 'Initial commit: 200Model8CLI with full capabilities'],
                ['git', 'branch', '-M', 'main'],
                ['git', 'remote', 'add', 'origin', clone_url.replace('https://', f'https://{github_token}@')],
                ['git', 'push', '-u', 'origin', 'main']
            ]

            for cmd in commands:
                result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
                if result.returncode != 0:
                    console.print(f"[yellow]⚠️ Git command failed: {' '.join(cmd)}[/yellow]")
                    console.print(f"[dim]{result.stderr}[/dim]")

            console.print(f"[green]✅ Code pushed to GitHub![/green]")
            console.print(f"[cyan]📦 To publish to NPM: npm publish[/cyan]")

        else:
            console.print(f"[red]❌ Failed to create repository: {response.text}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Self-publish error: {e}[/red]")


async def self_update_command(config: Config, github_token: str, version: str):
    """Update version and republish"""
    try:
        import subprocess
        import json

        console.print(f"[blue]🔄 Updating version ({version}) and republishing...[/blue]")

        # Update package.json version
        with open('package.json', 'r') as f:
            package_data = json.load(f)

        current_version = package_data['version']
        major, minor, patch = map(int, current_version.split('.'))

        if version == 'major':
            major += 1
            minor = 0
            patch = 0
        elif version == 'minor':
            minor += 1
            patch = 0
        else:  # patch
            patch += 1

        new_version = f"{major}.{minor}.{patch}"
        package_data['version'] = new_version

        with open('package.json', 'w') as f:
            json.dump(package_data, f, indent=2)

        # Git commit and push
        commands = [
            ['git', 'add', '.'],
            ['git', 'commit', '-m', f'Version bump to {new_version}'],
            ['git', 'push'],
            ['npm', 'publish']
        ]

        for cmd in commands:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(f"[green]✅ {' '.join(cmd)}[/green]")
            else:
                console.print(f"[red]❌ Failed: {' '.join(cmd)}[/red]")
                console.print(f"[dim]{result.stderr}[/dim]")

        console.print(f"[green]🎉 Updated to version {new_version} and published![/green]")

    except Exception as e:
        console.print(f"[red]❌ Self-update error: {e}[/red]")


async def agent_command(config: Config, task: str, browser: str, verbose: bool):
    """Execute an autonomous agent task"""
    try:
        from model8cli.agent.core import AdvancedAgent

        console.print(f"[blue]🤖 Agent Task: {task}[/blue]")
        if verbose:
            console.print(f"[dim]Browser: {browser}[/dim]")

        # Initialize agent
        agent = AdvancedAgent(config)

        # Execute task
        result = await agent.execute_task(task)

        if result["success"]:
            console.print(f"[green]✅ Task completed successfully![/green]")
            if verbose and "result" in result:
                console.print(f"[dim]Result: {result['result']}[/dim]")
        else:
            console.print(f"[red]❌ Agent error: {result.get('error', 'Unknown error')}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Agent error: {e}[/red]")
        logger.error("Agent command failed", error=str(e))


async def local_models_command(config: Config, set_model: Optional[str] = None):
    """List and manage local Ollama models"""
    try:
        from model8cli.core.ollama_client import OllamaClient
        from rich.table import Table

        console.print("[blue]🔍 Checking for local Ollama models...[/blue]")

        # Initialize Ollama client
        ollama_client = OllamaClient()

        # Check if Ollama is available
        if not await ollama_client.is_available():
            console.print("[red]❌ Ollama is not running or not installed[/red]")
            console.print("[yellow]💡 To use local models:[/yellow]")
            console.print("  1. Install Ollama from https://ollama.ai")
            console.print("  2. Start Ollama service")
            console.print("  3. Pull models with: ollama pull <model-name>")
            return

        # Get available models
        models = await ollama_client.list_models()

        if not models:
            console.print("[yellow]⚠️ No local models found[/yellow]")
            console.print("[cyan]💡 Pull models with: ollama pull llama2[/cyan]")
            return

        # Display models in a table
        table = Table(title=f"Local Ollama Models ({len(models)} found)")
        table.add_column("Model Name", style="green")
        table.add_column("Size", style="blue", justify="right")
        table.add_column("Modified", style="dim")
        table.add_column("Status", style="cyan")

        for i, model in enumerate(models, 1):
            # Format size
            size_gb = model.size / (1024**3)
            size_str = f"{size_gb:.1f} GB"

            # Format modified date
            from datetime import datetime
            modified = datetime.fromisoformat(model.modified_at.replace('Z', '+00:00'))
            modified_str = modified.strftime("%Y-%m-%d %H:%M")

            # Check if this is the current default
            current_default = config.models.default
            status = "Current" if f"ollama/{model.name}" == current_default else "Available"

            table.add_row(
                f"{i}. {model.name}",
                size_str,
                modified_str,
                status
            )

        console.print(table)

        # Important note about tool calling limitations
        console.print("\n[yellow]⚠️  Note: Local Ollama models have limited tool calling capabilities.[/yellow]")
        console.print("[yellow]   For full tool support (web search, browser automation, etc.), use OpenRouter or Groq models.[/yellow]")
        console.print("[cyan]💡 Switch to OpenRouter: 200model8cli switch[/cyan]")
        console.print("[cyan]💡 Switch to Groq: 200model8cli groq switch[/cyan]")

        # Handle setting a model as default
        if set_model:
            # Find the model
            model_found = None
            for model in models:
                if model.name == set_model or str(models.index(model) + 1) == set_model:
                    model_found = model
                    break

            if model_found:
                # Update config to use local model
                local_model_id = f"ollama/{model_found.name}"
                config.models.default = local_model_id
                config.save_config()
                console.print(f"[green]✅ Set default model to: {local_model_id}[/green]")
                console.print("[cyan]💡 Try: 200model8cli ask 'hello'[/cyan]")
            else:
                console.print(f"[red]❌ Model '{set_model}' not found[/red]")
        else:
            console.print("\n[cyan]💡 To set a local model as default:[/cyan]")
            console.print("  200model8cli local --set <model-name>")
            console.print("  200model8cli local --set <number>")

        await ollama_client.close()

    except Exception as e:
        console.print(f"[red]❌ Error managing local models: {e}[/red]")


async def quick_command_execute(config: Config, command: str):
    """Execute a terminal command directly"""
    try:
        from model8cli.tools.system_tools import SystemTools

        console.print(f"[blue]💻 Executing: {command}[/blue]")

        # Get the command execution tool (first tool in SystemTools)
        system_tools = SystemTools(config)
        command_tool = system_tools.get_tools()[0]  # Get the execute_command tool
        result = await command_tool.execute(command)

        if result.success:
            console.print(f"[green]✅ Command executed successfully[/green]")
            if result.result.get("stdout"):
                console.print(f"[blue]📤 Output:[/blue]")
                console.print(result.result["stdout"])
            if result.result.get("stderr"):
                console.print(f"[yellow]⚠️ Warnings:[/yellow]")
                console.print(result.result["stderr"])
        else:
            console.print(f"[red]❌ Command failed: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error executing command: {e}[/red]")


async def agent_command(config: Config, task_description: str, browser: str = "default", verbose: bool = False):
    """Execute advanced agent task"""
    try:
        from model8cli.agent.core import AdvancedAgent

        console.print(f"[blue]🤖 Advanced Agent Starting...[/blue]")
        console.print(f"[blue]📋 Task: {task_description}[/blue]")

        # Create agent
        agent = AdvancedAgent(config)

        # Show agent capabilities if verbose
        if verbose:
            status = agent.get_agent_status()
            console.print(f"[green]🔧 Agent loaded with {status['total_tools']} tools[/green]")
            console.print("[blue]🎯 Capabilities:[/blue]")
            for capability in status['capabilities']:
                console.print(f"  • {capability}")
            console.print()

        # Execute the task
        console.print("[blue]⚡ Planning and executing task...[/blue]")
        result = await agent.execute_task(task_description)

        if result["success"]:
            console.print("[green]✅ Task completed successfully![/green]")

            if verbose and "result" in result:
                execution_results = result["result"].get("execution_results", [])
                console.print(f"[blue]📊 Execution Summary:[/blue]")
                console.print(f"  • Total steps: {result['result'].get('total_steps', 0)}")
                console.print(f"  • Successful: {result['result'].get('successful_steps', 0)}")
                console.print(f"  • Failed: {result['result'].get('failed_steps', 0)}")

                console.print("[blue]🔍 Step Details:[/blue]")
                for step in execution_results:
                    status_icon = "✅" if step["success"] else "❌"
                    console.print(f"  {status_icon} Step {step['step']}: {step['description']}")
                    if not step["success"] and step.get("error"):
                        console.print(f"    Error: {step['error']}")
        else:
            console.print(f"[red]❌ Task failed: {result.get('error', 'Unknown error')}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Agent error: {e}[/red]")


async def groq_models_command(config: Config, set_model: Optional[str]):
    """List and manage Groq models"""
    try:
        from model8cli.core.groq_client import GroqClient

        console.print("[blue]🚀 Groq Models[/blue]")

        # Check if Groq API key is available
        if not config.groq_api_key:
            console.print("[red]❌ Groq API key is required[/red]")
            console.print("[yellow]💡 Set your Groq API key with: 200model8cli set-groq-key YOUR_KEY[/yellow]")
            return

        # Get available models
        groq_client = GroqClient(config)
        models = groq_client.get_available_models()

        if not models:
            console.print("[yellow]⚠️  No Groq models available[/yellow]")
            return

        console.print(f"\n[green]✅ Found {len(models)} Groq models:[/green]\n")

        # Display models with numbers
        for i, model in enumerate(models, 1):
            # Show rate limits
            rpm = model.requests_per_minute
            rpd = model.requests_per_day
            tpm = model.tokens_per_minute
            tpd = model.tokens_per_day if model.tokens_per_day > 0 else "No limit"

            console.print(f"  {i:2d}. [bold]{model.id}[/bold]")
            console.print(f"      {model.name}")
            console.print(f"      Limits: {rpm} req/min, {rpd} req/day, {tpm} tok/min, {tpd} tok/day")
            console.print()

        # Handle model setting
        if set_model:
            # Try to find model by number or name
            selected_model = None

            # Check if it's a number
            try:
                model_num = int(set_model)
                if 1 <= model_num <= len(models):
                    selected_model = models[model_num - 1]
            except ValueError:
                # Check if it's a model name
                for model in models:
                    if model.id == set_model:
                        selected_model = model
                        break

            if selected_model:
                # Update config with groq/ prefix
                config.models.default = f"groq/{selected_model.id}"
                config.save_config()
                console.print(f"[green]✅ Default model set to: groq/{selected_model.id}[/green]")
                console.print("[cyan]💡 Try: 200model8cli ask 'hello'[/cyan]")
            else:
                console.print(f"[red]❌ Model '{set_model}' not found[/red]")
        else:
            console.print("\n[cyan]💡 To set a Groq model as default:[/cyan]")
            console.print("  200model8cli groq --set <model-name>")
            console.print("  200model8cli groq --set <number>")

        await groq_client.close()

    except Exception as e:
        console.print(f"[red]❌ Error managing Groq models: {e}[/red]")


async def groq_switch_command(config: Config):
    """Interactive Groq model switching"""
    try:
        from model8cli.core.groq_client import GroqClient
        from rich.prompt import Prompt

        console.print("🔍 Groq Model Switcher")

        # Check if Groq API key is available
        if not config.groq_api_key:
            console.print("[red]❌ Groq API key is required for model switching[/red]")
            console.print("[yellow]💡 Set your Groq API key with: 200model8cli set-groq-key YOUR_KEY[/yellow]")
            return

        # Get available models
        groq_client = GroqClient(config)
        models = groq_client.get_available_models()

        if not models:
            console.print("[yellow]⚠️  No Groq models available[/yellow]")
            return

        console.print(f"\n[green]✅ Available Groq models:[/green]\n")

        # Display models with numbers
        for i, model in enumerate(models, 1):
            # Show rate limits
            rpm = model.requests_per_minute
            rpd = model.requests_per_day
            tpm = model.tokens_per_minute
            tpd = model.tokens_per_day if model.tokens_per_day > 0 else "No limit"

            console.print(f"  {i:2d}. [bold]{model.id}[/bold]")
            console.print(f"      {model.name}")
            console.print(f"      Limits: {rpm} req/min, {rpd} req/day, {tpm} tok/min, {tpd} tok/day")
            console.print()

        # Get user selection
        while True:
            try:
                choice = Prompt.ask(
                    "\n[bold blue]Select a model[/bold blue]",
                    default="1"
                )

                if choice.lower() in ['q', 'quit', 'exit']:
                    console.print("[yellow]Model switching cancelled[/yellow]")
                    return

                # Try to parse as number
                try:
                    model_num = int(choice)
                    if 1 <= model_num <= len(models):
                        selected_model = models[model_num - 1]
                        break
                    else:
                        console.print(f"[red]Please enter a number between 1 and {len(models)}[/red]")
                        continue
                except ValueError:
                    # Try to find by model name
                    found = False
                    for model in models:
                        if model.id.lower() == choice.lower():
                            selected_model = model
                            found = True
                            break

                    if found:
                        break
                    else:
                        console.print(f"[red]Model '{choice}' not found. Please try again.[/red]")
                        continue

            except KeyboardInterrupt:
                console.print("\n[yellow]Model switching cancelled[/yellow]")
                return

        # Update config with groq/ prefix
        config.models.default = f"groq/{selected_model.id}"
        config.save_config()

        console.print(f"\n[green]✅ Switched to Groq model: {selected_model.id}[/green]")
        console.print(f"[green]📝 Model: {selected_model.name}[/green]")
        console.print("[cyan]💡 Try: 200model8cli ask 'hello'[/cyan]")

        await groq_client.close()

    except Exception as e:
        console.print(f"[red]❌ Error switching Groq models: {e}[/red]")


async def set_github_token_command(config: Config, token: str):
    """Set GitHub token command"""
    try:
        config.api.github_token = token
        config._save_github_token_to_config(token)

        console.print(f"[green]✅ GitHub token saved successfully![/green]")
        console.print(f"[dim]Token: {token[:8]}...{token[-4:]}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Failed to save GitHub token: {e}[/red]")


async def github_create_repo_command(config: Config, name: str, description: str, private: bool, gitignore: str, license: str):
    """Create GitHub repository command"""
    try:
        from .tools.github_tools import CreateRepositoryTool

        tool = CreateRepositoryTool(config)
        result = await tool.execute(
            name=name,
            description=description,
            private=private,
            gitignore_template=gitignore,
            license_template=license
        )

        if result.success:
            repo_info = result.result
            console.print(f"[green]✅ Repository created successfully![/green]")
            console.print(f"[blue]Name:[/blue] {repo_info['full_name']}")
            console.print(f"[blue]URL:[/blue] {repo_info['html_url']}")
            console.print(f"[blue]Clone URL:[/blue] {repo_info['clone_url']}")
            if repo_info['private']:
                console.print(f"[yellow]🔒 Private repository[/yellow]")
        else:
            console.print(f"[red]❌ Failed to create repository: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Repository creation error: {e}[/red]")


async def github_create_pr_command(config: Config, owner: str, repo: str, title: str, head: str, body: str, base: str, draft: bool):
    """Create GitHub pull request command"""
    try:
        from .tools.github_tools import CreatePullRequestTool

        tool = CreatePullRequestTool(config)
        result = await tool.execute(
            owner=owner,
            repo=repo,
            title=title,
            head=head,
            body=body,
            base=base,
            draft=draft
        )

        if result.success:
            pr_info = result.result
            console.print(f"[green]✅ Pull request created successfully![/green]")
            console.print(f"[blue]Number:[/blue] #{pr_info['number']}")
            console.print(f"[blue]Title:[/blue] {pr_info['title']}")
            console.print(f"[blue]URL:[/blue] {pr_info['html_url']}")
            console.print(f"[blue]Branch:[/blue] {pr_info['head']} → {pr_info['base']}")
            if pr_info['draft']:
                console.print(f"[yellow]📝 Draft pull request[/yellow]")
        else:
            console.print(f"[red]❌ Failed to create pull request: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Pull request creation error: {e}[/red]")


async def github_list_issues_command(config: Config, owner: str, repo: str, state: str, labels: str, limit: int):
    """List GitHub issues command"""
    try:
        from .tools.github_tools import ListIssuesTool

        tool = ListIssuesTool(config)
        result = await tool.execute(
            owner=owner,
            repo=repo,
            state=state,
            labels=labels,
            limit=limit
        )

        if result.success:
            issues_info = result.result
            console.print(f"[green]📋 Found {issues_info['total_count']} issues in {issues_info['repository']}[/green]")

            for issue in issues_info['issues']:
                status_color = "green" if issue['state'] == 'open' else "red"
                console.print(f"[{status_color}]#{issue['number']}[/{status_color}] {issue['title']}")
                console.print(f"  [dim]by {issue['user']} • {issue['comments']} comments • {issue['created_at'][:10]}[/dim]")
                if issue['labels']:
                    labels_str = ', '.join(issue['labels'])
                    console.print(f"  [blue]Labels:[/blue] {labels_str}")
                console.print()
        else:
            console.print(f"[red]❌ Failed to list issues: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Issues listing error: {e}[/red]")


async def github_create_issue_command(config: Config, owner: str, repo: str, title: str, body: str, labels: list, assignees: list):
    """Create GitHub issue command"""
    try:
        from .tools.github_tools import CreateIssueTool

        tool = CreateIssueTool(config)
        result = await tool.execute(
            owner=owner,
            repo=repo,
            title=title,
            body=body,
            labels=labels,
            assignees=assignees
        )

        if result.success:
            issue_info = result.result
            console.print(f"[green]✅ Issue created successfully![/green]")
            console.print(f"[blue]Number:[/blue] #{issue_info['number']}")
            console.print(f"[blue]Title:[/blue] {issue_info['title']}")
            console.print(f"[blue]URL:[/blue] {issue_info['html_url']}")
            if issue_info['labels']:
                labels_str = ', '.join(issue_info['labels'])
                console.print(f"[blue]Labels:[/blue] {labels_str}")
            if issue_info['assignees']:
                assignees_str = ', '.join(issue_info['assignees'])
                console.print(f"[blue]Assignees:[/blue] {assignees_str}")
        else:
            console.print(f"[red]❌ Failed to create issue: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Issue creation error: {e}[/red]")


async def github_list_prs_command(config: Config, owner: str, repo: str, state: str, base: str, head: str, limit: int):
    """List GitHub pull requests command"""
    try:
        from .tools.github_tools import ListPullRequestsTool

        tool = ListPullRequestsTool(config)
        result = await tool.execute(
            owner=owner,
            repo=repo,
            state=state,
            base=base,
            head=head,
            limit=limit
        )

        if result.success:
            prs_info = result.result
            console.print(f"[green]🔀 Found {prs_info['total_count']} pull requests in {prs_info['repository']}[/green]")

            for pr in prs_info['pull_requests']:
                status_color = "green" if pr['state'] == 'open' else "red"
                draft_indicator = " [yellow](draft)[/yellow]" if pr['draft'] else ""
                console.print(f"[{status_color}]#{pr['number']}[/{status_color}] {pr['title']}{draft_indicator}")
                console.print(f"  [dim]by {pr['user']} • {pr['head']} → {pr['base']} • {pr['created_at'][:10]}[/dim]")
                console.print(f"  [dim]+{pr['additions']} -{pr['deletions']} • {pr['commits']} commits • {pr['comments']} comments[/dim]")
                console.print()
        else:
            console.print(f"[red]❌ Failed to list pull requests: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Pull requests listing error: {e}[/red]")


async def learning_mode_command(config: Config):
    """Start learning mode"""
    try:
        from .ui.learning_mode import LearningMode
        from .core.api import OpenRouterClient
        from .core.models import ModelManager
        from .tools.base import ToolRegistry
        from .tools.file_ops import FileOperations
        from .tools.web_tools import WebTools
        from .tools.git_tools import GitTools
        from .tools.github_tools import GitHubTools
        from .tools.system_tools import SystemTools
        from .tools.code_tools import CodeTools
        from .tools.knowledge_tools import KnowledgeTools

        # Initialize components
        async with OpenRouterClient(config) as api_client:
            model_manager = ModelManager(config, api_client)
            await model_manager.initialize()

            # Setup tools
            tool_registry = ToolRegistry(config)

            # Register all tools
            file_ops = FileOperations(config)
            for tool in file_ops.get_tools():
                tool_registry.register_tool(tool)

            web_tools = WebTools(config)
            for tool in web_tools.get_tools():
                tool_registry.register_tool(tool)

            git_tools = GitTools(config)
            for tool in git_tools.get_tools():
                tool_registry.register_tool(tool)

            github_tools = GitHubTools(config)
            for tool in github_tools.get_tools():
                tool_registry.register_tool(tool)

            knowledge_tools = KnowledgeTools(config)
            for tool in knowledge_tools.get_tools():
                tool_registry.register_tool(tool)

            system_tools = SystemTools(config)
            for tool in system_tools.get_tools():
                tool_registry.register_tool(tool)

            code_tools = CodeTools(config)
            for tool in code_tools.get_tools():
                tool_registry.register_tool(tool)

            # Start learning mode
            learning_mode = LearningMode(config, api_client, model_manager, tool_registry)
            await learning_mode.start_learning_mode()

    except Exception as e:
        console.print(f"[red]❌ Learning mode error: {e}[/red]")


async def knowledge_search_command(config: Config, query: str, category: str, limit: int):
    """Search knowledge base command"""
    try:
        from .tools.knowledge_tools import KnowledgeSearchTool

        tool = KnowledgeSearchTool(config)
        result = await tool.execute(query=query, category=category, limit=limit)

        if result.success:
            search_results = result.result
            console.print(f"[green]🔍 Found {search_results['total_found']} results for '{query}'[/green]")

            if search_results['category']:
                console.print(f"[blue]Category:[/blue] {search_results['category']}")

            for i, entry in enumerate(search_results['results'], 1):
                console.print(Panel(
                    f"[bold]{entry['title']}[/bold]\n\n{entry['content']}\n\n"
                    f"[dim]Category: {entry['category']} | Tags: {', '.join(entry['tags'])} | Source: {entry['source']}[/dim]",
                    title=f"Result {i}",
                    border_style="cyan"
                ))
        else:
            console.print(f"[red]❌ Search failed: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Knowledge search error: {e}[/red]")


async def knowledge_add_command(config: Config, title: str, content: str, category: str, tags: list):
    """Add knowledge entry command"""
    try:
        from .tools.knowledge_tools import AddKnowledgeTool

        tool = AddKnowledgeTool(config)
        result = await tool.execute(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source="cli_command"
        )

        if result.success:
            entry_info = result.result
            console.print(f"[green]✅ Knowledge entry added successfully![/green]")
            console.print(f"[blue]ID:[/blue] {entry_info['id']}")
            console.print(f"[blue]Title:[/blue] {entry_info['title']}")
            console.print(f"[blue]Category:[/blue] {entry_info['category']}")
            if entry_info['tags']:
                console.print(f"[blue]Tags:[/blue] {', '.join(entry_info['tags'])}")
        else:
            console.print(f"[red]❌ Failed to add knowledge entry: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Knowledge add error: {e}[/red]")


async def knowledge_categories_command(config: Config):
    """List knowledge categories command"""
    try:
        from .tools.knowledge_tools import ListKnowledgeCategoriesTools

        tool = ListKnowledgeCategoriesTools(config)
        result = await tool.execute()

        if result.success:
            categories_info = result.result
            console.print(f"[green]📚 Found {categories_info['total_count']} categories:[/green]")

            for category in categories_info['categories']:
                console.print(f"  • {category}")
        else:
            console.print(f"[red]❌ Failed to list categories: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Knowledge categories error: {e}[/red]")


async def workflow_execute_command(config: Config, workflow_id: str, variables: dict, is_template: bool):
    """Execute workflow command"""
    try:
        from .tools.workflow_tools import ExecuteWorkflowTool
        from .tools.base import ToolRegistry
        from .tools.file_ops import FileOperations
        from .tools.web_tools import WebTools
        from .tools.git_tools import GitTools
        from .tools.github_tools import GitHubTools
        from .tools.system_tools import SystemTools
        from .tools.code_tools import CodeTools
        from .tools.knowledge_tools import KnowledgeTools

        # Setup tool registry
        tool_registry = ToolRegistry(config)

        # Register all tools
        for tool_class in [FileOperations, WebTools, GitTools, GitHubTools,
                          SystemTools, CodeTools, KnowledgeTools]:
            tools = tool_class(config)
            for tool in tools.get_tools():
                tool_registry.register_tool(tool)

        tool = ExecuteWorkflowTool(config, tool_registry)
        result = await tool.execute(
            workflow_id=workflow_id,
            variables=variables,
            is_template=is_template
        )

        if result.success:
            workflow_result = result.result
            console.print(f"[green]✅ Workflow '{workflow_result['name']}' executed successfully![/green]")
            console.print(f"[blue]Status:[/blue] {workflow_result['status']}")
            console.print(f"[blue]Started:[/blue] {workflow_result['started_at']}")
            console.print(f"[blue]Completed:[/blue] {workflow_result['completed_at']}")

            console.print("\n[bold cyan]📋 Steps:[/bold cyan]")
            for step in workflow_result['steps']:
                status_color = {
                    'completed': 'green',
                    'failed': 'red',
                    'skipped': 'yellow',
                    'running': 'blue'
                }.get(step['status'], 'white')

                console.print(f"  [{status_color}]●[/{status_color}] {step['name']} - {step['status']}")
                if step.get('error'):
                    console.print(f"    [red]Error: {step['error']}[/red]")
        else:
            console.print(f"[red]❌ Workflow execution failed: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Workflow execution error: {e}[/red]")


async def workflow_list_command(config: Config, include_templates: bool):
    """List workflows command"""
    try:
        from .tools.workflow_tools import ListWorkflowsTool
        from .tools.base import ToolRegistry

        tool_registry = ToolRegistry(config)
        tool = ListWorkflowsTool(config, tool_registry)
        result = await tool.execute(include_templates=include_templates)

        if result.success:
            workflows_info = result.result
            console.print(f"[green]📋 Found {workflows_info['total_count']} workflows and templates[/green]")

            if workflows_info['workflows']:
                console.print("\n[bold cyan]💼 Saved Workflows:[/bold cyan]")
                for workflow in workflows_info['workflows']:
                    console.print(f"  • {workflow}")

            if workflows_info['templates']:
                console.print("\n[bold yellow]📄 Templates:[/bold yellow]")
                for template in workflows_info['templates']:
                    console.print(f"  • {template}")
        else:
            console.print(f"[red]❌ Failed to list workflows: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Workflow list error: {e}[/red]")


async def workflow_create_command(config: Config, workflow_id: str, name: str, description: str,
                                steps: list, variables: dict, tags: list):
    """Create workflow command"""
    try:
        from .tools.workflow_tools import CreateWorkflowTool
        from .tools.base import ToolRegistry

        tool_registry = ToolRegistry(config)
        tool = CreateWorkflowTool(config, tool_registry)
        result = await tool.execute(
            workflow_id=workflow_id,
            name=name,
            description=description,
            steps=steps,
            variables=variables,
            tags=tags
        )

        if result.success:
            workflow_info = result.result
            console.print(f"[green]✅ Workflow created successfully![/green]")
            console.print(f"[blue]ID:[/blue] {workflow_info['workflow_id']}")
            console.print(f"[blue]Name:[/blue] {workflow_info['name']}")
            console.print(f"[blue]Steps:[/blue] {workflow_info['steps_count']}")
        else:
            console.print(f"[red]❌ Failed to create workflow: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Workflow creation error: {e}[/red]")


async def workflow_template_command(config: Config, template_name: str):
    """Get workflow template command"""
    try:
        from .tools.workflow_tools import GetWorkflowTemplateTool
        from .tools.base import ToolRegistry

        tool_registry = ToolRegistry(config)
        tool = GetWorkflowTemplateTool(config, tool_registry)
        result = await tool.execute(template_name=template_name)

        if result.success:
            template = result.result
            console.print(f"[green]📄 Template: {template['name']}[/green]")
            console.print(f"[blue]Description:[/blue] {template['description']}")

            console.print("\n[bold cyan]📋 Steps:[/bold cyan]")
            for i, step in enumerate(template['steps'], 1):
                console.print(f"  {i}. {step['name']} ({step['tool']})")

            if template.get('variables'):
                console.print("\n[bold yellow]🔧 Variables:[/bold yellow]")
                for key, value in template['variables'].items():
                    console.print(f"  • {key}: {value}")
        else:
            console.print(f"[red]❌ Template not found: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Template error: {e}[/red]")


async def ollama_recommend_command(config: Config, use_case: str, size_preference: str):
    """Ollama model recommendation command"""
    try:
        from .tools.ollama_tools import OllamaModelRecommendationTool

        tool = OllamaModelRecommendationTool(config)
        result = await tool.execute(use_case=use_case, size_preference=size_preference)

        if result.success:
            recommendations = result.result
            console.print(f"[green]🤖 Model Recommendations for {recommendations['use_case']} (size: {recommendations['size_preference']})[/green]")

            for i, model in enumerate(recommendations['recommendations'], 1):
                score_color = "green" if model['use_case_score'] >= 8 else "yellow" if model['use_case_score'] >= 6 else "red"
                console.print(f"\n[bold cyan]{i}. {model['name']}[/bold cyan] ({model['size']})")
                console.print(f"   {model['description']}")
                console.print(f"   [bold]Scores:[/bold] Tool Calling: {model['tool_calling_score']}/10, "
                            f"Reasoning: {model['reasoning_score']}/10, Speed: {model['speed_score']}/10")
                console.print(f"   [{score_color}]Use Case Score: {model['use_case_score']}/10[/{score_color}]")
                console.print(f"   [dim]Category: {model['category']}[/dim]")

            console.print(f"\n[blue]💡 Installation:[/blue] {recommendations['installation_command']}")
            console.print(f"[blue]💡 Usage:[/blue] {recommendations['usage_tip']}")
        else:
            console.print(f"[red]❌ Failed to get recommendations: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Ollama recommendation error: {e}[/red]")


async def ollama_test_command(config: Config, model: str, test_type: str):
    """Ollama tool calling test command"""
    try:
        from .tools.ollama_tools import OllamaToolCallingTestTool

        tool = OllamaToolCallingTestTool(config)
        result = await tool.execute(model=model, test_type=test_type)

        if result.success:
            test_result = result.result
            console.print(f"[blue]🧪 Testing {test_result['model']} with {test_result['test_type']} test[/blue]")

            if test_result['success']:
                console.print(f"[green]✅ {test_result['analysis']}[/green]")
                console.print(f"[blue]Tool calls detected:[/blue] {test_result['tool_calls_detected']}")

                if test_result.get('tool_calls'):
                    console.print("\n[bold cyan]🔧 Generated Tool Calls:[/bold cyan]")
                    for i, call in enumerate(test_result['tool_calls'], 1):
                        func = call.get('function', {})
                        console.print(f"  {i}. {func.get('name', 'unknown')}({func.get('arguments', '{}')})")
            else:
                console.print(f"[red]❌ {test_result['analysis']}[/red]")
                if test_result['response_content']:
                    console.print(f"[yellow]Response:[/yellow] {test_result['response_content'][:200]}...")

            console.print(f"\n[dim]Test completed for model: {test_result['model']}[/dim]")
        else:
            console.print(f"[red]❌ Test failed: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Ollama test error: {e}[/red]")


async def ollama_optimize_command(config: Config, system_info: Optional[Dict[str, Any]]):
    """Ollama optimization command"""
    try:
        from .tools.ollama_tools import OllamaOptimizationTool

        tool = OllamaOptimizationTool(config)
        result = await tool.execute(system_info=system_info)

        if result.success:
            optimization = result.result

            console.print("[green]🚀 Ollama Tool Calling Optimization Tips[/green]")

            for category, tips in optimization['optimization_tips'].items():
                category_title = category.replace('_', ' ').title()
                console.print(f"\n[bold cyan]📋 {category_title}:[/bold cyan]")
                for tip in tips:
                    console.print(f"  • {tip}")

            console.print(f"\n[bold yellow]⚙️ Recommended Settings:[/bold yellow]")
            settings = optimization['recommended_settings']
            for setting, value in settings.items():
                console.print(f"  • {setting}: {value}")

            console.print(f"\n[bold blue]✨ Best Practices:[/bold blue]")
            for practice in optimization['best_practices']:
                console.print(f"  • {practice}")
        else:
            console.print(f"[red]❌ Failed to get optimization tips: {result.error}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Ollama optimization error: {e}[/red]")


async def self_aware_agent_command(config: Config):
    """Start self-aware agent mode"""
    try:
        from .agents.self_aware_agent import start_self_aware_agent_mode
        await start_self_aware_agent_mode(config)
    except Exception as e:
        console.print(f"[red]❌ Self-aware agent error: {e}[/red]")


async def ollama_list_command(config: Config):
    """List available Ollama models"""
    try:
        from model8cli.core.ollama_client import OllamaClient
        from rich.table import Table

        console.print("[blue]🔍 Checking for local Ollama models...[/blue]")

        # Initialize Ollama client
        ollama_client = OllamaClient()

        # Check if Ollama is available
        if not await ollama_client.is_available():
            console.print("[red]❌ Ollama is not running or not installed[/red]")
            console.print("[yellow]💡 To use local models:[/yellow]")
            console.print("  1. Install Ollama from https://ollama.ai")
            console.print("  2. Start Ollama service")
            console.print("  3. Pull models with: ollama pull <model-name>")
            return

        # Get available models
        models = await ollama_client.list_models()
        await ollama_client.close()

        if not models:
            console.print("[yellow]⚠️  No local models found[/yellow]")
            console.print("[cyan]💡 Pull models with: ollama pull <model-name>[/cyan]")
            return

        # Create table
        table = Table(title="Available Ollama Models")
        table.add_column("Model", style="cyan", no_wrap=True)
        table.add_column("Size", style="green")
        table.add_column("Modified", style="yellow")

        for model in models:
            # Format size
            size_gb = model.size / (1024**3)
            size_str = f"{size_gb:.1f} GB"

            # Format modified date
            modified = model.modified_at[:10] if model.modified_at else "Unknown"

            table.add_row(model.name, size_str, modified)

        console.print(table)
        console.print(f"\n[green]✅ Found {len(models)} local models[/green]")
        console.print("[cyan]💡 Use with: 200model8cli use-model ollama/<model-name>[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error listing Ollama models: {e}[/red]")


async def ollama_switch_command(config: Config):
    """Interactive Ollama model switching"""
    try:
        from model8cli.core.ollama_client import OllamaClient
        from rich.prompt import Prompt

        console.print("🔍 Ollama Model Switcher")

        # Initialize Ollama client
        ollama_client = OllamaClient()

        # Check if Ollama is available
        if not await ollama_client.is_available():
            console.print("[red]❌ Ollama is not running or not installed[/red]")
            console.print("[yellow]💡 To use local models:[/yellow]")
            console.print("  1. Install Ollama from https://ollama.ai")
            console.print("  2. Start Ollama service")
            console.print("  3. Pull models with: ollama pull <model-name>")
            return

        # Get available models
        models = await ollama_client.list_models()
        await ollama_client.close()

        if not models:
            console.print("[yellow]⚠️  No local models found[/yellow]")
            console.print("[cyan]💡 Pull models with: ollama pull <model-name>[/cyan]")
            return

        console.print("\n✅ Available Ollama models:\n")

        # Display models
        for i, model in enumerate(models, 1):
            size_gb = model.size / (1024**3)
            console.print(f"   {i}. {model.name}")
            console.print(f"      Size: {size_gb:.1f} GB")
            console.print(f"      Modified: {model.modified_at[:10] if model.modified_at else 'Unknown'}")
            console.print()

        # Get user selection
        while True:
            try:
                choice = Prompt.ask(
                    "\n[yellow]Select a model (number or name)[/yellow]",
                    default="1"
                )

                selected_model = None
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(models):
                        selected_model = models[idx]
                else:
                    # Direct model name
                    for model in models:
                        if choice in model.name:
                            selected_model = model
                            break

                if selected_model:
                    break
                else:
                    console.print("[red]❌ Invalid selection. Please try again.[/red]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Model switching cancelled[/yellow]")
                return

        # Update config with ollama/ prefix
        config.models.default = f"ollama/{selected_model.name}"
        config.save_config()

        console.print(f"\n[green]✅ Switched to Ollama model: {selected_model.name}[/green]")
        size_gb = selected_model.size / (1024**3)
        console.print(f"[green]📝 Size: {size_gb:.1f} GB[/green]")
        console.print("[cyan]💡 Try: 200model8cli ask 'hello'[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error switching Ollama models: {e}[/red]")


if __name__ == '__main__':
    main()
