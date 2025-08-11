"""
Helper utilities for 200Model8CLI

Common utility functions used throughout the application.
"""

import os
import sys
import time
import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable, TypeVar, Awaitable
from datetime import datetime, timezone
import json
import yaml
import re

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


def get_project_root() -> Path:
    """Get the project root directory"""
    current = Path(__file__).resolve()
    while current.parent != current:
        if (current / "pyproject.toml").exists() or (current / "setup.py").exists():
            return current
        current = current.parent
    return Path.cwd()


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, create if it doesn't"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_hash(file_path: Union[str, Path]) -> str:
    """Get SHA256 hash of a file"""
    path = Path(file_path)
    if not path.exists():
        return ""
    
    hash_sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Get comprehensive file information"""
    path = Path(file_path)
    
    if not path.exists():
        return {"exists": False}
    
    stat = path.stat()
    
    return {
        "exists": True,
        "path": str(path.resolve()),
        "name": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "size": stat.st_size,
        "size_mb": stat.st_size / (1024 * 1024),
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
        "accessed": stat.st_atime,
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "is_symlink": path.is_symlink(),
        "permissions": oct(stat.st_mode)[-3:],
        "hash": get_file_hash(path) if path.is_file() else None,
    }


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """Format duration in human readable format"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_timestamp(timestamp: float, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format timestamp as string"""
    return datetime.fromtimestamp(timestamp).strftime(format_str)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extract code blocks from markdown text"""
    pattern = r'```(\w+)?\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    code_blocks = []
    for language, code in matches:
        code_blocks.append({
            "language": language or "text",
            "code": code.strip(),
        })
    
    return code_blocks


def detect_file_language(file_path: Union[str, Path]) -> str:
    """Detect programming language from file extension"""
    path = Path(file_path)
    extension = path.suffix.lower()
    
    language_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'jsx',
        '.tsx': 'tsx',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.php': 'php',
        '.rb': 'ruby',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.clj': 'clojure',
        '.hs': 'haskell',
        '.ml': 'ocaml',
        '.r': 'r',
        '.sql': 'sql',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.less': 'less',
        '.vue': 'vue',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.xml': 'xml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'ini',
        '.md': 'markdown',
        '.rst': 'rst',
        '.sh': 'bash',
        '.bat': 'batch',
        '.ps1': 'powershell',
        '.dockerfile': 'dockerfile',
        '.makefile': 'makefile',
        '.cmake': 'cmake',
        '.gradle': 'gradle',
    }
    
    return language_map.get(extension, 'text')


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Safely load JSON with fallback"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_yaml_loads(text: str, default: Any = None) -> Any:
    """Safely load YAML with fallback"""
    try:
        return yaml.safe_load(text)
    except (yaml.YAMLError, TypeError):
        return default


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Flatten nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """Split list into chunks of specified size"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def debounce(wait: float):
    """Debounce decorator for functions"""
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        last_called = [0.0]
        result = [None]
        
        def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_called[0] >= wait:
                result[0] = func(*args, **kwargs)
                last_called[0] = now
            return result[0]
        
        return wrapper
    return decorator


async def async_debounce(wait: float):
    """Async debounce decorator"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
        last_called = [0.0]
        result = [None]
        
        async def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_called[0] >= wait:
                result[0] = await func(*args, **kwargs)
                last_called[0] = now
            return result[0]
        
        return wrapper
    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Retry decorator with exponential backoff"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(
                        "Function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e)
                    )
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


async def async_retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Async retry decorator with exponential backoff"""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(
                        "Async function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    import platform
    import psutil
    
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
        "disk_usage": {
            "total": psutil.disk_usage('/').total,
            "used": psutil.disk_usage('/').used,
            "free": psutil.disk_usage('/').free,
        } if sys.platform != 'win32' else {
            "total": psutil.disk_usage('C:\\').total,
            "used": psutil.disk_usage('C:\\').used,
            "free": psutil.disk_usage('C:\\').free,
        }
    }


def create_temp_file(content: str, suffix: str = '.tmp', prefix: str = 'model8cli_') -> Path:
    """Create a temporary file with content"""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix=suffix,
        prefix=prefix,
        delete=False,
        encoding='utf-8'
    ) as f:
        f.write(content)
        return Path(f.name)


def cleanup_temp_files(pattern: str = 'model8cli_*'):
    """Clean up temporary files matching pattern"""
    temp_dir = Path(tempfile.gettempdir())
    for temp_file in temp_dir.glob(pattern):
        try:
            if temp_file.is_file():
                temp_file.unlink()
                logger.debug("Cleaned up temp file", file=str(temp_file))
        except Exception as e:
            logger.warning("Failed to clean up temp file", file=str(temp_file), error=str(e))


def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generate_id(length: int = 8) -> str:
    """Generate a random ID"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def is_binary_file(file_path: Union[str, Path]) -> bool:
    """Check if file is binary"""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True  # Assume binary if can't read


def get_line_count(file_path: Union[str, Path]) -> int:
    """Get number of lines in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
