"""Integration management endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_integrations():
    """Get integrations - placeholder."""
    return {"message": "Get integrations endpoint - to be implemented"}


@router.post("/gmail/connect")
async def connect_gmail():
    """Connect Gmail - placeholder."""
    return {"message": "Connect Gmail endpoint - to be implemented"} 