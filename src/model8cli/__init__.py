"""
200Model8CLI - OpenRouter CLI Agent

A sophisticated command-line interface tool that uses OpenRouter's API 
to access multiple AI models with comprehensive tool calling capabilities.
"""

__version__ = "1.0.0"
__author__ = "200Model8CLI Development Team"
__email__ = "dev@200model8cli.com"

from .core.api import OpenRouterClient
from .core.models import ModelManager
from .core.session import SessionManager
from .core.config import Config

__all__ = [
    "OpenRouterClient",
    "ModelManager", 
    "SessionManager",
    "Config",
]
