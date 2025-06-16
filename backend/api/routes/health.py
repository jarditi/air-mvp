"""Health check endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.llm_client import get_openai_client, LLMError
from config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


class DetailedHealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, Any]


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    return HealthResponse(status="healthy", version=settings.APP_VERSION)


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """Detailed health check with service status."""
    services = {}
    overall_status = "healthy"
    
    # Check OpenAI service
    try:
        client = get_openai_client()
        openai_health = await client.health_check()
        services["openai"] = openai_health
        if openai_health["status"] != "healthy":
            overall_status = "degraded"
    except LLMError:
        services["openai"] = {
            "status": "unavailable",
            "error": "OpenAI client not initialized",
            "api_accessible": False
        }
        overall_status = "degraded"
    except Exception as e:
        services["openai"] = {
            "status": "error",
            "error": str(e),
            "api_accessible": False
        }
        overall_status = "degraded"
    
    # TODO: Add database connectivity check
    # TODO: Add Redis connectivity check
    # TODO: Add Weaviate connectivity check
    
    return DetailedHealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        services=services
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add database connectivity check
    return {"status": "ready"}


@router.get("/openai")
async def openai_health_check():
    """Specific OpenAI health check endpoint."""
    try:
        client = get_openai_client()
        health_status = await client.health_check()
        return health_status
    except LLMError as e:
        raise HTTPException(status_code=503, detail=f"OpenAI service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI health check failed: {e}") 