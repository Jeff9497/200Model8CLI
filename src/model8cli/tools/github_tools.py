"""
GitHub integration tools for 200Model8CLI

Provides comprehensive GitHub API integration including repository management,
pull requests, issues, and workflow automation.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx
from dataclasses import dataclass

import structlog

from .base import BaseTool, ToolResult, ToolCategory
from ..core.config import Config
from ..utils.security import SecurityValidator

logger = structlog.get_logger(__name__)


@dataclass
class GitHubConfig:
    """GitHub configuration"""
    token: Optional[str] = None
    base_url: str = "https://api.github.com"
    timeout: int = 30


class GitHubClient:
    """GitHub API client"""
    
    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self.token = token
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "200Model8CLI/1.0.0"
            },
            timeout=30.0
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def get(self, endpoint: str, **params) -> Dict[str, Any]:
        """Make GET request to GitHub API"""
        response = await self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to GitHub API"""
        response = await self.client.post(endpoint, json=data)
        response.raise_for_status()
        return response.json()
    
    async def patch(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make PATCH request to GitHub API"""
        response = await self.client.patch(endpoint, json=data)
        response.raise_for_status()
        return response.json()
    
    async def delete(self, endpoint: str) -> bool:
        """Make DELETE request to GitHub API"""
        response = await self.client.delete(endpoint)
        response.raise_for_status()
        return response.status_code == 204


class CreateRepositoryTool(BaseTool):
    """Tool for creating GitHub repositories"""
    
    name = "create_github_repo"
    description = "Create a new GitHub repository"
    category = ToolCategory.GIT_TOOLS
    
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Repository name"
            },
            "description": {
                "type": "string", 
                "description": "Repository description"
            },
            "private": {
                "type": "boolean",
                "description": "Whether the repository should be private",
                "default": False
            },
            "auto_init": {
                "type": "boolean",
                "description": "Whether to initialize with README",
                "default": True
            },
            "gitignore_template": {
                "type": "string",
                "description": "Gitignore template (e.g., 'Python', 'Node')",
                "default": None
            },
            "license_template": {
                "type": "string",
                "description": "License template (e.g., 'mit', 'apache-2.0')",
                "default": None
            }
        },
        "required": ["name"]
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)
    
    async def execute(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None
    ) -> ToolResult:
        try:
            if not self.github_token:
                return ToolResult(success=False, error="GitHub token not configured")
            
            async with GitHubClient(self.github_token) as client:
                repo_data = {
                    "name": name,
                    "description": description,
                    "private": private,
                    "auto_init": auto_init
                }
                
                if gitignore_template:
                    repo_data["gitignore_template"] = gitignore_template
                
                if license_template:
                    repo_data["license_template"] = license_template
                
                repo = await client.post("/user/repos", repo_data)
                
                return ToolResult(
                    success=True,
                    result={
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "html_url": repo["html_url"],
                        "clone_url": repo["clone_url"],
                        "ssh_url": repo["ssh_url"],
                        "private": repo["private"],
                        "description": repo["description"],
                        "created_at": repo["created_at"]
                    }
                )
                
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create repository: {str(e)}")


class CreatePullRequestTool(BaseTool):
    """Tool for creating GitHub pull requests"""
    
    name = "create_pull_request"
    description = "Create a new pull request on GitHub"
    category = ToolCategory.GIT_TOOLS
    
    parameters = {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner"
            },
            "repo": {
                "type": "string",
                "description": "Repository name"
            },
            "title": {
                "type": "string",
                "description": "Pull request title"
            },
            "body": {
                "type": "string",
                "description": "Pull request description"
            },
            "head": {
                "type": "string",
                "description": "Branch to merge from"
            },
            "base": {
                "type": "string",
                "description": "Branch to merge into",
                "default": "main"
            },
            "draft": {
                "type": "boolean",
                "description": "Create as draft PR",
                "default": False
            }
        },
        "required": ["owner", "repo", "title", "head"]
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)
    
    async def execute(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        body: str = "",
        base: str = "main",
        draft: bool = False
    ) -> ToolResult:
        try:
            if not self.github_token:
                return ToolResult(success=False, error="GitHub token not configured")
            
            async with GitHubClient(self.github_token) as client:
                pr_data = {
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                    "draft": draft
                }
                
                pr = await client.post(f"/repos/{owner}/{repo}/pulls", pr_data)
                
                return ToolResult(
                    success=True,
                    result={
                        "number": pr["number"],
                        "title": pr["title"],
                        "html_url": pr["html_url"],
                        "state": pr["state"],
                        "draft": pr["draft"],
                        "head": pr["head"]["ref"],
                        "base": pr["base"]["ref"],
                        "created_at": pr["created_at"],
                        "user": pr["user"]["login"]
                    }
                )
                
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create pull request: {str(e)}")


class ListIssuesTool(BaseTool):
    """Tool for listing GitHub issues"""
    
    name = "list_github_issues"
    description = "List issues from a GitHub repository"
    category = ToolCategory.GIT_TOOLS
    
    parameters = {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner"
            },
            "repo": {
                "type": "string",
                "description": "Repository name"
            },
            "state": {
                "type": "string",
                "description": "Issue state",
                "enum": ["open", "closed", "all"],
                "default": "open"
            },
            "labels": {
                "type": "string",
                "description": "Comma-separated list of labels"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of issues to return",
                "default": 30
            }
        },
        "required": ["owner", "repo"]
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)
    
    async def execute(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: Optional[str] = None,
        limit: int = 30
    ) -> ToolResult:
        try:
            if not self.github_token:
                return ToolResult(success=False, error="GitHub token not configured")
            
            async with GitHubClient(self.github_token) as client:
                params = {
                    "state": state,
                    "per_page": min(limit, 100)
                }
                
                if labels:
                    params["labels"] = labels
                
                issues = await client.get(f"/repos/{owner}/{repo}/issues", **params)
                
                # Filter out pull requests (GitHub API includes PRs in issues)
                issues = [issue for issue in issues if "pull_request" not in issue]
                
                result_issues = []
                for issue in issues:
                    result_issues.append({
                        "number": issue["number"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "html_url": issue["html_url"],
                        "user": issue["user"]["login"],
                        "labels": [label["name"] for label in issue["labels"]],
                        "created_at": issue["created_at"],
                        "updated_at": issue["updated_at"],
                        "comments": issue["comments"]
                    })
                
                return ToolResult(
                    success=True,
                    result={
                        "issues": result_issues,
                        "total_count": len(result_issues),
                        "repository": f"{owner}/{repo}",
                        "state_filter": state
                    }
                )
                
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list issues: {str(e)}")


class CreateIssueTool(BaseTool):
    """Tool for creating GitHub issues"""

    name = "create_github_issue"
    description = "Create a new issue on GitHub"
    category = ToolCategory.GIT_TOOLS

    parameters = {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner"
            },
            "repo": {
                "type": "string",
                "description": "Repository name"
            },
            "title": {
                "type": "string",
                "description": "Issue title"
            },
            "body": {
                "type": "string",
                "description": "Issue description"
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Labels to assign to the issue"
            },
            "assignees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Users to assign to the issue"
            }
        },
        "required": ["owner", "repo", "title"]
    }

    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)

    async def execute(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> ToolResult:
        try:
            if not self.github_token:
                return ToolResult(success=False, error="GitHub token not configured")

            async with GitHubClient(self.github_token) as client:
                issue_data = {
                    "title": title,
                    "body": body
                }

                if labels:
                    issue_data["labels"] = labels

                if assignees:
                    issue_data["assignees"] = assignees

                issue = await client.post(f"/repos/{owner}/{repo}/issues", issue_data)

                return ToolResult(
                    success=True,
                    result={
                        "number": issue["number"],
                        "title": issue["title"],
                        "html_url": issue["html_url"],
                        "state": issue["state"],
                        "user": issue["user"]["login"],
                        "labels": [label["name"] for label in issue["labels"]],
                        "assignees": [assignee["login"] for assignee in issue["assignees"]],
                        "created_at": issue["created_at"]
                    }
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create issue: {str(e)}")


class ListPullRequestsTool(BaseTool):
    """Tool for listing GitHub pull requests"""

    name = "list_pull_requests"
    description = "List pull requests from a GitHub repository"
    category = ToolCategory.GIT_TOOLS

    parameters = {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner"
            },
            "repo": {
                "type": "string",
                "description": "Repository name"
            },
            "state": {
                "type": "string",
                "description": "PR state",
                "enum": ["open", "closed", "all"],
                "default": "open"
            },
            "base": {
                "type": "string",
                "description": "Base branch to filter by"
            },
            "head": {
                "type": "string",
                "description": "Head branch to filter by"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of PRs to return",
                "default": 30
            }
        },
        "required": ["owner", "repo"]
    }

    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)

    async def execute(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        base: Optional[str] = None,
        head: Optional[str] = None,
        limit: int = 30
    ) -> ToolResult:
        try:
            if not self.github_token:
                return ToolResult(success=False, error="GitHub token not configured")

            async with GitHubClient(self.github_token) as client:
                params = {
                    "state": state,
                    "per_page": min(limit, 100)
                }

                if base:
                    params["base"] = base

                if head:
                    params["head"] = head

                prs = await client.get(f"/repos/{owner}/{repo}/pulls", **params)

                result_prs = []
                for pr in prs:
                    result_prs.append({
                        "number": pr["number"],
                        "title": pr["title"],
                        "state": pr["state"],
                        "html_url": pr["html_url"],
                        "user": pr["user"]["login"],
                        "head": pr["head"]["ref"],
                        "base": pr["base"]["ref"],
                        "draft": pr["draft"],
                        "mergeable": pr["mergeable"],
                        "created_at": pr["created_at"],
                        "updated_at": pr["updated_at"],
                        "comments": pr["comments"],
                        "commits": pr["commits"],
                        "additions": pr["additions"],
                        "deletions": pr["deletions"]
                    })

                return ToolResult(
                    success=True,
                    result={
                        "pull_requests": result_prs,
                        "total_count": len(result_prs),
                        "repository": f"{owner}/{repo}",
                        "state_filter": state
                    }
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list pull requests: {str(e)}")


class GitHubWorkflowTool(BaseTool):
    """Tool for GitHub workflow automation"""

    name = "github_workflow"
    description = "Execute common GitHub workflows"
    category = ToolCategory.GIT_TOOLS

    parameters = {
        "type": "object",
        "properties": {
            "workflow_type": {
                "type": "string",
                "description": "Type of workflow to execute",
                "enum": ["feature_branch", "hotfix", "release", "review_ready"]
            },
            "owner": {
                "type": "string",
                "description": "Repository owner"
            },
            "repo": {
                "type": "string",
                "description": "Repository name"
            },
            "branch_name": {
                "type": "string",
                "description": "Branch name for the workflow"
            },
            "title": {
                "type": "string",
                "description": "Title for PR/issue"
            },
            "description": {
                "type": "string",
                "description": "Description for PR/issue"
            }
        },
        "required": ["workflow_type", "owner", "repo"]
    }

    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)

    async def execute(
        self,
        workflow_type: str,
        owner: str,
        repo: str,
        branch_name: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> ToolResult:
        try:
            if not self.github_token:
                return ToolResult(success=False, error="GitHub token not configured")

            if workflow_type == "feature_branch":
                return await self._create_feature_branch_workflow(
                    owner, repo, branch_name, title, description
                )
            elif workflow_type == "review_ready":
                return await self._create_review_ready_workflow(
                    owner, repo, branch_name, title, description
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Workflow type '{workflow_type}' not implemented yet"
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Workflow execution failed: {str(e)}")

    async def _create_feature_branch_workflow(
        self, owner: str, repo: str, branch_name: str, title: str, description: str
    ) -> ToolResult:
        """Create a feature branch workflow"""
        async with GitHubClient(self.github_token) as client:
            # This would typically involve:
            # 1. Creating a new branch
            # 2. Setting up branch protection
            # 3. Creating a draft PR
            # For now, we'll create a draft PR

            pr_tool = CreatePullRequestTool(self.config)
            return await pr_tool.execute(
                owner=owner,
                repo=repo,
                title=title or f"Feature: {branch_name}",
                body=description or f"Feature branch for {branch_name}",
                head=branch_name,
                base="main",
                draft=True
            )

    async def _create_review_ready_workflow(
        self, owner: str, repo: str, branch_name: str, title: str, description: str
    ) -> ToolResult:
        """Mark a feature as ready for review"""
        async with GitHubClient(self.github_token) as client:
            # Convert draft PR to ready for review
            # This is a simplified implementation
            return ToolResult(
                success=True,
                result={
                    "workflow": "review_ready",
                    "message": f"Branch {branch_name} marked as ready for review",
                    "next_steps": [
                        "Request reviewers",
                        "Run CI/CD checks",
                        "Update PR description"
                    ]
                }
            )


# GitHub Tools registry
class GitHubSelfManagementTool(BaseTool):
    """Tool for managing the 200Model8CLI repository itself"""

    name = "manage_own_repository"
    description = "Manage the 200Model8CLI repository - check issues, create PRs, push code"
    category = ToolCategory.GIT_TOOLS

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": ["check_issues", "push_code", "create_pr", "check_status", "analyze_repo"]
            },
            "message": {
                "type": "string",
                "description": "Commit message or PR description"
            },
            "branch": {
                "type": "string",
                "description": "Branch name for operations",
                "default": "main"
            }
        },
        "required": ["action"]
    }

    def __init__(self, config: Config):
        super().__init__(config)
        self.github_token = getattr(config.api, 'github_token', None)
        self.repo_owner = "J3ff"  # Assuming this is the owner
        self.repo_name = "200Model8CLI"

    async def execute(
        self,
        action: str,
        message: Optional[str] = None,
        branch: str = "main"
    ) -> ToolResult:
        try:
            if action == "check_issues":
                return await self._check_own_issues()
            elif action == "push_code":
                return await self._push_own_code(message or "Update code via self-aware agent")
            elif action == "create_pr":
                return await self._create_own_pr(message or "Automated improvements")
            elif action == "check_status":
                return await self._check_repo_status()
            elif action == "analyze_repo":
                return await self._analyze_own_repo()
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            return ToolResult(success=False, error=f"Self-management failed: {str(e)}")

    async def _check_own_issues(self) -> ToolResult:
        """Check issues in the 200Model8CLI repository"""
        if not self.github_token:
            return ToolResult(success=False, error="GitHub token not configured")

        async with GitHubClient(self.github_token) as client:
            try:
                issues = await client.get(f"/repos/{self.repo_owner}/{self.repo_name}/issues", state="open")

                issue_list = []
                for issue in issues:
                    issue_list.append({
                        "number": issue["number"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "html_url": issue["html_url"],
                        "user": issue["user"]["login"],
                        "labels": [label["name"] for label in issue["labels"]],
                        "created_at": issue["created_at"],
                        "body": issue["body"][:200] + "..." if len(issue.get("body", "")) > 200 else issue.get("body", "")
                    })

                return ToolResult(
                    success=True,
                    result={
                        "repository": f"{self.repo_owner}/{self.repo_name}",
                        "total_issues": len(issue_list),
                        "issues": issue_list,
                        "analysis": self._analyze_issues(issue_list)
                    }
                )

            except Exception as e:
                return ToolResult(success=False, error=f"Failed to check issues: {str(e)}")

    async def _push_own_code(self, commit_message: str) -> ToolResult:
        """Push current code changes"""
        try:
            import subprocess
            import os

            # Get current working directory (should be project root)
            project_root = os.getcwd()

            # Check if there are changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                capture_output=True,
                text=True
            )

            if not result.stdout.strip():
                return ToolResult(
                    success=True,
                    result={
                        "message": "No changes to commit",
                        "status": "up_to_date"
                    }
                )

            # Add all changes
            subprocess.run(["git", "add", "."], cwd=project_root, check=True)

            # Commit changes
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=project_root,
                check=True
            )

            # Push changes
            push_result = subprocess.run(
                ["git", "push"],
                cwd=project_root,
                capture_output=True,
                text=True
            )

            if push_result.returncode == 0:
                return ToolResult(
                    success=True,
                    result={
                        "message": "Code pushed successfully",
                        "commit_message": commit_message,
                        "status": "pushed"
                    }
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Push failed: {push_result.stderr}"
                )

        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, error=f"Git operation failed: {str(e)}")
        except Exception as e:
            return ToolResult(success=False, error=f"Push operation failed: {str(e)}")

    async def _create_own_pr(self, description: str) -> ToolResult:
        """Create a pull request for improvements"""
        if not self.github_token:
            return ToolResult(success=False, error="GitHub token not configured")

        # This would create a PR from a feature branch to main
        # For now, return a placeholder
        return ToolResult(
            success=True,
            result={
                "message": "PR creation would be implemented here",
                "description": description,
                "status": "planned"
            }
        )

    async def _check_repo_status(self) -> ToolResult:
        """Check repository status"""
        try:
            import subprocess
            import os

            project_root = os.getcwd()

            # Get git status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                capture_output=True,
                text=True
            )

            # Get recent commits
            log_result = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                cwd=project_root,
                capture_output=True,
                text=True
            )

            # Get branch info
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project_root,
                capture_output=True,
                text=True
            )

            return ToolResult(
                success=True,
                result={
                    "current_branch": branch_result.stdout.strip(),
                    "uncommitted_changes": len(status_result.stdout.strip().split('\n')) if status_result.stdout.strip() else 0,
                    "recent_commits": log_result.stdout.strip().split('\n') if log_result.stdout.strip() else [],
                    "status": "clean" if not status_result.stdout.strip() else "has_changes"
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Status check failed: {str(e)}")

    async def _analyze_own_repo(self) -> ToolResult:
        """Analyze the repository for insights"""
        try:
            import os
            from pathlib import Path

            project_root = Path(os.getcwd())

            analysis = {
                "total_files": 0,
                "python_files": 0,
                "directories": 0,
                "estimated_loc": 0,
                "main_modules": [],
                "recent_activity": "active"
            }

            # Analyze project structure
            for root, dirs, files in os.walk(project_root / "src"):
                analysis["directories"] += len(dirs)
                for file in files:
                    analysis["total_files"] += 1
                    if file.endswith(".py"):
                        analysis["python_files"] += 1
                        file_path = Path(root) / file

                        # Count lines
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lines = len(f.readlines())
                                analysis["estimated_loc"] += lines

                                # Identify main modules
                                if lines > 100 and file in ["cli.py", "api.py", "config.py"]:
                                    analysis["main_modules"].append(str(file_path.relative_to(project_root)))
                        except:
                            pass

            return ToolResult(
                success=True,
                result={
                    "repository_analysis": analysis,
                    "health_score": self._calculate_health_score(analysis),
                    "recommendations": self._get_repo_recommendations(analysis)
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Repository analysis failed: {str(e)}")

    def _analyze_issues(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze issues for insights"""
        if not issues:
            return {"summary": "No open issues", "priority": "low"}

        # Categorize issues
        bugs = [i for i in issues if any("bug" in label.lower() for label in i["labels"])]
        features = [i for i in issues if any("feature" in label.lower() or "enhancement" in label.lower() for label in i["labels"])]

        return {
            "summary": f"{len(issues)} open issues",
            "bugs": len(bugs),
            "features": len(features),
            "priority": "high" if bugs else "medium" if features else "low",
            "oldest_issue": min(issues, key=lambda x: x["created_at"])["title"] if issues else None
        }

    def _calculate_health_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate repository health score"""
        score = 70  # Base score

        # Bonus for good structure
        if analysis["python_files"] > 10:
            score += 10
        if analysis["estimated_loc"] > 1000:
            score += 10
        if len(analysis["main_modules"]) >= 3:
            score += 10

        return min(score, 100)

    def _get_repo_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Get recommendations for repository improvement"""
        recommendations = []

        if analysis["estimated_loc"] > 5000:
            recommendations.append("Consider breaking down large modules")
        if analysis["python_files"] < 5:
            recommendations.append("Consider adding more modular structure")

        recommendations.extend([
            "Keep adding comprehensive documentation",
            "Consider adding automated testing",
            "Regular code quality checks would be beneficial"
        ])

        return recommendations


class GitHubTools:
    """Collection of GitHub integration tools"""

    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            CreateRepositoryTool(config),
            CreatePullRequestTool(config),
            ListIssuesTool(config),
            CreateIssueTool(config),
            ListPullRequestsTool(config),
            GitHubWorkflowTool(config),
            GitHubSelfManagementTool(config),  # New self-management tool
        ]

    def get_tools(self) -> List[BaseTool]:
        """Get all GitHub tools"""
        return self.tools
