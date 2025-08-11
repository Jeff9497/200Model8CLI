"""
Banner display for 200Model8CLI

Provides ASCII art banners and welcome messages with rich formatting.
"""

from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from typing import Optional

console = Console()


def create_ascii_banner() -> str:
    """Create the main ASCII banner for 200Model8CLI"""
    return """
██████╗  ██████╗  ██████╗ ███╗   ███╗ ██████╗ ██████╗ ███████╗██╗      █████╗  ██████╗██╗     ██╗
╚════██╗██╔═████╗██╔═████╗████╗ ████║██╔═████╗██╔══██╗██╔════╝██║     ██╔══██╗██╔════╝██║     ██║
 █████╔╝██║██╔██║██║██╔██║██╔████╔██║██║██╔██║██║  ██║█████╗  ██║     ╚█████╔╝██║     ██║     ██║
██╔═══╝ ████╔╝██║████╔╝██║██║╚██╔╝██║████╔╝██║██║  ██║██╔══╝  ██║     ██╔══██╗██║     ██║     ██║
███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║╚██████╔╝██████╔╝███████╗███████╗╚█████╔╝╚██████╗███████╗██║
╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝ ╚════╝  ╚═════╝╚══════╝╚═╝
"""


def create_compact_banner() -> str:
    """Create a more compact ASCII banner"""
    return """
██████╗  ██████╗  ██████╗ ███╗   ███╗ █████╗  ██████╗██╗     ██╗
╚════██╗██╔═████╗██╔═████╗████╗ ████║██╔══██╗██╔════╝██║     ██║
 █████╔╝██║██╔██║██║██╔██║██╔████╔██║╚█████╔╝██║     ██║     ██║
██╔═══╝ ████╔╝██║████╔╝██║██║╚██╔╝██║██╔══██╗██║     ██║     ██║
███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║╚█████╔╝╚██████╗███████╗██║
╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝ ╚════╝  ╚═════╝╚══════╝╚═╝
"""


def display_welcome_banner(model: Optional[str] = None, version: str = "1.0.0"):
    """Display the welcome banner with ASCII art"""

    # ASCII Art Banner
    ascii_banner = """
[bold blue]██████╗  ██████╗  ██████╗ ███╗   ███╗  █████╗     ██████╗██╗     ██╗[/bold blue]
[bold blue]╚════██╗██╔═████╗██╔═████╗████╗ ████║ ██╔══██╗   ██╔════╝██║     ██║[/bold blue]
[bold blue] █████╔╝██║██╔██║██║██╔██║██╔████╔██║ ╚█████_|   ██║     ██║     ██║[/bold blue]
[bold blue]██╔═══╝ ████╔╝██║████╔╝██║██║╚██╔╝██║ ██╔══██╗   ██║     ██║     ██║[/bold blue]
[bold blue]███████╗╚██████╔╝╚██████╔╝██║ ╚═╝ ██║ ╚█████╔╝    ██████╗███████╗██║[/bold blue]
[bold blue]╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝  ╚════╝     ╚═════╝╚══════╝╚═╝[/bold blue]
"""

    # Create info text
    info_text = f"""[bold blue]🤖 Advanced AI Development Assistant[/bold blue]
[blue]Model:[/blue] {model or 'Multi-Model Support'}  [blue]Version:[/blue] v{version}"""

    # Display banner
    console.print(ascii_banner.strip())
    console.print(Panel(
        Align.center(info_text),
        border_style="blue",
        padding=(0, 2)
    ))


def display_agent_banner():
    """Display banner for agent mode"""
    banner = Text()
    banner.append("🤖 ", style="bold blue")
    banner.append("AGENT MODE ACTIVATED", style="bold blue")
    banner.append(" 🚀", style="bold blue")

    subtitle = Text()
    subtitle.append("Autonomous AI Assistant Ready", style="blue")

    content = Text()
    content.append_text(Align.center(banner))
    content.append("\n")
    content.append_text(Align.center(subtitle))

    console.print(Panel(
        content,
        border_style="blue",
        padding=(1, 2),
        title="[bold blue]Agent[/bold blue]",
        title_align="center"
    ))


def display_tool_banner(tool_count: int):
    """Display banner showing available tools"""
    banner = Text()
    banner.append("🔧 ", style="bold blue")
    banner.append(f"{tool_count} TOOLS LOADED", style="bold blue")
    banner.append(" ⚡", style="bold blue")

    console.print(Panel(
        Align.center(banner),
        border_style="blue",
        padding=(0, 1),
        title="[bold blue]Tools Ready[/bold blue]",
        title_align="center"
    ))


def display_model_switch_banner(old_model: str, new_model: str):
    """Display banner for model switching"""
    banner = Text()
    banner.append("🔄 Model Switch: ", style="bold blue")
    banner.append(f"{old_model}", style="dim blue")
    banner.append(" → ", style="bold blue")
    banner.append(f"{new_model}", style="bold blue")

    console.print(Panel(
        Align.center(banner),
        border_style="blue",
        padding=(0, 1),
        title="[bold blue]Model Updated[/bold blue]",
        title_align="center"
    ))
