"""Application configuration management."""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # App
    APP_NAME: str = "AIR MVP"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API
    API_V1_STR: str = "/api/v1"
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # Redis
    REDIS_URL: str = Field(..., env="REDIS_URL")
    
    # Vector Database
    WEAVIATE_URL: str = Field(..., env="WEAVIATE_URL")
    PINECONE_API_KEY: Optional[str] = Field(None, env="PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: Optional[str] = Field(None, env="PINECONE_ENVIRONMENT")
    
    # Authentication
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    # Auth0/Clerk
    AUTH0_DOMAIN: Optional[str] = Field(None, env="AUTH0_DOMAIN")
    AUTH0_CLIENT_ID: Optional[str] = Field(None, env="AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET: Optional[str] = Field(None, env="AUTH0_CLIENT_SECRET")
    
    # Clerk.dev
    CLERK_PUBLISHABLE_KEY: Optional[str] = Field(None, env="CLERK_PUBLISHABLE_KEY")
    CLERK_SECRET_KEY: Optional[str] = Field(None, env="CLERK_SECRET_KEY")
    CLERK_JWT_VERIFICATION_KEY: Optional[str] = Field(None, env="CLERK_JWT_VERIFICATION_KEY")
    
    # OpenAI
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_MODEL: str = "gpt-4"
    
    # LangSmith
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: Optional[str] = Field(None, env="LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT: str = "air-mvp"
    
    # Google APIs
    GOOGLE_CLIENT_ID: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(None, env="GOOGLE_CLIENT_SECRET")
    
    # Google Cloud Configuration (OAuth)
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = Field(None, env="GOOGLE_CLOUD_PROJECT_ID")
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = Field(None, env="GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = Field(None, env="GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_OAUTH_REDIRECT_URI: Optional[str] = Field(None, env="GOOGLE_OAUTH_REDIRECT_URI")
    
    # LinkedIn
    LINKEDIN_CLIENT_ID: Optional[str] = Field(None, env="LINKEDIN_CLIENT_ID")
    LINKEDIN_CLIENT_SECRET: Optional[str] = Field(None, env="LINKEDIN_CLIENT_SECRET")
    
    # Celery
    CELERY_BROKER_URL: str = Field(..., env="REDIS_URL")
    CELERY_RESULT_BACKEND: str = Field(..., env="REDIS_URL")
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings() 