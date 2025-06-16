"""Integration model for OAuth tokens and platform connections."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, Boolean, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class Integration(BaseModel):
    """Integration model for OAuth tokens and integration status for external platforms."""
    
    __tablename__ = "integrations"
    
    # Foreign key to user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Platform identification
    platform = Column(String(50), nullable=False, index=True)  # 'google', 'linkedin', 'microsoft', 'github'
    provider_name = Column(String(50), nullable=False)  # Human-readable name
    status = Column(String(20), default="disconnected", index=True)  # 'connected', 'disconnected', 'error', 'expired', 'revoked'
    
    # OAuth tokens (encrypted at application level)
    access_token_encrypted = Column(Text)  # Encrypted access token
    refresh_token_encrypted = Column(Text)  # Encrypted refresh token
    token_type = Column(String(20), default="Bearer")
    token_expires_at = Column(DateTime)
    scope = Column(ARRAY(Text))  # Array of granted permissions
    
    # OAuth flow state management
    oauth_state = Column(String(255))  # State parameter for OAuth flow
    oauth_code_verifier = Column(String(255))  # PKCE code verifier
    redirect_uri = Column(Text)  # Redirect URI used for this integration
    
    # Sync configuration and status
    last_sync_at = Column(DateTime)
    last_successful_sync_at = Column(DateTime)
    sync_frequency = Column(String(20), default="hourly")  # 'realtime', 'hourly', 'daily', 'manual'
    auto_sync_enabled = Column(Boolean, default=True)
    
    # Error tracking and retry logic
    error_message = Column(Text)
    error_count = Column(Integer, default=0)
    last_error_at = Column(DateTime)
    retry_after = Column(DateTime)  # When to retry after rate limiting
    
    # Usage tracking
    total_syncs = Column(Integer, default=0)
    total_items_synced = Column(Integer, default=0)
    last_sync_duration_seconds = Column(Integer)
    
    # Platform-specific settings and metadata
    platform_metadata = Column(JSONB, default=dict)  # Platform-specific settings
    sync_settings = Column(JSONB, default=dict)  # User sync preferences
    
    # Feature flags
    features_enabled = Column(ARRAY(Text), default=list)  # Enabled features for this integration
    
    # Relationships
    user = relationship("User", back_populates="integrations")
    # TODO: Temporarily commented out to fix import issues
    # sync_jobs = relationship("SyncJob", back_populates="integration", cascade="all, delete-orphan")
    # status_events = relationship("IntegrationStatusEvent", back_populates="integration", cascade="all, delete-orphan")
    # health_checks = relationship("IntegrationHealthCheck", back_populates="integration", cascade="all, delete-orphan")
    # alerts = relationship("IntegrationAlert", back_populates="integration", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'platform', name='uq_user_platform'),
    )
    
    def __init__(self, **kwargs):
        """Initialize integration with proper defaults."""
        super().__init__(**kwargs)
        self._encryption_service = None
    
    @property
    def access_token(self) -> Optional[str]:
        """Decrypt and return the access token."""
        if not self.access_token_encrypted:
            return None
        try:
            if not hasattr(self, '_encryption_service') or not self._encryption_service:
                from lib.crypto import get_encryption_service
                self._encryption_service = get_encryption_service()
            return self._encryption_service.decrypt_string(self.access_token_encrypted)
        except Exception:
            return None
    
    @access_token.setter
    def access_token(self, value: Optional[str]) -> None:
        """Encrypt and store the access token."""
        if value is None:
            self.access_token_encrypted = None
        else:
            if not hasattr(self, '_encryption_service') or not self._encryption_service:
                from lib.crypto import get_encryption_service
                self._encryption_service = get_encryption_service()
            self.access_token_encrypted = self._encryption_service.encrypt_string(value)
    
    @property
    def refresh_token(self) -> Optional[str]:
        """Decrypt and return the refresh token."""
        if not self.refresh_token_encrypted:
            return None
        try:
            if not hasattr(self, '_encryption_service') or not self._encryption_service:
                from lib.crypto import get_encryption_service
                self._encryption_service = get_encryption_service()
            return self._encryption_service.decrypt_string(self.refresh_token_encrypted)
        except Exception:
            return None
    
    @refresh_token.setter
    def refresh_token(self, value: Optional[str]) -> None:
        """Encrypt and store the refresh token."""
        if value is None:
            self.refresh_token_encrypted = None
        else:
            if not hasattr(self, '_encryption_service') or not self._encryption_service:
                from lib.crypto import get_encryption_service
                self._encryption_service = get_encryption_service()
            self.refresh_token_encrypted = self._encryption_service.encrypt_string(value)
    
    def store_oauth_token(self, oauth_token) -> None:
        """Store an OAuth token with proper encryption."""
        self.access_token = oauth_token.access_token
        self.refresh_token = oauth_token.refresh_token
        self.token_type = oauth_token.token_type
        self.token_expires_at = datetime.fromtimestamp(oauth_token.expires_at) if oauth_token.expires_at else None
        
        # Parse and store scopes
        if oauth_token.scope:
            self.scope = oauth_token.scope.split(' ') if isinstance(oauth_token.scope, str) else oauth_token.scope
        
        # Update status
        self.status = "connected"
        self.error_message = None
        self.error_count = 0
        self.updated_at = datetime.utcnow()
    
    def get_oauth_token(self):
        """Retrieve the stored OAuth token."""
        if not self.access_token:
            return None
        
        from lib.oauth_client import OAuthToken
        
        expires_at = None
        if self.token_expires_at:
            expires_at = int(self.token_expires_at.timestamp())
        
        return OAuthToken(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            token_type=self.token_type,
            expires_at=expires_at,
            scope=' '.join(self.scope) if self.scope else None
        )
    
    def is_token_expired(self) -> bool:
        """Check if the stored token is expired."""
        oauth_token = self.get_oauth_token()
        return oauth_token.is_expired() if oauth_token else True
    
    def is_token_expiring_soon(self, buffer_minutes: int = 5) -> bool:
        """Check if the token expires soon."""
        oauth_token = self.get_oauth_token()
        return oauth_token.expires_soon(buffer_minutes * 60) if oauth_token else True
    
    def mark_sync_started(self) -> None:
        """Mark that a sync operation has started."""
        self.last_sync_at = datetime.utcnow()
        self.total_syncs = (self.total_syncs or 0) + 1
    
    def mark_sync_completed(self, items_synced: int = 0, duration_seconds: int = 0) -> None:
        """Mark that a sync operation completed successfully."""
        now = datetime.utcnow()
        self.last_successful_sync_at = now
        self.total_items_synced = (self.total_items_synced or 0) + items_synced
        self.last_sync_duration_seconds = duration_seconds
        self.error_count = 0
        self.error_message = None
        self.retry_after = None
        self.updated_at = now
    
    def mark_sync_failed(self, error_message: str, retry_after_minutes: Optional[int] = None) -> None:
        """Mark that a sync operation failed."""
        now = datetime.utcnow()
        self.error_message = error_message
        self.error_count = (self.error_count or 0) + 1
        self.last_error_at = now
        
        if retry_after_minutes:
            from datetime import timedelta
            self.retry_after = now + timedelta(minutes=retry_after_minutes)
        
        # Update status based on error type
        if "expired" in error_message.lower() or "unauthorized" in error_message.lower():
            self.status = "expired"
        else:
            self.status = "error"
        
        self.updated_at = now
    
    def revoke_tokens(self) -> None:
        """Revoke and clear all stored tokens."""
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.scope = None
        self.status = "revoked"
        self.oauth_state = None
        self.oauth_code_verifier = None
        self.updated_at = datetime.utcnow()
    
    def can_retry_sync(self) -> bool:
        """Check if sync can be retried based on retry_after timestamp."""
        if not self.retry_after:
            return True
        return datetime.utcnow() >= self.retry_after
    
    def get_provider_enum(self):
        """Get the OAuthProvider enum for this integration."""
        try:
            from lib.oauth_client import OAuthProvider
            return OAuthProvider(self.platform)
        except (ValueError, ImportError):
            return None
    
    def update_sync_settings(self, settings: Dict[str, Any]) -> None:
        """Update sync settings for this integration."""
        current_settings = self.sync_settings or {}
        current_settings.update(settings)
        self.sync_settings = current_settings
        self.updated_at = datetime.utcnow()
    
    def enable_feature(self, feature: str) -> None:
        """Enable a specific feature for this integration."""
        if not self.features_enabled:
            self.features_enabled = []
        if feature not in self.features_enabled:
            self.features_enabled.append(feature)
            self.updated_at = datetime.utcnow()
    
    def disable_feature(self, feature: str) -> None:
        """Disable a specific feature for this integration."""
        if self.features_enabled and feature in self.features_enabled:
            self.features_enabled.remove(feature)
            self.updated_at = datetime.utcnow()
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled."""
        return feature in (self.features_enabled or [])
    
    @property
    def scopes(self) -> List[str]:
        """Get scopes as a list (for backward compatibility)."""
        return self.scope or []
    
    @scopes.setter
    def scopes(self, value: List[str]) -> None:
        """Set scopes from a list (for backward compatibility)."""
        self.scope = value
    
    @property
    def provider(self) -> str:
        """Get provider (maps to platform for backward compatibility)."""
        return self.platform
    
    @provider.setter
    def provider(self, value: str) -> None:
        """Set provider (maps to platform for backward compatibility)."""
        self.platform = value
    
    @property
    def provider_user_id(self) -> Optional[str]:
        """Get provider user ID from metadata."""
        return self.platform_metadata.get('user_id') or self.platform_metadata.get('email_address')
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata (alias for platform_metadata)."""
        return self.platform_metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding sensitive data."""
        data = super().to_dict()
        
        # Remove encrypted fields from output
        data.pop('access_token_encrypted', None)
        data.pop('refresh_token_encrypted', None)
        data.pop('oauth_state', None)
        data.pop('oauth_code_verifier', None)
        
        # Add computed fields
        data['has_valid_token'] = not self.is_token_expired()
        data['token_expires_soon'] = self.is_token_expiring_soon()
        data['can_retry'] = self.can_retry_sync()
        
        return data
    
    def __repr__(self) -> str:
        """String representation of the integration."""
        return f"<Integration(id={self.id}, platform={self.platform}, status={self.status})>"


class OAuthState(BaseModel):
    """Temporary storage for OAuth flow state parameters."""
    
    __tablename__ = "oauth_states"
    
    # OAuth flow parameters
    state = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(50), nullable=False)
    redirect_uri = Column(Text, nullable=False)
    code_verifier = Column(String(255))  # For PKCE
    scopes = Column(ARRAY(Text))
    
    # Expiry and cleanup
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User")
    
    def __init__(self, **kwargs):
        """Initialize with default expiry."""
        if 'expires_at' not in kwargs:
            from datetime import timedelta
            kwargs['expires_at'] = datetime.utcnow() + timedelta(minutes=10)  # 10 minute expiry
        if 'used' not in kwargs:
            kwargs['used'] = False
        super().__init__(**kwargs)
    
    def is_expired(self) -> bool:
        """Check if this state has expired."""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if this state is valid (not used and not expired)."""
        return not self.used and not self.is_expired()
    
    def mark_used(self) -> None:
        """Mark this state as used."""
        self.used = True
        self.updated_at = datetime.utcnow()
    
    def __repr__(self) -> str:
        """String representation of the OAuth state."""
        return f"<OAuthState(state={self.state}, platform={self.platform}, used={self.used})>" 