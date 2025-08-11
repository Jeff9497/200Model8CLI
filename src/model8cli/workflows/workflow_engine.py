"""
Workflow Engine for 200Model8CLI

Provides multi-step task automation, custom workflow creation, and template system.
"""

import asyncio
import json
import yaml
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import structlog

from ..core.config import Config
from ..tools.base import ToolRegistry, ToolResult

logger = structlog.get_logger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Individual workflow step"""
    id: str
    name: str
    tool: str
    parameters: Dict[str, Any]
    condition: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[int] = None
    on_failure: str = "stop"  # stop, continue, retry
    status: StepStatus = StepStatus.PENDING
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class Workflow:
    """Workflow definition"""
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "user"
    tags: List[str] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class WorkflowEngine:
    """Workflow execution engine"""
    
    def __init__(self, config: Config, tool_registry: ToolRegistry):
        self.config = config
        self.tool_registry = tool_registry
        self.workflows_dir = config.config_dir / "workflows"
        self.workflows_dir.mkdir(exist_ok=True)
        
        # Built-in workflow templates
        self.templates = {
            "git_feature_workflow": self._create_git_feature_template(),
            "project_setup": self._create_project_setup_template(),
            "code_review": self._create_code_review_template(),
            "deployment": self._create_deployment_template(),
            "research_workflow": self._create_research_template()
        }
    
    def _create_git_feature_template(self) -> Dict[str, Any]:
        """Create Git feature workflow template"""
        return {
            "name": "Git Feature Workflow",
            "description": "Complete feature development workflow with Git",
            "steps": [
                {
                    "id": "check_status",
                    "name": "Check Git Status",
                    "tool": "git_status",
                    "parameters": {"path": "."}
                },
                {
                    "id": "create_branch",
                    "name": "Create Feature Branch",
                    "tool": "execute_command",
                    "parameters": {"command": "git checkout -b feature/{{feature_name}}"}
                },
                {
                    "id": "add_changes",
                    "name": "Add Changes",
                    "tool": "git_add",
                    "parameters": {"path": ".", "files": ["."]}
                },
                {
                    "id": "commit_changes",
                    "name": "Commit Changes",
                    "tool": "git_commit",
                    "parameters": {"message": "{{commit_message}}", "add_all": True}
                },
                {
                    "id": "push_branch",
                    "name": "Push Branch",
                    "tool": "git_push",
                    "parameters": {"branch": "feature/{{feature_name}}"}
                }
            ],
            "variables": {
                "feature_name": "new-feature",
                "commit_message": "Add new feature"
            }
        }
    
    def _create_project_setup_template(self) -> Dict[str, Any]:
        """Create project setup workflow template"""
        return {
            "name": "Project Setup Workflow",
            "description": "Initialize a new project with common structure",
            "steps": [
                {
                    "id": "create_directories",
                    "name": "Create Project Directories",
                    "tool": "create_directory",
                    "parameters": {"path": "{{project_name}}/src", "parents": True}
                },
                {
                    "id": "create_readme",
                    "name": "Create README",
                    "tool": "write_file",
                    "parameters": {
                        "path": "{{project_name}}/README.md",
                        "content": "# {{project_name}}\n\n{{project_description}}"
                    }
                },
                {
                    "id": "create_gitignore",
                    "name": "Create .gitignore",
                    "tool": "write_file",
                    "parameters": {
                        "path": "{{project_name}}/.gitignore",
                        "content": "*.pyc\n__pycache__/\n.env\nnode_modules/\n.DS_Store"
                    }
                },
                {
                    "id": "init_git",
                    "name": "Initialize Git",
                    "tool": "execute_command",
                    "parameters": {"command": "git init {{project_name}}"}
                }
            ],
            "variables": {
                "project_name": "my-project",
                "project_description": "A new project"
            }
        }
    
    def _create_code_review_template(self) -> Dict[str, Any]:
        """Create code review workflow template"""
        return {
            "name": "Code Review Workflow",
            "description": "Automated code review and analysis",
            "steps": [
                {
                    "id": "analyze_code",
                    "name": "Analyze Code",
                    "tool": "analyze_code",
                    "parameters": {"path": "{{code_path}}", "analysis_type": "detailed"}
                },
                {
                    "id": "format_code",
                    "name": "Format Code",
                    "tool": "format_code",
                    "parameters": {"path": "{{code_path}}"}
                },
                {
                    "id": "lint_code",
                    "name": "Lint Code",
                    "tool": "lint_code",
                    "parameters": {"path": "{{code_path}}"}
                },
                {
                    "id": "run_tests",
                    "name": "Run Tests",
                    "tool": "execute_command",
                    "parameters": {"command": "{{test_command}}"}
                }
            ],
            "variables": {
                "code_path": "./src",
                "test_command": "python -m pytest"
            }
        }
    
    def _create_deployment_template(self) -> Dict[str, Any]:
        """Create deployment workflow template"""
        return {
            "name": "Deployment Workflow",
            "description": "Deploy application with checks",
            "steps": [
                {
                    "id": "run_tests",
                    "name": "Run Tests",
                    "tool": "execute_command",
                    "parameters": {"command": "{{test_command}}"}
                },
                {
                    "id": "build_app",
                    "name": "Build Application",
                    "tool": "execute_command",
                    "parameters": {"command": "{{build_command}}"}
                },
                {
                    "id": "deploy_app",
                    "name": "Deploy Application",
                    "tool": "execute_command",
                    "parameters": {"command": "{{deploy_command}}"}
                },
                {
                    "id": "health_check",
                    "name": "Health Check",
                    "tool": "web_fetch",
                    "parameters": {"url": "{{health_check_url}}"}
                }
            ],
            "variables": {
                "test_command": "npm test",
                "build_command": "npm run build",
                "deploy_command": "npm run deploy",
                "health_check_url": "https://myapp.com/health"
            }
        }
    
    def _create_research_template(self) -> Dict[str, Any]:
        """Create research workflow template"""
        return {
            "name": "Research Workflow",
            "description": "Comprehensive research and documentation",
            "steps": [
                {
                    "id": "web_search",
                    "name": "Web Search",
                    "tool": "web_search",
                    "parameters": {"query": "{{research_topic}}"}
                },
                {
                    "id": "knowledge_search",
                    "name": "Search Knowledge Base",
                    "tool": "knowledge_search",
                    "parameters": {"query": "{{research_topic}}"}
                },
                {
                    "id": "create_summary",
                    "name": "Create Research Summary",
                    "tool": "write_file",
                    "parameters": {
                        "path": "research_{{timestamp}}.md",
                        "content": "# Research: {{research_topic}}\n\nDate: {{timestamp}}\n\n## Findings\n\n{{findings}}"
                    }
                },
                {
                    "id": "add_to_knowledge",
                    "name": "Add to Knowledge Base",
                    "tool": "add_knowledge",
                    "parameters": {
                        "title": "Research: {{research_topic}}",
                        "content": "{{findings}}",
                        "category": "research",
                        "tags": ["research", "{{research_topic}}"]
                    }
                }
            ],
            "variables": {
                "research_topic": "AI development",
                "timestamp": "{{now}}",
                "findings": "Research findings will be populated here"
            }
        }
    
    async def execute_workflow(self, workflow: Workflow, variables: Optional[Dict[str, Any]] = None) -> Workflow:
        """Execute a workflow"""
        logger.info("Starting workflow execution", workflow_id=workflow.id, name=workflow.name)
        
        # Update workflow status
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now().isoformat()
        
        # Merge variables
        if variables:
            workflow.variables.update(variables)
        
        try:
            for step in workflow.steps:
                if workflow.status == WorkflowStatus.CANCELLED:
                    break
                
                # Check condition if specified
                if step.condition and not self._evaluate_condition(step.condition, workflow.variables):
                    step.status = StepStatus.SKIPPED
                    continue
                
                # Execute step
                await self._execute_step(step, workflow.variables)
                
                # Handle step failure
                if step.status == StepStatus.FAILED:
                    if step.on_failure == "stop":
                        workflow.status = WorkflowStatus.FAILED
                        workflow.error = step.error
                        break
                    elif step.on_failure == "retry" and step.retry_count < step.max_retries:
                        step.retry_count += 1
                        step.status = StepStatus.PENDING
                        await self._execute_step(step, workflow.variables)
            
            # Update final status
            if workflow.status == WorkflowStatus.RUNNING:
                failed_steps = [s for s in workflow.steps if s.status == StepStatus.FAILED]
                if failed_steps:
                    workflow.status = WorkflowStatus.FAILED
                    workflow.error = f"Failed steps: {[s.name for s in failed_steps]}"
                else:
                    workflow.status = WorkflowStatus.COMPLETED
            
            workflow.completed_at = datetime.now().isoformat()
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            workflow.completed_at = datetime.now().isoformat()
            logger.error("Workflow execution failed", workflow_id=workflow.id, error=str(e))
        
        logger.info("Workflow execution completed", 
                   workflow_id=workflow.id, 
                   status=workflow.status.value)
        
        return workflow
    
    async def _execute_step(self, step: WorkflowStep, variables: Dict[str, Any]):
        """Execute a single workflow step"""
        logger.info("Executing step", step_id=step.id, step_name=step.name)
        
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now().isoformat()
        
        try:
            # Substitute variables in parameters
            parameters = self._substitute_variables(step.parameters, variables)
            
            # Get tool and execute
            if step.tool in self.tool_registry.tools:
                tool = self.tool_registry.tools[step.tool]
                result = await tool.execute(**parameters)
                step.result = result
                
                if result.success:
                    step.status = StepStatus.COMPLETED
                    # Update variables with result if needed
                    if result.result and isinstance(result.result, dict):
                        variables.update({f"{step.id}_result": result.result})
                else:
                    step.status = StepStatus.FAILED
                    step.error = result.error
            else:
                step.status = StepStatus.FAILED
                step.error = f"Tool '{step.tool}' not found"
            
            step.completed_at = datetime.now().isoformat()
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now().isoformat()
            logger.error("Step execution failed", step_id=step.id, error=str(e))
    
    def _substitute_variables(self, obj: Any, variables: Dict[str, Any]) -> Any:
        """Substitute variables in object"""
        if isinstance(obj, str):
            # Handle special variables
            if "{{now}}" in obj:
                obj = obj.replace("{{now}}", datetime.now().isoformat())
            if "{{timestamp}}" in obj:
                obj = obj.replace("{{timestamp}}", datetime.now().strftime("%Y%m%d_%H%M%S"))
            
            # Substitute user variables
            for key, value in variables.items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in obj:
                    obj = obj.replace(placeholder, str(value))
            return obj
        elif isinstance(obj, dict):
            return {k: self._substitute_variables(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_variables(item, variables) for item in obj]
        else:
            return obj
    
    def _evaluate_condition(self, condition: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a simple condition"""
        # Simple condition evaluation (can be extended)
        try:
            # Replace variables in condition
            for key, value in variables.items():
                condition = condition.replace(f"{{{{{key}}}}}", str(value))
            
            # Evaluate simple expressions
            return eval(condition)
        except Exception:
            return True  # Default to true if condition can't be evaluated
    
    def save_workflow(self, workflow: Workflow) -> bool:
        """Save workflow to file"""
        try:
            workflow_file = self.workflows_dir / f"{workflow.id}.yaml"
            
            # Convert workflow to dict
            workflow_dict = {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "version": workflow.version,
                "author": workflow.author,
                "tags": workflow.tags,
                "variables": workflow.variables,
                "steps": [
                    {
                        "id": step.id,
                        "name": step.name,
                        "tool": step.tool,
                        "parameters": step.parameters,
                        "condition": step.condition,
                        "max_retries": step.max_retries,
                        "timeout": step.timeout,
                        "on_failure": step.on_failure
                    }
                    for step in workflow.steps
                ]
            }
            
            with open(workflow_file, 'w', encoding='utf-8') as f:
                yaml.dump(workflow_dict, f, default_flow_style=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error("Failed to save workflow", workflow_id=workflow.id, error=str(e))
            return False
    
    def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Load workflow from file"""
        try:
            workflow_file = self.workflows_dir / f"{workflow_id}.yaml"
            
            if not workflow_file.exists():
                return None
            
            with open(workflow_file, 'r', encoding='utf-8') as f:
                workflow_dict = yaml.safe_load(f)
            
            # Convert dict to workflow
            steps = []
            for step_dict in workflow_dict.get("steps", []):
                step = WorkflowStep(
                    id=step_dict["id"],
                    name=step_dict["name"],
                    tool=step_dict["tool"],
                    parameters=step_dict["parameters"],
                    condition=step_dict.get("condition"),
                    max_retries=step_dict.get("max_retries", 3),
                    timeout=step_dict.get("timeout"),
                    on_failure=step_dict.get("on_failure", "stop")
                )
                steps.append(step)
            
            workflow = Workflow(
                id=workflow_dict["id"],
                name=workflow_dict["name"],
                description=workflow_dict["description"],
                version=workflow_dict.get("version", "1.0.0"),
                author=workflow_dict.get("author", "user"),
                tags=workflow_dict.get("tags", []),
                variables=workflow_dict.get("variables", {}),
                steps=steps
            )
            
            return workflow
            
        except Exception as e:
            logger.error("Failed to load workflow", workflow_id=workflow_id, error=str(e))
            return None
    
    def list_workflows(self) -> List[str]:
        """List available workflows"""
        workflows = []
        
        # Add saved workflows
        for workflow_file in self.workflows_dir.glob("*.yaml"):
            workflows.append(workflow_file.stem)
        
        # Add templates
        workflows.extend(self.templates.keys())
        
        return sorted(workflows)
    
    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get workflow template"""
        return self.templates.get(template_name)
    
    def create_workflow_from_template(self, template_name: str, workflow_id: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Workflow]:
        """Create workflow from template"""
        template = self.get_template(template_name)
        if not template:
            return None
        
        # Create workflow steps
        steps = []
        for step_dict in template["steps"]:
            step = WorkflowStep(
                id=step_dict["id"],
                name=step_dict["name"],
                tool=step_dict["tool"],
                parameters=step_dict["parameters"],
                condition=step_dict.get("condition"),
                max_retries=step_dict.get("max_retries", 3),
                timeout=step_dict.get("timeout"),
                on_failure=step_dict.get("on_failure", "stop")
            )
            steps.append(step)
        
        # Merge variables
        workflow_variables = template.get("variables", {})
        if variables:
            workflow_variables.update(variables)
        
        workflow = Workflow(
            id=workflow_id,
            name=template["name"],
            description=template["description"],
            variables=workflow_variables,
            steps=steps
        )
        
        return workflow
