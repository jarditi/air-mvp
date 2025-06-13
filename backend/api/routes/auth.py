"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Dict, Any

from lib.database import get_db
from services.auth import get_current_user, get_current_active_user, get_auth_service
from models.orm.user import User
from models.schemas.user import UserResponseSchema, UserDetailResponseSchema, UserUpdateSchema

router = APIRouter()


@router.get("/me", response_model=UserDetailResponseSchema)
async def get_current_user_profile(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user profile information."""
    auth_service = get_auth_service()
    
    # Get user stats
    stats = auth_service.get_user_stats(current_user, db)
    
    # Convert to response schema
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name or "",
        "timezone": current_user.timezone,
        "subscription_tier": current_user.subscription_tier,
        "subscription_status": current_user.subscription_status,
        "is_verified": current_user.is_verified,
        "is_active": current_user.is_active,
        "auth_provider": current_user.auth_provider,
        "avatar_url": current_user.avatar_url,
        "onboarding_completed": current_user.onboarding_completed,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "last_login_at": current_user.last_login_at,
        "contact_count": stats.get("contact_count", 0),
        "interaction_count": stats.get("interaction_count", 0)
    }
    
    return user_data


@router.put("/me", response_model=UserResponseSchema)
async def update_current_user_profile(
    user_update: UserUpdateSchema,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user profile information."""
    auth_service = get_auth_service()
    
    # Convert Pydantic model to dict, excluding unset fields
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Update user profile
    updated_user = auth_service.update_user_profile(current_user, update_data, db)
    
    return updated_user


@router.post("/token/refresh")
async def refresh_token(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh internal API token."""
    auth_service = get_auth_service()
    
    # Create new internal token
    new_token = auth_service.create_internal_token(current_user)
    
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": auth_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/stats")
async def get_user_stats(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user statistics and metadata."""
    auth_service = get_auth_service()
    stats = auth_service.get_user_stats(current_user, db)
    
    return stats


@router.post("/deactivate")
async def deactivate_account(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deactivate current user account."""
    auth_service = get_auth_service()
    
    success = auth_service.deactivate_user(current_user, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )
    
    return {"message": "Account deactivated successfully"}


@router.get("/health")
async def auth_health_check():
    """Check authentication service health."""
    auth_service = get_auth_service()
    
    health_status = {
        "service": "authentication",
        "status": "healthy",
        "clerk_configured": auth_service.clerk_client is not None,
        "jwt_verification_configured": auth_service.settings.CLERK_JWT_VERIFICATION_KEY is not None
    }
    
    return health_status


@router.get("/test-auth")
async def test_auth(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Test authentication endpoint for debugging."""
    if not authorization:
        return {"error": "No authorization header"}
    
    if not authorization.startswith("Bearer "):
        return {"error": "Invalid authorization format"}
    
    token = authorization.split(" ")[1]
    
    try:
        auth_service = get_auth_service()
        
        # Create credentials manually
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        # Test authentication
        user = auth_service.authenticate_request(credentials, db)
        
        return {
            "success": True,
            "user_id": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider
        }
        
    except Exception as e:
        return {"error": str(e)} 