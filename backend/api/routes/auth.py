"""Authentication endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Login endpoint - placeholder."""
    return {"message": "Login endpoint - to be implemented"}


@router.post("/logout")
async def logout():
    """Logout endpoint - placeholder."""
    return {"message": "Logout endpoint - to be implemented"} 