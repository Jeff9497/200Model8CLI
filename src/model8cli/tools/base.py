"""
Base tool system for 200Model8CLI

Provides the foundation for tool calling, registration, and execution.
"""

import asyncio
import inspect
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union, Type
from dataclasses import dataclass, field
from enum import Enum
import time

import structlog

from ..core.config import Config
from ..utils.security import SecurityValidator

logger = structlog.get_logger(__name__)


class ToolCategory(Enum):
    """Tool categories"""
    FILE_OPERATIONS = "file_operations"
    WEB_TOOLS = "web_tools"
    GIT_TOOLS = "git_tools"
    CODE_TOOLS = "code_tools"
    SYSTEM_TOOLS = "system_tools"
    CUSTOM = "custom"


@dataclass
class ToolParameter:
    """Tool parameter definition"""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    pattern: Optional[str] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


@dataclass
class ToolDefinition:
    """Tool definition for OpenRouter API"""
    name: str
    description: str
    parameters: Dict[str, Any]
    category: ToolCategory = ToolCategory.CUSTOM
    enabled: bool = True
    requires_confirmation: bool = False
    dangerous: bool = False


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    Base class for all tools
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.security = SecurityValidator(config)
        self.enabled = True
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.error_count = 0
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description"""
        pass
    
    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """Tool category"""
        pass
    
    @property
    def requires_confirmation(self) -> bool:
        """Whether tool requires user confirmation"""
        return False
    
    @property
    def dangerous(self) -> bool:
        """Whether tool is potentially dangerous"""
        return False
    
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameters"""
        # Default implementation - can be overridden
        return []
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool"""
        pass
    
    def get_tool_definition(self) -> ToolDefinition:
        """Get OpenRouter tool definition"""
        # Handle both old get_parameters() method and new parameters attribute
        if hasattr(self, 'parameters') and isinstance(self.parameters, dict):
            # New style - parameters is a dict
            return ToolDefinition(
                name=self.name,
                description=self.description,
                parameters=self.parameters,
                category=self.category,
                enabled=self.enabled,
                requires_confirmation=self.requires_confirmation,
                dangerous=self.dangerous,
            )
        else:
            # Old style - get_parameters() method
            parameters = self.get_parameters()

            # Convert parameters to OpenRouter format
            properties = {}
            required = []

            for param in parameters:
                prop_def = {
                    "type": param.type,
                    "description": param.description,
                }

                if param.enum:
                    prop_def["enum"] = param.enum
                if param.pattern:
                    prop_def["pattern"] = param.pattern
                if param.min_value is not None:
                    prop_def["minimum"] = param.min_value
                if param.max_value is not None:
                    prop_def["maximum"] = param.max_value
                if param.min_length is not None:
                    prop_def["minLength"] = param.min_length
                if param.max_length is not None:
                    prop_def["maxLength"] = param.max_length
                if param.default is not None:
                    prop_def["default"] = param.default

                properties[param.name] = prop_def

                if param.required:
                    required.append(param.name)

            return ToolDefinition(
                name=self.name,
                description=self.description,
                parameters={
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
                category=self.category,
                enabled=self.enabled,
                requires_confirmation=self.requires_confirmation,
                dangerous=self.dangerous,
            )
    
    def validate_parameters(self, **kwargs) -> bool:
        """Validate tool parameters"""
        parameters = self.get_parameters()
        param_dict = {p.name: p for p in parameters}
        
        # Check required parameters
        for param in parameters:
            if param.required and param.name not in kwargs:
                logger.error("Missing required parameter", tool=self.name, parameter=param.name)
                return False
        
        # Validate parameter types and constraints
        for name, value in kwargs.items():
            if name not in param_dict:
                logger.warning("Unknown parameter", tool=self.name, parameter=name)
                continue
            
            param = param_dict[name]
            
            # Type validation
            if not self._validate_type(value, param.type):
                logger.error("Invalid parameter type", tool=self.name, parameter=name, expected=param.type)
                return False
            
            # Constraint validation
            if not self._validate_constraints(value, param):
                logger.error("Parameter constraint violation", tool=self.name, parameter=name)
                return False
        
        return True
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate parameter type"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, skip validation
        
        return isinstance(value, expected)
    
    def _validate_constraints(self, value: Any, param: ToolParameter) -> bool:
        """Validate parameter constraints"""
        # Enum validation
        if param.enum and value not in param.enum:
            return False
        
        # Pattern validation for strings
        if param.pattern and isinstance(value, str):
            import re
            if not re.match(param.pattern, value):
                return False
        
        # Numeric constraints
        if param.min_value is not None and isinstance(value, (int, float)):
            if value < param.min_value:
                return False
        
        if param.max_value is not None and isinstance(value, (int, float)):
            if value > param.max_value:
                return False
        
        # String length constraints
        if param.min_length is not None and isinstance(value, str):
            if len(value) < param.min_length:
                return False
        
        if param.max_length is not None and isinstance(value, str):
            if len(value) > param.max_length:
                return False
        
        return True
    
    async def safe_execute(self, **kwargs) -> ToolResult:
        """Safely execute tool with validation and error handling"""
        start_time = time.time()
        
        try:
            # Validate parameters
            if not self.validate_parameters(**kwargs):
                return ToolResult(
                    success=False,
                    error="Parameter validation failed",
                    execution_time=time.time() - start_time,
                )
            
            # Execute tool
            result = await self.execute(**kwargs)
            
            # Update metrics
            execution_time = time.time() - start_time
            self.execution_count += 1
            self.total_execution_time += execution_time
            
            if not result.success:
                self.error_count += 1
            
            result.execution_time = execution_time
            
            logger.debug(
                "Tool executed",
                tool=self.name,
                success=result.success,
                execution_time=execution_time,
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.execution_count += 1
            self.total_execution_time += execution_time
            self.error_count += 1
            
            logger.error("Tool execution failed", tool=self.name, error=str(e))
            
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                execution_time=execution_time,
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tool execution statistics"""
        avg_execution_time = (
            self.total_execution_time / self.execution_count
            if self.execution_count > 0
            else 0.0
        )
        
        success_rate = (
            (self.execution_count - self.error_count) / self.execution_count
            if self.execution_count > 0
            else 1.0
        )
        
        return {
            "name": self.name,
            "category": self.category.value,
            "enabled": self.enabled,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "avg_execution_time": avg_execution_time,
            "total_execution_time": self.total_execution_time,
        }


class ToolRegistry:
    """
    Registry for managing tools
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.tools: Dict[str, BaseTool] = {}
        self.categories: Dict[ToolCategory, List[str]] = {}
        
        logger.info("Tool registry initialized")
    
    def register_tool(self, tool: BaseTool):
        """Register a tool"""
        if tool.name in self.tools:
            logger.warning("Tool already registered, replacing", tool=tool.name)
        
        self.tools[tool.name] = tool
        
        # Update category index
        if tool.category not in self.categories:
            self.categories[tool.category] = []
        
        if tool.name not in self.categories[tool.category]:
            self.categories[tool.category].append(tool.name)
        
        logger.info("Tool registered", tool=tool.name, category=tool.category.value)
    
    def unregister_tool(self, tool_name: str):
        """Unregister a tool"""
        if tool_name not in self.tools:
            logger.warning("Tool not found for unregistration", tool=tool_name)
            return
        
        tool = self.tools[tool_name]
        del self.tools[tool_name]
        
        # Update category index
        if tool.category in self.categories:
            if tool_name in self.categories[tool.category]:
                self.categories[tool.category].remove(tool_name)
        
        logger.info("Tool unregistered", tool=tool_name)
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """Get tools by category"""
        tool_names = self.categories.get(category, [])
        return [self.tools[name] for name in tool_names if name in self.tools]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools"""
        return list(self.tools.values())
    
    def get_enabled_tools(self) -> List[BaseTool]:
        """Get all enabled tools"""
        return [tool for tool in self.tools.values() if tool.enabled]
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get OpenRouter tool definitions for all enabled tools"""
        definitions = []
        
        for tool in self.get_enabled_tools():
            tool_def = tool.get_tool_definition()
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": tool_def.parameters,
                }
            })
        
        return definitions
    
    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
            )
        
        if not tool.enabled:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' is disabled",
            )
        
        return await tool.safe_execute(**kwargs)
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        total_tools = len(self.tools)
        enabled_tools = len(self.get_enabled_tools())
        
        category_counts = {}
        for category, tool_names in self.categories.items():
            category_counts[category.value] = len(tool_names)
        
        tool_stats = [tool.get_stats() for tool in self.tools.values()]
        
        return {
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "categories": category_counts,
            "tools": tool_stats,
        }
