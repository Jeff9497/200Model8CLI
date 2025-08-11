"""
UI module for 200Model8CLI

Contains the CLI interface, interactive mode, and rich formatting components.
"""

# from .cli import main  # Avoid circular import
from .interactive import InteractiveMode
from .formatting import RichFormatter

__all__ = [
    "InteractiveMode",
    "RichFormatter",
]
