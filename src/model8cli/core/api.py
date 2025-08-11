"""
OpenRouter API Client for 200Model8CLI

Handles all interactions with the OpenRouter API including authentication,
model management, streaming responses, and retry logic.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
from dataclasses import dataclass
from enum import Enum

import httpx
import structlog
from asyncio_throttle import Throttler

from .config import Config

logger = structlog.get_logger(__name__)


class ModelType(Enum):
    """Supported model types"""
    CLAUDE_3_OPUS = "anthropic/claude-3-opus"
    CLAUDE_3_SONNET = "anthropic/claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "anthropic/claude-3-haiku-20240307"
    GPT_4_TURBO = "openai/gpt-4-turbo"
    GPT_4 = "openai/gpt-4"
    GPT_3_5_TURBO = "openai/gpt-3.5-turbo"
    LLAMA_3_70B = "meta-llama/llama-3-70b-instruct"
    LLAMA_3_8B = "meta-llama/llama-3-8b-instruct"
    GEMINI_PRO = "google/gemini-pro"
    GEMINI_PRO_VISION = "google/gemini-pro-vision"
    KIMI_K2_FREE = "moonshotai/kimi-k2:free"
    QWERKY_72B_FREE = "featherless/qwerky-72b:free"
    DEEPSEEK_R1_0528_FREE = "deepseek/deepseek-r1-0528:free"
    DEEPSEEK_CHAT_V3_FREE = "deepseek/deepseek-chat-v3-0324:free"
    GEMMA_3_27B_FREE = "google/gemma-3-27b-it:free"
    DEEPSEEK_R1_FREE = "deepseek/deepseek-r1:free"


@dataclass
class ModelInfo:
    """Information about a model"""
    id: str
    name: str
    description: str
    context_length: int
    pricing: Dict[str, float]
    per_request_limits: Optional[Dict[str, int]] = None


@dataclass
class Message:
    """Chat message structure"""
    role: str  # "user", "assistant", "system"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    """Tool call structure"""
    id: str
    type: str
    function: Dict[str, Any]


@dataclass
class ChatResponse:
    """Response from chat completion"""
    id: str
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    created: int


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors"""
    pass


class AuthenticationError(OpenRouterError):
    """Authentication failed"""
    pass


class RateLimitError(OpenRouterError):
    """Rate limit exceeded"""
    pass


class ModelNotFoundError(OpenRouterError):
    """Model not found or not available"""
    pass


class OpenRouterClient:
    """
    OpenRouter API client with comprehensive error handling, retry logic,
    and streaming support.
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize HTTP client with proper headers
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "HTTP-Referer": "https://200model8cli.com",
                "X-Title": "200Model8CLI",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(config.api_timeout),
        )
        
        # Rate limiting
        self.throttler = Throttler(rate_limit=config.rate_limit_per_minute, period=60)
        
        # Retry configuration
        self.max_retries = config.max_retries
        self.base_delay = config.base_retry_delay
        
        logger.info("OpenRouter client initialized", model=config.default_model)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Make a request to the OpenRouter API with retry logic
        """
        url = f"{endpoint}"
        
        for attempt in range(self.max_retries + 1):
            try:
                # Apply rate limiting
                async with self.throttler:
                    if method.upper() == "GET":
                        response = await self.client.get(url)
                    elif method.upper() == "POST":
                        if stream:
                            return self._stream_request(url, data)
                        response = await self.client.post(url, json=data)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle response
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError("Invalid API key")
                elif response.status_code == 429:
                    if attempt < self.max_retries:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            "Rate limit hit, retrying",
                            attempt=attempt + 1,
                            delay=delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise RateLimitError("Rate limit exceeded")
                elif response.status_code == 404:
                    raise ModelNotFoundError("Model not found or not available")
                else:
                    response.raise_for_status()
                    
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        "Request failed, retrying",
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay
                    )
                    await asyncio.sleep(delay)
                    continue
                raise OpenRouterError(f"Request failed: {e}")
        
        raise OpenRouterError("Max retries exceeded")
    
    async def _stream_request(
        self, url: str, data: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handle streaming requests"""
        data["stream"] = True
        
        async with self.client.stream("POST", url, json=data) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise OpenRouterError(f"Streaming request failed: {error_text}")
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_data = line[6:]  # Remove "data: " prefix
                    if chunk_data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_data)
                        yield chunk
                    except json.JSONDecodeError:
                        continue
    
    async def get_models(self) -> List[ModelInfo]:
        """Get list of available models"""
        try:
            response = await self._make_request("GET", "/models")
            models = []
            
            for model_data in response.get("data", []):
                model_info = ModelInfo(
                    id=model_data["id"],
                    name=model_data.get("name", model_data["id"]),
                    description=model_data.get("description", ""),
                    context_length=model_data.get("context_length", 4096),
                    pricing=model_data.get("pricing", {}),
                    per_request_limits=model_data.get("per_request_limits"),
                )
                models.append(model_info)
            
            logger.info("Retrieved models", count=len(models))
            return models
            
        except Exception as e:
            logger.error("Failed to get models", error=str(e))
            raise OpenRouterError(f"Failed to get models: {e}")
    
    async def chat_completion(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Union[ChatResponse, AsyncGenerator[Dict[str, Any], None]]:
        """
        Create a chat completion - routes to appropriate provider
        """
        # Validate inputs
        if not messages:
            raise ValueError("Messages cannot be empty")

        # Use default model if not specified
        if not model:
            model = self.config.default_model

        # Route to Ollama for local models
        if model.startswith("ollama/"):
            return await self._handle_ollama_completion(
                messages, model, tools, tool_choice, temperature, max_tokens, stream
            )

        # Route to Groq for Groq models
        if model.startswith("groq/") or self._is_groq_model(model):
            return await self._handle_groq_completion(
                messages, model, tools, tool_choice, temperature, max_tokens, stream
            )
        
        # Prepare request data
        request_data = {
            "model": model,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    **({"tool_calls": msg.tool_calls} if msg.tool_calls else {}),
                    **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
                }
                for msg in messages
            ],
            "temperature": temperature,
        }
        
        if max_tokens:
            request_data["max_tokens"] = max_tokens
        
        if tools:
            request_data["tools"] = tools
            
        if tool_choice:
            request_data["tool_choice"] = tool_choice
        
        # Basic request validation
        if not request_data.get("messages"):
            raise ValueError("Messages are required")
        
        try:
            if stream:
                return self._make_request("POST", "/chat/completions", request_data, stream=True)
            else:
                response = await self._make_request("POST", "/chat/completions", request_data)

                # Handle missing fields gracefully
                return ChatResponse(
                    id=response.get("id", "unknown"),
                    model=response.get("model", model),
                    choices=response.get("choices", []),
                    usage=response.get("usage", {}),
                    created=response.get("created", 0),
                )
                
        except Exception as e:
            logger.error("Chat completion failed", error=str(e), model=model)
            raise OpenRouterError(f"Chat completion failed: {e}")

    async def _handle_ollama_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> ChatResponse:
        """Handle chat completion for Ollama models"""
        try:
            from .ollama_client import OllamaClient, ChatMessage

            # Extract model name (remove ollama/ prefix)
            ollama_model = model.replace("ollama/", "")

            # Initialize Ollama client
            ollama_client = OllamaClient()

            # Check if Ollama is available
            if not await ollama_client.is_available():
                raise OpenRouterError("Ollama is not running. Please start Ollama service.")

            # Convert messages to Ollama format
            ollama_messages = []
            for msg in messages:
                ollama_messages.append(ChatMessage(
                    role=msg.role,
                    content=msg.content
                ))

            # Make request to Ollama
            response = await ollama_client.chat_completion(
                model=ollama_model,
                messages=ollama_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                tools=tools,
                tool_choice=tool_choice
            )

            await ollama_client.close()

            # Convert Ollama response to OpenRouter format
            # response.message is a dict with 'role' and 'content' keys
            message = {
                "role": "assistant",
                "content": response.message.get("content", "") if response.message else ""
            }

            # Add tool calls if present
            if response.message and "tool_calls" in response.message:
                message["tool_calls"] = response.message["tool_calls"]
                # If there are tool calls, content should be None
                if response.message["tool_calls"]:
                    message["content"] = None

            return ChatResponse(
                id=f"ollama-{ollama_model}",
                model=model,  # Keep the ollama/ prefix
                choices=[{"message": message}],
                usage={
                    "prompt_tokens": response.prompt_eval_count or 0,
                    "completion_tokens": response.eval_count or 0,
                    "total_tokens": (response.prompt_eval_count or 0) + (response.eval_count or 0)
                },
                created=0,
            )

        except Exception as e:
            logger.error("Ollama completion failed", error=str(e), model=model)
            raise OpenRouterError(f"Ollama completion failed: {e}")

    def _is_groq_model(self, model: str) -> bool:
        """Check if a model is a Groq model"""
        from .groq_client import GroqClient
        return model in GroqClient.AVAILABLE_MODELS

    async def _handle_groq_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> ChatResponse:
        """Handle chat completion for Groq models"""
        try:
            from .groq_client import GroqClient

            # Remove groq/ prefix if present
            groq_model = model.replace("groq/", "")

            # Initialize Groq client
            groq_client = GroqClient(self.config)

            # Make request to Groq
            response = await groq_client.chat_completion(
                model=groq_model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            await groq_client.close()
            return response

        except Exception as e:
            logger.error("Groq completion failed", error=str(e))
            raise OpenRouterError(f"Groq completion failed: {e}")

    async def health_check(self) -> bool:
        """Check if the API is healthy"""
        try:
            await self.get_models()
            return True
        except Exception:
            return False
