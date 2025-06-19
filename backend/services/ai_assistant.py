"""
AI Assistant Service with Response Caching (Task 3.3.4)

This service provides AI-powered assistance with intelligent response caching
to optimize performance and reduce costs for the AIR MVP.

Features:
- Simple cache-aside pattern with Redis
- Basic TTL expiration (1-hour default)
- Wrapper around existing LLM client calls
- Simple cache hit/miss logging
- Integration with token usage tracking
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

import redis
from sqlalchemy.orm import Session

from config import settings
from lib.logger import logger
from lib.llm_client import get_openai_client, LLMUsageType, OpenAIModel, LLMResponse
from lib.exceptions import AIRException


class AIAssistantError(AIRException):
    """AI Assistant specific errors"""
    pass


@dataclass
class CacheStats:
    """Cache statistics for monitoring"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time_ms: float = 0.0
    cost_savings_usd: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "avg_response_time_ms": self.avg_response_time_ms,
            "cost_savings_usd": self.cost_savings_usd
        }


class AIAssistantService:
    """
    AI Assistant Service with intelligent response caching
    
    Provides AI-powered assistance while optimizing costs and performance
    through Redis-based response caching with simple TTL management.
    """
    
    def __init__(self, db: Session):
        """
        Initialize AI Assistant Service
        
        Args:
            db: Database session for logging and metrics
        """
        self.db = db
        
        # Initialize Redis client
        try:
            self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
            # Test connection
            self.redis_client.ping()
            logger.info("AI Assistant Redis client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self.redis_client = None
        
        # Cache configuration
        self.cache_prefix = "ai_cache"
        self.default_ttl = 3600  # 1 hour
        self.ttl_by_type = {
            "briefing": 86400,      # 24 hours for briefings
            "message": 3600,        # 1 hour for messages  
            "insight": 7200,        # 2 hours for insights
            "summary": 14400,       # 4 hours for summaries
            "analysis": 3600        # 1 hour for analysis
        }
        
        # Statistics tracking
        self.stats = CacheStats()
        
        logger.info("AIAssistantService initialized")
    
    def _generate_cache_key(
        self, 
        prompt: str, 
        user_id: str, 
        request_type: str,
        model: str = "gpt-3.5-turbo",
        **kwargs
    ) -> str:
        """
        Generate simple cache key for request
        
        Args:
            prompt: The prompt text
            user_id: User identifier
            request_type: Type of request (briefing, message, etc.)
            model: LLM model being used
            **kwargs: Additional parameters that affect the response
            
        Returns:
            Cache key string
        """
        # Create content for hashing
        cache_content = {
            "prompt": prompt.strip(),
            "model": model,
            "request_type": request_type,
            **kwargs
        }
        
        # Generate hash of content
        content_str = json.dumps(cache_content, sort_keys=True)
        content_hash = hashlib.md5(content_str.encode()).hexdigest()[:16]
        
        # Generate cache key
        cache_key = f"{self.cache_prefix}:{request_type}:{user_id}:{content_hash}"
        return cache_key
    
    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response from Redis
        
        Args:
            cache_key: Cache key to lookup
            
        Returns:
            Cached response data or None if not found
        """
        if not self.redis_client:
            return None
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Failed to get cached response: {e}")
            return None
    
    async def _cache_response(
        self, 
        cache_key: str, 
        response_data: Dict[str, Any], 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache response in Redis
        
        Args:
            cache_key: Cache key to store under
            response_data: Response data to cache
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            True if successfully cached, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            cached_data = json.dumps(response_data)
            self.redis_client.setex(cache_key, ttl, cached_data)
            return True
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")
            return False
    
    async def generate_with_cache(
        self,
        prompt: str,
        user_id: str,
        request_type: str,
        usage_type: LLMUsageType,
        model: Optional[OpenAIModel] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        force_refresh: bool = False,
        **kwargs
    ) -> LLMResponse:
        """
        Generate AI response with intelligent caching
        
        Args:
            prompt: The prompt to send to the AI
            user_id: User identifier
            request_type: Type of request for cache categorization
            usage_type: Type of LLM usage for tracking
            model: OpenAI model to use
            system_message: Optional system message
            temperature: Model temperature
            max_tokens: Maximum tokens to generate
            force_refresh: Skip cache and force new generation
            **kwargs: Additional parameters for the LLM
            
        Returns:
            LLM response with cache metadata
        """
        start_time = time.time()
        
        # Update request count
        self.stats.total_requests += 1
        
        # Generate cache key
        cache_params = {
            "system_message": system_message,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        model_str = model.value if model else "gpt-3.5-turbo"
        cache_key = self._generate_cache_key(
            prompt=prompt,
            user_id=user_id,
            request_type=request_type,
            model=model_str,
            **cache_params
        )
        
        # Try cache first (unless force refresh)
        cached_response = None
        if not force_refresh:
            cached_response = await self._get_cached_response(cache_key)
        
        if cached_response:
            # Cache hit
            self.stats.cache_hits += 1
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Update stats
            self.stats.avg_response_time_ms = (
                (self.stats.avg_response_time_ms * (self.stats.total_requests - 1) + response_time_ms) 
                / self.stats.total_requests
            )
            
            # Add cost savings estimate
            estimated_cost = cached_response.get("estimated_cost", 0.0)
            self.stats.cost_savings_usd += estimated_cost
            
            logger.info(f"Cache hit for {request_type} request (key: {cache_key[:20]}...)")
            
            # Reconstruct LLMResponse from cached data
            return LLMResponse(
                content=cached_response["content"],
                model=OpenAIModel(cached_response["model"]),
                usage=None,  # Usage not tracked for cached responses
                finish_reason=cached_response.get("finish_reason", "stop"),
                cached=True
            )
        
        # Cache miss - generate new response
        self.stats.cache_misses += 1
        
        try:
            # Get OpenAI client and generate response
            client = get_openai_client()
            if not client:
                raise AIAssistantError("OpenAI client not available")
            
            logger.info(f"Cache miss for {request_type} request - generating new response")
            
            # Generate new response
            response = await client.generate_completion(
                prompt=prompt,
                usage_type=usage_type,
                model=model,
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                **kwargs
            )
            
            # Prepare data for caching
            cache_data = {
                "content": response.content,
                "model": response.model.value,
                "finish_reason": response.finish_reason,
                "estimated_cost": response.usage.cost_usd if response.usage else 0.0,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "cache_key": cache_key
            }
            
            # Cache the response
            cache_ttl = self.ttl_by_type.get(request_type, self.default_ttl)
            await self._cache_response(cache_key, cache_data, cache_ttl)
            
            # Update response time stats
            response_time_ms = int((time.time() - start_time) * 1000)
            self.stats.avg_response_time_ms = (
                (self.stats.avg_response_time_ms * (self.stats.total_requests - 1) + response_time_ms) 
                / self.stats.total_requests
            )
            
            logger.info(f"Generated and cached new {request_type} response (cost: ${response.usage.cost_usd:.6f})")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}")
            raise AIAssistantError(f"Failed to generate AI response: {e}")
    
    async def generate_briefing(
        self,
        contact_name: str,
        contact_context: str,
        meeting_context: str,
        user_id: str,
        force_refresh: bool = False
    ) -> LLMResponse:
        """
        Generate pre-meeting briefing with caching
        
        Args:
            contact_name: Name of the contact
            contact_context: Context about the contact (company, role, etc.)
            meeting_context: Context about the upcoming meeting
            user_id: User identifier
            force_refresh: Skip cache and generate fresh briefing
            
        Returns:
            Generated briefing response
        """
        system_message = """You are an AI assistant helping to prepare for professional meetings. 
Generate a concise, actionable pre-meeting briefing that includes:
1. Key background information about the contact
2. Relevant talking points for the meeting
3. Questions to ask or topics to discuss
4. Any important context to remember

Keep the briefing professional, concise, and focused on actionable insights."""

        prompt = f"""Generate a pre-meeting briefing for:

Contact: {contact_name}
Contact Context: {contact_context}
Meeting Context: {meeting_context}

Please provide a structured briefing with key points, talking points, and suggested questions."""

        return await self.generate_with_cache(
            prompt=prompt,
            user_id=user_id,
            request_type="briefing",
            usage_type=LLMUsageType.BRIEFING_GENERATION,
            system_message=system_message,
            temperature=0.7,
            force_refresh=force_refresh
        )
    
    async def generate_message(
        self,
        message_type: str,
        recipient_context: str,
        message_context: str,
        user_id: str,
        tone: str = "professional",
        force_refresh: bool = False
    ) -> LLMResponse:
        """
        Generate AI-assisted message with caching
        
        Args:
            message_type: Type of message (follow_up, cold_outreach, etc.)
            recipient_context: Context about the recipient
            message_context: Context about the message purpose
            user_id: User identifier
            tone: Desired tone (professional, friendly, formal)
            force_refresh: Skip cache and generate fresh message
            
        Returns:
            Generated message response
        """
        system_message = f"""You are an AI assistant helping to draft professional communications.
Generate a {tone} {message_type} message that is:
1. Personalized and relevant
2. Clear and concise
3. Action-oriented when appropriate
4. Professional and appropriate for business context

The message should feel natural and authentic, not overly formal or robotic."""

        prompt = f"""Generate a {message_type} message with the following context:

Recipient Context: {recipient_context}
Message Context: {message_context}
Desired Tone: {tone}

Please provide a well-crafted message that is appropriate for the context and tone."""

        return await self.generate_with_cache(
            prompt=prompt,
            user_id=user_id,
            request_type="message",
            usage_type=LLMUsageType.MESSAGE_DRAFTING,
            system_message=system_message,
            temperature=0.8,  # Slightly higher temperature for creativity
            force_refresh=force_refresh
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get current cache statistics
        
        Returns:
            Dictionary with cache performance metrics
        """
        return self.stats.to_dict()
    
    async def clear_cache(self, pattern: Optional[str] = None) -> int:
        """
        Clear cached responses
        
        Args:
            pattern: Optional pattern to match keys (default clears all AI cache)
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0
        
        try:
            pattern = pattern or f"{self.cache_prefix}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cached responses matching pattern: {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0
    
    async def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cached responses for a specific user
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of keys deleted
        """
        pattern = f"{self.cache_prefix}:*:{user_id}:*"
        return await self.clear_cache(pattern)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check AI Assistant service health
        
        Returns:
            Health status including cache connectivity
        """
        health_status = {
            "service": "ai_assistant",
            "status": "healthy",
            "redis_connected": False,
            "cache_stats": self.get_cache_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Check Redis connectivity
        try:
            if self.redis_client:
                self.redis_client.ping()
                health_status["redis_connected"] = True
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["redis_error"] = str(e)
        
        # Check OpenAI client
        try:
            client = get_openai_client()
            health_status["openai_available"] = client is not None
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["openai_error"] = str(e)
        
        return health_status 