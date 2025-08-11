"""
Configuration Management for 200Model8CLI

Handles configuration loading, validation, and management from multiple sources.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
import yaml
import json
from dotenv import load_dotenv

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class APIConfig:
    """API configuration"""
    openrouter_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    groq_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    github_token: str = ""
    timeout: int = 30
    max_retries: int = 3
    base_retry_delay: float = 1.0
    rate_limit_per_minute: int = 60


@dataclass
class ModelConfig:
    """Model configuration"""
    default: str = "deepseek/deepseek-chat-v3-0324:free"  # Prioritized - excellent tool calling
    available: List[str] = field(default_factory=lambda: [
        # PRIORITIZED MODELS - Excellent tool calling capability
        "deepseek/deepseek-chat-v3-0324:free",  # ⭐ BEST - Reliable tool calling
        "deepseek/deepseek-chat:free",           # ⭐ GOOD - Reliable tool calling

        # OTHER FREE MODELS - Tool calling may vary
        "moonshotai/kimi-k2:free",
        "featherless/qwerky-72b:free",
        "deepseek/deepseek-r1-0528:free",
        "google/gemma-3-27b-it:free",
        "deepseek/deepseek-r1:free",

        # GROQ MODELS - Fast inference with tool calling support
        "groq/llama-3.1-8b-instant",
        "groq/llama-3.3-70b-versatile",
        "groq/llama3-70b-8192",
        "groq/llama3-8b-8192",
        "groq/gemma2-9b-it",
        "groq/meta-llama/llama-4-scout-17b-16e-instruct",
        "groq/meta-llama/llama-4-maverick-17b-128e-instruct",
        "groq/deepseek-r1-distill-llama-70b",
        "groq/mistral-saba-24b",
        "groq/moonshotai/kimi-k2-instruct",
        "groq/qwen/qwen3-32b",
        "groq/compound-beta",
        "groq/compound-beta-mini",
        "groq/allam-2-7b",
        "groq/meta-llama/llama-guard-4-12b",
        "groq/meta-llama/llama-prompt-guard-2-22m",
        "groq/meta-llama/llama-prompt-guard-2-86m",

        # PREMIUM MODELS - Generally good tool calling but require credits
        "anthropic/claude-3-opus",
        "anthropic/claude-3-sonnet-20240229",
        "anthropic/claude-3-haiku-20240307",
        "openai/gpt-4-turbo",
        "openai/gpt-4",
        "openai/gpt-3.5-turbo",
        "meta-llama/llama-3-70b-instruct",
        "meta-llama/llama-3-8b-instruct",
        "google/gemini-pro",
        "google/gemini-pro-vision",
    ])
    auto_select: bool = True
    fallback_model: str = "openai/gpt-3.5-turbo"


@dataclass
class ToolsConfig:
    """Tools configuration"""
    web_search_enabled: bool = True
    web_search_engine: str = "searxng"
    web_search_max_results: int = 5
    file_operations_enabled: bool = True
    file_max_size_mb: int = 10
    file_allowed_extensions: List[str] = field(default_factory=lambda: [
        ".py", ".js", ".ts", ".java", ".cpp", ".h", ".c", ".cs", ".go",
        ".rs", ".php", ".rb", ".swift", ".kt", ".scala", ".clj", ".hs",
        ".ml", ".r", ".sql", ".html", ".css", ".scss", ".less", ".vue",
        ".jsx", ".tsx", ".json", ".yaml", ".yml", ".xml", ".toml", ".ini",
        ".cfg", ".conf", ".md", ".rst", ".txt", ".log", ".sh", ".bat",
        ".ps1", ".dockerfile", ".makefile", ".cmake", ".gradle"
    ])
    git_operations_enabled: bool = True
    system_operations_enabled: bool = True
    code_analysis_enabled: bool = True


@dataclass
class UIConfig:
    """UI configuration"""
    streaming: bool = True
    syntax_highlighting: bool = True
    rich_formatting: bool = True
    max_context_length: int = 32000
    show_token_usage: bool = True
    show_model_info: bool = True
    interactive_mode: bool = True
    color_scheme: str = "dark"
    editor: str = "auto"  # auto, vim, emacs, nano


@dataclass
class SecurityConfig:
    """Security configuration"""
    validate_inputs: bool = True
    sandbox_mode: bool = False
    confirm_destructive_ops: bool = True
    backup_before_edit: bool = True
    max_file_size_mb: int = 100
    allowed_domains: List[str] = field(default_factory=lambda: [
        "github.com", "gitlab.com", "bitbucket.org", "stackoverflow.com",
        "docs.python.org", "developer.mozilla.org", "npmjs.com"
    ])
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm -rf", "del /f", "format", "fdisk", "dd if=", ":(){ :|:& };:"
    ])


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "structured"  # structured, json, plain
    file_enabled: bool = True
    file_path: str = "~/.200model8cli/logs/app.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    console_enabled: bool = True


class Config:
    """
    Main configuration class that loads and manages all configuration settings
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config_dir = self.config_path.parent
        
        # Load environment variables
        load_dotenv()
        
        # Initialize configuration sections
        self.api = APIConfig(openrouter_key="", groq_key="")
        self.models = ModelConfig()
        self.tools = ToolsConfig()
        self.ui = UIConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        
        # Load configuration
        self._load_config()
        
        # Validate configuration
        self._validate_config()
        
        logger.info("Configuration loaded", config_path=str(self.config_path))
    
    @staticmethod
    def _get_default_config_path() -> Path:
        """Get the default configuration file path"""
        if sys.platform == "win32":
            config_dir = Path.home() / ".200model8cli"
        else:
            config_dir = Path.home() / ".200model8cli"
        
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.yaml"
    
    def _load_config(self):
        """Load configuration from file and environment variables"""
        # Load from file if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
                self._apply_config_data(config_data)
                logger.debug("Configuration loaded from file")
            except Exception as e:
                logger.warning("Failed to load config file", error=str(e))
        
        # Override with environment variables
        self._load_from_environment()
        
        # Create default config file if it doesn't exist
        if not self.config_path.exists():
            self.save_config()
    
    def _apply_config_data(self, config_data: Dict[str, Any]):
        """Apply configuration data to config objects"""
        # API configuration
        if "api" in config_data:
            api_config = config_data["api"]
            stored_key = api_config.get("openrouter_key", "")
            logger.debug(f"Found stored key in config: {stored_key[:20]}..." if stored_key else "No stored key found")
            # Use stored key if it's not a placeholder
            if stored_key and stored_key != "${OPENROUTER_API_KEY}":
                self.api.openrouter_key = stored_key
                logger.debug("API key loaded from config file")
            else:
                logger.debug("API key is placeholder or empty")

            # Load Groq key
            groq_key = api_config.get("groq_key", "")
            if groq_key and groq_key != "${GROQ_API_KEY}":
                self.api.groq_key = groq_key
                logger.debug("Groq API key loaded from config file")

            self.api.base_url = api_config.get("base_url", self.api.base_url)
            self.api.groq_base_url = api_config.get("groq_base_url", self.api.groq_base_url)
            self.api.timeout = api_config.get("timeout", self.api.timeout)
            self.api.max_retries = api_config.get("max_retries", self.api.max_retries)
            self.api.base_retry_delay = api_config.get("base_retry_delay", self.api.base_retry_delay)
            self.api.rate_limit_per_minute = api_config.get("rate_limit_per_minute", self.api.rate_limit_per_minute)
        
        # Models configuration
        if "models" in config_data:
            models_config = config_data["models"]
            self.models.default = models_config.get("default", self.models.default)
            self.models.available = models_config.get("available", self.models.available)
            self.models.auto_select = models_config.get("auto_select", self.models.auto_select)
            self.models.fallback_model = models_config.get("fallback_model", self.models.fallback_model)
        
        # Tools configuration
        if "tools" in config_data:
            tools_config = config_data["tools"]
            self.tools.web_search_enabled = tools_config.get("web_search_enabled", self.tools.web_search_enabled)
            self.tools.web_search_engine = tools_config.get("web_search_engine", self.tools.web_search_engine)
            self.tools.web_search_max_results = tools_config.get("web_search_max_results", self.tools.web_search_max_results)
            self.tools.file_operations_enabled = tools_config.get("file_operations_enabled", self.tools.file_operations_enabled)
            self.tools.file_max_size_mb = tools_config.get("file_max_size_mb", self.tools.file_max_size_mb)
            self.tools.file_allowed_extensions = tools_config.get("file_allowed_extensions", self.tools.file_allowed_extensions)
            self.tools.git_operations_enabled = tools_config.get("git_operations_enabled", self.tools.git_operations_enabled)
            self.tools.system_operations_enabled = tools_config.get("system_operations_enabled", self.tools.system_operations_enabled)
            self.tools.code_analysis_enabled = tools_config.get("code_analysis_enabled", self.tools.code_analysis_enabled)
        
        # UI configuration
        if "ui" in config_data:
            ui_config = config_data["ui"]
            self.ui.streaming = ui_config.get("streaming", self.ui.streaming)
            self.ui.syntax_highlighting = ui_config.get("syntax_highlighting", self.ui.syntax_highlighting)
            self.ui.rich_formatting = ui_config.get("rich_formatting", self.ui.rich_formatting)
            self.ui.max_context_length = ui_config.get("max_context_length", self.ui.max_context_length)
            self.ui.show_token_usage = ui_config.get("show_token_usage", self.ui.show_token_usage)
            self.ui.show_model_info = ui_config.get("show_model_info", self.ui.show_model_info)
            self.ui.interactive_mode = ui_config.get("interactive_mode", self.ui.interactive_mode)
            self.ui.color_scheme = ui_config.get("color_scheme", self.ui.color_scheme)
            self.ui.editor = ui_config.get("editor", self.ui.editor)
        
        # Security configuration
        if "security" in config_data:
            security_config = config_data["security"]
            self.security.validate_inputs = security_config.get("validate_inputs", self.security.validate_inputs)
            self.security.sandbox_mode = security_config.get("sandbox_mode", self.security.sandbox_mode)
            self.security.confirm_destructive_ops = security_config.get("confirm_destructive_ops", self.security.confirm_destructive_ops)
            self.security.backup_before_edit = security_config.get("backup_before_edit", self.security.backup_before_edit)
            self.security.max_file_size_mb = security_config.get("max_file_size_mb", self.security.max_file_size_mb)
            self.security.allowed_domains = security_config.get("allowed_domains", self.security.allowed_domains)
            self.security.blocked_commands = security_config.get("blocked_commands", self.security.blocked_commands)
        
        # Logging configuration
        if "logging" in config_data:
            logging_config = config_data["logging"]
            self.logging.level = logging_config.get("level", self.logging.level)
            self.logging.format = logging_config.get("format", self.logging.format)
            self.logging.file_enabled = logging_config.get("file_enabled", self.logging.file_enabled)
            self.logging.file_path = logging_config.get("file_path", self.logging.file_path)
            self.logging.max_file_size_mb = logging_config.get("max_file_size_mb", self.logging.max_file_size_mb)
            self.logging.backup_count = logging_config.get("backup_count", self.logging.backup_count)
            self.logging.console_enabled = logging_config.get("console_enabled", self.logging.console_enabled)
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        # API key from environment (only override if env var is set)
        env_key = os.getenv("OPENROUTER_API_KEY")
        if env_key:
            self.api.openrouter_key = env_key
            # Save API key to config for persistence
            self._save_api_key_to_config(env_key)
        # If no env var but no API key loaded from config, keep it empty

        # Groq API key from environment
        groq_env_key = os.getenv("GROQ_API_KEY")
        if groq_env_key:
            self.api.groq_key = groq_env_key
            # Save Groq API key to config for persistence
            self._save_groq_key_to_config(groq_env_key)

        # GitHub token from environment
        github_env_key = os.getenv("GITHUB_TOKEN")
        if github_env_key:
            self.api.github_token = github_env_key
            # Save GitHub token to config for persistence
            self._save_github_token_to_config(github_env_key)

        # Other environment overrides
        if os.getenv("MODEL8CLI_DEFAULT_MODEL"):
            self.models.default = os.getenv("MODEL8CLI_DEFAULT_MODEL")
        
        if os.getenv("MODEL8CLI_LOG_LEVEL"):
            self.logging.level = os.getenv("MODEL8CLI_LOG_LEVEL")
        
        if os.getenv("MODEL8CLI_STREAMING"):
            self.ui.streaming = os.getenv("MODEL8CLI_STREAMING").lower() == "true"
    
    def _validate_config(self):
        """Validate configuration settings"""
        errors = []

        # Validate API key (only if not setting it via command)
        if not self.api.openrouter_key and not os.getenv("SKIP_API_KEY_VALIDATION"):
            errors.append("OpenRouter API key is required")

        # Skip model validation during startup for faster loading
        if os.getenv("SKIP_MODEL_VALIDATION"):
            return

        # Skip model validation for dynamic models (free models, local models, etc.)
        # This allows using any model ID without hardcoded validation
        if (":free" in self.models.default or
            self.models.default.startswith("ollama/") or
            self.models.default.startswith("groq/") or
            os.getenv("SKIP_MODEL_VALIDATION")):
            logger.debug("Skipping model validation for dynamic model", model=self.models.default)
        else:
            # Only validate hardcoded premium models
            if self.models.default not in self.models.available:
                logger.warning(f"Model '{self.models.default}' not in hardcoded list, but allowing anyway")

        # Validate file size limits
        if self.tools.file_max_size_mb <= 0:
            errors.append("File max size must be positive")

        if self.security.max_file_size_mb <= 0:
            errors.append("Security max file size must be positive")

        # Validate timeout settings
        if self.api.timeout <= 0:
            errors.append("API timeout must be positive")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            logger.error("Configuration validation failed", errors=errors)
            raise ValueError(error_msg)
    
    def save_config(self):
        """Save current configuration to file"""
        # Use actual API key if available, otherwise use placeholder
        api_key_to_save = self.api.openrouter_key if self.api.openrouter_key else "${OPENROUTER_API_KEY}"
        groq_key_to_save = self.api.groq_key if self.api.groq_key else "${GROQ_API_KEY}"

        config_data = {
            "api": {
                "openrouter_key": api_key_to_save,
                "groq_key": groq_key_to_save,
                "base_url": self.api.base_url,
                "groq_base_url": self.api.groq_base_url,
                "timeout": self.api.timeout,
                "max_retries": self.api.max_retries,
                "base_retry_delay": self.api.base_retry_delay,
                "rate_limit_per_minute": self.api.rate_limit_per_minute,
            },
            "models": {
                "default": self.models.default,
                "available": self.models.available,
                "auto_select": self.models.auto_select,
                "fallback_model": self.models.fallback_model,
            },
            "tools": {
                "web_search_enabled": self.tools.web_search_enabled,
                "web_search_engine": self.tools.web_search_engine,
                "web_search_max_results": self.tools.web_search_max_results,
                "file_operations_enabled": self.tools.file_operations_enabled,
                "file_max_size_mb": self.tools.file_max_size_mb,
                "file_allowed_extensions": self.tools.file_allowed_extensions,
                "git_operations_enabled": self.tools.git_operations_enabled,
                "system_operations_enabled": self.tools.system_operations_enabled,
                "code_analysis_enabled": self.tools.code_analysis_enabled,
            },
            "ui": {
                "streaming": self.ui.streaming,
                "syntax_highlighting": self.ui.syntax_highlighting,
                "rich_formatting": self.ui.rich_formatting,
                "max_context_length": self.ui.max_context_length,
                "show_token_usage": self.ui.show_token_usage,
                "show_model_info": self.ui.show_model_info,
                "interactive_mode": self.ui.interactive_mode,
                "color_scheme": self.ui.color_scheme,
                "editor": self.ui.editor,
            },
            "security": {
                "validate_inputs": self.security.validate_inputs,
                "sandbox_mode": self.security.sandbox_mode,
                "confirm_destructive_ops": self.security.confirm_destructive_ops,
                "backup_before_edit": self.security.backup_before_edit,
                "max_file_size_mb": self.security.max_file_size_mb,
                "allowed_domains": self.security.allowed_domains,
                "blocked_commands": self.security.blocked_commands,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file_enabled": self.logging.file_enabled,
                "file_path": self.logging.file_path,
                "max_file_size_mb": self.logging.max_file_size_mb,
                "backup_count": self.logging.backup_count,
                "console_enabled": self.logging.console_enabled,
            },
        }
        
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            logger.info("Configuration saved", path=str(self.config_path))
            
        except Exception as e:
            logger.error("Failed to save configuration", error=str(e))
            raise

    def _save_api_key_to_config(self, api_key: str):
        """Save API key to config file for persistence"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            else:
                config_data = {}

            # Update API key in config
            if "api" not in config_data:
                config_data["api"] = {}
            config_data["api"]["openrouter_key"] = api_key

            # Save updated config
            self.config_dir.mkdir(exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            logger.info("API key saved to config for persistence")

        except Exception as e:
            logger.warning("Failed to save API key to config", error=str(e))

    def _save_groq_key_to_config(self, api_key: str):
        """Save Groq API key to config file for persistence"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            else:
                config_data = {}

            # Update Groq API key in config
            if "api" not in config_data:
                config_data["api"] = {}
            config_data["api"]["groq_key"] = api_key

            # Save updated config
            self.config_dir.mkdir(exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            logger.info("Groq API key saved to config for persistence")

        except Exception as e:
            logger.warning("Failed to save Groq API key to config", error=str(e))

    def _save_github_token_to_config(self, token: str):
        """Save GitHub token to config file for persistence"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            else:
                config_data = {}

            # Update GitHub token in config
            if "api" not in config_data:
                config_data["api"] = {}
            config_data["api"]["github_token"] = token

            # Save updated config
            self.config_dir.mkdir(exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            logger.info("GitHub token saved to config for persistence")

        except Exception as e:
            logger.warning("Failed to save GitHub token to config", error=str(e))

    @property
    def openrouter_api_key(self) -> str:
        """Get OpenRouter API key"""
        return self.api.openrouter_key

    @property
    def groq_api_key(self) -> str:
        """Get Groq API key"""
        return self.api.groq_key

    @property
    def github_token(self) -> str:
        """Get GitHub token"""
        return self.api.github_token
    
    @property
    def default_model(self) -> str:
        """Get default model"""
        return self.models.default
    
    @property
    def api_timeout(self) -> int:
        """Get API timeout"""
        return self.api.timeout
    
    @property
    def max_retries(self) -> int:
        """Get max retries"""
        return self.api.max_retries
    
    @property
    def base_retry_delay(self) -> float:
        """Get base retry delay"""
        return self.api.base_retry_delay
    
    @property
    def rate_limit_per_minute(self) -> int:
        """Get rate limit per minute"""
        return self.api.rate_limit_per_minute
