"""
Git & Version Control Tools for 200Model8CLI

Provides Git operations, GitHub integration, and intelligent commit message generation.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import re

import structlog
from git import Repo, InvalidGitRepositoryError
import httpx

from .base import BaseTool, ToolCategory, ToolParameter, ToolResult
from ..core.config import Config

logger = structlog.get_logger(__name__)


class GitStatusTool(BaseTool):
    """Check Git repository status"""
    
    @property
    def name(self) -> str:
        return "git_status"
    
    @property
    def description(self) -> str:
        return "Check the status of the Git repository"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to repository (default: current directory)",
                required=False,
                default=".",
            ),
        ]
    
    async def execute(self, path: str = ".") -> ToolResult:
        try:
            repo_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(repo_path):
                return ToolResult(success=False, error="Path validation failed")
            
            # Open repository
            try:
                repo = Repo(repo_path)
            except InvalidGitRepositoryError:
                return ToolResult(success=False, error="Not a Git repository")
            
            # Get status information
            status_info = {
                "repository_path": str(repo_path),
                "current_branch": repo.active_branch.name,
                "is_dirty": repo.is_dirty(),
                "untracked_files": repo.untracked_files,
                "modified_files": [item.a_path for item in repo.index.diff(None)],
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
                "commits_ahead": 0,
                "commits_behind": 0,
                "remote_url": None,
            }
            
            # Get remote information
            try:
                origin = repo.remote('origin')
                status_info["remote_url"] = list(origin.urls)[0]
                
                # Get ahead/behind info
                try:
                    ahead_behind = repo.git.rev_list('--left-right', '--count', 'HEAD...origin/HEAD')
                    if ahead_behind:
                        parts = ahead_behind.split('\t')
                        if len(parts) == 2:
                            status_info["commits_ahead"] = int(parts[0])
                            status_info["commits_behind"] = int(parts[1])
                except Exception:
                    pass  # Remote tracking might not be set up
            except Exception:
                pass  # No remote configured
            
            # Get recent commits
            recent_commits = []
            for commit in repo.iter_commits(max_count=5):
                recent_commits.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                })
            
            status_info["recent_commits"] = recent_commits
            
            return ToolResult(success=True, result=status_info)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Git status failed: {str(e)}")


class GitCommitTool(BaseTool):
    """Commit changes with AI-generated message"""
    
    @property
    def name(self) -> str:
        return "git_commit"
    
    @property
    def description(self) -> str:
        return "Commit staged changes with an optional AI-generated commit message"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT_TOOLS
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="message",
                type="string",
                description="Commit message (if not provided, will analyze changes)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to repository (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="add_all",
                type="boolean",
                description="Add all modified files before committing (default: false)",
                required=False,
                default=False,
            ),
        ]
    
    async def execute(
        self,
        message: Optional[str] = None,
        path: str = ".",
        add_all: bool = False
    ) -> ToolResult:
        try:
            repo_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(repo_path):
                return ToolResult(success=False, error="Path validation failed")
            
            # Open repository
            try:
                repo = Repo(repo_path)
            except InvalidGitRepositoryError:
                return ToolResult(success=False, error="Not a Git repository")
            
            # Add files if requested
            if add_all:
                repo.git.add(A=True)
            
            # Check if there are staged changes
            if not repo.index.diff("HEAD"):
                return ToolResult(success=False, error="No staged changes to commit")
            
            # Generate commit message if not provided
            if not message:
                message = await self._generate_commit_message(repo)
            
            # Commit changes
            commit = repo.index.commit(message)
            
            return ToolResult(
                success=True,
                result={
                    "commit_hash": commit.hexsha[:8],
                    "message": message,
                    "files_changed": len(repo.index.diff("HEAD~1")),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Git commit failed: {str(e)}")
    
    async def _generate_commit_message(self, repo: Repo) -> str:
        """Generate commit message based on changes"""
        try:
            # Get diff of staged changes
            diff = repo.git.diff('--cached')
            
            if not diff:
                return "Update files"
            
            # Analyze changes to generate message
            # This is a simple implementation - in a full version, 
            # you'd use the AI model to generate better messages
            
            # Count file types and changes
            added_files = []
            modified_files = []
            deleted_files = []
            
            for item in repo.index.diff("HEAD"):
                if item.change_type == 'A':
                    added_files.append(item.a_path)
                elif item.change_type == 'M':
                    modified_files.append(item.a_path)
                elif item.change_type == 'D':
                    deleted_files.append(item.a_path)
            
            # Generate message based on changes
            message_parts = []
            
            if added_files:
                if len(added_files) == 1:
                    message_parts.append(f"Add {added_files[0]}")
                else:
                    message_parts.append(f"Add {len(added_files)} files")
            
            if modified_files:
                if len(modified_files) == 1:
                    message_parts.append(f"Update {modified_files[0]}")
                else:
                    message_parts.append(f"Update {len(modified_files)} files")
            
            if deleted_files:
                if len(deleted_files) == 1:
                    message_parts.append(f"Remove {deleted_files[0]}")
                else:
                    message_parts.append(f"Remove {len(deleted_files)} files")
            
            if message_parts:
                return " and ".join(message_parts)
            else:
                return "Update repository"
                
        except Exception as e:
            logger.warning("Failed to generate commit message", error=str(e))
            return "Update files"


class GitPushTool(BaseTool):
    """Push commits to remote repository"""
    
    @property
    def name(self) -> str:
        return "git_push"
    
    @property
    def description(self) -> str:
        return "Push commits to remote repository"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT_TOOLS
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="remote",
                type="string",
                description="Remote name (default: origin)",
                required=False,
                default="origin",
            ),
            ToolParameter(
                name="branch",
                type="string",
                description="Branch to push (default: current branch)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to repository (default: current directory)",
                required=False,
                default=".",
            ),
        ]
    
    async def execute(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        path: str = "."
    ) -> ToolResult:
        try:
            repo_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(repo_path):
                return ToolResult(success=False, error="Path validation failed")
            
            # Open repository
            try:
                repo = Repo(repo_path)
            except InvalidGitRepositoryError:
                return ToolResult(success=False, error="Not a Git repository")
            
            # Get current branch if not specified
            if not branch:
                branch = repo.active_branch.name
            
            # Push to remote
            origin = repo.remote(remote)
            push_info = origin.push(branch)
            
            # Analyze push results
            results = []
            for info in push_info:
                results.append({
                    "local_ref": str(info.local_ref),
                    "remote_ref": str(info.remote_ref),
                    "flags": info.flags,
                    "summary": info.summary,
                })
            
            return ToolResult(
                success=True,
                result={
                    "remote": remote,
                    "branch": branch,
                    "push_results": results,
                    "total_pushes": len(results),
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Git push failed: {str(e)}")


class GitPullTool(BaseTool):
    """Pull changes from remote repository"""
    
    @property
    def name(self) -> str:
        return "git_pull"
    
    @property
    def description(self) -> str:
        return "Pull changes from remote repository"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="remote",
                type="string",
                description="Remote name (default: origin)",
                required=False,
                default="origin",
            ),
            ToolParameter(
                name="branch",
                type="string",
                description="Branch to pull (default: current branch)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to repository (default: current directory)",
                required=False,
                default=".",
            ),
        ]
    
    async def execute(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        path: str = "."
    ) -> ToolResult:
        try:
            repo_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(repo_path):
                return ToolResult(success=False, error="Path validation failed")
            
            # Open repository
            try:
                repo = Repo(repo_path)
            except InvalidGitRepositoryError:
                return ToolResult(success=False, error="Not a Git repository")
            
            # Get current branch if not specified
            if not branch:
                branch = repo.active_branch.name
            
            # Pull from remote
            origin = repo.remote(remote)
            pull_info = origin.pull(branch)
            
            # Analyze pull results
            results = []
            for info in pull_info:
                results.append({
                    "ref": str(info.ref),
                    "flags": info.flags,
                    "note": info.note,
                    "old_commit": info.old_commit.hexsha[:8] if info.old_commit else None,
                    "commit": info.commit.hexsha[:8] if info.commit else None,
                })
            
            return ToolResult(
                success=True,
                result={
                    "remote": remote,
                    "branch": branch,
                    "pull_results": results,
                    "total_pulls": len(results),
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Git pull failed: {str(e)}")


class GitBranchTool(BaseTool):
    """Create and manage Git branches"""
    
    @property
    def name(self) -> str:
        return "git_branch"
    
    @property
    def description(self) -> str:
        return "Create, list, or switch Git branches"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.GIT_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum=["list", "create", "switch", "delete"],
            ),
            ToolParameter(
                name="branch_name",
                type="string",
                description="Branch name (required for create, switch, delete)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to repository (default: current directory)",
                required=False,
                default=".",
            ),
        ]
    
    async def execute(
        self,
        action: str,
        branch_name: Optional[str] = None,
        path: str = "."
    ) -> ToolResult:
        try:
            repo_path = Path(path).resolve()
            
            # Security validation
            if not self.security.validate_file_path(repo_path):
                return ToolResult(success=False, error="Path validation failed")
            
            # Open repository
            try:
                repo = Repo(repo_path)
            except InvalidGitRepositoryError:
                return ToolResult(success=False, error="Not a Git repository")
            
            if action == "list":
                return await self._list_branches(repo)
            elif action == "create":
                if not branch_name:
                    return ToolResult(success=False, error="Branch name required for create action")
                return await self._create_branch(repo, branch_name)
            elif action == "switch":
                if not branch_name:
                    return ToolResult(success=False, error="Branch name required for switch action")
                return await self._switch_branch(repo, branch_name)
            elif action == "delete":
                if not branch_name:
                    return ToolResult(success=False, error="Branch name required for delete action")
                return await self._delete_branch(repo, branch_name)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(success=False, error=f"Git branch operation failed: {str(e)}")
    
    async def _list_branches(self, repo: Repo) -> ToolResult:
        """List all branches"""
        branches = []
        current_branch = repo.active_branch.name
        
        for branch in repo.branches:
            branches.append({
                "name": branch.name,
                "is_current": branch.name == current_branch,
                "commit": branch.commit.hexsha[:8],
                "commit_message": branch.commit.message.strip(),
            })
        
        return ToolResult(
            success=True,
            result={
                "current_branch": current_branch,
                "branches": branches,
                "total_branches": len(branches),
            }
        )
    
    async def _create_branch(self, repo: Repo, branch_name: str) -> ToolResult:
        """Create a new branch"""
        # Check if branch already exists
        if branch_name in [b.name for b in repo.branches]:
            return ToolResult(success=False, error=f"Branch '{branch_name}' already exists")
        
        # Create branch
        new_branch = repo.create_head(branch_name)
        
        return ToolResult(
            success=True,
            result={
                "branch_name": branch_name,
                "created": True,
                "commit": new_branch.commit.hexsha[:8],
            }
        )
    
    async def _switch_branch(self, repo: Repo, branch_name: str) -> ToolResult:
        """Switch to a branch"""
        # Check if branch exists
        if branch_name not in [b.name for b in repo.branches]:
            return ToolResult(success=False, error=f"Branch '{branch_name}' does not exist")
        
        # Switch branch
        repo.git.checkout(branch_name)
        
        return ToolResult(
            success=True,
            result={
                "branch_name": branch_name,
                "switched": True,
                "commit": repo.active_branch.commit.hexsha[:8],
            }
        )
    
    async def _delete_branch(self, repo: Repo, branch_name: str) -> ToolResult:
        """Delete a branch"""
        # Check if branch exists
        if branch_name not in [b.name for b in repo.branches]:
            return ToolResult(success=False, error=f"Branch '{branch_name}' does not exist")
        
        # Check if it's the current branch
        if branch_name == repo.active_branch.name:
            return ToolResult(success=False, error="Cannot delete the current branch")
        
        # Delete branch
        repo.delete_head(branch_name)
        
        return ToolResult(
            success=True,
            result={
                "branch_name": branch_name,
                "deleted": True,
            }
        )


# Git Tools registry
class GitTools:
    """Collection of Git and version control tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            GitStatusTool(config),
            GitCommitTool(config),
            GitPushTool(config),
            GitPullTool(config),
            GitBranchTool(config),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all Git tools"""
        return self.tools
