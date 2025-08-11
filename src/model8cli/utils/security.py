"""
Security utilities for 200Model8CLI

Provides input validation, safe execution, and security checks.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
import hashlib
import tempfile

import structlog

logger = structlog.get_logger(__name__)


class SecurityValidator:
    """
    Security validator for input validation and safe execution
    """
    
    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        r'rm\s+-rf',
        r'del\s+/[fs]',
        r'format\s+[a-z]:',
        r'fdisk',
        r'dd\s+if=',
        r':\(\)\{\s*:\|\:&\s*\};:',  # Fork bomb
        r'sudo\s+rm',
        r'chmod\s+777',
        r'wget.*\|\s*sh',
        r'curl.*\|\s*sh',
        r'eval\s*\(',
        r'exec\s*\(',
        r'system\s*\(',
        r'popen\s*\(',
        r'subprocess\.',
        r'os\.system',
        r'__import__',
        r'globals\(\)',
        r'locals\(\)',
    ]
    
    # Safe file extensions
    SAFE_EXTENSIONS = {
        '.py', '.js', '.ts', '.java', '.cpp', '.h', '.c', '.cs', '.go',
        '.rs', '.php', '.rb', '.swift', '.kt', '.scala', '.clj', '.hs',
        '.ml', '.r', '.sql', '.html', '.css', '.scss', '.less', '.vue',
        '.jsx', '.tsx', '.json', '.yaml', '.yml', '.xml', '.toml', '.ini',
        '.cfg', '.conf', '.md', '.rst', '.txt', '.log', '.sh', '.bat',
        '.ps1', '.dockerfile', '.makefile', '.cmake', '.gradle'
    }
    
    # Allowed domains for web requests
    ALLOWED_DOMAINS = {
        'github.com', 'gitlab.com', 'bitbucket.org', 'stackoverflow.com',
        'docs.python.org', 'developer.mozilla.org', 'npmjs.com',
        'pypi.org', 'crates.io', 'maven.apache.org', 'nuget.org'
    }
    
    def __init__(self, config=None):
        self.config = config
        
        # Update patterns and domains from config if available
        if config and hasattr(config, 'security'):
            if hasattr(config.security, 'blocked_commands'):
                self.DANGEROUS_PATTERNS.extend(config.security.blocked_commands)
            if hasattr(config.security, 'allowed_domains'):
                self.ALLOWED_DOMAINS.update(config.security.allowed_domains)
    
    def validate_file_path(self, file_path: Union[str, Path]) -> bool:
        """Validate file path for safety"""
        try:
            path = Path(file_path).resolve()
            
            # Check for directory traversal
            if '..' in str(path):
                logger.warning("Directory traversal detected", path=str(path))
                return False
            
            # Check if path is within allowed directories
            allowed_paths = [
                Path.cwd().resolve(),  # Current working directory
                Path.home().resolve(),  # User's home directory
                Path.home().resolve() / "Documents",  # Documents folder
                Path.home().resolve() / "Desktop",    # Desktop folder
                Path.home().resolve() / "Downloads",  # Downloads folder
            ]

            # Allow access to any subdirectory of allowed paths
            path_allowed = False
            for allowed_path in allowed_paths:
                try:
                    path.relative_to(allowed_path)
                    path_allowed = True
                    break
                except ValueError:
                    continue

            if not path_allowed:
                logger.warning("Path outside allowed directories", path=str(path))
                return False
            
            # Check file extension
            if path.suffix and path.suffix.lower() not in self.SAFE_EXTENSIONS:
                logger.warning("Unsafe file extension", extension=path.suffix)
                return False
            
            return True
            
        except Exception as e:
            logger.error("File path validation failed", path=str(file_path), error=str(e))
            return False
    
    def validate_file_size(self, file_path: Union[str, Path], max_size_mb: int = 10) -> bool:
        """Validate file size"""
        try:
            path = Path(file_path)
            if not path.exists():
                return True  # File doesn't exist yet, size check passes
            
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb:
                logger.warning("File too large", path=str(path), size_mb=size_mb, max_size_mb=max_size_mb)
                return False
            
            return True
            
        except Exception as e:
            logger.error("File size validation failed", path=str(file_path), error=str(e))
            return False
    
    def validate_command(self, command: str) -> bool:
        """Validate command for dangerous patterns"""
        command_lower = command.lower()
        
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command_lower, re.IGNORECASE):
                logger.warning("Dangerous command pattern detected", command=command, pattern=pattern)
                return False
        
        return True
    
    def validate_url(self, url: str) -> bool:
        """Validate URL for safety"""
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ('http', 'https'):
                logger.warning("Invalid URL scheme", url=url, scheme=parsed.scheme)
                return False
            
            # Check domain
            domain = parsed.netloc.lower()
            if domain not in self.ALLOWED_DOMAINS:
                # Check if it's a subdomain of allowed domain
                allowed = False
                for allowed_domain in self.ALLOWED_DOMAINS:
                    if domain.endswith(f'.{allowed_domain}') or domain == allowed_domain:
                        allowed = True
                        break
                
                if not allowed:
                    logger.warning("Domain not allowed", url=url, domain=domain)
                    return False
            
            return True
            
        except Exception as e:
            logger.error("URL validation failed", url=url, error=str(e))
            return False
    
    def validate_chat_request(self, request_data: Dict[str, Any]) -> bool:
        """Validate chat request data"""
        try:
            # Check required fields
            if 'messages' not in request_data:
                logger.warning("Missing messages in chat request")
                return False
            
            messages = request_data['messages']
            if not isinstance(messages, list) or not messages:
                logger.warning("Invalid messages format")
                return False
            
            # Validate each message
            for i, message in enumerate(messages):
                if not isinstance(message, dict):
                    logger.warning("Invalid message format", index=i)
                    return False
                
                if 'role' not in message or 'content' not in message:
                    logger.warning("Missing required message fields", index=i)
                    return False
                
                # Check content length
                content = message['content']
                if len(content) > 100000:  # 100KB limit
                    logger.warning("Message content too long", index=i, length=len(content))
                    return False
                
                # Check for dangerous patterns in content
                if not self.validate_command(content):
                    return False
            
            # Validate model
            model = request_data.get('model', '')
            if not model or not isinstance(model, str):
                logger.warning("Invalid model specification")
                return False
            
            # Validate temperature
            temperature = request_data.get('temperature', 0.7)
            if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
                logger.warning("Invalid temperature", temperature=temperature)
                return False
            
            # Validate max_tokens
            max_tokens = request_data.get('max_tokens')
            if max_tokens is not None:
                if not isinstance(max_tokens, int) or max_tokens <= 0 or max_tokens > 100000:
                    logger.warning("Invalid max_tokens", max_tokens=max_tokens)
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Chat request validation failed", error=str(e))
            return False
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe use"""
        # Remove dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255-len(ext)] + ext
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = 'untitled'
        
        return sanitized
    
    def create_safe_temp_file(self, content: str, suffix: str = '.tmp') -> Path:
        """Create a temporary file with safe content"""
        try:
            # Validate content
            if len(content) > 10 * 1024 * 1024:  # 10MB limit
                raise ValueError("Content too large for temporary file")
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
                f.write(content)
                temp_path = Path(f.name)
            
            logger.debug("Safe temporary file created", path=str(temp_path))
            return temp_path
            
        except Exception as e:
            logger.error("Failed to create safe temporary file", error=str(e))
            raise
    
    def hash_content(self, content: str) -> str:
        """Create hash of content for integrity checking"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def validate_json_data(self, data: Any, max_depth: int = 10) -> bool:
        """Validate JSON data for safety"""
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                return False
            
            if isinstance(obj, dict):
                if len(obj) > 1000:  # Limit dict size
                    return False
                for key, value in obj.items():
                    if not isinstance(key, str) or len(key) > 1000:
                        return False
                    if not check_depth(value, current_depth + 1):
                        return False
            elif isinstance(obj, list):
                if len(obj) > 1000:  # Limit list size
                    return False
                for item in obj:
                    if not check_depth(item, current_depth + 1):
                        return False
            elif isinstance(obj, str):
                if len(obj) > 100000:  # 100KB limit for strings
                    return False
            
            return True
        
        try:
            return check_depth(data)
        except Exception as e:
            logger.error("JSON validation failed", error=str(e))
            return False
    
    def safe_execute_command(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        timeout: int = 30,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Safely execute a command with validation"""
        # Validate command
        command_str = ' '.join(command)
        if not self.validate_command(command_str):
            raise ValueError(f"Command failed security validation: {command_str}")
        
        # Validate working directory
        if cwd and not self.validate_file_path(cwd):
            raise ValueError(f"Working directory failed validation: {cwd}")
        
        try:
            # Execute with restrictions
            import platform

            # On Windows, use shell=True for built-in commands
            use_shell = platform.system() == "Windows"

            result = subprocess.run(
                command,
                cwd=cwd,
                timeout=timeout,
                capture_output=capture_output,
                text=True,
                check=False,  # Don't raise on non-zero exit
                shell=use_shell,
            )
            
            logger.debug("Command executed safely", command=command_str, returncode=result.returncode)
            return result
            
        except subprocess.TimeoutExpired:
            logger.warning("Command timed out", command=command_str, timeout=timeout)
            raise
        except Exception as e:
            logger.error("Command execution failed", command=command_str, error=str(e))
            raise
    
    def create_backup(self, file_path: Union[str, Path]) -> Optional[Path]:
        """Create a backup of a file"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            # Validate file path
            if not self.validate_file_path(path):
                raise ValueError(f"File path failed validation: {path}")
            
            # Create backup path
            backup_path = path.with_suffix(path.suffix + '.backup')
            counter = 1
            while backup_path.exists():
                backup_path = path.with_suffix(f'{path.suffix}.backup.{counter}')
                counter += 1
            
            # Copy file
            import shutil
            shutil.copy2(path, backup_path)
            
            logger.info("Backup created", original=str(path), backup=str(backup_path))
            return backup_path
            
        except Exception as e:
            logger.error("Failed to create backup", file_path=str(file_path), error=str(e))
            return None
