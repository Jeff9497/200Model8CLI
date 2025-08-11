"""
File Operations Tools for 200Model8CLI

Comprehensive file operations including read, write, edit, search, backup, and diff.
"""

import os
import shutil
import difflib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import re
import json
import time

import aiofiles
import structlog

from .base import BaseTool, ToolCategory, ToolParameter, ToolResult
from ..core.config import Config
from ..utils.helpers import get_file_info, format_file_size, detect_file_language, is_binary_file

logger = structlog.get_logger(__name__)


class ReadFileTool(BaseTool):
    """Read file contents"""
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to read",
                required=True,
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="File encoding (default: utf-8)",
                required=False,
                default="utf-8",
            ),
            ToolParameter(
                name="max_size_mb",
                type="number",
                description="Maximum file size in MB (default: 10)",
                required=False,
                default=10,
                min_value=0.1,
                max_value=100,
            ),
        ]
    
    async def execute(self, path: str, encoding: str = "utf-8", max_size_mb: float = 10) -> ToolResult:
        try:
            file_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(file_path):
                return ToolResult(success=False, error="File path validation failed")
            
            if not self.security.validate_file_size(file_path, max_size_mb):
                return ToolResult(success=False, error=f"File too large (max: {max_size_mb}MB)")
            
            # Check if file exists
            if not file_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")
            
            if not file_path.is_file():
                return ToolResult(success=False, error=f"Path is not a file: {path}")
            
            # Check if binary file
            if is_binary_file(file_path):
                return ToolResult(success=False, error="Cannot read binary file")
            
            # Read file
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                content = await f.read()
            
            file_info = get_file_info(file_path)
            
            return ToolResult(
                success=True,
                result={
                    "content": content,
                    "path": str(file_path),
                    "size": file_info["size"],
                    "size_formatted": format_file_size(file_info["size"]),
                    "language": detect_file_language(file_path),
                    "line_count": content.count('\n') + 1 if content else 0,
                },
                metadata={"file_info": file_info}
            )
            
        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"Cannot decode file with encoding: {encoding}")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read file: {str(e)}")


class WriteFileTool(BaseTool):
    """Write content to a file"""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file, creating directories if needed"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to write",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write to the file",
                required=True,
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="File encoding (default: utf-8)",
                required=False,
                default="utf-8",
            ),
            ToolParameter(
                name="create_backup",
                type="boolean",
                description="Create backup if file exists (default: true)",
                required=False,
                default=True,
            ),
        ]
    
    async def execute(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_backup: bool = True
    ) -> ToolResult:
        try:
            file_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(file_path):
                return ToolResult(success=False, error="File path validation failed")
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup if file exists
            backup_path = None
            if file_path.exists() and create_backup:
                backup_path = self.security.create_backup(file_path)
            
            # Write file
            async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
                await f.write(content)
            
            file_info = get_file_info(file_path)
            
            return ToolResult(
                success=True,
                result={
                    "path": str(file_path),
                    "size": file_info["size"],
                    "size_formatted": format_file_size(file_info["size"]),
                    "backup_created": backup_path is not None,
                    "backup_path": str(backup_path) if backup_path else None,
                    "line_count": content.count('\n') + 1 if content else 0,
                },
                metadata={"file_info": file_info}
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to write file: {str(e)}")


class EditFileTool(BaseTool):
    """Edit existing file with specific changes"""
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit an existing file by applying specific changes"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to edit",
                required=True,
            ),
            ToolParameter(
                name="changes",
                type="string",
                description="Description of changes to make",
                required=True,
            ),
            ToolParameter(
                name="line_start",
                type="integer",
                description="Starting line number for changes (1-based, optional)",
                required=False,
                min_value=1,
            ),
            ToolParameter(
                name="line_end",
                type="integer",
                description="Ending line number for changes (1-based, optional)",
                required=False,
                min_value=1,
            ),
            ToolParameter(
                name="create_backup",
                type="boolean",
                description="Create backup before editing (default: true)",
                required=False,
                default=True,
            ),
        ]
    
    async def execute(
        self,
        path: str,
        changes: str,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        create_backup: bool = True
    ) -> ToolResult:
        try:
            file_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(file_path):
                return ToolResult(success=False, error="File path validation failed")
            
            if not file_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")
            
            # Read current content
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                original_content = await f.read()
            
            # Create backup
            backup_path = None
            if create_backup:
                backup_path = self.security.create_backup(file_path)
            
            # For now, this is a placeholder for AI-powered editing
            # In a real implementation, this would use the AI model to apply changes
            # based on the description and optional line range
            
            # Simple implementation: append changes as comment
            lines = original_content.split('\n')
            
            if line_start and line_end:
                # Insert changes at specific line range
                if line_start <= len(lines) and line_end <= len(lines):
                    comment_prefix = self._get_comment_prefix(file_path)
                    change_comment = f"{comment_prefix} EDIT: {changes}"
                    lines.insert(line_start - 1, change_comment)
            else:
                # Append changes as comment at end
                comment_prefix = self._get_comment_prefix(file_path)
                change_comment = f"{comment_prefix} EDIT: {changes}"
                lines.append(change_comment)
            
            new_content = '\n'.join(lines)
            
            # Write modified content
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(new_content)
            
            file_info = get_file_info(file_path)
            
            return ToolResult(
                success=True,
                result={
                    "path": str(file_path),
                    "changes_applied": changes,
                    "backup_created": backup_path is not None,
                    "backup_path": str(backup_path) if backup_path else None,
                    "original_size": len(original_content),
                    "new_size": len(new_content),
                    "size_formatted": format_file_size(file_info["size"]),
                },
                metadata={"file_info": file_info}
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to edit file: {str(e)}")
    
    def _get_comment_prefix(self, file_path: Path) -> str:
        """Get appropriate comment prefix for file type"""
        language = detect_file_language(file_path)
        
        comment_map = {
            'python': '#',
            'javascript': '//',
            'typescript': '//',
            'java': '//',
            'cpp': '//',
            'c': '//',
            'csharp': '//',
            'go': '//',
            'rust': '//',
            'php': '//',
            'ruby': '#',
            'swift': '//',
            'kotlin': '//',
            'scala': '//',
            'bash': '#',
            'powershell': '#',
            'yaml': '#',
            'toml': '#',
            'ini': '#',
            'sql': '--',
            'html': '<!--',
            'css': '/*',
        }
        
        return comment_map.get(language, '#')


class SearchFilesTool(BaseTool):
    """Search for files and content"""
    
    @property
    def name(self) -> str:
        return "search_files"
    
    @property
    def description(self) -> str:
        return "Search for files by name pattern or content with regex support"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="directory",
                type="string",
                description="Directory to search in (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="File name pattern or regex to search for",
                required=False,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content pattern to search for within files",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="Search recursively in subdirectories (default: true)",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="case_sensitive",
                type="boolean",
                description="Case sensitive search (default: false)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results (default: 100)",
                required=False,
                default=100,
                min_value=1,
                max_value=1000,
            ),
        ]
    
    async def execute(
        self,
        directory: str = ".",
        pattern: Optional[str] = None,
        content: Optional[str] = None,
        recursive: bool = True,
        case_sensitive: bool = False,
        max_results: int = 100
    ) -> ToolResult:
        try:
            search_dir = Path(directory).resolve()
            
            # Security validation
            if not self.security.validate_file_path(search_dir):
                return ToolResult(success=False, error="Directory path validation failed")
            
            if not search_dir.exists():
                return ToolResult(success=False, error=f"Directory not found: {directory}")
            
            if not search_dir.is_dir():
                return ToolResult(success=False, error=f"Path is not a directory: {directory}")
            
            results = []
            
            # Search for files
            if pattern:
                file_results = await self._search_by_pattern(
                    search_dir, pattern, recursive, case_sensitive, max_results
                )
                results.extend(file_results)
            
            # Search file contents
            if content:
                content_results = await self._search_by_content(
                    search_dir, content, recursive, case_sensitive, max_results - len(results)
                )
                results.extend(content_results)
            
            # If no specific search criteria, list files
            if not pattern and not content:
                file_results = await self._list_files(search_dir, recursive, max_results)
                results.extend(file_results)
            
            return ToolResult(
                success=True,
                result={
                    "results": results[:max_results],
                    "total_found": len(results),
                    "search_directory": str(search_dir),
                    "pattern": pattern,
                    "content_search": content,
                    "recursive": recursive,
                    "case_sensitive": case_sensitive,
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {str(e)}")
    
    async def _search_by_pattern(
        self,
        directory: Path,
        pattern: str,
        recursive: bool,
        case_sensitive: bool,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Search files by name pattern"""
        results = []
        flags = 0 if case_sensitive else re.IGNORECASE
        
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            # If regex fails, use as literal string
            pattern = re.escape(pattern)
            regex = re.compile(pattern, flags)
        
        glob_pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(glob_pattern):
            if len(results) >= max_results:
                break
            
            if file_path.is_file() and regex.search(file_path.name):
                file_info = get_file_info(file_path)
                results.append({
                    "type": "file_match",
                    "path": str(file_path),
                    "name": file_path.name,
                    "size": file_info["size"],
                    "size_formatted": format_file_size(file_info["size"]),
                    "modified": file_info["modified"],
                    "language": detect_file_language(file_path),
                })
        
        return results
    
    async def _search_by_content(
        self,
        directory: Path,
        content: str,
        recursive: bool,
        case_sensitive: bool,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Search file contents"""
        results = []
        flags = 0 if case_sensitive else re.IGNORECASE
        
        try:
            regex = re.compile(content, flags)
        except re.error:
            # If regex fails, use as literal string
            content = re.escape(content)
            regex = re.compile(content, flags)
        
        glob_pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(glob_pattern):
            if len(results) >= max_results:
                break
            
            if file_path.is_file() and not is_binary_file(file_path):
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        file_content = await f.read()
                    
                    matches = list(regex.finditer(file_content))
                    if matches:
                        file_info = get_file_info(file_path)
                        
                        # Get line numbers for matches
                        lines = file_content.split('\n')
                        match_info = []
                        
                        for match in matches[:10]:  # Limit matches per file
                            start_pos = match.start()
                            line_num = file_content[:start_pos].count('\n') + 1
                            line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                            
                            match_info.append({
                                "line": line_num,
                                "content": line_content.strip(),
                                "match": match.group(),
                                "start": match.start() - file_content.rfind('\n', 0, start_pos) - 1,
                                "end": match.end() - file_content.rfind('\n', 0, start_pos) - 1,
                            })
                        
                        results.append({
                            "type": "content_match",
                            "path": str(file_path),
                            "name": file_path.name,
                            "size": file_info["size"],
                            "size_formatted": format_file_size(file_info["size"]),
                            "modified": file_info["modified"],
                            "language": detect_file_language(file_path),
                            "matches": match_info,
                            "total_matches": len(matches),
                        })
                
                except (UnicodeDecodeError, PermissionError):
                    continue  # Skip files that can't be read
        
        return results
    
    async def _list_files(
        self,
        directory: Path,
        recursive: bool,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """List files in directory"""
        results = []
        glob_pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(glob_pattern):
            if len(results) >= max_results:
                break
            
            if file_path.is_file():
                file_info = get_file_info(file_path)
                results.append({
                    "type": "file_list",
                    "path": str(file_path),
                    "name": file_path.name,
                    "size": file_info["size"],
                    "size_formatted": format_file_size(file_info["size"]),
                    "modified": file_info["modified"],
                    "language": detect_file_language(file_path),
                })
        
        return results


class DiffFilesTool(BaseTool):
    """Compare two files and show differences"""

    @property
    def name(self) -> str:
        return "diff_files"

    @property
    def description(self) -> str:
        return "Compare two files and show their differences"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file1",
                type="string",
                description="Path to the first file",
                required=True,
            ),
            ToolParameter(
                name="file2",
                type="string",
                description="Path to the second file",
                required=True,
            ),
            ToolParameter(
                name="context_lines",
                type="integer",
                description="Number of context lines to show (default: 3)",
                required=False,
                default=3,
                min_value=0,
                max_value=20,
            ),
        ]

    async def execute(
        self,
        file1: str,
        file2: str,
        context_lines: int = 3
    ) -> ToolResult:
        try:
            path1 = Path(file1).resolve()
            path2 = Path(file2).resolve()

            # Security validation
            if not self.security.validate_file_path(path1) or not self.security.validate_file_path(path2):
                return ToolResult(success=False, error="File path validation failed")

            # Check if files exist
            if not path1.exists():
                return ToolResult(success=False, error=f"File not found: {file1}")
            if not path2.exists():
                return ToolResult(success=False, error=f"File not found: {file2}")

            # Read files
            async with aiofiles.open(path1, 'r', encoding='utf-8') as f:
                content1 = await f.read()
            async with aiofiles.open(path2, 'r', encoding='utf-8') as f:
                content2 = await f.read()

            # Generate diff
            lines1 = content1.splitlines(keepends=True)
            lines2 = content2.splitlines(keepends=True)

            diff = list(difflib.unified_diff(
                lines1,
                lines2,
                fromfile=str(path1),
                tofile=str(path2),
                n=context_lines
            ))

            # Count changes
            additions = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
            deletions = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

            return ToolResult(
                success=True,
                result={
                    "file1": str(path1),
                    "file2": str(path2),
                    "diff": ''.join(diff),
                    "additions": additions,
                    "deletions": deletions,
                    "total_changes": additions + deletions,
                    "identical": len(diff) == 0,
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Diff failed: {str(e)}")


class CopyFileTool(BaseTool):
    """Copy files with directory creation"""

    @property
    def name(self) -> str:
        return "copy_file"

    @property
    def description(self) -> str:
        return "Copy a file to another location, creating directories if needed"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="source",
                type="string",
                description="Source file path",
                required=True,
            ),
            ToolParameter(
                name="destination",
                type="string",
                description="Destination file path",
                required=True,
            ),
            ToolParameter(
                name="overwrite",
                type="boolean",
                description="Overwrite destination if it exists (default: false)",
                required=False,
                default=False,
            ),
        ]

    async def execute(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> ToolResult:
        try:
            src_path = Path(source).resolve()
            dst_path = Path(destination).resolve()

            # Security validation
            if not self.security.validate_file_path(src_path) or not self.security.validate_file_path(dst_path):
                return ToolResult(success=False, error="File path validation failed")

            # Check source exists
            if not src_path.exists():
                return ToolResult(success=False, error=f"Source file not found: {source}")

            if not src_path.is_file():
                return ToolResult(success=False, error=f"Source is not a file: {source}")

            # Check destination
            if dst_path.exists() and not overwrite:
                return ToolResult(success=False, error=f"Destination exists and overwrite is false: {destination}")

            # Create destination directory
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(src_path, dst_path)

            src_info = get_file_info(src_path)
            dst_info = get_file_info(dst_path)

            return ToolResult(
                success=True,
                result={
                    "source": str(src_path),
                    "destination": str(dst_path),
                    "size": dst_info["size"],
                    "size_formatted": format_file_size(dst_info["size"]),
                    "overwritten": dst_path.exists(),
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Copy failed: {str(e)}")


class DeleteFileTool(BaseTool):
    """Safe file deletion with confirmation"""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Safely delete a file with confirmation"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS

    @property
    def requires_confirmation(self) -> bool:
        return True

    @property
    def dangerous(self) -> bool:
        return True

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to delete",
                required=True,
            ),
            ToolParameter(
                name="create_backup",
                type="boolean",
                description="Create backup before deletion (default: true)",
                required=False,
                default=True,
            ),
        ]

    async def execute(
        self,
        path: str,
        create_backup: bool = True
    ) -> ToolResult:
        try:
            file_path = Path(path).resolve()

            # Security validation
            if not self.security.validate_file_path(file_path):
                return ToolResult(success=False, error="File path validation failed")

            if not file_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            if not file_path.is_file():
                return ToolResult(success=False, error=f"Path is not a file: {path}")

            file_info = get_file_info(file_path)

            # Create backup
            backup_path = None
            if create_backup:
                backup_path = self.security.create_backup(file_path)

            # Delete file
            file_path.unlink()

            return ToolResult(
                success=True,
                result={
                    "deleted_file": str(file_path),
                    "size": file_info["size"],
                    "size_formatted": format_file_size(file_info["size"]),
                    "backup_created": backup_path is not None,
                    "backup_path": str(backup_path) if backup_path else None,
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Delete failed: {str(e)}")


class CreateDirectoryTool(BaseTool):
    """Create directories recursively"""

    @property
    def name(self) -> str:
        return "create_directory"

    @property
    def description(self) -> str:
        return "Create a directory and all necessary parent directories"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATIONS

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Directory path to create",
                required=True,
            ),
        ]

    async def execute(self, path: str) -> ToolResult:
        try:
            dir_path = Path(path).resolve()

            # Security validation
            if not self.security.validate_file_path(dir_path):
                return ToolResult(success=False, error="Directory path validation failed")

            # Create directory
            dir_path.mkdir(parents=True, exist_ok=True)

            return ToolResult(
                success=True,
                result={
                    "created_directory": str(dir_path),
                    "exists": dir_path.exists(),
                    "is_directory": dir_path.is_dir(),
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Directory creation failed: {str(e)}")


# File Operations registry
class FileOperations:
    """Collection of file operation tools"""

    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            ReadFileTool(config),
            WriteFileTool(config),
            EditFileTool(config),
            SearchFilesTool(config),
            DiffFilesTool(config),
            CopyFileTool(config),
            DeleteFileTool(config),
            CreateDirectoryTool(config),
        ]

    def get_tools(self) -> List[BaseTool]:
        """Get all file operation tools"""
        return self.tools
