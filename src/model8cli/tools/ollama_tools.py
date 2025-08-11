"""
Ollama-specific tools for 200Model8CLI

Provides enhanced local model management and tool calling optimization.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

import structlog

from .base import BaseTool, ToolResult, ToolCategory
from ..core.config import Config
from ..core.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)


class OllamaModelRecommendationTool(BaseTool):
    """Tool for recommending best Ollama models for tool calling"""
    
    name = "recommend_ollama_models"
    description = "Get recommendations for best Ollama models for tool calling"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "use_case": {
                "type": "string",
                "description": "Use case for model selection",
                "enum": ["tool_calling", "coding", "general", "reasoning"],
                "default": "tool_calling"
            },
            "size_preference": {
                "type": "string",
                "description": "Model size preference",
                "enum": ["small", "medium", "large", "any"],
                "default": "medium"
            }
        },
        "required": []
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
        
        # Model recommendations based on tool calling performance
        self.model_recommendations = {
            "excellent": [
                {
                    "name": "llama3.1:8b",
                    "size": "4.7GB",
                    "description": "Excellent tool calling, fast inference",
                    "tool_calling_score": 9,
                    "reasoning_score": 8,
                    "speed_score": 9
                },
                {
                    "name": "llama3.1:70b",
                    "size": "40GB",
                    "description": "Best tool calling accuracy, slower inference",
                    "tool_calling_score": 10,
                    "reasoning_score": 10,
                    "speed_score": 6
                },
                {
                    "name": "qwen2.5:7b",
                    "size": "4.4GB",
                    "description": "Great tool calling, good for coding",
                    "tool_calling_score": 9,
                    "reasoning_score": 8,
                    "speed_score": 8
                }
            ],
            "good": [
                {
                    "name": "mistral:7b",
                    "size": "4.1GB",
                    "description": "Good tool calling, general purpose",
                    "tool_calling_score": 7,
                    "reasoning_score": 7,
                    "speed_score": 8
                },
                {
                    "name": "codellama:7b",
                    "size": "3.8GB",
                    "description": "Good for coding tasks with tools",
                    "tool_calling_score": 7,
                    "reasoning_score": 8,
                    "speed_score": 8
                },
                {
                    "name": "phi3:3.8b",
                    "size": "2.3GB",
                    "description": "Small but capable, good for basic tool calling",
                    "tool_calling_score": 6,
                    "reasoning_score": 6,
                    "speed_score": 9
                }
            ],
            "basic": [
                {
                    "name": "llama3.2:3b",
                    "size": "2.0GB",
                    "description": "Basic tool calling, very fast",
                    "tool_calling_score": 5,
                    "reasoning_score": 5,
                    "speed_score": 10
                },
                {
                    "name": "gemma2:2b",
                    "size": "1.6GB",
                    "description": "Lightweight, basic tool support",
                    "tool_calling_score": 4,
                    "reasoning_score": 4,
                    "speed_score": 10
                }
            ]
        }
    
    async def execute(
        self,
        use_case: str = "tool_calling",
        size_preference: str = "medium"
    ) -> ToolResult:
        try:
            # Filter recommendations based on preferences
            recommendations = []
            
            for category, models in self.model_recommendations.items():
                for model in models:
                    # Filter by size preference
                    if size_preference != "any":
                        size_gb = float(model["size"].replace("GB", ""))
                        if size_preference == "small" and size_gb > 5:
                            continue
                        elif size_preference == "medium" and (size_gb < 3 or size_gb > 15):
                            continue
                        elif size_preference == "large" and size_gb < 10:
                            continue
                    
                    # Score based on use case
                    if use_case == "tool_calling":
                        score = model["tool_calling_score"]
                    elif use_case == "coding":
                        score = (model["tool_calling_score"] + model["reasoning_score"]) / 2
                    elif use_case == "reasoning":
                        score = model["reasoning_score"]
                    else:  # general
                        score = (model["tool_calling_score"] + model["reasoning_score"] + model["speed_score"]) / 3
                    
                    model_info = model.copy()
                    model_info["category"] = category
                    model_info["use_case_score"] = round(score, 1)
                    recommendations.append(model_info)
            
            # Sort by use case score
            recommendations.sort(key=lambda x: x["use_case_score"], reverse=True)
            
            return ToolResult(
                success=True,
                result={
                    "use_case": use_case,
                    "size_preference": size_preference,
                    "recommendations": recommendations[:5],  # Top 5
                    "installation_command": "ollama pull <model_name>",
                    "usage_tip": "Use 'ollama/<model_name>' as the model name in 200model8cli"
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Model recommendation failed: {str(e)}")


class OllamaToolCallingTestTool(BaseTool):
    """Tool for testing tool calling capabilities of Ollama models"""
    
    name = "test_ollama_tool_calling"
    description = "Test tool calling capabilities of an Ollama model"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Ollama model name to test"
            },
            "test_type": {
                "type": "string",
                "description": "Type of test to run",
                "enum": ["basic", "complex", "multiple_tools"],
                "default": "basic"
            }
        },
        "required": ["model"]
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
    
    async def execute(
        self,
        model: str,
        test_type: str = "basic"
    ) -> ToolResult:
        try:
            from ..core.ollama_client import OllamaClient, ChatMessage
            
            # Initialize Ollama client
            ollama_client = OllamaClient()
            
            # Check if Ollama is available
            if not await ollama_client.is_available():
                return ToolResult(success=False, error="Ollama is not running")
            
            # Define test tools
            test_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather information for a location",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "The city and state, e.g. San Francisco, CA"
                                },
                                "unit": {
                                    "type": "string",
                                    "enum": ["celsius", "fahrenheit"],
                                    "description": "Temperature unit"
                                }
                            },
                            "required": ["location"]
                        }
                    }
                }
            ]
            
            if test_type in ["complex", "multiple_tools"]:
                test_tools.append({
                    "type": "function",
                    "function": {
                        "name": "calculate",
                        "description": "Perform mathematical calculations",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression to evaluate"
                                }
                            },
                            "required": ["expression"]
                        }
                    }
                })
            
            # Create test message
            if test_type == "basic":
                test_message = "What's the weather like in New York?"
            elif test_type == "complex":
                test_message = "What's the weather in London and calculate 15 * 23?"
            else:  # multiple_tools
                test_message = "Get weather for Tokyo, calculate 100 / 4, and tell me which tool you'd use for each task"
            
            messages = [ChatMessage(role="user", content=test_message)]
            
            # Test tool calling
            response = await ollama_client.chat_completion(
                model=model,
                messages=messages,
                tools=test_tools,
                temperature=0.1
            )
            
            await ollama_client.close()
            
            # Analyze response
            message = response.message
            has_tool_calls = "tool_calls" in message and message["tool_calls"]
            
            result = {
                "model": model,
                "test_type": test_type,
                "success": has_tool_calls,
                "response_content": message.get("content", ""),
                "tool_calls_detected": len(message.get("tool_calls", [])),
                "raw_response": message
            }
            
            if has_tool_calls:
                result["tool_calls"] = message["tool_calls"]
                result["analysis"] = "✅ Model successfully generated tool calls"
            else:
                result["analysis"] = "❌ Model did not generate proper tool calls"
            
            return ToolResult(success=True, result=result)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Tool calling test failed: {str(e)}")


class OllamaOptimizationTool(BaseTool):
    """Tool for optimizing Ollama performance for tool calling"""
    
    name = "optimize_ollama_tool_calling"
    description = "Get optimization tips for better Ollama tool calling performance"
    category = ToolCategory.CUSTOM
    
    parameters = {
        "type": "object",
        "properties": {
            "system_info": {
                "type": "object",
                "description": "System information (RAM, GPU, etc.)",
                "properties": {
                    "ram_gb": {"type": "number"},
                    "has_gpu": {"type": "boolean"},
                    "gpu_memory_gb": {"type": "number"}
                }
            }
        },
        "required": []
    }
    
    def __init__(self, config: Config):
        super().__init__(config)
    
    async def execute(self, system_info: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            tips = {
                "general": [
                    "Use models with 'instruct' or 'chat' variants for better tool calling",
                    "Set temperature to 0.1-0.3 for more consistent tool calling",
                    "Use specific, clear tool descriptions",
                    "Test tool calling with simple examples first"
                ],
                "performance": [
                    "Keep Ollama running in the background to avoid startup delays",
                    "Use SSD storage for faster model loading",
                    "Close other applications to free up RAM",
                    "Consider using smaller models for faster inference"
                ],
                "troubleshooting": [
                    "If tool calling fails, try rephrasing the request",
                    "Check that the model supports instruction following",
                    "Verify tool parameter schemas are correct",
                    "Use 'ollama logs' to debug issues"
                ]
            }
            
            # Add system-specific recommendations
            if system_info:
                ram_gb = system_info.get("ram_gb", 8)
                has_gpu = system_info.get("has_gpu", False)
                
                if ram_gb < 8:
                    tips["system_specific"] = [
                        "Consider using smaller models (3B or 7B parameters)",
                        "Close other applications to free up RAM",
                        "Use quantized models for lower memory usage"
                    ]
                elif ram_gb >= 16:
                    tips["system_specific"] = [
                        "You can run larger models (13B-70B parameters)",
                        "Consider running multiple models simultaneously",
                        "Use higher context lengths for complex tasks"
                    ]
                
                if has_gpu:
                    tips["gpu_optimization"] = [
                        "Ensure Ollama is using GPU acceleration",
                        "Use 'ollama ps' to check GPU usage",
                        "Consider using larger models with GPU acceleration"
                    ]
            
            return ToolResult(
                success=True,
                result={
                    "optimization_tips": tips,
                    "recommended_settings": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1
                    },
                    "best_practices": [
                        "Always test tool calling with new models",
                        "Use consistent prompt formats",
                        "Monitor model performance and adjust as needed",
                        "Keep Ollama updated to the latest version"
                    ]
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Optimization tips failed: {str(e)}")


# Ollama Tools registry
class OllamaTools:
    """Collection of Ollama-specific tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            OllamaModelRecommendationTool(config),
            OllamaToolCallingTestTool(config),
            OllamaOptimizationTool(config),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all Ollama tools"""
        return self.tools
