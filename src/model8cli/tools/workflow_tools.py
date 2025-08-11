"""
Workflow tools for 200Model8CLI

Provides workflow execution, template management, and automation capabilities.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

import structlog

from .base import BaseTool, ToolResult, ToolCategory
from ..core.config import Config
from ..workflows.workflow_engine import WorkflowEngine, Workflow, WorkflowStep

logger = structlog.get_logger(__name__)


class ExecuteWorkflowTool(BaseTool):
    """Tool for executing workflows"""
    
    name = "execute_workflow"
    description = "Execute a workflow by ID or template name"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "workflow_id": {
                "type": "string",
                "description": "Workflow ID or template name to execute"
            },
            "variables": {
                "type": "object",
                "description": "Variables to pass to the workflow"
            },
            "is_template": {
                "type": "boolean",
                "description": "Whether the workflow_id is a template name",
                "default": False
            }
        },
        "required": ["workflow_id"]
    }
    
    def __init__(self, config: Config, tool_registry):
        super().__init__(config)
        self.workflow_engine = WorkflowEngine(config, tool_registry)
    
    async def execute(
        self,
        workflow_id: str,
        variables: Optional[Dict[str, Any]] = None,
        is_template: bool = False
    ) -> ToolResult:
        try:
            if is_template:
                # Create workflow from template
                workflow = self.workflow_engine.create_workflow_from_template(
                    workflow_id, f"{workflow_id}_{int(asyncio.get_event_loop().time())}", variables
                )
                if not workflow:
                    return ToolResult(success=False, error=f"Template '{workflow_id}' not found")
            else:
                # Load existing workflow
                workflow = self.workflow_engine.load_workflow(workflow_id)
                if not workflow:
                    return ToolResult(success=False, error=f"Workflow '{workflow_id}' not found")
            
            # Execute workflow
            executed_workflow = await self.workflow_engine.execute_workflow(workflow, variables)
            
            # Prepare result
            result = {
                "workflow_id": executed_workflow.id,
                "name": executed_workflow.name,
                "status": executed_workflow.status.value,
                "started_at": executed_workflow.started_at,
                "completed_at": executed_workflow.completed_at,
                "steps": []
            }
            
            for step in executed_workflow.steps:
                step_result = {
                    "id": step.id,
                    "name": step.name,
                    "status": step.status.value,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at
                }
                
                if step.error:
                    step_result["error"] = step.error
                
                if step.result and step.result.success:
                    step_result["result"] = step.result.result
                
                result["steps"].append(step_result)
            
            if executed_workflow.error:
                result["error"] = executed_workflow.error
            
            return ToolResult(
                success=executed_workflow.status.value in ["completed"],
                result=result
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Workflow execution failed: {str(e)}")


class ListWorkflowsTool(BaseTool):
    """Tool for listing available workflows and templates"""
    
    name = "list_workflows"
    description = "List available workflows and templates"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "include_templates": {
                "type": "boolean",
                "description": "Include workflow templates",
                "default": True
            }
        },
        "required": []
    }
    
    def __init__(self, config: Config, tool_registry):
        super().__init__(config)
        self.workflow_engine = WorkflowEngine(config, tool_registry)
    
    async def execute(self, include_templates: bool = True) -> ToolResult:
        try:
            workflows = self.workflow_engine.list_workflows()
            templates = list(self.workflow_engine.templates.keys()) if include_templates else []
            
            result = {
                "workflows": workflows,
                "templates": templates,
                "total_count": len(workflows) + len(templates)
            }
            
            return ToolResult(success=True, result=result)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list workflows: {str(e)}")


class CreateWorkflowTool(BaseTool):
    """Tool for creating custom workflows"""
    
    name = "create_workflow"
    description = "Create a custom workflow"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "workflow_id": {
                "type": "string",
                "description": "Unique workflow ID"
            },
            "name": {
                "type": "string",
                "description": "Workflow name"
            },
            "description": {
                "type": "string",
                "description": "Workflow description"
            },
            "steps": {
                "type": "array",
                "description": "Workflow steps",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "tool": {"type": "string"},
                        "parameters": {"type": "object"},
                        "condition": {"type": "string"},
                        "on_failure": {"type": "string", "enum": ["stop", "continue", "retry"]}
                    },
                    "required": ["id", "name", "tool", "parameters"]
                }
            },
            "variables": {
                "type": "object",
                "description": "Default workflow variables"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Workflow tags"
            }
        },
        "required": ["workflow_id", "name", "description", "steps"]
    }
    
    def __init__(self, config: Config, tool_registry):
        super().__init__(config)
        self.workflow_engine = WorkflowEngine(config, tool_registry)
    
    async def execute(
        self,
        workflow_id: str,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        variables: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> ToolResult:
        try:
            # Create workflow steps
            workflow_steps = []
            for step_dict in steps:
                step = WorkflowStep(
                    id=step_dict["id"],
                    name=step_dict["name"],
                    tool=step_dict["tool"],
                    parameters=step_dict["parameters"],
                    condition=step_dict.get("condition"),
                    on_failure=step_dict.get("on_failure", "stop")
                )
                workflow_steps.append(step)
            
            # Create workflow
            workflow = Workflow(
                id=workflow_id,
                name=name,
                description=description,
                steps=workflow_steps,
                variables=variables or {},
                tags=tags or []
            )
            
            # Save workflow
            success = self.workflow_engine.save_workflow(workflow)
            
            if success:
                return ToolResult(
                    success=True,
                    result={
                        "workflow_id": workflow_id,
                        "name": name,
                        "description": description,
                        "steps_count": len(workflow_steps),
                        "message": "Workflow created successfully"
                    }
                )
            else:
                return ToolResult(success=False, error="Failed to save workflow")
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create workflow: {str(e)}")


class GetWorkflowTemplateTool(BaseTool):
    """Tool for getting workflow template details"""
    
    name = "get_workflow_template"
    description = "Get details of a workflow template"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "template_name": {
                "type": "string",
                "description": "Template name"
            }
        },
        "required": ["template_name"]
    }
    
    def __init__(self, config: Config, tool_registry):
        super().__init__(config)
        self.workflow_engine = WorkflowEngine(config, tool_registry)
    
    async def execute(self, template_name: str) -> ToolResult:
        try:
            template = self.workflow_engine.get_template(template_name)
            
            if template:
                return ToolResult(success=True, result=template)
            else:
                return ToolResult(success=False, error=f"Template '{template_name}' not found")
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get template: {str(e)}")


# Workflow Tools registry
class WorkflowTools:
    """Collection of workflow automation tools"""
    
    def __init__(self, config: Config, tool_registry):
        self.config = config
        self.tool_registry = tool_registry
        self.tools = [
            ExecuteWorkflowTool(config, tool_registry),
            ListWorkflowsTool(config, tool_registry),
            CreateWorkflowTool(config, tool_registry),
            GetWorkflowTemplateTool(config, tool_registry),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all workflow tools"""
        return self.tools
