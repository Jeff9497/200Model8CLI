"""
Ollama API client for local model support
"""
import asyncio
import json
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
import httpx
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ChatMessage:
    """Chat message for Ollama"""
    role: str
    content: str


@dataclass
class ChatResponse:
    """Response from Ollama chat completion"""
    message: Dict[str, Any]
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


@dataclass
class OllamaModel:
    """Ollama model information"""
    name: str
    size: int
    digest: str
    modified_at: str


class OllamaClient:
    """Client for Ollama API"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=None)  # No timeout for local models
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def list_models(self) -> List[OllamaModel]:
        """List available Ollama models"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                models.append(OllamaModel(
                    name=model_data["name"],
                    size=model_data["size"],
                    digest=model_data["digest"],
                    modified_at=model_data["modified_at"]
                ))
            
            return models
            
        except Exception as e:
            logger.error("Failed to list Ollama models", error=str(e))
            return []
    
    async def is_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except:
            return False
    
    async def chat_completion(
        self,
        model: str,
        messages: List[ChatMessage],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> ChatResponse:
        """Create chat completion with Ollama"""
        try:
            # Handle tool calling for Ollama models
            if tools:
                return await self._handle_tool_calling_completion(
                    model, messages, tools, tool_choice, temperature, max_tokens, stream
                )

            # Convert messages to Ollama format
            ollama_messages = []
            for msg in messages:
                ollama_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

            request_data = {
                "model": model,
                "messages": ollama_messages,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                }
            }

            if max_tokens:
                request_data["options"]["num_predict"] = max_tokens

            logger.debug(f"Making Ollama request to {self.base_url}/api/chat", model=model, messages_count=len(ollama_messages))

            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=request_data
            )

            logger.debug(f"Ollama response status: {response.status_code}")
            response.raise_for_status()

            if stream:
                return self._handle_streaming_response(response)
            else:
                data = response.json()
                logger.debug(f"Ollama response data keys: {list(data.keys())}")

                # Validate response structure
                if "message" not in data:
                    raise ValueError(f"Invalid Ollama response: missing 'message' field. Got: {data}")

                return ChatResponse(
                    message=data["message"],
                    done=data.get("done", True),
                    total_duration=data.get("total_duration"),
                    load_duration=data.get("load_duration"),
                    prompt_eval_count=data.get("prompt_eval_count"),
                    prompt_eval_duration=data.get("prompt_eval_duration"),
                    eval_count=data.get("eval_count"),
                    eval_duration=data.get("eval_duration")
                )
                
        except Exception as e:
            error_msg = str(e) if str(e) else f"Unknown error ({type(e).__name__})"
            logger.error("Ollama chat completion failed", error=error_msg, model=model, exception_type=type(e).__name__)
            # Also log the full traceback for debugging
            import traceback
            logger.debug("Ollama chat completion traceback", traceback=traceback.format_exc())
            raise Exception(f"Ollama chat completion failed: {error_msg}")

    async def _handle_tool_calling_completion(
        self,
        model: str,
        messages: List[ChatMessage],
        tools: List[Dict[str, Any]],
        tool_choice: Optional[Union[str, Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int],
        stream: bool
    ) -> ChatResponse:
        """Handle tool calling for Ollama models using prompt engineering"""
        try:
            # Create tool calling prompt
            tool_prompt = self._create_tool_calling_prompt(messages, tools, tool_choice)

            # Convert to Ollama messages
            ollama_messages = [{"role": "user", "content": tool_prompt}]

            request_data = {
                "model": model,
                "messages": ollama_messages,
                "stream": False,  # Tool calling requires non-streaming
                "options": {
                    "temperature": temperature,
                }
            }

            if max_tokens:
                request_data["options"]["num_predict"] = max_tokens

            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=request_data
            )
            response.raise_for_status()

            data = response.json()
            response_content = data["message"].get("content", "")

            # Parse tool calls from response
            tool_calls = self._parse_tool_calls(response_content, tools)

            # Create response with tool calls
            message = {
                "role": "assistant",
                "content": response_content if not tool_calls else None,
            }

            if tool_calls:
                message["tool_calls"] = tool_calls

            return ChatResponse(
                message=message,
                done=data.get("done", True),
                total_duration=data.get("total_duration"),
                load_duration=data.get("load_duration"),
                prompt_eval_count=data.get("prompt_eval_count"),
                prompt_eval_duration=data.get("prompt_eval_duration"),
                eval_count=data.get("eval_count"),
                eval_duration=data.get("eval_duration")
            )

        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error in tool calling"
            logger.error("Ollama tool calling failed", error=error_msg)
            raise Exception(f"Ollama tool calling failed: {error_msg}")

    def _create_tool_calling_prompt(
        self,
        messages: List[ChatMessage],
        tools: List[Dict[str, Any]],
        tool_choice: Optional[Union[str, Dict[str, Any]]]
    ) -> str:
        """Create a prompt that enables tool calling for Ollama models"""

        # Build conversation history
        conversation = ""
        for msg in messages:
            if msg.role == "user":
                conversation += f"Human: {msg.content}\n"
            elif msg.role == "assistant":
                conversation += f"Assistant: {msg.content}\n"
            elif msg.role == "system":
                conversation = f"System: {msg.content}\n" + conversation

        # Build tools description
        tools_description = "Available tools:\n"
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            description = func.get("description", "No description")
            parameters = func.get("parameters", {})

            tools_description += f"\n{name}: {description}\n"

            if parameters.get("properties"):
                tools_description += "Parameters:\n"
                for param_name, param_info in parameters["properties"].items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    required = param_name in parameters.get("required", [])
                    req_marker = " (required)" if required else " (optional)"
                    tools_description += f"  - {param_name} ({param_type}){req_marker}: {param_desc}\n"

        # Create the prompt
        prompt = f"""You are an AI assistant with access to tools. When you need to use a tool, respond with a JSON object in this exact format:

{{
  "tool_calls": [
    {{
      "id": "call_<unique_id>",
      "type": "function",
      "function": {{
        "name": "<tool_name>",
        "arguments": "<json_string_of_arguments>"
      }}
    }}
  ]
}}

{tools_description}

{conversation}

If you need to use a tool, respond ONLY with the JSON tool call format above. If you don't need to use a tool, respond normally with your answer."""

        return prompt

    def _parse_tool_calls(self, response_content: str, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse tool calls from Ollama response"""
        try:
            # Try to find JSON in the response
            import re

            # Look for JSON object containing tool_calls
            json_match = re.search(r'\{.*"tool_calls".*\}', response_content, re.DOTALL)
            if not json_match:
                return []

            json_str = json_match.group(0)
            parsed = json.loads(json_str)

            if "tool_calls" in parsed:
                tool_calls = parsed["tool_calls"]

                # Validate and format tool calls
                formatted_calls = []
                for call in tool_calls:
                    if isinstance(call, dict) and "function" in call:
                        # Ensure proper format
                        formatted_call = {
                            "id": call.get("id", f"call_{len(formatted_calls)}"),
                            "type": "function",
                            "function": {
                                "name": call["function"].get("name", ""),
                                "arguments": call["function"].get("arguments", "{}")
                            }
                        }
                        formatted_calls.append(formatted_call)

                return formatted_calls

            return []

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.debug("Failed to parse tool calls from Ollama response", error=str(e))
            return []

    async def _handle_streaming_response(self, response) -> AsyncGenerator[str, None]:
        """Handle streaming response from Ollama"""
        async for line in response.aiter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                except json.JSONDecodeError:
                    continue
    
    async def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=300.0  # 5 minutes for model download
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error("Failed to pull Ollama model", model=model_name, error=str(e))
            return False
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama"""
        try:
            response = await self.client.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name}
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error("Failed to delete Ollama model", model=model_name, error=str(e))
            return False

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
