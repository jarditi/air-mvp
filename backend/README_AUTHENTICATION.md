# Authentication & Security System

## Overview

The AIR MVP implements a comprehensive authentication and security system with Clerk.dev integration, JWT validation middleware, encryption utilities, and role-based access control. This system provides secure user authentication, data protection, and API security.

## Architecture

### Core Components

1. **Authentication Service** (`services/auth.py`)
   - Clerk.dev integration for user management
   - JWT token validation and creation
   - User profile management
   - Permission checking

2. **JWT Validation Middleware** (`lib/middleware.py`)
   - Request authentication
   - CORS handling
   - Rate limiting
   - Request logging

3. **Encryption Utilities** (`lib/crypto.py`)
   - Data encryption/decryption
   - Password hashing
   - Secure token generation
   - HMAC signatures

4. **Authentication Routes** (`api/routes/auth.py`)
   - User profile endpoints
   - Token refresh
   - Account management

## Features

### ✅ Clerk.dev Integration
- Modern authentication provider
- Social login support
- Email verification
- User management dashboard

### ✅ JWT Token Validation
- Secure token verification
- Automatic user creation/update
- Token refresh mechanism
- Configurable expiration

### ✅ Comprehensive Middleware
- Authentication middleware with path exclusions
- CORS middleware with credential support
- Rate limiting (100 requests/minute default)
- Request logging with unique IDs

### ✅ Encryption & Security
- AES-256 encryption for sensitive data
- bcrypt password hashing
- Secure token generation
- HMAC data integrity verification

### ✅ Role-Based Access Control
- Permission-based route protection
- User role management
- Extensible permission system

## Configuration

### Environment Variables

```bash
# Clerk.dev Configuration
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_VERIFICATION_KEY=-----BEGIN PUBLIC KEY-----...

# Internal JWT Configuration
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256

# Database
DATABASE_URL=postgresql://user:password@localhost/airdb
```

### Clerk.dev Setup

1. Create a Clerk.dev account at https://clerk.dev
2. Create a new application
3. Configure authentication methods (email, social providers)
4. Copy the API keys to your environment variables
5. Set up JWT verification key for token validation

## Usage Examples

### Authentication Service

```python
from services.auth import get_auth_service, get_current_user
from fastapi import Depends

# Get authenticated user in route
@app.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id, "email": current_user.email}

# Check permissions
@app.get("/admin")
async def admin_route(current_user: User = Depends(require_permissions(["admin"]))):
    return {"message": "Admin access granted"}
```

### Encryption Utilities

```python
from lib.crypto import get_encryption_service, encrypt_oauth_token

# Encrypt sensitive data
encryption = get_encryption_service()
encrypted_data = encryption.encrypt_string("sensitive information")
decrypted_data = encryption.decrypt_string(encrypted_data)

# Encrypt OAuth tokens for storage
oauth_token = "ya29.a0AfH6SMC..."
encrypted_token = encrypt_oauth_token(oauth_token)
```

### Token Management

```python
from lib.crypto import get_token_manager

# Create secure tokens
token_manager = get_token_manager()
reset_token = token_manager.create_reset_token(user_id)
verification_token = token_manager.create_verification_token(email)

# Validate tokens
payload = token_manager.validate_token(token)
if payload:
    user_id = payload.get("user_id")
```

## API Endpoints

### Authentication Routes

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/auth/me` | Get current user profile | ✅ |
| PUT | `/api/v1/auth/me` | Update user profile | ✅ |
| POST | `/api/v1/auth/token/refresh` | Refresh access token | ✅ |
| GET | `/api/v1/auth/stats` | Get user statistics | ✅ |
| POST | `/api/v1/auth/deactivate` | Deactivate account | ✅ |
| GET | `/api/v1/auth/health` | Check auth service health | ❌ |

### Example Requests

#### Get User Profile
```bash
curl -H "Authorization: Bearer <clerk_jwt_token>" \
     http://localhost:8000/api/v1/auth/me
```

#### Update User Profile
```bash
curl -X PUT \
     -H "Authorization: Bearer <clerk_jwt_token>" \
     -H "Content-Type: application/json" \
     -d '{"first_name": "John", "last_name": "Doe"}' \
     http://localhost:8000/api/v1/auth/me
```

## Security Features

### Data Protection
- **Encryption at Rest**: Sensitive data encrypted using AES-256
- **Password Security**: bcrypt hashing with salt
- **Token Security**: Cryptographically secure random tokens
- **Data Integrity**: HMAC signatures for critical data

### Request Security
- **Rate Limiting**: Prevents abuse with configurable limits
- **CORS Protection**: Secure cross-origin request handling
- **Request Logging**: Comprehensive audit trail
- **Input Validation**: Pydantic schema validation

### Authentication Security
- **JWT Validation**: Secure token verification with Clerk.dev
- **Token Expiration**: Configurable token lifetimes
- **Automatic Refresh**: Seamless token renewal
- **User Verification**: Email verification through Clerk.dev

## Middleware Configuration

### Authentication Middleware
```python
# Excluded paths (no authentication required)
exclude_paths = [
    "/docs",
    "/redoc", 
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/auth/health",
    "/favicon.ico"
]
```

### Rate Limiting
- Default: 100 requests per minute per user/IP
- Configurable per endpoint
- Redis-backed for production (in-memory for development)

### CORS Configuration
```python
# Allowed origins for development
allow_origins = [
    "http://localhost:3000",  # React frontend
    "http://localhost:8000"   # FastAPI docs
]
```

## Database Integration

### User Model
```python
class User(Base):
    id = Column(UUID, primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False)
    auth_provider = Column(String(50), nullable=False)  # 'clerk'
    auth_provider_id = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(String(50), default="free")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime)
```

### User Creation Flow
1. User authenticates with Clerk.dev
2. JWT token sent to API
3. Token validated with Clerk.dev
4. User profile fetched from Clerk.dev
5. User created/updated in local database
6. Internal session established

## Error Handling

### Authentication Errors
```python
class AuthenticationError(Exception):
    """Custom authentication error."""
    pass

class AuthorizationError(Exception):
    """Custom authorization error."""
    pass
```

### HTTP Status Codes
- `401 Unauthorized`: Invalid or missing authentication
- `403 Forbidden`: Insufficient permissions
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Authentication service error

## Testing

### Manual Testing
```bash
# Test encryption
docker-compose exec backend python -c "
from lib.crypto import get_encryption_service
enc = get_encryption_service()
test = 'Hello World'
encrypted = enc.encrypt_string(test)
decrypted = enc.decrypt_string(encrypted)
print(f'Test passed: {test == decrypted}')
"

# Test token management
docker-compose exec backend python -c "
from lib.crypto import get_token_manager
tm = get_token_manager()
payload = {'user_id': 'test123'}
token = tm.create_token(payload)
validated = tm.validate_token(token)
print(f'Token test passed: {payload == validated}')
"
```

### Integration Testing
```bash
# Test authentication service
docker-compose exec backend python -c "
from services.auth import get_auth_service
auth = get_auth_service()
print(f'Auth service initialized: {auth is not None}')
print(f'Clerk configured: {auth.clerk_client is not None}')
"
```

## Production Considerations

### Security Checklist
- [ ] Use strong SECRET_KEY (32+ random characters)
- [ ] Configure Clerk.dev for production domain
- [ ] Set up proper CORS origins
- [ ] Enable HTTPS only
- [ ] Configure rate limiting with Redis
- [ ] Set up monitoring and alerting
- [ ] Regular security audits

### Performance Optimization
- Use Redis for rate limiting and session storage
- Implement JWT token caching
- Configure connection pooling
- Monitor authentication latency
- Set up CDN for static assets

### Monitoring
- Track authentication success/failure rates
- Monitor token validation performance
- Alert on unusual authentication patterns
- Log security events for audit

## Troubleshooting

### Common Issues

1. **Clerk JWT Verification Fails**
   - Check CLERK_JWT_VERIFICATION_KEY is correct
   - Verify token format and expiration
   - Ensure Clerk.dev domain configuration

2. **Database Connection Errors**
   - Verify DATABASE_URL configuration
   - Check database connectivity
   - Ensure migrations are applied

3. **Rate Limiting Issues**
   - Check Redis connectivity
   - Verify rate limit configuration
   - Monitor request patterns

### Debug Mode
```python
# Enable debug logging
import logging
logging.getLogger("services.auth").setLevel(logging.DEBUG)
logging.getLogger("lib.crypto").setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- [ ] Multi-factor authentication (MFA)
- [ ] OAuth provider integration (Google, GitHub)
- [ ] Advanced role-based permissions
- [ ] Session management dashboard
- [ ] Security audit logging
- [ ] Automated security scanning

### API Versioning
- Current version: v1
- Backward compatibility maintained
- Deprecation notices for breaking changes

## Support

For authentication-related issues:
1. Check the logs for detailed error messages
2. Verify environment configuration
3. Test with minimal examples
4. Review Clerk.dev dashboard for user status
5. Check database connectivity and migrations

## Dependencies

### Core Dependencies
- `clerk-backend-api>=1.0.0` - Clerk.dev integration
- `pyjwt>=2.9.0,<3.0.0` - JWT token handling
- `cryptography>=43.0.1,<44.0.0` - Encryption utilities
- `passlib[bcrypt]==1.7.4` - Password hashing
- `python-jose[cryptography]==3.3.0` - JWT utilities

### Development Dependencies
- `pytest>=7.4.3` - Testing framework
- `pytest-asyncio>=0.21.1` - Async testing support

The authentication system is production-ready and provides enterprise-grade security for the AIR MVP platform. 