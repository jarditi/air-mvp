"""AI assistant endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/briefing")
async def generate_briefing():
    """Generate pre-meeting briefing - placeholder."""
    return {"message": "Generate briefing endpoint - to be implemented"}


@router.post("/message")
async def generate_message():
    """Generate AI message - placeholder."""
    return {"message": "Generate message endpoint - to be implemented"} 