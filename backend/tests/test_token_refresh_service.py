"""Tests for TokenRefreshService."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from services.token_refresh import TokenRefreshService, RefreshResult, TokenRefreshError
from lib.oauth_client import OAuthClient, OAuthProvider, OAuthToken, OAuthError
from models.orm.integration import Integration
from models.orm.user import User


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_oauth_client():
    """Mock OAuth client."""
    return Mock(spec=OAuthClient)


@pytest.fixture
def token_refresh_service(mock_db, mock_oauth_client):
    """TokenRefreshService instance with mocked dependencies."""
    return TokenRefreshService(mock_db, mock_oauth_client)


@pytest.fixture
def sample_integration():
    """Sample integration for testing."""
    integration = Mock(spec=Integration)
    integration.id = uuid4()
    integration.user_id = uuid4()
    integration.platform = "google"
    integration.status = "connected"
    integration.refresh_token = "refresh_token_123"
    integration.error_count = 0
    integration.retry_after = None
    integration.is_token_expiring_soon.return_value = True
    integration.get_provider_enum.return_value = OAuthProvider.GOOGLE
    integration.store_oauth_token = Mock()
    integration.mark_sync_failed = Mock()
    return integration


@pytest.fixture
def sample_oauth_token():
    """Sample OAuth token for testing."""
    return OAuthToken(
        access_token="new_access_token",
        refresh_token="new_refresh_token",
        token_type="Bearer",
        expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        scope="email profile"
    )


class TestTokenRefreshService:
    """Test cases for TokenRefreshService."""
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, token_refresh_service, sample_integration, sample_oauth_token):
        """Test successful token refresh."""
        # Setup
        token_refresh_service.oauth_client.refresh_token = AsyncMock(return_value=sample_oauth_token)
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.SUCCESS
        assert error is None
        sample_integration.store_oauth_token.assert_called_once_with(sample_oauth_token)
        token_refresh_service.db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_token_not_expiring(self, token_refresh_service, sample_integration):
        """Test skipping refresh when token is not expiring."""
        # Setup
        sample_integration.is_token_expiring_soon.return_value = False
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.SUCCESS
        assert error is None
        token_refresh_service.oauth_client.refresh_token.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_refresh_token_no_refresh_token(self, token_refresh_service, sample_integration):
        """Test handling when no refresh token is available."""
        # Setup
        sample_integration.refresh_token = None
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.NO_REFRESH_TOKEN
        assert "No refresh token available" in error
        assert sample_integration.status == "expired"
    
    @pytest.mark.asyncio
    async def test_refresh_token_rate_limited(self, token_refresh_service, sample_integration):
        """Test handling rate limiting."""
        # Setup
        sample_integration.retry_after = datetime.utcnow() + timedelta(minutes=10)
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.RATE_LIMITED
        assert "Rate limited" in error
    
    @pytest.mark.asyncio
    async def test_refresh_token_oauth_error_invalid_grant(self, token_refresh_service, sample_integration):
        """Test handling OAuth error with invalid grant."""
        # Setup
        token_refresh_service.oauth_client.refresh_token = AsyncMock(
            side_effect=OAuthError("invalid_grant: refresh token expired")
        )
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.REVOKED
        assert "Refresh token expired or revoked" in error
        assert sample_integration.status == "revoked"
        assert sample_integration.refresh_token is None
    
    @pytest.mark.asyncio
    async def test_refresh_token_oauth_error_rate_limit(self, token_refresh_service, sample_integration):
        """Test handling OAuth rate limit error."""
        # Setup
        token_refresh_service.oauth_client.refresh_token = AsyncMock(
            side_effect=OAuthError("rate_limit exceeded")
        )
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.RATE_LIMITED
        assert "rate_limit exceeded" in error
        sample_integration.mark_sync_failed.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_token_unknown_provider(self, token_refresh_service, sample_integration):
        """Test handling unknown provider."""
        # Setup
        sample_integration.get_provider_enum.return_value = None
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.PROVIDER_ERROR
        assert "Unknown provider" in error
    
    @pytest.mark.asyncio
    async def test_refresh_token_unexpected_error(self, token_refresh_service, sample_integration):
        """Test handling unexpected errors."""
        # Setup
        token_refresh_service.oauth_client.refresh_token = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        
        # Execute
        result, error = await token_refresh_service.refresh_token_for_integration(sample_integration)
        
        # Assert
        assert result == RefreshResult.FAILED
        assert "Unexpected error" in error
        sample_integration.mark_sync_failed.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_expiring_tokens_no_tokens(self, token_refresh_service):
        """Test bulk refresh when no tokens are expiring."""
        # Setup
        token_refresh_service.db.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        result = await token_refresh_service.refresh_expiring_tokens()
        
        # Assert
        assert result["total"] == 0
    
    @pytest.mark.asyncio
    async def test_refresh_expiring_tokens_with_integrations(self, token_refresh_service, sample_integration, sample_oauth_token):
        """Test bulk refresh with expiring tokens."""
        # Setup
        integrations = [sample_integration]
        token_refresh_service.db.query.return_value.filter.return_value.all.return_value = integrations
        token_refresh_service.oauth_client.refresh_token = AsyncMock(return_value=sample_oauth_token)
        
        # Execute
        result = await token_refresh_service.refresh_expiring_tokens(buffer_minutes=5, max_concurrent=1)
        
        # Assert
        assert result["total"] == 1
        assert result["success"] == 1
        assert result["failed"] == 0
    
    @pytest.mark.asyncio
    async def test_refresh_user_tokens_no_integrations(self, token_refresh_service):
        """Test user token refresh when user has no integrations."""
        # Setup
        user_id = str(uuid4())
        token_refresh_service.db.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        result = await token_refresh_service.refresh_user_tokens(user_id)
        
        # Assert
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_refresh_user_tokens_with_integrations(self, token_refresh_service, sample_integration, sample_oauth_token):
        """Test user token refresh with integrations."""
        # Setup
        user_id = str(uuid4())
        integrations = [sample_integration]
        token_refresh_service.db.query.return_value.filter.return_value.all.return_value = integrations
        token_refresh_service.oauth_client.refresh_token = AsyncMock(return_value=sample_oauth_token)
        
        # Execute
        result = await token_refresh_service.refresh_user_tokens(user_id)
        
        # Assert
        assert str(sample_integration.id) in result
        assert result[str(sample_integration.id)][0] == RefreshResult.SUCCESS
    
    @pytest.mark.asyncio
    async def test_validate_token_success(self, token_refresh_service, sample_integration):
        """Test successful token validation."""
        # Setup
        oauth_token = Mock()
        sample_integration.get_oauth_token.return_value = oauth_token
        token_refresh_service.oauth_client.get_user_info = AsyncMock(return_value={"id": "123"})
        
        # Execute
        result = await token_refresh_service.validate_token(sample_integration)
        
        # Assert
        assert result is True
        token_refresh_service.oauth_client.get_user_info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_token_failure(self, token_refresh_service, sample_integration):
        """Test token validation failure."""
        # Setup
        oauth_token = Mock()
        sample_integration.get_oauth_token.return_value = oauth_token
        token_refresh_service.oauth_client.get_user_info = AsyncMock(
            side_effect=Exception("Token invalid")
        )
        
        # Execute
        result = await token_refresh_service.validate_token(sample_integration)
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_token_no_provider(self, token_refresh_service, sample_integration):
        """Test token validation with unknown provider."""
        # Setup
        sample_integration.get_provider_enum.return_value = None
        
        # Execute
        result = await token_refresh_service.validate_token(sample_integration)
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_token_no_token(self, token_refresh_service, sample_integration):
        """Test token validation with no token."""
        # Setup
        sample_integration.get_oauth_token.return_value = None
        
        # Execute
        result = await token_refresh_service.validate_token(sample_integration)
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_revoke_integration_tokens_success(self, token_refresh_service, sample_integration):
        """Test successful token revocation."""
        # Setup
        sample_integration.access_token = "access_token_123"
        token_refresh_service.oauth_client.revoke_token = AsyncMock(return_value=True)
        sample_integration.revoke_tokens = Mock()
        
        # Execute
        result = await token_refresh_service.revoke_integration_tokens(sample_integration)
        
        # Assert
        assert result is True
        token_refresh_service.oauth_client.revoke_token.assert_called_once()
        sample_integration.revoke_tokens.assert_called_once()
        token_refresh_service.db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_revoke_integration_tokens_no_token(self, token_refresh_service, sample_integration):
        """Test token revocation with no access token."""
        # Setup
        sample_integration.access_token = None
        sample_integration.revoke_tokens = Mock()
        
        # Execute
        result = await token_refresh_service.revoke_integration_tokens(sample_integration)
        
        # Assert
        assert result is True  # Nothing to revoke is considered success
        token_refresh_service.oauth_client.revoke_token.assert_not_called()
        sample_integration.revoke_tokens.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_revoke_integration_tokens_unknown_provider(self, token_refresh_service, sample_integration):
        """Test token revocation with unknown provider."""
        # Setup
        sample_integration.get_provider_enum.return_value = None
        
        # Execute
        result = await token_refresh_service.revoke_integration_tokens(sample_integration)
        
        # Assert
        assert result is False
    
    def test_can_refresh_now_no_retry_after(self, token_refresh_service, sample_integration):
        """Test can refresh when no retry_after is set."""
        # Setup
        sample_integration.retry_after = None
        
        # Execute
        result = token_refresh_service._can_refresh_now(sample_integration)
        
        # Assert
        assert result is True
    
    def test_can_refresh_now_retry_after_passed(self, token_refresh_service, sample_integration):
        """Test can refresh when retry_after time has passed."""
        # Setup
        sample_integration.retry_after = datetime.utcnow() - timedelta(minutes=1)
        
        # Execute
        result = token_refresh_service._can_refresh_now(sample_integration)
        
        # Assert
        assert result is True
    
    def test_can_refresh_now_retry_after_not_passed(self, token_refresh_service, sample_integration):
        """Test cannot refresh when retry_after time has not passed."""
        # Setup
        sample_integration.retry_after = datetime.utcnow() + timedelta(minutes=1)
        
        # Execute
        result = token_refresh_service._can_refresh_now(sample_integration)
        
        # Assert
        assert result is False
    
    def test_get_retry_delay_no_retry_after(self, token_refresh_service, sample_integration):
        """Test get retry delay when no retry_after is set."""
        # Setup
        sample_integration.retry_after = None
        
        # Execute
        result = token_refresh_service._get_retry_delay(sample_integration)
        
        # Assert
        assert result == 0
    
    def test_get_retry_delay_with_retry_after(self, token_refresh_service, sample_integration):
        """Test get retry delay with retry_after set."""
        # Setup
        sample_integration.retry_after = datetime.utcnow() + timedelta(minutes=5)
        
        # Execute
        result = token_refresh_service._get_retry_delay(sample_integration)
        
        # Assert
        assert result > 0
        assert result <= 300  # 5 minutes in seconds
    
    def test_calculate_retry_delay_exponential_backoff(self, token_refresh_service, sample_integration):
        """Test exponential backoff calculation."""
        # Test different error counts
        test_cases = [
            (0, 60),    # 60 * 2^0 = 60
            (1, 120),   # 60 * 2^1 = 120
            (2, 240),   # 60 * 2^2 = 240
            (3, 480),   # 60 * 2^3 = 480
            (10, 3600), # Max delay is 3600 seconds
        ]
        
        for error_count, expected_delay in test_cases:
            sample_integration.error_count = error_count
            result = token_refresh_service._calculate_retry_delay(sample_integration)
            assert result == expected_delay
    
    def test_get_refresh_statistics(self, token_refresh_service):
        """Test getting refresh statistics."""
        # Setup mock query results
        mock_query = Mock()
        token_refresh_service.db.query.return_value = mock_query
        
        # Mock status counts
        mock_query.filter.return_value.count.side_effect = [5, 2, 1, 0, 3]  # connected, expired, error, revoked, disconnected
        
        # Mock other counts
        mock_query.filter.return_value.count.side_effect = [5, 2, 1, 0, 3, 1, 2, 1]  # Add expiring_soon, error_count, rate_limited
        
        # Execute
        result = token_refresh_service.get_refresh_statistics()
        
        # Assert
        assert "status_counts" in result
        assert "total_integrations" in result
        assert "expiring_within_hour" in result
        assert "with_errors" in result
        assert "rate_limited" in result


class TestTokenRefreshError:
    """Test cases for TokenRefreshError."""
    
    def test_token_refresh_error_creation(self):
        """Test TokenRefreshError creation."""
        error = TokenRefreshError("Test error", RefreshResult.FAILED, retry_after=300)
        
        assert str(error) == "Test error"
        assert error.result == RefreshResult.FAILED
        assert error.retry_after == 300
    
    def test_token_refresh_error_without_retry_after(self):
        """Test TokenRefreshError creation without retry_after."""
        error = TokenRefreshError("Test error", RefreshResult.PROVIDER_ERROR)
        
        assert str(error) == "Test error"
        assert error.result == RefreshResult.PROVIDER_ERROR
        assert error.retry_after is None


if __name__ == "__main__":
    pytest.main([__file__]) 