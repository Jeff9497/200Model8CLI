"""
System Tools for 200Model8CLI

Provides system operations, command execution, and environment management.
"""

import asyncio
import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

import structlog
import psutil

from .base import BaseTool, ToolCategory, ToolParameter, ToolResult
from ..core.config import Config
from ..utils.helpers import get_system_info, format_file_size

logger = structlog.get_logger(__name__)


class ExecuteCommandTool(BaseTool):
    """Execute system commands safely"""
    
    @property
    def name(self) -> str:
        return "execute_command"
    
    @property
    def description(self) -> str:
        return "Execute system commands with safety checks"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM_TOOLS
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    @property
    def dangerous(self) -> bool:
        return True
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="Command to execute",
                required=True,
            ),
            ToolParameter(
                name="working_directory",
                type="string",
                description="Working directory (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout in seconds (default: 30)",
                required=False,
                default=30,
                min_value=1,
                max_value=300,
            ),
            ToolParameter(
                name="capture_output",
                type="boolean",
                description="Capture command output (default: true)",
                required=False,
                default=True,
            ),
        ]
    
    async def execute(
        self,
        command: str,
        working_directory: str = ".",
        timeout: int = 30,
        capture_output: bool = True
    ) -> ToolResult:
        try:
            # Convert Unix commands to Windows equivalents
            command = self._convert_command_for_windows(command)

            # Security validation
            if not self.security.validate_command(command):
                return ToolResult(success=False, error="Command failed security validation")

            work_dir = Path(working_directory).resolve()
            if not self.security.validate_file_path(work_dir):
                return ToolResult(success=False, error="Working directory validation failed")

            # Execute command safely
            result = self.security.safe_execute_command(
                command.split(),
                cwd=work_dir,
                timeout=timeout,
                capture_output=capture_output
            )
            
            return ToolResult(
                success=result.returncode == 0,
                result={
                    "command": command,
                    "working_directory": str(work_dir),
                    "return_code": result.returncode,
                    "stdout": result.stdout if capture_output else None,
                    "stderr": result.stderr if capture_output else None,
                    "execution_time": timeout,  # Approximate
                }
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Command timed out after {timeout} seconds")
        except Exception as e:
            return ToolResult(success=False, error=f"Command execution failed: {str(e)}")

    def _convert_command_for_windows(self, command: str) -> str:
        """Convert Unix commands to Windows equivalents"""
        import platform

        if platform.system() != "Windows":
            return command

        # Common Unix to Windows command mappings
        command_mappings = {
            "ls": "dir",
            "ls -la": "dir",
            "ls -l": "dir",
            "ls -a": "dir /a",
            "cat": "type",
            "pwd": "cd",
            "cp": "copy",
            "mv": "move",
            "rm": "del",
            "mkdir": "mkdir",
            "rmdir": "rmdir",
            "grep": "findstr",
            "which": "where",
            "ps": "tasklist",
            "kill": "taskkill",
            "clear": "cls",
            "head": "more",
            "tail": "more",
        }

        # Check for exact matches first
        if command in command_mappings:
            return command_mappings[command]

        # Check for commands that start with mapped commands
        for unix_cmd, windows_cmd in command_mappings.items():
            if command.startswith(unix_cmd + " "):
                # Replace the command but keep the arguments
                return command.replace(unix_cmd, windows_cmd, 1)

        return command


class SystemInfoTool(BaseTool):
    """Get system information"""
    
    @property
    def name(self) -> str:
        return "system_info"
    
    @property
    def description(self) -> str:
        return "Get comprehensive system information"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="include_processes",
                type="boolean",
                description="Include running processes (default: false)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="include_network",
                type="boolean",
                description="Include network information (default: false)",
                required=False,
                default=False,
            ),
        ]
    
    async def execute(
        self,
        include_processes: bool = False,
        include_network: bool = False
    ) -> ToolResult:
        try:
            # Get basic system info
            info = get_system_info()
            
            # Add Python environment info
            info["python"] = {
                "version": sys.version,
                "executable": sys.executable,
                "path": sys.path[:5],  # First 5 paths
                "platform": sys.platform,
            }
            
            # Add current working directory
            info["current_directory"] = str(Path.cwd())
            
            # Add environment variables (filtered)
            safe_env_vars = [
                "PATH", "HOME", "USER", "USERNAME", "SHELL", "TERM",
                "LANG", "LC_ALL", "TZ", "PWD", "OLDPWD"
            ]
            info["environment"] = {
                key: os.environ.get(key, "") 
                for key in safe_env_vars 
                if key in os.environ
            }
            
            # Add disk usage for current directory
            try:
                disk_usage = shutil.disk_usage(Path.cwd())
                info["current_disk_usage"] = {
                    "total": format_file_size(disk_usage.total),
                    "used": format_file_size(disk_usage.used),
                    "free": format_file_size(disk_usage.free),
                    "percent_used": (disk_usage.used / disk_usage.total) * 100,
                }
            except Exception:
                pass
            
            # Add process information if requested
            if include_processes:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Sort by CPU usage and take top 10
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
                info["top_processes"] = processes[:10]
            
            # Add network information if requested
            if include_network:
                try:
                    network_info = {
                        "interfaces": {},
                        "connections": len(psutil.net_connections()),
                    }
                    
                    for interface, addrs in psutil.net_if_addrs().items():
                        network_info["interfaces"][interface] = [
                            {
                                "family": addr.family.name,
                                "address": addr.address,
                                "netmask": addr.netmask,
                            }
                            for addr in addrs
                        ]
                    
                    info["network"] = network_info
                except Exception:
                    pass
            
            return ToolResult(success=True, result=info)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get system info: {str(e)}")


class CheckDependenciesTool(BaseTool):
    """Check if dependencies are installed"""
    
    @property
    def name(self) -> str:
        return "check_dependencies"
    
    @property
    def description(self) -> str:
        return "Check if required dependencies/commands are available"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="dependencies",
                type="array",
                description="List of dependencies to check",
                required=True,
            ),
            ToolParameter(
                name="check_type",
                type="string",
                description="Type of check to perform",
                required=False,
                default="command",
                enum=["command", "python_package", "both"],
            ),
        ]
    
    async def execute(
        self,
        dependencies: List[str],
        check_type: str = "command"
    ) -> ToolResult:
        try:
            results = []
            
            for dep in dependencies:
                dep_result = {
                    "name": dep,
                    "available": False,
                    "version": None,
                    "location": None,
                    "check_type": check_type,
                }
                
                if check_type in ["command", "both"]:
                    # Check if command is available
                    command_available = shutil.which(dep) is not None
                    if command_available:
                        dep_result["available"] = True
                        dep_result["location"] = shutil.which(dep)
                        
                        # Try to get version
                        try:
                            version_result = subprocess.run(
                                [dep, "--version"],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if version_result.returncode == 0:
                                dep_result["version"] = version_result.stdout.strip()
                        except Exception:
                            try:
                                version_result = subprocess.run(
                                    [dep, "-V"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if version_result.returncode == 0:
                                    dep_result["version"] = version_result.stdout.strip()
                            except Exception:
                                pass
                
                if check_type in ["python_package", "both"] and not dep_result["available"]:
                    # Check if Python package is available
                    try:
                        import importlib
                        module = importlib.import_module(dep)
                        dep_result["available"] = True
                        dep_result["location"] = getattr(module, '__file__', 'built-in')
                        
                        # Try to get version
                        version = getattr(module, '__version__', None)
                        if version:
                            dep_result["version"] = version
                    except ImportError:
                        pass
                
                results.append(dep_result)
            
            # Summary
            available_count = sum(1 for r in results if r["available"])
            
            return ToolResult(
                success=True,
                result={
                    "dependencies": results,
                    "total_checked": len(dependencies),
                    "available": available_count,
                    "missing": len(dependencies) - available_count,
                    "all_available": available_count == len(dependencies),
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Dependency check failed: {str(e)}")


class EnvironmentTool(BaseTool):
    """Manage environment variables"""
    
    @property
    def name(self) -> str:
        return "environment"
    
    @property
    def description(self) -> str:
        return "Get, set, or list environment variables"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: get, set, list, or unset",
                required=True,
                enum=["get", "set", "list", "unset"],
            ),
        ]
    
    async def execute(
        self,
        action: str,
        **kwargs
    ) -> ToolResult:
        try:
            # Extract optional parameters
            variable_name = kwargs.get("variable_name")
            variable_value = kwargs.get("variable_value")

            if action == "list":
                # List all environment variables (filtered for security)
                safe_vars = {}
                sensitive_patterns = [
                    "password", "secret", "key", "token", "auth", "credential"
                ]
                
                for key, value in os.environ.items():
                    # Filter out sensitive variables
                    if any(pattern.lower() in key.lower() for pattern in sensitive_patterns):
                        safe_vars[key] = "[HIDDEN]"
                    else:
                        safe_vars[key] = value
                
                return ToolResult(
                    success=True,
                    result={
                        "action": "list",
                        "variables": safe_vars,
                        "total_variables": len(os.environ),
                        "shown_variables": len(safe_vars),
                    }
                )
            
            elif action == "get":
                if not variable_name:
                    return ToolResult(success=False, error="Variable name required for get action")
                
                value = os.environ.get(variable_name)
                return ToolResult(
                    success=True,
                    result={
                        "action": "get",
                        "variable_name": variable_name,
                        "value": value,
                        "exists": value is not None,
                    }
                )
            
            elif action == "set":
                if not variable_name or variable_value is None:
                    return ToolResult(success=False, error="Variable name and value required for set action")
                
                # Security check - don't allow setting sensitive variables
                sensitive_patterns = ["password", "secret", "key", "token"]
                if any(pattern.lower() in variable_name.lower() for pattern in sensitive_patterns):
                    return ToolResult(success=False, error="Cannot set sensitive environment variables")
                
                old_value = os.environ.get(variable_name)
                os.environ[variable_name] = variable_value
                
                return ToolResult(
                    success=True,
                    result={
                        "action": "set",
                        "variable_name": variable_name,
                        "old_value": old_value,
                        "new_value": variable_value,
                        "was_existing": old_value is not None,
                    }
                )
            
            elif action == "unset":
                if not variable_name:
                    return ToolResult(success=False, error="Variable name required for unset action")
                
                old_value = os.environ.get(variable_name)
                if old_value is not None:
                    del os.environ[variable_name]
                
                return ToolResult(
                    success=True,
                    result={
                        "action": "unset",
                        "variable_name": variable_name,
                        "old_value": old_value,
                        "was_existing": old_value is not None,
                    }
                )
            
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(success=False, error=f"Environment operation failed: {str(e)}")


class ProcessManagerTool(BaseTool):
    """Manage system processes"""
    
    @property
    def name(self) -> str:
        return "process_manager"
    
    @property
    def description(self) -> str:
        return "List, monitor, or manage system processes"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM_TOOLS
    
    @property
    def dangerous(self) -> bool:
        return True  # Can kill processes
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum=["list", "info", "kill"],
            ),
            ToolParameter(
                name="process_id",
                type="integer",
                description="Process ID (for info and kill actions)",
                required=False,
            ),
            ToolParameter(
                name="process_name",
                type="string",
                description="Process name pattern (for list filtering)",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of processes to return (default: 20)",
                required=False,
                default=20,
                min_value=1,
                max_value=100,
            ),
        ]
    
    async def execute(
        self,
        action: str,
        process_id: Optional[int] = None,
        process_name: Optional[str] = None,
        limit: int = 20
    ) -> ToolResult:
        try:
            if action == "list":
                processes = []
                
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
                    try:
                        proc_info = proc.info
                        
                        # Filter by name if specified
                        if process_name and process_name.lower() not in proc_info['name'].lower():
                            continue
                        
                        processes.append({
                            "pid": proc_info['pid'],
                            "name": proc_info['name'],
                            "cpu_percent": proc_info['cpu_percent'],
                            "memory_percent": proc_info['memory_percent'],
                            "status": proc_info['status'],
                            "create_time": proc_info['create_time'],
                        })
                        
                        if len(processes) >= limit:
                            break
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Sort by CPU usage
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                
                return ToolResult(
                    success=True,
                    result={
                        "action": "list",
                        "processes": processes,
                        "total_found": len(processes),
                        "filter": process_name,
                    }
                )
            
            elif action == "info":
                if not process_id:
                    return ToolResult(success=False, error="Process ID required for info action")
                
                try:
                    proc = psutil.Process(process_id)
                    info = {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "status": proc.status(),
                        "cpu_percent": proc.cpu_percent(),
                        "memory_percent": proc.memory_percent(),
                        "create_time": proc.create_time(),
                        "cwd": proc.cwd(),
                        "cmdline": proc.cmdline(),
                        "num_threads": proc.num_threads(),
                    }
                    
                    return ToolResult(
                        success=True,
                        result={
                            "action": "info",
                            "process_info": info,
                        }
                    )
                    
                except psutil.NoSuchProcess:
                    return ToolResult(success=False, error=f"Process {process_id} not found")
                except psutil.AccessDenied:
                    return ToolResult(success=False, error=f"Access denied to process {process_id}")
            
            elif action == "kill":
                if not process_id:
                    return ToolResult(success=False, error="Process ID required for kill action")
                
                try:
                    proc = psutil.Process(process_id)
                    proc_name = proc.name()
                    proc.terminate()
                    
                    # Wait a bit and check if it's really terminated
                    try:
                        proc.wait(timeout=3)
                        terminated = True
                    except psutil.TimeoutExpired:
                        # Force kill if terminate didn't work
                        proc.kill()
                        terminated = True
                    
                    return ToolResult(
                        success=True,
                        result={
                            "action": "kill",
                            "process_id": process_id,
                            "process_name": proc_name,
                            "terminated": terminated,
                        }
                    )
                    
                except psutil.NoSuchProcess:
                    return ToolResult(success=False, error=f"Process {process_id} not found")
                except psutil.AccessDenied:
                    return ToolResult(success=False, error=f"Access denied to kill process {process_id}")
            
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(success=False, error=f"Process management failed: {str(e)}")


# System Tools registry
class SystemTools:
    """Collection of system operation tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            ExecuteCommandTool(config),
            SystemInfoTool(config),
            CheckDependenciesTool(config),
            EnvironmentTool(config),
            ProcessManagerTool(config),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all system tools"""
        return self.tools
