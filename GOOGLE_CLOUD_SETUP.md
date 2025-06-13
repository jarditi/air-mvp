# Google Cloud Setup Guide for AIR MVP

## Overview

This guide will help you set up Google Cloud project and API credentials for Gmail and Calendar integration in the AIR MVP application running in Docker.

## Prerequisites

- Docker and Docker Compose installed
- Google account
- Access to Google Cloud Console

## Step 1: Create Google Cloud Project

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create New Project**
   - Click "Select a project" dropdown at the top
   - Click "New Project"
   - Enter project name: `air-mvp` (or your preferred name)
   - Note the **Project ID** (will be auto-generated, e.g., `air-mvp-123456`)
   - Click "Create"

## Step 2: Enable Required APIs

1. **Navigate to APIs & Services**
   - Go to: https://console.cloud.google.com/apis/library
   - Make sure your project is selected

2. **Enable the following APIs:**
   - **Gmail API**: https://console.cloud.google.com/apis/library/gmail.googleapis.com
   - **Google Calendar API**: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
   - **People API**: https://console.cloud.google.com/apis/library/people.googleapis.com
   - **Cloud Resource Manager API**: https://console.cloud.google.com/apis/library/cloudresourcemanager.googleapis.com

   For each API:
   - Click on the API name
   - Click "Enable"
   - Wait for enablement to complete

## Step 3: Configure OAuth Consent Screen

1. **Go to OAuth Consent Screen**
   - Visit: https://console.cloud.google.com/apis/credentials/consent
   - Choose "External" user type (for testing)
   - Click "Create"

2. **Fill in App Information:**
   ```
   App name: AIR MVP
   User support email: your-email@example.com
   Developer contact information: your-email@example.com
   ```

3. **Add Scopes (Step 2):**
   - Click "Add or Remove Scopes"
   - Add these scopes:
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/userinfo.email`
     - `https://www.googleapis.com/auth/userinfo.profile`

4. **Add Test Users (Step 3):**
   - Add your email address as a test user
   - Add any other emails you want to test with

## Step 4: Create OAuth Credentials

1. **Go to Credentials**
   - Visit: https://console.cloud.google.com/apis/credentials
   - Click "Create Credentials" > "OAuth client ID"

2. **Configure OAuth Client:**
   ```
   Application type: Web application
   Name: AIR MVP Web Client
   
   Authorized JavaScript origins:
   - http://localhost:3000
   - http://localhost:8000
   
   Authorized redirect URIs:
   - http://localhost:8000/auth/google/callback
   - http://localhost:8000/api/v1/integrations/gmail/oauth/callback
   ```

3. **Download Credentials:**
   - Click "Create"
   - Note down the **Client ID** and **Client Secret**
   - Download the JSON file (optional, for backup)

## Step 5: Update Environment Variables

1. **Update your `.env` file** with the credentials:
   ```bash
   # Google Cloud Configuration
   GOOGLE_CLOUD_PROJECT_ID=your-project-id-here
   GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret-here
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback
   ```

2. **For Docker environment**, make sure these variables are set:
   ```bash
   # Database (Docker services)
   DATABASE_URL=postgresql://postgres:password@db:5432/airmvp
   REDIS_URL=redis://redis:6379
   WEAVIATE_URL=http://weaviate:8080
   CELERY_BROKER_URL=redis://redis:6379
   CELERY_RESULT_BACKEND=redis://redis:6379
   
   # Your existing keys
   SECRET_KEY=your-secret-key
   OPENAI_API_KEY=your-openai-key
   
   # Google Cloud (fill in from Step 4)
   GOOGLE_CLOUD_PROJECT_ID=your-project-id
   GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback
   ```

## Step 6: Start the Application

1. **Start all Docker services:**
   ```bash
   docker-compose up -d
   ```

2. **Check service status:**
   ```bash
   docker-compose ps
   ```

3. **View logs if needed:**
   ```bash
   docker-compose logs backend
   ```

## Step 7: Test the Setup

1. **Check API Documentation:**
   - Visit: http://localhost:8000/docs
   - Look for Gmail integration endpoints

2. **Test Gmail Setup Instructions:**
   - Visit: http://localhost:8000/api/v1/integrations/gmail/setup-instructions
   - Should return setup information

3. **Initiate OAuth Flow:**
   - Visit: http://localhost:8000/api/v1/integrations/gmail/oauth/initiate?user_id=test-user
   - Should redirect to Google OAuth consent screen

## Troubleshooting

### Common Issues:

1. **"Invalid client" error:**
   - Check that Client ID and Secret are correct
   - Verify redirect URI matches exactly

2. **"Access blocked" error:**
   - Make sure OAuth consent screen is configured
   - Add your email as a test user
   - Check that required scopes are added

3. **"API not enabled" error:**
   - Verify all required APIs are enabled in Google Cloud Console
   - Wait a few minutes after enabling APIs

4. **Docker connection issues:**
   - Make sure all services are running: `docker-compose ps`
   - Check logs: `docker-compose logs backend`
   - Restart services: `docker-compose restart`

### Useful Commands:

```bash
# Restart all services
docker-compose restart

# View backend logs
docker-compose logs -f backend

# Access backend container
docker-compose exec backend bash

# Run database migrations
docker-compose exec backend alembic upgrade head

# Test Google Cloud configuration
docker-compose exec backend python -c "from lib.google_cloud_config import google_cloud_manager; print(google_cloud_manager.get_oauth_config())"
```

## Security Notes

- Never commit OAuth client secrets to version control
- Use environment variables for all sensitive configuration
- Regularly rotate OAuth client secrets
- Monitor API usage and quotas in Google Cloud Console
- Use least privilege principle for any service accounts

## Next Steps

After setup is complete:

1. **Test Gmail Integration:**
   - Complete OAuth flow
   - Test email fetching
   - Verify contact extraction

2. **Set up Calendar Integration:**
   - Follow similar OAuth flow for Calendar API
   - Test meeting data extraction

3. **Configure Contact Population:**
   - Test calendar-based contact extraction
   - Verify email-based contact filtering
   - Test contact deduplication logic

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose logs backend`
3. Verify Google Cloud Console configuration
4. Test API endpoints in the documentation at http://localhost:8000/docs 