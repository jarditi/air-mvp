"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from config import settings
from lib.database import init_db
from lib.logger import setup_logging
from lib.middleware import setup_middleware
from api.routes import health, auth, contacts, integrations, ai_assistant, integration_status, contact_scoring
from api.routes import gmail_integration, calendar_contacts, email_contacts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    await init_db()
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

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(contacts.router, prefix=f"{settings.API_V1_STR}/contacts", tags=["contacts"])
app.include_router(integrations.router, prefix=f"{settings.API_V1_STR}/integrations", tags=["integrations"])
app.include_router(integration_status.router, prefix=f"{settings.API_V1_STR}", tags=["integration-status"])
app.include_router(gmail_integration.router, prefix=f"{settings.API_V1_STR}/integrations", tags=["gmail-integration"])
app.include_router(contact_scoring.router, prefix=f"{settings.API_V1_STR}", tags=["contact-scoring"])
app.include_router(calendar_contacts.router, prefix=f"{settings.API_V1_STR}", tags=["calendar-contacts"])
app.include_router(email_contacts.router, prefix=f"{settings.API_V1_STR}", tags=["email-contacts"])
app.include_router(ai_assistant.router, prefix=f"{settings.API_V1_STR}/ai", tags=["ai"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": f"Welcome to {settings.APP_NAME} API"} 