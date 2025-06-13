"""Contacts management endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_contacts():
    """Get contacts - placeholder."""
    return {"message": "Get contacts endpoint - to be implemented"}


@router.get("/{contact_id}")
async def get_contact(contact_id: str):
    """Get contact by ID - placeholder."""
    return {"message": f"Get contact {contact_id} endpoint - to be implemented"} 