"""Generic OAuth2 client for handling multiple providers."""

import asyncio
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from pydantic import BaseModel, Field

from config import settings
from lib.exceptions import AIRException
from lib.logger import logger


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    LINKEDIN = "linkedin"
    MICROSOFT = "microsoft"
    GITHUB = "github"


class OAuthScope(str, Enum):
    """Common OAuth scopes across providers."""
    # Google scopes
    GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
    GMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"
    CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
    CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"
    CONTACTS_READONLY = "https://www.googleapis.com/auth/contacts.readonly"
    PROFILE = "https://www.googleapis.com/auth/userinfo.profile"
    EMAIL = "https://www.googleapis.com/auth/userinfo.email"
    
    # LinkedIn scopes
    LINKEDIN_PROFILE = "r_liteprofile"
    LINKEDIN_EMAIL = "r_emailaddress"
    LINKEDIN_CONNECTIONS = "r_basicprofile"
    
    # Microsoft scopes
    OUTLOOK_READ = "https://graph.microsoft.com/Mail.Read"
    OUTLOOK_SEND = "https://graph.microsoft.com/Mail.Send"
    CALENDAR_READ = "https://graph.microsoft.com/Calendars.Read"
    
    # GitHub scopes
    GITHUB_USER = "user"
    GITHUB_REPO = "repo"


@dataclass
class OAuthToken:
    """OAuth token data structure."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    expires_at: Optional[int] = None
    scope: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return time.time() >= self.expires_at
    
    @property
    def expired(self) -> bool:
        """Property to check if token is expired (for compatibility)."""
        return self.is_expired()
    
    def expires_soon(self, buffer_seconds: int = 300) -> bool:
        """Check if token expires within buffer_seconds."""
        if not self.expires_at:
            return False
        return time.time() >= (self.expires_at - buffer_seconds)


class OAuthError(AIRException):
    """OAuth-specific error."""
    
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class OAuthProviderConfig(BaseModel):
    """Configuration for an OAuth provider."""
    name: OAuthProvider
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    userinfo_url: Optional[str] = None
    revoke_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    redirect_uri: Optional[str] = None


class BaseOAuthProvider(ABC):
    """Base class for OAuth providers."""
    
    def __init__(self, config: OAuthProviderConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @abstractmethod
    def get_auth_url(self, state: str, scopes: Optional[List[str]] = None) -> str:
        """Generate authorization URL."""
        pass
    
    @abstractmethod
    async def exchange_code(self, code: str, state: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> OAuthToken:
        """Refresh access token."""
        pass
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke access token."""
        if not self.config.revoke_url:
            logger.warning(f"No revoke URL configured for {self.config.name}")
            return False
        
        try:
            response = await self.client.post(
                self.config.revoke_url,
                data={"token": token}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    async def get_user_info(self, token: OAuthToken) -> Dict[str, Any]:
        """Get user information using access token."""
        if not self.config.userinfo_url:
            raise OAuthError(f"No userinfo URL configured for {self.config.name}")
        
        headers = {"Authorization": f"{token.token_type} {token.access_token}"}
        
        try:
            response = await self.client.get(
                self.config.userinfo_url,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise OAuthError(f"Failed to get user info: {e.response.text}")
        except Exception as e:
            raise OAuthError(f"Failed to get user info: {str(e)}")


class GoogleOAuthProvider(BaseOAuthProvider):
    """Google OAuth provider implementation."""
    
    def get_auth_url(self, state: str, scopes: Optional[List[str]] = None) -> str:
        """Generate Google OAuth authorization URL."""
        scopes = scopes or self.config.scopes
        
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(scopes),
            "response_type": "code",
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent"  # Force consent to get refresh token
        }
        
        return f"{self.config.auth_url}?{urlencode(params)}"
    
    async def exchange_code(self, code: str, state: str) -> OAuthToken:
        """Exchange authorization code for Google access token."""
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.config.redirect_uri
        }
        
        try:
            response = await self.client.post(
                self.config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
            
            expires_at = None
            if "expires_in" in token_data:
                expires_at = int(time.time()) + token_data["expires_in"]
            
            return OAuthToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                expires_at=expires_at,
                scope=token_data.get("scope")
            )
        except httpx.HTTPStatusError as e:
            raise OAuthError(f"Failed to exchange code: {e.response.text}")
        except Exception as e:
            raise OAuthError(f"Failed to exchange code: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> OAuthToken:
        """Refresh Google access token."""
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            response = await self.client.post(
                self.config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
            
            expires_at = None
            if "expires_in" in token_data:
                expires_at = int(time.time()) + token_data["expires_in"]
            
            return OAuthToken(
                access_token=token_data["access_token"],
                refresh_token=refresh_token,  # Keep original refresh token
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                expires_at=expires_at,
                scope=token_data.get("scope")
            )
        except httpx.HTTPStatusError as e:
            raise OAuthError(f"Failed to refresh token: {e.response.text}")
        except Exception as e:
            raise OAuthError(f"Failed to refresh token: {str(e)}")


class LinkedInOAuthProvider(BaseOAuthProvider):
    """LinkedIn OAuth provider implementation."""
    
    def get_auth_url(self, state: str, scopes: Optional[List[str]] = None) -> str:
        """Generate LinkedIn OAuth authorization URL."""
        scopes = scopes or self.config.scopes
        
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(scopes),
            "response_type": "code",
            "state": state
        }
        
        return f"{self.config.auth_url}?{urlencode(params)}"
    
    async def exchange_code(self, code: str, state: str) -> OAuthToken:
        """Exchange authorization code for LinkedIn access token."""
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.config.redirect_uri
        }
        
        try:
            response = await self.client.post(
                self.config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
            
            expires_at = None
            if "expires_in" in token_data:
                expires_at = int(time.time()) + token_data["expires_in"]
            
            return OAuthToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                expires_at=expires_at,
                scope=token_data.get("scope")
            )
        except httpx.HTTPStatusError as e:
            raise OAuthError(f"Failed to exchange code: {e.response.text}")
        except Exception as e:
            raise OAuthError(f"Failed to exchange code: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> OAuthToken:
        """LinkedIn doesn't support refresh tokens in v2 API."""
        raise OAuthError("LinkedIn OAuth v2 does not support refresh tokens")


class OAuthClient:
    """Generic OAuth client that manages multiple providers."""
    
    def __init__(self):
        self.providers: Dict[OAuthProvider, BaseOAuthProvider] = {}
        self._setup_providers()
    
    def _setup_providers(self):
        """Initialize OAuth providers based on configuration."""
        # Google OAuth setup - Updated to use new environment variables
        google_client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None) or getattr(settings, 'GOOGLE_CLIENT_ID', None)
        google_client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', None) or getattr(settings, 'GOOGLE_CLIENT_SECRET', None)
        google_redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', None) or getattr(settings, 'GOOGLE_REDIRECT_URI', None)
        
        if google_client_id and google_client_secret:
            google_config = OAuthProviderConfig(
                name=OAuthProvider.GOOGLE,
                client_id=google_client_id,
                client_secret=google_client_secret,
                auth_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
                revoke_url="https://oauth2.googleapis.com/revoke",
                scopes=[
                    OAuthScope.PROFILE,
                    OAuthScope.EMAIL,
                    OAuthScope.GMAIL_READONLY,
                    OAuthScope.CALENDAR_READONLY
                ],
                redirect_uri=google_redirect_uri or "http://localhost:8000/auth/google/callback"
            )
            self.providers[OAuthProvider.GOOGLE] = GoogleOAuthProvider(google_config)
        
        # LinkedIn OAuth setup
        if settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET:
            linkedin_config = OAuthProviderConfig(
                name=OAuthProvider.LINKEDIN,
                client_id=settings.LINKEDIN_CLIENT_ID,
                client_secret=settings.LINKEDIN_CLIENT_SECRET,
                auth_url="https://www.linkedin.com/oauth/v2/authorization",
                token_url="https://www.linkedin.com/oauth/v2/accessToken",
                userinfo_url="https://api.linkedin.com/v2/people/~",
                scopes=[
                    OAuthScope.LINKEDIN_PROFILE,
                    OAuthScope.LINKEDIN_EMAIL
                ]
            )
            self.providers[OAuthProvider.LINKEDIN] = LinkedInOAuthProvider(linkedin_config)
    
    def get_provider(self, provider: OAuthProvider) -> BaseOAuthProvider:
        """Get OAuth provider instance."""
        if provider not in self.providers:
            raise OAuthError(f"Provider {provider} not configured")
        return self.providers[provider]
    
    def generate_state(self) -> str:
        """Generate secure state parameter for OAuth flow."""
        return secrets.token_urlsafe(32)
    
    def get_auth_url(
        self, 
        provider: OAuthProvider, 
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
        state: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Get authorization URL for provider.
        
        Returns:
            Tuple of (auth_url, state)
        """
        oauth_provider = self.get_provider(provider)
        oauth_provider.config.redirect_uri = redirect_uri
        
        if not state:
            state = self.generate_state()
        
        auth_url = oauth_provider.get_auth_url(state, scopes)
        return auth_url, state
    
    async def exchange_code(
        self, 
        provider: OAuthProvider, 
        code: str, 
        state: str,
        redirect_uri: str
    ) -> OAuthToken:
        """Exchange authorization code for access token."""
        oauth_provider = self.get_provider(provider)
        oauth_provider.config.redirect_uri = redirect_uri
        
        return await oauth_provider.exchange_code(code, state)
    
    async def refresh_token(
        self, 
        provider: OAuthProvider, 
        refresh_token: str
    ) -> OAuthToken:
        """Refresh access token."""
        oauth_provider = self.get_provider(provider)
        return await oauth_provider.refresh_token(refresh_token)
    
    async def revoke_token(
        self, 
        provider: OAuthProvider, 
        token: str
    ) -> bool:
        """Revoke access token."""
        oauth_provider = self.get_provider(provider)
        return await oauth_provider.revoke_token(token)
    
    async def get_user_info(
        self, 
        provider: OAuthProvider, 
        token: OAuthToken
    ) -> Dict[str, Any]:
        """Get user information using access token."""
        oauth_provider = self.get_provider(provider)
        return await oauth_provider.get_user_info(token)
    
    async def ensure_valid_token(
        self, 
        provider: OAuthProvider, 
        token: OAuthToken
    ) -> OAuthToken:
        """
        Ensure token is valid, refresh if needed.
        
        Returns:
            Valid OAuthToken (may be refreshed)
        """
        if not token.expires_soon():
            return token
        
        if not token.refresh_token:
            raise OAuthError("Token expired and no refresh token available")
        
        logger.info(f"Refreshing token for provider {provider}")
        return await self.refresh_token(provider, token.refresh_token)
    
    def get_available_providers(self) -> List[OAuthProvider]:
        """Get list of configured providers."""
        return list(self.providers.keys())


# Global OAuth client instance
oauth_client = OAuthClient()


async def get_oauth_client() -> OAuthClient:
    """Dependency to get OAuth client instance."""
    return oauth_client 