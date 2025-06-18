"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from config import settings
from lib.database import init_db
from lib.logger import setup_logging
from lib.middleware import setup_middleware
from lib.llm_client import initialize_openai_client, OpenAIModel, set_token_usage_service
from services.token_usage_service import TokenUsageService
from api.routes import health, auth, contacts, integration_status, contact_scoring, token_usage
from api.routes import gmail_integration, calendar_contacts, email_contacts, contact_deduplication, interaction_timeline, jobs, ai_assistant, integration_success, conversation_threads


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    await init_db()
    
    # Initialize OpenAI client
    try:
        # Map string model name to enum
        model_mapping = {
            "gpt-4-turbo-preview": OpenAIModel.GPT_4_TURBO,
            "gpt-4": OpenAIModel.GPT_4,
            "gpt-3.5-turbo": OpenAIModel.GPT_3_5_TURBO,
            "gpt-3.5-turbo-16k": OpenAIModel.GPT_3_5_TURBO_16K,
        }
        default_model = model_mapping.get(settings.OPENAI_DEFAULT_MODEL, OpenAIModel.GPT_3_5_TURBO)
        
        initialize_openai_client(
            api_key=settings.OPENAI_API_KEY,
            default_model=default_model,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT,
            rate_limit_rpm=settings.OPENAI_RATE_LIMIT_RPM
        )
        
        # Initialize token usage service and connect to OpenAI client
        from lib.database import get_db
        db = next(get_db())
        token_service = TokenUsageService(db)
        set_token_usage_service(token_service)
        
    except Exception as e:
        # Log error but don't crash the app - AI features will be disabled
        import logging
        logging.error(f"Failed to initialize OpenAI client: {e}")
    
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-native Relationship Management System",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Setup middleware (authentication, CORS, logging, rate limiting)
setup_middleware(app)

# Include routers - organized by functionality
# Core API routes
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(contacts.router, prefix=f"{settings.API_V1_STR}/contacts", tags=["contacts"])
app.include_router(ai_assistant.router, prefix=f"{settings.API_V1_STR}/ai", tags=["ai"])
app.include_router(token_usage.router, prefix=f"{settings.API_V1_STR}/token-usage", tags=["token-usage"])

# Integration routes
app.include_router(integration_status.router, prefix=f"{settings.API_V1_STR}")
app.include_router(gmail_integration.router, prefix=f"{settings.API_V1_STR}/integrations/gmail")
app.include_router(integration_success.router)

# Contact management routes
app.include_router(contact_scoring.router, prefix="/api/v1")
app.include_router(calendar_contacts.router, prefix="/api/v1")
app.include_router(email_contacts.router, prefix="/api/v1")
app.include_router(contact_deduplication.router, prefix="/api/v1")
app.include_router(interaction_timeline.router, prefix="/api/v1")

# Conversation threading routes
app.include_router(conversation_threads.router, prefix="/api/v1")

# Background job routes
app.include_router(jobs.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": f"Welcome to {settings.APP_NAME} API"}


@app.get("/auth/google/callback")
async def google_oauth_redirect(code: str = None, state: str = None, error: str = None):
    """Redirect OAuth callback to the proper API endpoint."""
    # Build the redirect URL with all query parameters
    redirect_url = f"/api/v1/auth/google/callback"
    params = []
    if code:
        params.append(f"code={code}")
    if state:
        params.append(f"state={state}")
    if error:
        params.append(f"error={error}")
    
    if params:
        redirect_url += "?" + "&".join(params)
    
    return RedirectResponse(url=redirect_url, status_code=302) 