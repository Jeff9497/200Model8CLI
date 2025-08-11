"""
Groq API client for 200Model8CLI
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass

import httpx
import structlog

from .config import Config
from .api import Message, ChatResponse, OpenRouterError

logger = structlog.get_logger(__name__)


@dataclass
class GroqModel:
    """Groq model information"""
    id: str
    name: str
    context_length: int
    requests_per_minute: int
    requests_per_day: int
    tokens_per_minute: int
    tokens_per_day: int


class GroqClient:
    """Client for Groq API"""
    
    BASE_URL = "https://api.groq.com/openai/v1"
    
    # Available Groq models with their limits
    AVAILABLE_MODELS = {
        "allam-2-7b": GroqModel(
            id="allam-2-7b",
            name="Allam 2 7B",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=7000,
            tokens_per_minute=6000,
            tokens_per_day=500000
        ),
        "compound-beta": GroqModel(
            id="compound-beta",
            name="Compound Beta",
            context_length=8192,
            requests_per_minute=15,
            requests_per_day=200,
            tokens_per_minute=70000,
            tokens_per_day=0  # No limit
        ),
        "compound-beta-mini": GroqModel(
            id="compound-beta-mini",
            name="Compound Beta Mini",
            context_length=8192,
            requests_per_minute=15,
            requests_per_day=200,
            tokens_per_minute=70000,
            tokens_per_day=0  # No limit
        ),
        "deepseek-r1-distill-llama-70b": GroqModel(
            id="deepseek-r1-distill-llama-70b",
            name="DeepSeek R1 Distill Llama 70B",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=1000,
            tokens_per_minute=6000,
            tokens_per_day=100000
        ),
        "gemma2-9b-it": GroqModel(
            id="gemma2-9b-it",
            name="Gemma 2 9B IT",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=15000,
            tokens_per_day=500000
        ),
        "llama-3.1-8b-instant": GroqModel(
            id="llama-3.1-8b-instant",
            name="Llama 3.1 8B Instant",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=6000,
            tokens_per_day=500000
        ),
        "llama-3.3-70b-versatile": GroqModel(
            id="llama-3.3-70b-versatile",
            name="Llama 3.3 70B Versatile",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=1000,
            tokens_per_minute=12000,
            tokens_per_day=100000
        ),
        "llama3-70b-8192": GroqModel(
            id="llama3-70b-8192",
            name="Llama 3 70B 8192",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=6000,
            tokens_per_day=500000
        ),
        "llama3-8b-8192": GroqModel(
            id="llama3-8b-8192",
            name="Llama 3 8B 8192",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=6000,
            tokens_per_day=500000
        ),
        "meta-llama/llama-4-maverick-17b-128e-instruct": GroqModel(
            id="meta-llama/llama-4-maverick-17b-128e-instruct",
            name="Llama 4 Maverick 17B 128E Instruct",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=1000,
            tokens_per_minute=6000,
            tokens_per_day=500000
        ),
        "meta-llama/llama-4-scout-17b-16e-instruct": GroqModel(
            id="meta-llama/llama-4-scout-17b-16e-instruct",
            name="Llama 4 Scout 17B 16E Instruct",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=1000,
            tokens_per_minute=30000,
            tokens_per_day=500000
        ),
        "meta-llama/llama-guard-4-12b": GroqModel(
            id="meta-llama/llama-guard-4-12b",
            name="Llama Guard 4 12B",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=15000,
            tokens_per_day=500000
        ),
        "meta-llama/llama-prompt-guard-2-22m": GroqModel(
            id="meta-llama/llama-prompt-guard-2-22m",
            name="Llama Prompt Guard 2 22M",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=15000,
            tokens_per_day=500000
        ),
        "meta-llama/llama-prompt-guard-2-86m": GroqModel(
            id="meta-llama/llama-prompt-guard-2-86m",
            name="Llama Prompt Guard 2 86M",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=14400,
            tokens_per_minute=15000,
            tokens_per_day=500000
        ),
        "mistral-saba-24b": GroqModel(
            id="mistral-saba-24b",
            name="Mistral Saba 24B",
            context_length=8192,
            requests_per_minute=30,
            requests_per_day=1000,
            tokens_per_minute=6000,
            tokens_per_day=500000
        ),
        "moonshotai/kimi-k2-instruct": GroqModel(
            id="moonshotai/kimi-k2-instruct",
            name="Kimi K2 Instruct",
            context_length=8192,
            requests_per_minute=60,
            requests_per_day=1000,
            tokens_per_minute=10000,
            tokens_per_day=300000
        ),
        "qwen/qwen3-32b": GroqModel(
            id="qwen/qwen3-32b",
            name="Qwen 3 32B",
            context_length=8192,
            requests_per_minute=60,
            requests_per_day=1000,
            tokens_per_minute=6000,
            tokens_per_day=500000
        )
    }
    
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize HTTP client with proper headers
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {config.groq_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(config.api_timeout),
        )
        
        logger.info("Groq client initialized")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def get_available_models(self) -> List[GroqModel]:
        """Get list of available Groq models"""
        return list(self.AVAILABLE_MODELS.values())
    
    def get_model_info(self, model_id: str) -> Optional[GroqModel]:
        """Get information about a specific model"""
        return self.AVAILABLE_MODELS.get(model_id)
    
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> ChatResponse:
        """
        Create a chat completion using Groq API
        """
        # Validate inputs
        if not messages:
            raise ValueError("Messages cannot be empty")
        
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
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=request_data
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error("Groq API error", status=response.status_code, error=error_text)
                raise OpenRouterError(f"Groq API error: {response.status_code} - {error_text}")
            
            response_data = response.json()
            
            return ChatResponse(
                id=response_data.get("id", "unknown"),
                model=response_data.get("model", model),
                choices=response_data.get("choices", []),
                usage=response_data.get("usage", {}),
                created=response_data.get("created", 0),
            )
            
        except httpx.RequestError as e:
            logger.error("Groq request failed", error=str(e))
            raise OpenRouterError(f"Groq request failed: {e}")
        except Exception as e:
            logger.error("Groq chat completion failed", error=str(e), model=model)
            raise OpenRouterError(f"Groq chat completion failed: {e}")
