from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from uuid import UUID
from typing import Optional
import logging

from services.integration_service import IntegrationService
from lib.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

@router.get("/success", response_class=HTMLResponse)
async def integration_success(
    integration_id: Optional[str] = None,
    provider: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Success page after OAuth integration completion.
    
    Args:
        integration_id: The ID of the completed integration
        provider: The provider name (gmail, etc.)
        db: Database session
        
    Returns:
        HTML success page
    """
    try:
        # Validate integration exists
        if integration_id:
            integration_service = IntegrationService(db)
            integration = integration_service.get_integration(UUID(integration_id))
            
            if integration:
                # Generate success HTML with integration details
                return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integration Complete - AIR</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .success-card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .success-icon {{
            width: 80px;
            height: 80px;
            background: #10B981;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
        }}
        
        .checkmark {{
            width: 40px;
            height: 40px;
            border: 3px solid white;
            border-top: none;
            border-right: none;
            transform: rotate(-45deg);
            margin-top: 10px;
        }}
        
        h1 {{
            color: #1F2937;
            margin: 0 0 16px;
            font-size: 28px;
            font-weight: 600;
        }}
        
        .provider {{
            color: #6B7280;
            font-size: 18px;
            margin: 0 0 24px;
            text-transform: capitalize;
        }}
        
        .details {{
            background: #F9FAFB;
            border-radius: 8px;
            padding: 20px;
            margin: 24px 0;
            text-align: left;
        }}
        
        .detail-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 8px 0;
            font-size: 14px;
        }}
        
        .detail-label {{
            color: #6B7280;
            font-weight: 500;
        }}
        
        .detail-value {{
            color: #1F2937;
            font-weight: 600;
        }}
        
        .status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            background: #10B981;
            color: white;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .actions {{
            margin-top: 32px;
        }}
        
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            margin: 0 8px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #5a6fd8;
            transform: translateY(-1px);
        }}
        
        .btn-secondary {{
            background: #F3F4F6;
            color: #6B7280;
        }}
        
        .btn-secondary:hover {{
            background: #E5E7EB;
        }}
        
        .footer {{
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid #E5E7EB;
            color: #6B7280;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="success-card">
        <div class="success-icon">
            <div class="checkmark"></div>
        </div>
        
        <h1>Integration Complete!</h1>
        <p class="provider">{provider or 'Email'} integration successful</p>
        
        <div class="details">
            <div class="detail-row">
                <span class="detail-label">Integration ID:</span>
                <span class="detail-value">{integration_id[:8]}...</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span class="status">{integration.status}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Created:</span>
                <span class="detail-value">{integration.created_at.strftime('%B %d, %Y at %I:%M %p')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Email:</span>
                <span class="detail-value">{integration.platform_metadata.get('email_address', 'N/A')}</span>
            </div>
        </div>
        
        <div class="actions">
            <a href="/docs" class="btn btn-primary">View API Docs</a>
            <a href="javascript:window.close()" class="btn btn-secondary">Close Window</a>
        </div>
        
        <div class="footer">
            <p>Your {provider or 'email'} account is now connected to AIR.<br>
            You can start syncing your data and extracting contacts.</p>
        </div>
    </div>
    
    <script>
        // Auto-close after 10 seconds if opened in popup
        if (window.opener) {{
            setTimeout(() => {{
                window.close();
            }}, 10000);
        }}
    </script>
</body>
</html>
                """
        
        # Default success page if no integration details
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integration Complete - AIR</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; margin: 0; padding: 40px; text-align: center;">
    <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h1 style="color: #2563eb; margin-bottom: 16px;">Integration Complete!</h1>
        <p style="color: #6b7280; font-size: 16px;">Your integration has been set up successfully.</p>
        <div style="margin-top: 32px;">
            <a href="/docs" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View API Documentation</a>
        </div>
    </div>
</body>
</html>
        """
        
    except Exception as e:
        logger.error(f"Error displaying integration success page: {e}")
        # Return a generic success page
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integration Complete - AIR</title>
</head>
<body style="font-family: system-ui, sans-serif; background: #f5f5f5; margin: 0; padding: 40px; text-align: center;">
    <div style="background: white; max-width: 400px; margin: 0 auto; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h1 style="color: #059669;">✅ Success!</h1>
        <p>Your integration has been completed.</p>
        <a href="/docs" style="display: inline-block; margin-top: 20px; background: #059669; color: white; padding: 10px 20px; border-radius: 4px; text-decoration: none;">Continue</a>
    </div>
</body>
</html>
        """


@router.get("/error", response_class=HTMLResponse)
async def integration_error(
    error: Optional[str] = None,
    integration_id: Optional[str] = None,
    provider: Optional[str] = None
):
    """
    Error page for failed OAuth integrations.
    
    Args:
        error: Error message
        integration_id: Integration ID if available
        provider: Provider name
        
    Returns:
        HTML error page
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integration Error - AIR</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #fee2e2 0%, #fca5a5 100%);
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .error-card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .error-icon {{
            width: 80px;
            height: 80px;
            background: #EF4444;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
            color: white;
            font-size: 40px;
            font-weight: bold;
        }}
        
        h1 {{
            color: #1F2937;
            margin: 0 0 16px;
            font-size: 28px;
            font-weight: 600;
        }}
        
        .error-message {{
            background: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 8px;
            padding: 16px;
            margin: 20px 0;
            color: #DC2626;
            font-family: monospace;
            font-size: 14px;
            text-align: left;
            word-break: break-word;
        }}
        
        .actions {{
            margin-top: 32px;
        }}
        
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            margin: 0 8px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .btn-primary {{
            background: #2563EB;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #1D4ED8;
        }}
        
        .btn-secondary {{
            background: #F3F4F6;
            color: #6B7280;
        }}
        
        .btn-secondary:hover {{
            background: #E5E7EB;
        }}
    </style>
</head>
<body>
    <div class="error-card">
        <div class="error-icon">!</div>
        
        <h1>Integration Failed</h1>
        <p>There was an error connecting your {provider or 'account'}.</p>
        
        {f'<div class="error-message">{error}</div>' if error else ''}
        
        <div class="actions">
            <a href="/docs" class="btn btn-primary">Try Again</a>
            <a href="javascript:window.close()" class="btn btn-secondary">Close</a>
        </div>
    </div>
</body>
</html>
    """ 