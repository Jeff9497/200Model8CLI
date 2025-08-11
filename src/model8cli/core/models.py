"""
Model Management for 200Model8CLI

Handles model selection, capabilities, pricing, and optimization.
"""

import asyncio
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import time

import structlog
from cachetools import TTLCache

from .api import OpenRouterClient, ModelInfo, ModelType
from .config import Config

logger = structlog.get_logger(__name__)


class ModelCapability(Enum):
    """Model capabilities"""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    LONG_CONTEXT = "long_context"
    FAST_RESPONSE = "fast_response"
    HIGH_QUALITY = "high_quality"


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    avg_response_time: float = 0.0
    success_rate: float = 1.0
    total_requests: int = 0
    failed_requests: int = 0
    last_used: float = field(default_factory=time.time)
    cost_per_1k_tokens: float = 0.0


@dataclass
class ModelProfile:
    """Complete model profile with capabilities and metrics"""
    info: ModelInfo
    capabilities: Set[ModelCapability]
    metrics: ModelMetrics
    is_available: bool = True
    recommended_for: List[str] = field(default_factory=list)


class ModelManager:
    """
    Manages model selection, capabilities, and performance optimization
    """
    
    # Model capability mappings
    MODEL_CAPABILITIES = {
        ModelType.CLAUDE_3_OPUS: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.LONG_CONTEXT,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.CLAUDE_3_SONNET: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.LONG_CONTEXT,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.CLAUDE_3_HAIKU: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.FAST_RESPONSE,
        },
        ModelType.GPT_4_TURBO: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.VISION,
            ModelCapability.LONG_CONTEXT,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.GPT_4: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.GPT_3_5_TURBO: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.FAST_RESPONSE,
        },
        ModelType.LLAMA_3_70B: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.LONG_CONTEXT,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.LLAMA_3_8B: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.FAST_RESPONSE,
        },
        ModelType.GEMINI_PRO: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.LONG_CONTEXT,
        },
        ModelType.GEMINI_PRO_VISION: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.VISION,
            ModelCapability.TOOL_CALLING,
            ModelCapability.FUNCTION_CALLING,
        },
        ModelType.KIMI_K2_FREE: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.LONG_CONTEXT,
            ModelCapability.FAST_RESPONSE,
        },
        ModelType.QWERKY_72B_FREE: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.DEEPSEEK_R1_0528_FREE: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.HIGH_QUALITY,
        },
        ModelType.DEEPSEEK_CHAT_V3_FREE: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.FAST_RESPONSE,
        },
        ModelType.GEMMA_3_27B_FREE: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.FAST_RESPONSE,
        },
        ModelType.DEEPSEEK_R1_FREE: {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.HIGH_QUALITY,
        },
    }
    
    # Model recommendations for specific tasks
    TASK_RECOMMENDATIONS = {
        "code_generation": [
            ModelType.CLAUDE_3_OPUS,
            ModelType.CLAUDE_3_SONNET,
            ModelType.GPT_4_TURBO,
            ModelType.DEEPSEEK_R1_FREE,
            ModelType.QWERKY_72B_FREE,
        ],
        "file_editing": [
            ModelType.CLAUDE_3_SONNET,
            ModelType.GPT_4_TURBO,
            ModelType.CLAUDE_3_OPUS,
            ModelType.DEEPSEEK_CHAT_V3_FREE,
        ],
        "quick_tasks": [
            ModelType.CLAUDE_3_HAIKU,
            ModelType.GPT_3_5_TURBO,
            ModelType.LLAMA_3_8B,
            ModelType.GEMMA_3_27B_FREE,
            ModelType.KIMI_K2_FREE,
        ],
        "complex_analysis": [
            ModelType.CLAUDE_3_OPUS,
            ModelType.GPT_4_TURBO,
            ModelType.LLAMA_3_70B,
            ModelType.DEEPSEEK_R1_FREE,
            ModelType.QWERKY_72B_FREE,
        ],
        "tool_calling": [
            ModelType.CLAUDE_3_OPUS,
            ModelType.CLAUDE_3_SONNET,
            ModelType.GPT_4_TURBO,
        ],
    }
    
    def __init__(self, config: Config, api_client: OpenRouterClient):
        self.config = config
        self.api_client = api_client
        
        # Model profiles cache
        self.model_profiles: Dict[str, ModelProfile] = {}
        self.model_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour TTL
        
        # Current model
        self.current_model = config.default_model
        
        logger.info("Model manager initialized", default_model=self.current_model)
    
    async def initialize(self):
        """Initialize model profiles from API"""
        try:
            models = await self.api_client.get_models()
            
            for model_info in models:
                # Get capabilities for this model
                model_type = self._get_model_type(model_info.id)
                capabilities = self.MODEL_CAPABILITIES.get(model_type, set())
                
                # Create model profile
                profile = ModelProfile(
                    info=model_info,
                    capabilities=capabilities,
                    metrics=ModelMetrics(
                        cost_per_1k_tokens=self._calculate_cost_per_1k(model_info.pricing)
                    ),
                    recommended_for=self._get_recommendations(model_type),
                )
                
                self.model_profiles[model_info.id] = profile
            
            logger.info("Model profiles initialized", count=len(self.model_profiles))
            
        except Exception as e:
            logger.error("Failed to initialize model profiles", error=str(e))
            # Don't use fallback - let it fail properly if no API key
            if "Illegal header value" in str(e) or "Bearer " in str(e):
                raise ValueError("OpenRouter API key is required but not properly configured")
            # Use fallback model profiles only for other errors
            self._initialize_fallback_profiles()
    
    def _get_model_type(self, model_id: str) -> Optional[ModelType]:
        """Get ModelType enum from model ID"""
        for model_type in ModelType:
            if model_type.value == model_id:
                return model_type
        return None
    
    def _calculate_cost_per_1k(self, pricing: Dict[str, float]) -> float:
        """Calculate average cost per 1k tokens"""
        if not pricing:
            return 0.0

        # Handle different pricing structures
        prompt_cost = 0.0
        completion_cost = 0.0

        # Try different key formats
        if "prompt" in pricing:
            prompt_val = pricing["prompt"]
            prompt_cost = float(prompt_val) if isinstance(prompt_val, (int, float, str)) else 0.0

        if "completion" in pricing:
            completion_val = pricing["completion"]
            completion_cost = float(completion_val) if isinstance(completion_val, (int, float, str)) else 0.0

        # Average of prompt and completion costs
        if prompt_cost == 0.0 and completion_cost == 0.0:
            return 0.0
        return (prompt_cost + completion_cost) / 2
    
    def _get_recommendations(self, model_type: Optional[ModelType]) -> List[str]:
        """Get task recommendations for a model"""
        if not model_type:
            return []
        
        recommendations = []
        for task, models in self.TASK_RECOMMENDATIONS.items():
            if model_type in models:
                recommendations.append(task)
        
        return recommendations
    
    def _initialize_fallback_profiles(self):
        """Initialize fallback model profiles when API is unavailable"""
        fallback_models = [
            ("anthropic/claude-3-opus", "Claude 3 Opus"),
            ("anthropic/claude-3-sonnet-20240229", "Claude 3 Sonnet"),
            ("openai/gpt-4-turbo", "GPT-4 Turbo"),
            ("openai/gpt-3.5-turbo", "GPT-3.5 Turbo"),
        ]
        
        for model_id, name in fallback_models:
            model_type = self._get_model_type(model_id)
            if model_type:
                capabilities = self.MODEL_CAPABILITIES.get(model_type, set())
                
                profile = ModelProfile(
                    info=ModelInfo(
                        id=model_id,
                        name=name,
                        description=f"Fallback profile for {name}",
                        context_length=4096,
                        pricing={},
                    ),
                    capabilities=capabilities,
                    metrics=ModelMetrics(),
                    recommended_for=self._get_recommendations(model_type),
                )
                
                self.model_profiles[model_id] = profile
        
        logger.warning("Using fallback model profiles")
    
    def get_available_models(self) -> List[ModelProfile]:
        """Get list of available models"""
        return [profile for profile in self.model_profiles.values() if profile.is_available]
    
    def get_model_profile(self, model_id: str) -> Optional[ModelProfile]:
        """Get profile for a specific model"""
        return self.model_profiles.get(model_id)
    
    def recommend_model(
        self,
        task_type: Optional[str] = None,
        required_capabilities: Optional[Set[ModelCapability]] = None,
        prefer_fast: bool = False,
        prefer_quality: bool = False,
        max_cost: Optional[float] = None,
    ) -> Optional[str]:
        """
        Recommend the best model for a given task
        """
        available_models = self.get_available_models()
        
        if not available_models:
            return self.current_model
        
        # Filter by task type
        if task_type and task_type in self.TASK_RECOMMENDATIONS:
            recommended_types = self.TASK_RECOMMENDATIONS[task_type]
            available_models = [
                profile for profile in available_models
                if self._get_model_type(profile.info.id) in recommended_types
            ]
        
        # Filter by required capabilities
        if required_capabilities:
            available_models = [
                profile for profile in available_models
                if required_capabilities.issubset(profile.capabilities)
            ]
        
        # Filter by cost
        if max_cost:
            available_models = [
                profile for profile in available_models
                if profile.metrics.cost_per_1k_tokens <= max_cost
            ]
        
        if not available_models:
            return self.current_model
        
        # Score models based on preferences
        scored_models = []
        for profile in available_models:
            score = 0.0
            
            # Base score from success rate
            score += profile.metrics.success_rate * 100
            
            # Preference adjustments
            if prefer_fast and ModelCapability.FAST_RESPONSE in profile.capabilities:
                score += 20
            
            if prefer_quality and ModelCapability.HIGH_QUALITY in profile.capabilities:
                score += 30
            
            # Cost efficiency (lower cost = higher score)
            if profile.metrics.cost_per_1k_tokens > 0:
                score += max(0, 50 - profile.metrics.cost_per_1k_tokens * 1000)
            
            # Recent usage bonus
            time_since_use = time.time() - profile.metrics.last_used
            if time_since_use < 3600:  # Used within last hour
                score += 10
            
            scored_models.append((score, profile))
        
        # Return the highest scoring model
        if scored_models:
            best_model = max(scored_models, key=lambda x: x[0])[1]
            return best_model.info.id
        
        return self.current_model
    
    def set_current_model(self, model_id: str) -> bool:
        """Set the current model"""
        if model_id in self.model_profiles:
            self.current_model = model_id
            logger.info("Current model changed", model=model_id)
            return True
        return False
    
    def update_model_metrics(
        self,
        model_id: str,
        response_time: float,
        success: bool,
        cost: Optional[float] = None,
    ):
        """Update model performance metrics"""
        if model_id not in self.model_profiles:
            return
        
        profile = self.model_profiles[model_id]
        metrics = profile.metrics
        
        # Update response time (moving average)
        if metrics.total_requests > 0:
            metrics.avg_response_time = (
                metrics.avg_response_time * metrics.total_requests + response_time
            ) / (metrics.total_requests + 1)
        else:
            metrics.avg_response_time = response_time
        
        # Update request counts
        metrics.total_requests += 1
        if not success:
            metrics.failed_requests += 1
        
        # Update success rate
        metrics.success_rate = (
            metrics.total_requests - metrics.failed_requests
        ) / metrics.total_requests
        
        # Update last used time
        metrics.last_used = time.time()
        
        # Update cost if provided
        if cost:
            metrics.cost_per_1k_tokens = cost
        
        logger.debug(
            "Model metrics updated",
            model=model_id,
            success_rate=metrics.success_rate,
            avg_response_time=metrics.avg_response_time,
        )
    
    def get_model_stats(self) -> Dict[str, Dict[str, any]]:
        """Get statistics for all models"""
        stats = {}
        for model_id, profile in self.model_profiles.items():
            stats[model_id] = {
                "name": profile.info.name,
                "capabilities": [cap.value for cap in profile.capabilities],
                "metrics": {
                    "avg_response_time": profile.metrics.avg_response_time,
                    "success_rate": profile.metrics.success_rate,
                    "total_requests": profile.metrics.total_requests,
                    "cost_per_1k_tokens": profile.metrics.cost_per_1k_tokens,
                },
                "recommended_for": profile.recommended_for,
                "is_available": profile.is_available,
            }
        return stats
