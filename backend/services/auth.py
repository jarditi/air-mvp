"""Authentication service with Clerk.dev integration."""

import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from clerk_backend_api import Clerk
from clerk_backend_api.models import User as ClerkUser

from config import get_settings
from models.orm.user import User
from lib.database import get_db

logger = logging.getLogger(__name__)

# Security scheme for FastAPI
security = HTTPBearer()


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


class AuthorizationError(Exception):
    """Custom authorization error."""
    pass


class AuthService:
    """Authentication service with Clerk.dev integration."""
    
    def __init__(self):
        """Initialize the authentication service."""
        self.settings = get_settings()
        self.clerk_client = None
        
        if self.settings.CLERK_SECRET_KEY:
            self.clerk_client = Clerk(bearer_auth=self.settings.CLERK_SECRET_KEY)
        else:
            logger.warning("Clerk secret key not configured")
    
    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token from Clerk."""
        try:
            if not self.settings.CLERK_JWT_VERIFICATION_KEY:
                raise AuthenticationError("JWT verification key not configured")
            
            # Decode the JWT token
            payload = jwt.decode(
                token,
                self.settings.CLERK_JWT_VERIFICATION_KEY,
                algorithms=["RS256"],
                audience=self.settings.CLERK_PUBLISHABLE_KEY
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise AuthenticationError("Token verification failed")
    
    def verify_clerk_token_via_api(self, token: str) -> Dict[str, Any]:
        """Verify a Clerk token using the Clerk API."""
        try:
            if not self.clerk_client:
                raise AuthenticationError("Clerk client not configured")
            
            # Use Clerk API to verify the session token
            # First, decode the token without verification to get the session ID
            import base64
            import json
            
            # Split the JWT token
            parts = token.split('.')
            if len(parts) != 3:
                raise AuthenticationError("Invalid token format")
            
            # Decode the payload (second part)
            payload_encoded = parts[1]
            # Add padding if needed
            payload_encoded += '=' * (4 - len(payload_encoded) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_encoded)
            payload = json.loads(payload_bytes)
            
            # Extract session ID and user ID
            session_id = payload.get('sid')
            user_id = payload.get('sub')
            
            if not session_id or not user_id:
                raise AuthenticationError("Invalid token payload")
            
            # Verify the session is active using Clerk API
            try:
                session = self.clerk_client.sessions.get(session_id=session_id)
                if session.status != 'active':
                    raise AuthenticationError("Session is not active")
                
                # Return the payload if session is valid
                return payload
                
            except Exception as e:
                logger.error(f"Clerk session verification failed: {e}")
                raise AuthenticationError("Session verification failed")
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Clerk token verification error: {e}")
            raise AuthenticationError("Token verification failed")

    def get_clerk_user(self, user_id: str) -> Optional[ClerkUser]:
        """Get user information from Clerk."""
        try:
            if not self.clerk_client:
                raise AuthenticationError("Clerk client not configured")
            
            user = self.clerk_client.users.get(user_id=user_id)
            return user
            
        except Exception as e:
            logger.error(f"Error fetching Clerk user {user_id}: {e}")
            return None
    
    def get_or_create_user(self, clerk_user_id: str, db: Session) -> User:
        """Get or create a user in our database based on Clerk user ID."""
        try:
            # First, try to find existing user
            user = db.query(User).filter(
                User.auth_provider == "clerk",
                User.auth_provider_id == clerk_user_id
            ).first()
            
            if user:
                # Update last login
                user.last_login_at = datetime.utcnow()
                db.commit()
                return user
            
            # Get user details from Clerk
            clerk_user = self.get_clerk_user(clerk_user_id)
            if not clerk_user:
                raise AuthenticationError(f"Clerk user {clerk_user_id} not found")
            
            # Extract email from Clerk user
            email = None
            if clerk_user.email_addresses:
                primary_email = next(
                    (email for email in clerk_user.email_addresses if email.id == clerk_user.primary_email_address_id),
                    clerk_user.email_addresses[0] if clerk_user.email_addresses else None
                )
                if primary_email:
                    email = primary_email.email_address
            
            if not email:
                raise AuthenticationError("No email address found for user")
            
            # Create new user
            full_name = None
            if clerk_user.first_name or clerk_user.last_name:
                name_parts = []
                if clerk_user.first_name:
                    name_parts.append(clerk_user.first_name)
                if clerk_user.last_name:
                    name_parts.append(clerk_user.last_name)
                full_name = " ".join(name_parts)
            
            user = User(
                email=email,
                auth_provider="clerk",
                auth_provider_id=clerk_user_id,
                full_name=full_name,
                is_verified=True,  # Clerk handles verification
                last_login_at=datetime.utcnow()
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            logger.info(f"Created new user {user.id} from Clerk user {clerk_user_id}")
            return user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating/updating user: {e}")
            raise AuthenticationError(f"User creation failed: {str(e)}")
    
    def authenticate_request(self, credentials: HTTPAuthorizationCredentials, db: Session) -> User:
        """Authenticate a request using JWT token."""
        try:
            # Try to verify as internal token first
            try:
                payload = self.verify_internal_token(credentials.credentials)
                
                # Extract user ID from internal token
                user_id = payload.get("sub")
                if not user_id:
                    raise AuthenticationError("No user ID in token")
                
                # Get user from database
                user = self.get_user_by_id(user_id, db)
                if not user:
                    raise AuthenticationError("User not found")
                
                # Update last login
                user.last_login_at = datetime.utcnow()
                db.commit()
                
                return user
                
            except AuthenticationError:
                # If internal token verification fails, try Clerk token
                if self.clerk_client:
                    # Try JWT verification first if key is available
                    if self.settings.CLERK_JWT_VERIFICATION_KEY:
                        payload = self.verify_jwt_token(credentials.credentials)
                    else:
                        # Fall back to API verification
                        payload = self.verify_clerk_token_via_api(credentials.credentials)
                    
                    # Extract user ID from Clerk token
                    clerk_user_id = payload.get("sub")
                    if not clerk_user_id:
                        raise AuthenticationError("No user ID in token")
                    
                    # Get or create user in our database
                    user = self.get_or_create_user(clerk_user_id, db)
                    
                    return user
                else:
                    # No Clerk configuration, re-raise the internal token error
                    raise
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError("Authentication failed")
    
    def check_user_permissions(self, user: User, required_permissions: list = None) -> bool:
        """Check if user has required permissions."""
        try:
            # Basic permission checks
            if not user.is_active:
                return False
            
            # For now, all active users have basic permissions
            # This can be extended for role-based access control
            if required_permissions is None:
                return True
            
            # Future: implement role-based permissions
            # For now, return True for basic permissions
            return True
            
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False
    
    def create_internal_token(self, user: User) -> str:
        """Create an internal JWT token for API access."""
        try:
            # Create payload
            payload = {
                "sub": str(user.id),
                "email": user.email,
                "auth_provider": user.auth_provider,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            }
            
            # Create token
            token = jwt.encode(
                payload,
                self.settings.SECRET_KEY,
                algorithm=self.settings.ALGORITHM
            )
            
            return token
            
        except Exception as e:
            logger.error(f"Token creation error: {e}")
            raise AuthenticationError("Token creation failed")
    
    def verify_internal_token(self, token: str) -> Dict[str, Any]:
        """Verify an internal JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.settings.ALGORITHM]
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
    
    def get_user_by_id(self, user_id: Union[str, UUID], db: Session) -> Optional[User]:
        """Get user by ID from database."""
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            
            user = db.query(User).filter(User.id == user_id).first()
            return user
            
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            return None
    
    def update_user_profile(self, user: User, profile_data: Dict[str, Any], db: Session) -> User:
        """Update user profile information."""
        try:
            # Update allowed fields
            allowed_fields = [
                'full_name', 'timezone', 'avatar_url', 'subscription_tier', 
                'privacy_settings'
            ]
            
            for field, value in profile_data.items():
                if field in allowed_fields and hasattr(user, field):
                    setattr(user, field, value)
            
            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)
            
            return user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user profile: {e}")
            raise AuthenticationError("Profile update failed")
    
    def deactivate_user(self, user: User, db: Session) -> bool:
        """Deactivate a user account."""
        try:
            user.is_active = False
            user.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Deactivated user {user.id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deactivating user: {e}")
            return False
    
    def get_user_stats(self, user: User, db: Session) -> Dict[str, Any]:
        """Get user statistics and metadata."""
        try:
            # Import here to avoid circular imports
            from models.orm.contact import Contact
            from models.orm.interaction import Interaction
            
            # Get basic stats
            contact_count = db.query(Contact).filter(Contact.user_id == user.id).count()
            interaction_count = db.query(Interaction).filter(Interaction.user_id == user.id).count()
            
            stats = {
                "user_id": str(user.id),
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "subscription_tier": user.subscription_tier,
                "is_verified": user.is_verified,
                "contact_count": contact_count,
                "interaction_count": interaction_count,
                "auth_provider": user.auth_provider
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}


# Global instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the global authentication service instance."""
    global _auth_service
    
    if _auth_service is None:
        _auth_service = AuthService()
    
    return _auth_service


# Dependency functions for FastAPI
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Any:
    """FastAPI dependency to get the current authenticated user."""
    try:
        auth_service = get_auth_service()
        user = auth_service.authenticate_request(credentials, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication dependency error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


def get_current_active_user(current_user: Any = Depends(get_current_user)) -> Any:
    """FastAPI dependency to get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_permissions(permissions: list = None):
    """FastAPI dependency factory for permission-based access control."""
    def permission_checker(current_user: Any = Depends(get_current_active_user)) -> Any:
        auth_service = get_auth_service()
        
        if not auth_service.check_user_permissions(current_user, permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return current_user
    
    return permission_checker


# Custom dependency that works correctly
def get_current_user_custom(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> Any:
    """Custom FastAPI dependency to get the current authenticated user."""
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = authorization.split(" ")[1]
        
        # Create credentials manually
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        auth_service = get_auth_service()
        user = auth_service.authenticate_request(credentials, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication dependency error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


def get_current_active_user_custom(current_user: Any = Depends(get_current_user_custom)) -> Any:
    """Custom FastAPI dependency to get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user 