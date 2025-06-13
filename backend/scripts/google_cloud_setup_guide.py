#!/usr/bin/env python3
"""
Google Cloud Setup Guide for AIR MVP

This script provides step-by-step instructions for setting up Google Cloud
project and API credentials for Gmail and Calendar integration.
"""

import os
import sys
from pathlib import Path


def print_header():
    """Print setup header"""
    print("=" * 70)
    print("🚀 AIR MVP - Google Cloud Setup Guide")
    print("=" * 70)
    print()
    print("This guide will walk you through setting up Google Cloud project")
    print("and API credentials for Gmail and Calendar integration.")
    print()


def print_step(step: int, title: str):
    """Print step header"""
    print(f"\n📋 Step {step}: {title}")
    print("-" * 50)


def step_1_create_project():
    """Step 1: Create Google Cloud Project"""
    print_step(1, "Create Google Cloud Project")
    
    print("1. Go to Google Cloud Console:")
    print("   🔗 https://console.cloud.google.com/projectcreate")
    print()
    print("2. Create a new project:")
    print("   • Click 'New Project'")
    print("   • Enter a project name (e.g., 'air-mvp-production')")
    print("   • Note down the Project ID (auto-generated)")
    print("   • Select billing account if required")
    print("   • Click 'Create'")
    print()
    print("📝 Save your Project ID - you'll need it later!")
    print("   Example: air-mvp-production-123456")


def step_2_enable_apis():
    """Step 2: Enable Required APIs"""
    print_step(2, "Enable Required APIs")
    
    print("1. Go to API Library:")
    print("   🔗 https://console.cloud.google.com/apis/library")
    print()
    print("2. Enable the following APIs (search and click 'Enable'):")
    print("   ✅ Gmail API")
    print("   ✅ Google Calendar API") 
    print("   ✅ People API (for contacts)")
    print("   ✅ Cloud Resource Manager API")
    print()
    print("3. For each API:")
    print("   • Search for the API name")
    print("   • Click on the API")
    print("   • Click 'Enable' button")
    print("   • Wait for enablement to complete")


def step_3_oauth_consent():
    """Step 3: Configure OAuth Consent Screen"""
    print_step(3, "Configure OAuth Consent Screen")
    
    print("1. Go to OAuth consent screen:")
    print("   🔗 https://console.cloud.google.com/apis/credentials/consent")
    print()
    print("2. Choose user type:")
    print("   • Select 'External' for testing/development")
    print("   • Click 'Create'")
    print()
    print("3. Fill in OAuth consent screen:")
    print("   • App name: 'AIR MVP'")
    print("   • User support email: your email")
    print("   • Developer contact: your email")
    print("   • Click 'Save and Continue'")
    print()
    print("4. Add scopes:")
    print("   • Click 'Add or Remove Scopes'")
    print("   • Add these scopes:")
    print("     - .../auth/gmail.readonly")
    print("     - .../auth/gmail.send") 
    print("     - .../auth/gmail.modify")
    print("     - .../auth/calendar.readonly")
    print("     - .../auth/userinfo.email")
    print("     - .../auth/userinfo.profile")
    print("   • Click 'Update' then 'Save and Continue'")
    print()
    print("5. Add test users (for development):")
    print("   • Add your email address")
    print("   • Add any other test user emails")
    print("   • Click 'Save and Continue'")


def step_4_create_credentials():
    """Step 4: Create OAuth Credentials"""
    print_step(4, "Create OAuth 2.0 Credentials")
    
    print("1. Go to Credentials page:")
    print("   🔗 https://console.cloud.google.com/apis/credentials")
    print()
    print("2. Create OAuth client ID:")
    print("   • Click 'Create Credentials' > 'OAuth client ID'")
    print("   • Choose 'Web application'")
    print("   • Name: 'AIR MVP Web Client'")
    print()
    print("3. Configure authorized redirect URIs:")
    print("   • Click 'Add URI' under 'Authorized redirect URIs'")
    print("   • Add: http://localhost:8000/auth/google/callback")
    print("   • Add: http://localhost:3000/auth/google/callback (for frontend)")
    print("   • Add your production domain when ready")
    print()
    print("4. Create and download:")
    print("   • Click 'Create'")
    print("   • Copy the Client ID and Client Secret")
    print("   • Optionally download the JSON file")
    print()
    print("📝 Save these credentials securely:")
    print("   • Client ID: ends with .apps.googleusercontent.com")
    print("   • Client Secret: random string")


def step_5_environment_setup():
    """Step 5: Environment Configuration"""
    print_step(5, "Configure Environment Variables")
    
    env_file = Path(__file__).parent.parent / '.env'
    
    print("1. Create/update your .env file:")
    print(f"   📁 Location: {env_file}")
    print()
    print("2. Add these environment variables:")
    print()
    print("# Google Cloud Configuration")
    print("GOOGLE_CLOUD_PROJECT_ID=your-project-id-here")
    print("GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com")
    print("GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret-here")
    print("GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback")
    print()
    print("3. Replace the placeholder values:")
    print("   • your-project-id-here → Your actual project ID")
    print("   • your-client-id → Your OAuth client ID")
    print("   • your-client-secret-here → Your OAuth client secret")
    print()
    print("⚠️  Security Notes:")
    print("   • Never commit .env file to version control")
    print("   • Add .env to your .gitignore file")
    print("   • Use different credentials for production")


def step_6_test_setup():
    """Step 6: Test Your Setup"""
    print_step(6, "Test Your Setup")
    
    print("1. Start your application:")
    print("   cd backend")
    print("   uvicorn main:app --reload")
    print()
    print("2. Test API endpoints:")
    print("   🔗 http://localhost:8000/docs")
    print()
    print("3. Test Gmail integration:")
    print("   • Visit: /api/v1/integrations/gmail/setup-instructions")
    print("   • Check: /api/v1/integrations/gmail/oauth/config")
    print()
    print("4. Initiate OAuth flow:")
    print("   • POST to: /api/v1/integrations/gmail/oauth/initiate")
    print("   • Follow the authorization URL")
    print("   • Complete the OAuth flow")


def security_best_practices():
    """Security best practices"""
    print_step("Security", "Best Practices")
    
    print("🔒 Security Checklist:")
    print()
    print("✅ Environment Variables:")
    print("   • Use .env file for local development")
    print("   • Use secure secret management in production")
    print("   • Never commit secrets to version control")
    print()
    print("✅ OAuth Configuration:")
    print("   • Use HTTPS in production redirect URIs")
    print("   • Regularly rotate client secrets")
    print("   • Monitor OAuth usage in Google Cloud Console")
    print()
    print("✅ API Security:")
    print("   • Enable API quotas and monitoring")
    print("   • Use least privilege principle")
    print("   • Monitor API usage patterns")
    print()
    print("✅ Production Deployment:")
    print("   • Use separate Google Cloud project for production")
    print("   • Configure proper domain verification")
    print("   • Set up monitoring and alerting")


def troubleshooting():
    """Common troubleshooting steps"""
    print_step("Troubleshooting", "Common Issues")
    
    print("❌ Common Issues and Solutions:")
    print()
    print("1. 'API not enabled' error:")
    print("   → Go to API Library and enable required APIs")
    print()
    print("2. 'Invalid client' error:")
    print("   → Check client ID and secret in .env file")
    print("   → Verify redirect URI matches exactly")
    print()
    print("3. 'Access denied' error:")
    print("   → Add your email to test users in OAuth consent")
    print("   → Check if app is in testing mode")
    print()
    print("4. 'Redirect URI mismatch' error:")
    print("   → Add exact redirect URI to OAuth client config")
    print("   → Check for trailing slashes and protocol (http/https)")
    print()
    print("5. Environment variable errors:")
    print("   → Verify .env file exists and has correct format")
    print("   → Restart application after changing .env")
    print()
    print("📞 Need Help?")
    print("   • Check Google Cloud Console error logs")
    print("   • Review API quotas and usage")
    print("   • Test with curl or Postman first")


def main():
    """Main setup guide"""
    print_header()
    
    # Ask what the user wants to do
    print("What would you like to do?")
    print("1. Complete setup guide (recommended)")
    print("2. Quick environment template")
    print("3. Security best practices")
    print("4. Troubleshooting guide")
    print()
    
    try:
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == "1":
            # Complete guide
            step_1_create_project()
            input("\nPress Enter to continue...")
            
            step_2_enable_apis()
            input("\nPress Enter to continue...")
            
            step_3_oauth_consent()
            input("\nPress Enter to continue...")
            
            step_4_create_credentials()
            input("\nPress Enter to continue...")
            
            step_5_environment_setup()
            input("\nPress Enter to continue...")
            
            step_6_test_setup()
            input("\nPress Enter to continue...")
            
            security_best_practices()
            
        elif choice == "2":
            # Quick template
            step_5_environment_setup()
            
        elif choice == "3":
            # Security guide
            security_best_practices()
            
        elif choice == "4":
            # Troubleshooting
            troubleshooting()
            
        else:
            print("Invalid choice. Running complete guide...")
            main()
            
    except KeyboardInterrupt:
        print("\n\nSetup guide cancelled.")
        sys.exit(0)
    
    print("\n" + "=" * 70)
    print("🎉 Setup guide complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Complete the Google Cloud setup steps above")
    print("2. Update your .env file with the credentials")
    print("3. Start your application and test the integration")
    print()
    print("📚 For more help, run this script again or check the documentation.")


if __name__ == "__main__":
    main() 