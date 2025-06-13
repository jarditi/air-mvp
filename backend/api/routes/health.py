"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add database connectivity check
    return {"status": "ready"} 