"""
OpenAI API Client for AIR MVP

This module provides a comprehensive client for interacting with OpenAI's API,
including GPT models for relationship intelligence, communication assistance,
and content analysis.

Features:
- Multiple model support (GPT-4, GPT-3.5-turbo)
- Rate limiting and retry logic
- Token usage tracking
- Error handling and logging
- Async support for high performance
- Cost optimization strategies
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import json
import logging

import openai
from openai import AsyncOpenAI
import tiktoken
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from lib.exceptions import AIRException
from lib.logger import logger

# Global token usage service instance
_token_usage_service = None


class OpenAIModel(str, Enum):
    """Supported OpenAI models with their characteristics"""
    GPT_4_TURBO = "gpt-4-turbo-preview"
    GPT_4 = "gpt-4"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_3_5_TURBO_16K = "gpt-3.5-turbo-16k"
    
    @property
    def max_tokens(self) -> int:
        """Maximum tokens for each model"""
        token_limits = {
            self.GPT_4_TURBO: 128000,
            self.GPT_4: 8192,
            self.GPT_3_5_TURBO: 4096,
            self.GPT_3_5_TURBO_16K: 16384
        }
        return token_limits[self]
    
    @property
    def cost_per_1k_tokens(self) -> Dict[str, float]:
        """Cost per 1K tokens (input/output) in USD"""
        costs = {
            self.GPT_4_TURBO: {"input": 0.01, "output": 0.03},
            self.GPT_4: {"input": 0.03, "output": 0.06},
            self.GPT_3_5_TURBO: {"input": 0.0015, "output": 0.002},
            self.GPT_3_5_TURBO_16K: {"input": 0.003, "output": 0.004}
        }
        return costs[self]


class LLMUsageType(str, Enum):
    """Types of LLM usage for tracking and optimization"""
    BRIEFING_GENERATION = "briefing_generation"
    MESSAGE_DRAFTING = "message_drafting"
    INTEREST_EXTRACTION = "interest_extraction"
    RELATIONSHIP_ANALYSIS = "relationship_analysis"
    CONTACT_ENRICHMENT = "contact_enrichment"
    CONVERSATION_SUMMARY = "conversation_summary"
    SENTIMENT_ANALYSIS = "sentiment_analysis"


@dataclass
class LLMUsage:
    """Track LLM usage for cost management and analytics"""
    model: OpenAIModel
    usage_type: LLMUsageType
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    response_time_ms: int
    timestamp: datetime
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "model": self.model.value,
            "usage_type": self.usage_type.value,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "request_id": self.request_id
        }


@dataclass
class LLMResponse:
    """Structured response from LLM with metadata"""
    content: str
    model: OpenAIModel
    usage: LLMUsage
    finish_reason: str
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "content": self.content,
            "model": self.model.value,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
                "cost_usd": self.usage.cost_usd
            },
            "finish_reason": self.finish_reason,
            "cached": self.cached,
            "response_time_ms": self.usage.response_time_ms
        }


class LLMError(AIRException):
    """LLM-specific errors"""
    
    def __init__(self, message: str, error_type: str = "llm_error", **kwargs):
        super().__init__(message, **kwargs)
        self.error_type = error_type


class OpenAIClient:
    """
    Comprehensive OpenAI API client for AIR MVP
    
    Features:
    - Async support for high performance
    - Automatic retry with exponential backoff
    - Token counting and cost tracking
    - Rate limiting protection
    - Error handling and logging
    - Model selection optimization
    """
    
    def __init__(
        self,
        api_key: str,
        default_model: OpenAIModel = OpenAIModel.GPT_3_5_TURBO,
        max_retries: int = 3,
        timeout: int = 60,
        rate_limit_rpm: int = 60  # Requests per minute
    ):
        """
        Initialize OpenAI client
        
        Args:
            api_key: OpenAI API key
            default_model: Default model to use
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
            rate_limit_rpm: Rate limit in requests per minute
        """
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.default_model = default_model
        self.max_retries = max_retries
        self.rate_limit_rpm = rate_limit_rpm
        
        # Rate limiting
        self._request_times: List[float] = []
        self._rate_limit_lock = asyncio.Lock()
        
        # Token encoders for different models
        self._encoders = {}
        
        logger.info(f"OpenAI client initialized with model {default_model.value}")
    
    def _get_encoder(self, model: OpenAIModel) -> tiktoken.Encoding:
        """Get token encoder for model"""
        if model not in self._encoders:
            try:
                self._encoders[model] = tiktoken.encoding_for_model(model.value)
            except KeyError:
                # Fallback to cl100k_base for newer models
                self._encoders[model] = tiktoken.get_encoding("cl100k_base")
        return self._encoders[model]
    
    def count_tokens(self, text: str, model: OpenAIModel) -> int:
        """Count tokens in text for given model"""
        encoder = self._get_encoder(model)
        return len(encoder.encode(text))
    
    def estimate_cost(
        self, 
        prompt_tokens: int, 
        completion_tokens: int, 
        model: OpenAIModel
    ) -> float:
        """Estimate cost in USD for token usage"""
        costs = model.cost_per_1k_tokens
        prompt_cost = (prompt_tokens / 1000) * costs["input"]
        completion_cost = (completion_tokens / 1000) * costs["output"]
        return prompt_cost + completion_cost
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting"""
        async with self._rate_limit_lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            self._request_times = [
                req_time for req_time in self._request_times 
                if now - req_time < 60
            ]
            
            # Check if we're at the rate limit
            if len(self._request_times) >= self.rate_limit_rpm:
                sleep_time = 60 - (now - self._request_times[0])
                if sleep_time > 0:
                    logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
            
            self._request_times.append(now)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError))
    )
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        model: OpenAIModel,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make API request with retry logic"""
        await self._enforce_rate_limit()
        
        try:
            response = await self.client.chat.completions.create(
                model=model.value,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMError(f"API request failed: {e}", "api_error")
    
    async def generate_completion(
        self,
        prompt: str,
        usage_type: LLMUsageType,
        model: Optional[OpenAIModel] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion with full tracking and error handling
        
        Args:
            prompt: User prompt
            usage_type: Type of usage for tracking
            model: Model to use (defaults to client default)
            system_message: Optional system message
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            user_id: User ID for tracking
            **kwargs: Additional OpenAI parameters
            
        Returns:
            LLMResponse with content and metadata
        """
        model = model or self.default_model
        start_time = time.time()
        
        # Build messages
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # Count prompt tokens
        prompt_text = system_message + "\n" + prompt if system_message else prompt
        prompt_tokens = self.count_tokens(prompt_text, model)
        
        # Validate token limits
        if prompt_tokens > model.max_tokens * 0.8:  # Leave room for completion
            raise LLMError(
                f"Prompt too long: {prompt_tokens} tokens (max: {model.max_tokens})",
                "token_limit_error"
            )
        
        success = True
        error_type = None
        error_message = None
        
        try:
            # Make API request
            response = await self._make_request(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Extract response data
            choice = response.choices[0]
            content = choice.message.content
            finish_reason = choice.finish_reason
            
            # Calculate usage and cost
            usage_data = response.usage
            completion_tokens = usage_data.completion_tokens
            total_tokens = usage_data.total_tokens
            cost = self.estimate_cost(prompt_tokens, completion_tokens, model)
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Create usage tracking
            usage = LLMUsage(
                model=model,
                usage_type=usage_type,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                request_id=response.id
            )
            
            logger.info(
                f"LLM completion: {usage_type.value}, "
                f"model={model.value}, tokens={total_tokens}, "
                f"cost=${cost:.4f}, time={response_time_ms}ms"
            )
            
            # Log usage to database if service is available
            if _token_usage_service:
                try:
                    await _token_usage_service.log_usage(
                        usage=usage,
                        prompt_length=len(prompt),
                        completion_length=len(content),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        success=True
                    )
                except Exception as e:
                    logger.error(f"Failed to log token usage: {e}")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason
            )
            
        except Exception as e:
            success = False
            error_type = type(e).__name__
            error_message = str(e)
            
            # Log failed usage if service is available
            if _token_usage_service:
                try:
                    # Create minimal usage object for failed request
                    failed_usage = LLMUsage(
                        model=model,
                        usage_type=usage_type,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=0,
                        total_tokens=prompt_tokens,
                        cost_usd=0.0,
                        response_time_ms=int((time.time() - start_time) * 1000),
                        timestamp=datetime.now(timezone.utc),
                        user_id=user_id,
                        request_id=None
                    )
                    
                    await _token_usage_service.log_usage(
                        usage=failed_usage,
                        prompt_length=len(prompt),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        success=False,
                        error_type=error_type,
                        error_message=error_message
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log failed token usage: {log_error}")
            
            logger.error(f"LLM generation failed: {e}")
            raise
    
    async def generate_structured_completion(
        self,
        prompt: str,
        usage_type: LLMUsageType,
        response_format: Dict[str, Any],
        model: Optional[OpenAIModel] = None,
        system_message: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON completion
        
        Args:
            prompt: User prompt
            usage_type: Type of usage for tracking
            response_format: JSON schema for response
            model: Model to use
            system_message: Optional system message
            user_id: User ID for tracking
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON response
        """
        # Add JSON formatting instruction to system message
        json_instruction = f"""
        You must respond with valid JSON that matches this schema:
        {json.dumps(response_format, indent=2)}
        
        Do not include any text outside the JSON response.
        """
        
        full_system_message = (
            f"{system_message}\n\n{json_instruction}" 
            if system_message 
            else json_instruction
        )
        
        response = await self.generate_completion(
            prompt=prompt,
            usage_type=usage_type,
            model=model,
            system_message=full_system_message,
            temperature=0.3,  # Lower temperature for structured output
            user_id=user_id,
            **kwargs
        )
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response.content}")
            raise LLMError(f"Invalid JSON response: {e}", "json_parse_error")
    
    async def analyze_sentiment(
        self,
        text: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of text
        
        Args:
            text: Text to analyze
            user_id: User ID for tracking
            
        Returns:
            Sentiment analysis results
        """
        prompt = f"""
        Analyze the sentiment of the following text and provide a detailed assessment:
        
        Text: "{text}"
        
        Consider:
        - Overall sentiment (positive, negative, neutral)
        - Emotional tone
        - Professional vs personal context
        - Confidence level
        """
        
        response_format = {
            "sentiment": "positive|negative|neutral",
            "confidence": "float between 0 and 1",
            "emotional_tone": "string describing emotional tone",
            "context": "professional|personal|mixed",
            "key_indicators": ["list of words/phrases that indicate sentiment"]
        }
        
        return await self.generate_structured_completion(
            prompt=prompt,
            usage_type=LLMUsageType.SENTIMENT_ANALYSIS,
            response_format=response_format,
            model=OpenAIModel.GPT_3_5_TURBO,  # Cost-effective for sentiment
            user_id=user_id
        )
    
    async def extract_interests(
        self,
        text: str,
        context: str = "general",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract interests and topics from text
        
        Args:
            text: Text to analyze
            context: Context of the text
            user_id: User ID for tracking
            
        Returns:
            Extracted interests and topics
        """
        prompt = f"""
        Extract interests, hobbies, and professional topics from the following text:
        
        Text: "{text}"
        Context: {context}
        
        Identify:
        - Professional interests and skills
        - Personal hobbies and interests
        - Industry/domain expertise
        - Technologies or tools mentioned
        - Confidence level for each interest
        """
        
        response_format = {
            "professional_interests": ["list of professional interests/skills"],
            "personal_interests": ["list of hobbies/personal interests"],
            "technologies": ["list of technologies/tools mentioned"],
            "industries": ["list of industries/domains"],
            "confidence_scores": {
                "professional": "float between 0 and 1",
                "personal": "float between 0 and 1",
                "overall": "float between 0 and 1"
            }
        }
        
        return await self.generate_structured_completion(
            prompt=prompt,
            usage_type=LLMUsageType.INTEREST_EXTRACTION,
            response_format=response_format,
            model=OpenAIModel.GPT_3_5_TURBO,
            user_id=user_id
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on OpenAI API
        
        Returns:
            Health check results
        """
        try:
            start_time = time.time()
            
            # Simple test completion
            response = await self.generate_completion(
                prompt="Say 'OK' if you can hear me.",
                usage_type=LLMUsageType.SENTIMENT_ANALYSIS,  # Use cheapest category
                model=OpenAIModel.GPT_3_5_TURBO,
                temperature=0,
                max_tokens=5
            )
            
            response_time = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "model": self.default_model.value,
                "test_response": response.content.strip(),
                "cost_usd": response.usage.cost_usd
            }
            
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "error_type": type(e).__name__
            }


# Global client instance
_openai_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    """Get the global OpenAI client instance"""
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialized. Call initialize_openai_client() first.")
    return _openai_client


def initialize_openai_client(
    api_key: str,
    default_model: OpenAIModel = OpenAIModel.GPT_3_5_TURBO,
    **kwargs
) -> OpenAIClient:
    """Initialize the global OpenAI client"""
    global _openai_client
    _openai_client = OpenAIClient(
        api_key=api_key,
        default_model=default_model,
        **kwargs
    )
    logger.info("Global OpenAI client initialized")
    return _openai_client


def set_token_usage_service(service):
    """Set the global token usage service for logging"""
    global _token_usage_service
    _token_usage_service = service
    logger.info("Token usage service configured for OpenAI client") 