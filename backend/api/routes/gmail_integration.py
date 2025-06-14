"""
Gmail Integration API Routes for AIR MVP

This module provides REST API endpoints for Gmail integration management,
including OAuth flow, sync operations, and status monitoring.
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from lib.database import get_db
from services.gmail_integration_service import GmailIntegrationService
from services.auth import get_current_user
from models.schemas.integration import IntegrationResponseSchema, IntegrationCreateSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gmail", tags=["Gmail Integration"])


# Pydantic models for request/response
class GmailOAuthInitiate(BaseModel):
    """Request model for initiating Gmail OAuth"""
    redirect_uri: Optional[str] = Field(None, description="Custom redirect URI")


class GmailOAuthCallback(BaseModel):
    """Request model for Gmail OAuth callback"""
    code: str = Field(..., description="Authorization code from Google")
    state: Optional[str] = Field(None, description="State parameter for verification")


class GmailSyncRequest(BaseModel):
    """Request model for Gmail sync"""
    force_full_sync: bool = Field(False, description="Force full sync instead of incremental")
    max_results: int = Field(100, description="Maximum number of messages to sync", ge=1, le=500)


class GmailSyncResponse(BaseModel):
    """Response model for Gmail sync"""
    messages_fetched: int
    messages_processed: int
    errors: List[str]
    sync_timestamp: str
    next_page_token: Optional[str] = None


class GmailIntegrationStatus(BaseModel):
    """Response model for Gmail integration status"""
    integration_id: str
    email_address: Optional[str]
    status: str
    health_status: str
    last_sync_at: Optional[str]
    messages_synced: int
    total_syncs: int
    recent_events: List[Dict[str, Any]]
    active_alerts: List[Dict[str, Any]]
    created_at: str
    updated_at: str


@router.get("/setup-instructions")
async def get_setup_instructions() -> Dict[str, Any]:
    """
    Get Gmail setup instructions and configuration guide
    
    Returns:
        Setup instructions for Google Cloud and Gmail API
    """
    try:
        # This doesn't require authentication as it's setup information
        service = GmailIntegrationService(db=None)  # No DB needed for instructions
        instructions = service.get_setup_instructions()
        
        return {
            "success": True,
            "data": instructions
        }
        
    except Exception as e:
        logger.error(f"Failed to get setup instructions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get setup instructions: {str(e)}"
        )


@router.post("/oauth/initiate")
async def initiate_oauth_flow(
    request: GmailOAuthInitiate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Initiate Gmail OAuth flow
    
    Args:
        request: OAuth initiation request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        OAuth flow information including authorization URL
    """
    try:
        service = GmailIntegrationService(db)
        
        oauth_data = await service.initiate_oauth_flow(
            user_id=current_user["user_id"],
            redirect_uri=request.redirect_uri
        )
        
        return {
            "success": True,
            "data": oauth_data
        }
        
    except Exception as e:
        logger.error(f"Failed to initiate Gmail OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.post("/oauth/callback")
async def handle_oauth_callback(
    request: GmailOAuthCallback,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> IntegrationResponseSchema:
    """
    Handle Gmail OAuth callback
    
    Args:
        request: OAuth callback request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Created Gmail integration
    """
    try:
        service = GmailIntegrationService(db)
        
        integration = await service.handle_oauth_callback(
            user_id=current_user["user_id"],
            code=request.code,
            state=request.state
        )
        
        return IntegrationResponseSchema(
            id=integration.id,
            user_id=integration.user_id,
            provider=integration.provider,
            provider_user_id=integration.provider_user_id,
            status=integration.status,
            scopes=integration.scopes,
            metadata=integration.metadata,
            created_at=integration.created_at,
            updated_at=integration.updated_at
        )
        
    except ValueError as e:
        logger.error(f"Invalid OAuth callback: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OAuth callback: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to handle Gmail OAuth callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to handle OAuth callback: {str(e)}"
        )


@router.get("/oauth/callback")
async def handle_oauth_callback_get(
    code: str = Query(..., description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="State parameter"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle Gmail OAuth callback via GET request (redirect from Google)
    
    Args:
        code: Authorization code from Google
        state: State parameter
        error: Error from OAuth provider
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Redirect response or error
    """
    try:
        if error:
            logger.error(f"OAuth error: {error}")
            raise HTTPException(
                status_code=400,
                detail=f"OAuth error: {error}"
            )
        
        service = GmailIntegrationService(db)
        
        integration = await service.handle_oauth_callback(
            user_id=current_user["user_id"],
            code=code,
            state=state
        )
        
        # Redirect to frontend success page
        return RedirectResponse(
            url=f"/integrations/gmail/success?integration_id={integration.id}",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to handle Gmail OAuth callback: {e}")
        # Redirect to frontend error page
        return RedirectResponse(
            url=f"/integrations/gmail/error?error={str(e)}",
            status_code=302
        )


@router.get("/integrations")
async def get_user_integrations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all Gmail integrations for the current user
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of user's Gmail integrations
    """
    try:
        service = GmailIntegrationService(db)
        
        integrations = await service.get_user_integrations(
            user_id=current_user["user_id"]
        )
        
        return {
            "success": True,
            "data": integrations,
            "count": len(integrations)
        }
        
    except Exception as e:
        logger.error(f"Failed to get user Gmail integrations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get integrations: {str(e)}"
        )


@router.get("/integrations/{integration_id}/status")
async def get_integration_status(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> GmailIntegrationStatus:
    """
    Get detailed status of a Gmail integration
    
    Args:
        integration_id: Integration identifier
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Detailed integration status
    """
    try:
        service = GmailIntegrationService(db)
        
        status_data = await service.get_integration_status(integration_id)
        
        return GmailIntegrationStatus(**status_data)
        
    except ValueError as e:
        logger.error(f"Gmail integration not found: {e}")
        raise HTTPException(
            status_code=404,
            detail="Gmail integration not found"
        )
    except Exception as e:
        logger.error(f"Failed to get Gmail integration status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get integration status: {str(e)}"
        )


@router.post("/integrations/{integration_id}/sync")
async def trigger_sync(
    integration_id: str,
    request: GmailSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Trigger Gmail sync for an integration
    
    Args:
        integration_id: Integration identifier
        request: Sync request parameters
        background_tasks: Background task manager
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Sync operation status
    """
    try:
        service = GmailIntegrationService(db)
        
        # For immediate sync (could also be done in background)
        sync_result = await service.trigger_sync(
            integration_id=integration_id,
            force_full_sync=request.force_full_sync
        )
        
        return {
            "success": True,
            "data": {
                "messages_fetched": sync_result.messages_fetched,
                "messages_processed": sync_result.messages_processed,
                "errors": sync_result.errors,
                "sync_timestamp": sync_result.sync_timestamp.isoformat(),
                "next_page_token": sync_result.next_page_token
            }
        }
        
    except ValueError as e:
        logger.error(f"Gmail integration not found: {e}")
        raise HTTPException(
            status_code=404,
            detail="Gmail integration not found"
        )
    except Exception as e:
        logger.error(f"Failed to trigger Gmail sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger sync: {str(e)}"
        )


@router.delete("/integrations/{integration_id}")
async def disconnect_integration(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Disconnect a Gmail integration
    
    Args:
        integration_id: Integration identifier
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Disconnection status
    """
    try:
        service = GmailIntegrationService(db)
        
        success = await service.disconnect_integration(integration_id)
        
        return {
            "success": success,
            "message": "Gmail integration disconnected successfully"
        }
        
    except ValueError as e:
        logger.error(f"Gmail integration not found: {e}")
        raise HTTPException(
            status_code=404,
            detail="Gmail integration not found"
        )
    except Exception as e:
        logger.error(f"Failed to disconnect Gmail integration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect integration: {str(e)}"
        )


@router.get("/integrations/{integration_id}/health")
async def check_integration_health(
    integration_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check health of a Gmail integration
    
    Args:
        integration_id: Integration identifier
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Health check results
    """
    try:
        service = GmailIntegrationService(db)
        
        # Get integration and perform health check
        from services.integration_service import IntegrationService
        integration_service = IntegrationService(db)
        integration = await integration_service.get_integration(integration_id)
        
        if not integration or integration.provider != 'gmail':
            raise HTTPException(
                status_code=404,
                detail="Gmail integration not found"
            )
        
        health_data = await service.gmail_client.check_health(integration)
        
        return {
            "success": True,
            "data": health_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check Gmail integration health: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check integration health: {str(e)}"
        )


@router.get("/config")
async def get_oauth_config() -> Dict[str, Any]:
    """
    Get OAuth configuration for Gmail (public information only)
    
    Returns:
        Public OAuth configuration
    """
    try:
        service = GmailIntegrationService(db=None)  # No DB needed for config
        config = service.get_oauth_config()
        
        # Return only public configuration
        public_config = {
            "client_id": config.get("client_id"),
            "scopes": config.get("scopes"),
            "auth_uri": config.get("auth_uri"),
            "redirect_uri": config.get("redirect_uri")
        }
        
        return {
            "success": True,
            "data": public_config
        }
        
    except Exception as e:
        logger.error(f"Failed to get OAuth config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get OAuth config: {str(e)}"
        )


@router.post("/integrations/{integration_id}/sync-with-contacts")
async def sync_messages_with_contacts(
    integration_id: str,
    incremental: bool = True,
    max_results: int = 100,
    extract_contacts: bool = True,
    db: Session = Depends(get_db)
):
    """
    Sync Gmail messages and extract contacts from email exchanges.
    
    This endpoint performs email synchronization and automatically extracts
    contact information from senders and recipients.
    """
    try:
        gmail_service = GmailIntegrationService(db)
        
        # Get integration
        integration = await gmail_service.integration_service.get_integration(integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # Perform sync with contact extraction
        result = await gmail_service.sync_messages_with_contacts(
            integration=integration,
            incremental=incremental,
            max_results=max_results,
            extract_contacts=extract_contacts
        )
        
        return {
            "success": True,
            "integration_id": integration_id,
            "sync_result": {
                "messages_fetched": result['sync_result'].messages_fetched,
                "messages_processed": result['sync_result'].messages_processed,
                "errors": result['sync_result'].errors,
                "sync_timestamp": result['sync_result'].sync_timestamp.isoformat()
            },
            "contacts": {
                "extracted": result['contacts_extracted'],
                "created": result['contacts_created'],
                "updated": result['contacts_updated'],
                "data": result['contacts_data'][:10]  # Limit response size
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to sync messages with contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integrations/{integration_id}/contacts/{contact_email}/history")
async def get_contact_email_history(
    integration_id: str,
    contact_email: str,
    max_results: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get email history for a specific contact.
    
    Returns all email exchanges between the user and the specified contact,
    organized by conversation threads.
    """
    try:
        gmail_service = GmailIntegrationService(db)
        
        # Get contact email history
        history = await gmail_service.get_contact_email_history(
            integration_id=integration_id,
            contact_email=contact_email,
            max_results=max_results
        )
        
        return {
            "success": True,
            "integration_id": integration_id,
            "contact_email": contact_email,
            "history": history
        }
        
    except Exception as e:
        logger.error(f"Failed to get contact email history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integrations/{integration_id}/contacts/suggestions")
async def get_contact_suggestions(
    integration_id: str,
    limit: int = 20,
    min_interactions: int = 2,
    db: Session = Depends(get_db)
):
    """
    Get contact suggestions based on email interactions.
    
    Returns a list of email addresses that appear frequently in the user's
    email exchanges and could be added as contacts.
    """
    try:
        gmail_service = GmailIntegrationService(db)
        
        # Get integration
        integration = await gmail_service.integration_service.get_integration(integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # Fetch recent messages to analyze for contact suggestions
        sync_result = await gmail_service.sync_messages(
            integration=integration,
            incremental=True,
            max_results=200  # Analyze more messages for better suggestions
        )
        
        # Extract contacts from messages
        user_email = integration.metadata.get('email_address', '')
        contacts_data = await gmail_service.gmail_client.extract_contacts_from_messages(
            messages=getattr(sync_result, 'messages', []),
            user_id=user_email
        )
        
        # Filter and sort suggestions
        suggestions = [
            contact for contact in contacts_data 
            if contact['interaction_count'] >= min_interactions
        ]
        suggestions.sort(key=lambda x: x['interaction_count'], reverse=True)
        
        return {
            "success": True,
            "integration_id": integration_id,
            "suggestions": suggestions[:limit],
            "total_analyzed": len(contacts_data),
            "filtered_count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Failed to get contact suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 