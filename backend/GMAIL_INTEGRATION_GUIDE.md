# Gmail Integration Guide for AIR MVP

## Overview

The Gmail integration provides comprehensive email synchronization, OAuth authentication, and email management capabilities for the AIR MVP application. This implementation includes:

- **Google Cloud Project Setup**: Complete configuration management
- **OAuth 2.0 Flow**: Secure authentication with Google
- **Email Synchronization**: Fetch, parse, and sync Gmail messages
- **Incremental Sync**: Efficient updates with pagination
- **Health Monitoring**: Integration status tracking and alerts
- **API Endpoints**: RESTful API for frontend integration

## Architecture

### Components

1. **Google Cloud Configuration** (`lib/google_cloud_config.py`)
   - Manages Google Cloud project settings
   - Handles OAuth client configuration
   - Provides setup instructions and validation

2. **Gmail Client** (`lib/gmail_client.py`)
   - Core Gmail API integration
   - Email message parsing and processing
   - OAuth token management and refresh

3. **Gmail Integration Service** (`services/gmail_integration_service.py`)
   - High-level business logic
   - OAuth flow orchestration
   - Sync management and scheduling

4. **API Routes** (`api/routes/gmail_integration.py`)
   - RESTful endpoints for frontend
   - OAuth callback handling
   - Integration management

## Setup Instructions

### 1. Google Cloud Project Setup

#### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project"
3. Enter project name and note the Project ID
4. Enable billing if required

#### Step 2: Enable Required APIs
1. Go to [APIs & Services > Library](https://console.cloud.google.com/apis/library)
2. Enable the following APIs:
   - Gmail API
   - Google Calendar API (for future use)
   - People API (for contacts)

#### Step 3: Create OAuth 2.0 Credentials
1. Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" > "OAuth client ID"
3. Choose "Web application"
4. Add authorized redirect URIs:
   - `http://localhost:8000/auth/google/callback` (development)
   - `https://yourdomain.com/auth/google/callback` (production)
5. Download the client configuration

#### Step 4: Configure OAuth Consent Screen
1. Go to [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Choose "External" user type for testing
3. Fill in application information:
   - App name: "AIR MVP"
   - User support email
   - Developer contact information
4. Add required scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
5. Add test users if needed

### 2. Environment Configuration

Create or update your `.env` file with the following variables:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT_ID=your-google-cloud-project-id
GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Optional: Service Account (for server-to-server operations)
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json

# Gmail API Configuration
GMAIL_MAX_RESULTS=100
GMAIL_SYNC_INTERVAL_MINUTES=15
```

### 3. Verification

Test your configuration:

```bash
# Set environment variables and test
export GOOGLE_CLOUD_PROJECT_ID=your-project-id
export GOOGLE_OAUTH_CLIENT_ID=your-client-id
export GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Test the configuration
python3 -c "from lib.google_cloud_config import GoogleCloudManager; m = GoogleCloudManager(); print('✅ Configuration valid')"
```

## API Endpoints

### Setup and Configuration

#### Get Setup Instructions
```http
GET /api/v1/integrations/gmail/setup-instructions
```

Returns detailed setup instructions and current configuration status.

#### Get OAuth Configuration
```http
GET /api/v1/integrations/gmail/config
```

Returns public OAuth configuration for frontend use.

### OAuth Flow

#### Initiate OAuth Flow
```http
POST /api/v1/integrations/gmail/oauth/initiate
Content-Type: application/json

{
  "redirect_uri": "http://localhost:8000/auth/google/callback"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
    "state": "gmail_oauth_user123_1234567890",
    "user_id": "user123",
    "provider": "gmail",
    "scopes": ["https://www.googleapis.com/auth/gmail.readonly", ...],
    "initiated_at": "2024-01-01T12:00:00Z"
  }
}
```

#### Handle OAuth Callback
```http
POST /api/v1/integrations/gmail/oauth/callback
Content-Type: application/json

{
  "code": "authorization_code_from_google",
  "state": "gmail_oauth_user123_1234567890"
}
```

Response:
```json
{
  "id": "integration-uuid",
  "user_id": "user123",
  "provider": "gmail",
  "provider_user_id": "user@example.com",
  "status": "active",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly", ...],
  "metadata": {
    "email_address": "user@example.com",
    "messages_total": 1500,
    "threads_total": 800
  },
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### Integration Management

#### Get User Integrations
```http
GET /api/v1/integrations/gmail/integrations
```

Response:
```json
{
  "success": true,
  "data": [
    {
      "integration_id": "integration-uuid",
      "email_address": "user@example.com",
      "status": "active",
      "health_status": "healthy",
      "last_sync_at": "2024-01-01T11:45:00Z",
      "messages_synced": 150,
      "created_at": "2024-01-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

#### Get Integration Status
```http
GET /api/v1/integrations/gmail/integrations/{integration_id}/status
```

Response:
```json
{
  "integration_id": "integration-uuid",
  "email_address": "user@example.com",
  "status": "active",
  "health_status": "healthy",
  "last_sync_at": "2024-01-01T11:45:00Z",
  "messages_synced": 150,
  "total_syncs": 12,
  "recent_events": [
    {
      "event_type": "sync_completed",
      "severity": "info",
      "message": "Gmail sync completed: 10 messages",
      "created_at": "2024-01-01T11:45:00Z"
    }
  ],
  "active_alerts": [],
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T11:45:00Z"
}
```

### Email Synchronization

#### Trigger Manual Sync
```http
POST /api/v1/integrations/gmail/integrations/{integration_id}/sync
Content-Type: application/json

{
  "force_full_sync": false,
  "max_results": 100
}
```

Response:
```json
{
  "success": true,
  "data": {
    "messages_fetched": 25,
    "messages_processed": 25,
    "errors": [],
    "sync_timestamp": "2024-01-01T12:00:00Z",
    "next_page_token": null
  }
}
```

#### Check Integration Health
```http
GET /api/v1/integrations/gmail/integrations/{integration_id}/health
```

Response:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "email_address": "user@example.com",
    "messages_total": 1500,
    "threads_total": 800,
    "last_check": "2024-01-01T12:00:00Z"
  }
}
```

#### Disconnect Integration
```http
DELETE /api/v1/integrations/gmail/integrations/{integration_id}
```

Response:
```json
{
  "success": true,
  "message": "Gmail integration disconnected successfully"
}
```

## Usage Examples

### Frontend Integration

#### 1. Initiate OAuth Flow
```javascript
// Initiate OAuth flow
const response = await fetch('/api/v1/integrations/gmail/oauth/initiate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${userToken}`
  },
  body: JSON.stringify({
    redirect_uri: window.location.origin + '/auth/google/callback'
  })
});

const { data } = await response.json();

// Redirect user to Google OAuth
window.location.href = data.authorization_url;
```

#### 2. Handle OAuth Callback
```javascript
// In your callback route handler
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

const response = await fetch('/api/v1/integrations/gmail/oauth/callback', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${userToken}`
  },
  body: JSON.stringify({ code, state })
});

const integration = await response.json();
console.log('Gmail integration created:', integration);
```

#### 3. Monitor Integration Status
```javascript
// Get integration status
const response = await fetch(`/api/v1/integrations/gmail/integrations/${integrationId}/status`, {
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});

const status = await response.json();
console.log('Integration status:', status);
```

### Backend Usage

#### 1. Direct Service Usage
```python
from services.gmail_integration_service import GmailIntegrationService
from lib.database import get_db

# Initialize service
db = get_db()
service = GmailIntegrationService(db)

# Initiate OAuth flow
oauth_data = await service.initiate_oauth_flow("user123")
print(f"Authorization URL: {oauth_data['authorization_url']}")

# Handle callback
integration = await service.handle_oauth_callback("user123", "auth_code", "state")
print(f"Integration created: {integration.id}")

# Sync messages
sync_result = await service.sync_messages(integration)
print(f"Synced {sync_result.messages_processed} messages")
```

#### 2. Background Sync (Future Enhancement)
```python
# This would be implemented with Celery workers
from workers.tasks import sync_gmail_integration

# Schedule background sync
sync_gmail_integration.delay(integration_id="integration-uuid")
```

## Email Message Structure

The Gmail client parses email messages into a structured format:

```python
@dataclass
class EmailMessage:
    id: str                    # Gmail message ID
    thread_id: str            # Gmail thread ID
    subject: str              # Email subject
    sender: str               # Full sender string
    sender_email: str         # Extracted sender email
    recipients: List[str]     # List of recipient emails
    cc: List[str]            # CC recipient emails
    bcc: List[str]           # BCC recipient emails
    date: datetime           # Email date
    body_text: str           # Plain text body
    body_html: str           # HTML body
    labels: List[str]        # Gmail labels
    attachments: List[Dict]  # Attachment metadata
    is_read: bool           # Read status
    is_important: bool      # Important flag
    snippet: str            # Email snippet
    raw_headers: Dict       # Raw email headers
```

## Error Handling

The integration includes comprehensive error handling:

### Common Error Scenarios

1. **Invalid OAuth Configuration**
   ```json
   {
     "error": "Invalid OAuth configuration",
     "details": "Missing GOOGLE_OAUTH_CLIENT_ID"
   }
   ```

2. **Expired Access Token**
   ```json
   {
     "error": "Token expired",
     "details": "Access token has expired and refresh failed"
   }
   ```

3. **API Rate Limiting**
   ```json
   {
     "error": "Rate limit exceeded",
     "details": "Gmail API rate limit exceeded, retry after 60 seconds"
   }
   ```

4. **Insufficient Permissions**
   ```json
   {
     "error": "Insufficient permissions",
     "details": "Required Gmail scopes not granted"
   }
   ```

### Error Recovery

The integration includes automatic error recovery:

- **Token Refresh**: Automatically refreshes expired access tokens
- **Retry Logic**: Retries failed API calls with exponential backoff
- **Health Monitoring**: Tracks integration health and generates alerts
- **Graceful Degradation**: Continues operation with reduced functionality

## Security Considerations

### Data Protection
- All OAuth tokens are encrypted in the database
- Sensitive configuration is stored in environment variables
- API endpoints require authentication
- Rate limiting prevents abuse

### Privacy Compliance
- Users can disconnect integrations at any time
- Email data is processed according to privacy policies
- Audit logging tracks all integration activities
- Data export and deletion capabilities

### Best Practices
- Never commit OAuth secrets to version control
- Use HTTPS in production
- Regularly rotate OAuth client secrets
- Monitor API usage and quotas
- Implement proper access controls

## Monitoring and Observability

### Health Checks
The integration provides comprehensive health monitoring:

```python
# Health check includes:
{
  "status": "healthy|unhealthy",
  "email_address": "user@example.com",
  "messages_total": 1500,
  "api_connectivity": "ok",
  "token_validity": "valid",
  "last_sync": "2024-01-01T12:00:00Z",
  "error_rate": 0.02
}
```

### Event Logging
All integration activities are logged:

- OAuth flow events
- Sync operations
- API errors
- Token refresh events
- Health check results

### Alerts
Automatic alerts for:

- Failed OAuth flows
- Sync failures
- Token expiration
- API rate limiting
- Health check failures

## Testing

### Unit Tests
```bash
# Run Gmail integration tests
python3 test_gmail_integration.py
```

### Integration Tests
```bash
# Test with real Google credentials (optional)
export GOOGLE_CLOUD_PROJECT_ID=your-project
export GOOGLE_OAUTH_CLIENT_ID=your-client-id
export GOOGLE_OAUTH_CLIENT_SECRET=your-secret

python3 test_gmail_real.py
```

### API Tests
```bash
# Test API endpoints
curl -X GET "http://localhost:8000/api/v1/integrations/gmail/setup-instructions"
```

## Troubleshooting

### Common Issues

1. **Configuration Errors**
   - Verify environment variables are set correctly
   - Check Google Cloud project settings
   - Ensure APIs are enabled

2. **OAuth Failures**
   - Verify redirect URIs match exactly
   - Check OAuth consent screen configuration
   - Ensure user has granted required permissions

3. **Sync Issues**
   - Check API quotas and rate limits
   - Verify token validity
   - Review error logs for specific issues

4. **Performance Issues**
   - Monitor API usage patterns
   - Optimize sync frequency
   - Implement pagination for large mailboxes

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('gmail_integration').setLevel(logging.DEBUG)
```

### Support Resources

- [Google Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google Cloud Console](https://console.cloud.google.com/)

## Future Enhancements

### Planned Features
1. **Real-time Notifications**: Gmail push notifications
2. **Advanced Filtering**: Custom email filters and rules
3. **Bulk Operations**: Batch email processing
4. **Analytics**: Email interaction analytics
5. **AI Integration**: Smart email categorization

### Performance Optimizations
1. **Caching**: Redis caching for frequently accessed data
2. **Background Processing**: Celery workers for async operations
3. **Database Optimization**: Indexed queries and connection pooling
4. **API Optimization**: Request batching and compression

This completes the Gmail integration implementation for the AIR MVP. The system is production-ready with comprehensive error handling, monitoring, and security features. 