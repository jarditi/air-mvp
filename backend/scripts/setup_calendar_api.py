#!/usr/bin/env python3
"""
Calendar API Setup Script

This script helps set up and validate Google Calendar API access for the AIR MVP application.
It checks configuration, validates API access, and provides setup instructions.
"""

import os
import sys
import json
from typing import Dict, Any
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lib.google_cloud_config import google_cloud_manager
from lib.oauth_client import OAuthClient


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n📋 {title}")
    print("-" * 40)


def print_success(message: str):
    """Print a success message"""
    print(f"✅ {message}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"⚠️  {message}")


def print_error(message: str):
    """Print an error message"""
    print(f"❌ {message}")


def print_info(message: str):
    """Print an info message"""
    print(f"ℹ️  {message}")


def check_environment_variables() -> Dict[str, Any]:
    """Check if required environment variables are set"""
    print_section("Environment Variables Check")
    
    required_vars = [
        'GOOGLE_CLOUD_PROJECT_ID',
        'GOOGLE_OAUTH_CLIENT_ID',
        'GOOGLE_OAUTH_CLIENT_SECRET'
    ]
    
    optional_vars = [
        'GOOGLE_OAUTH_REDIRECT_URI',
        'GOOGLE_SERVICE_ACCOUNT_PATH',
        'CALENDAR_MAX_RESULTS',
        'CALENDAR_SYNC_DAYS_BACK',
        'CALENDAR_SYNC_DAYS_FORWARD'
    ]
    
    results = {
        'required_set': True,
        'missing_required': [],
        'optional_set': [],
        'missing_optional': []
    }
    
    # Check required variables
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var} is set")
        else:
            print_error(f"{var} is missing")
            results['missing_required'].append(var)
            results['required_set'] = False
    
    # Check optional variables
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var} is set: {value}")
            results['optional_set'].append(var)
        else:
            print_info(f"{var} is not set (optional)")
            results['missing_optional'].append(var)
    
    return results


def validate_google_cloud_config() -> Dict[str, Any]:
    """Validate Google Cloud configuration"""
    print_section("Google Cloud Configuration")
    
    try:
        # Test loading configuration
        config = google_cloud_manager.config
        print_success(f"Project ID: {config.project_id}")
        print_success(f"Client ID: {config.client_id[:20]}...")
        print_success(f"Redirect URI: {config.redirect_uri}")
        
        # Check Calendar-specific scopes
        calendar_scopes = config.calendar_scopes
        print_success(f"Calendar scopes configured: {len(calendar_scopes)}")
        for scope in calendar_scopes:
            print(f"  - {scope}")
        
        return {'success': True, 'config': config}
        
    except Exception as e:
        print_error(f"Configuration error: {e}")
        return {'success': False, 'error': str(e)}


def validate_calendar_api_access() -> Dict[str, Any]:
    """Validate Calendar API access"""
    print_section("Calendar API Access Validation")
    
    try:
        results = google_cloud_manager.validate_calendar_api_access()
        
        # OAuth configuration
        if results['oauth_configured']:
            print_success("OAuth credentials configured")
        else:
            print_error("OAuth credentials not configured")
        
        # Scopes configuration
        if results['scopes_configured']:
            print_success("Calendar scopes configured")
            for scope in results.get('configured_scopes', []):
                print(f"  - {scope}")
        else:
            print_error("Calendar scopes not configured")
        
        # API access
        if results['calendar_api_enabled']:
            print_success("Calendar API access verified")
        else:
            print_warning("Calendar API access not verified")
        
        # Errors and warnings
        for error in results.get('errors', []):
            print_error(error)
        
        for warning in results.get('warnings', []):
            print_warning(warning)
        
        return results
        
    except Exception as e:
        print_error(f"Calendar API validation error: {e}")
        return {'success': False, 'error': str(e)}


def test_oauth_client() -> Dict[str, Any]:
    """Test OAuth client functionality"""
    print_section("OAuth Client Test")
    
    try:
        # Initialize OAuth client
        oauth_client = OAuthClient()
        print_success("OAuth client initialized")
        
        # Test available providers
        providers = oauth_client.get_available_providers()
        print_success(f"Available OAuth providers: {[p.value for p in providers]}")
        
        # Test authorization URL generation for Google
        from lib.oauth_client import OAuthProvider
        auth_url, state = oauth_client.get_auth_url(
            provider=OAuthProvider.GOOGLE,
            redirect_uri=google_cloud_manager.config.redirect_uri,
            scopes=google_cloud_manager.config.calendar_scopes
        )
        print_success("Authorization URL generated successfully")
        print_info(f"Auth URL length: {len(auth_url)} characters")
        print_info(f"State: {state}")
        
        return {'success': True, 'auth_url': auth_url, 'state': state}
        
    except Exception as e:
        print_error(f"OAuth client test failed: {e}")
        return {'success': False, 'error': str(e)}


def show_setup_instructions():
    """Show detailed setup instructions"""
    print_section("Setup Instructions")
    
    requirements = google_cloud_manager.get_calendar_api_requirements()
    
    print("🔧 Required APIs to Enable:")
    for api in requirements['required_apis']:
        print(f"  • {api['name']} ({api['api_id']})")
        print(f"    URL: {api['url']}")
        print(f"    Description: {api['description']}")
    
    print("\n🔑 Required OAuth Scopes:")
    for scope in requirements['required_scopes']:
        required_text = "REQUIRED" if scope['required'] else "OPTIONAL"
        print(f"  • {scope['scope']} ({required_text})")
        print(f"    Description: {scope['description']}")
        if 'note' in scope:
            print(f"    Note: {scope['note']}")
    
    print("\n🌐 OAuth Configuration:")
    oauth_setup = requirements['oauth_setup']
    print("  Authorized redirect URIs:")
    for uri in oauth_setup['redirect_uris']:
        print(f"    - {uri}")
    print("  Authorized JavaScript origins:")
    for origin in oauth_setup['javascript_origins']:
        print(f"    - {origin}")
    
    print("\n📝 Environment Variables:")
    print("  Required:")
    for var in requirements['environment_variables']:
        print(f"    - {var}")
    print("  Optional:")
    for var in requirements['optional_config']:
        print(f"    - {var}")


def show_next_steps(env_check: Dict[str, Any], config_check: Dict[str, Any], 
                   api_check: Dict[str, Any], oauth_check: Dict[str, Any]):
    """Show next steps based on validation results"""
    print_section("Next Steps")
    
    if not env_check['required_set']:
        print("1. ❌ Set missing environment variables:")
        for var in env_check['missing_required']:
            print(f"   - {var}")
        print("   See GOOGLE_CLOUD_SETUP.md for detailed instructions")
        return
    
    if not config_check['success']:
        print("2. ❌ Fix Google Cloud configuration issues")
        return
    
    if not oauth_check['success']:
        print("3. ❌ Fix OAuth client configuration")
        return
    
    if not api_check.get('calendar_api_enabled', False):
        print("4. ⚠️  Enable Calendar API in Google Cloud Console:")
        print("   - Go to: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com")
        print("   - Click 'Enable'")
        return
    
    print("🎉 Calendar API setup is complete!")
    print("\nYou can now proceed with:")
    print("  • Task 2.3.2: Create Calendar client")
    print("  • Task 2.3.3: Implement Calendar OAuth flow")
    print("  • Task 2.3.4: Build meeting/event fetching logic")


def main():
    """Main setup validation function"""
    print_header("Google Calendar API Setup Validation")
    
    # Check environment variables
    env_check = check_environment_variables()
    
    # Validate Google Cloud configuration
    config_check = validate_google_cloud_config()
    
    # Validate Calendar API access
    api_check = validate_calendar_api_access()
    
    # Test OAuth client
    oauth_check = test_oauth_client()
    
    # Show setup instructions
    show_setup_instructions()
    
    # Show next steps
    show_next_steps(env_check, config_check, api_check, oauth_check)
    
    # Summary
    print_header("Setup Summary")
    
    total_checks = 4
    passed_checks = sum([
        env_check['required_set'],
        config_check['success'],
        api_check.get('oauth_configured', False),
        oauth_check['success']
    ])
    
    print(f"Setup Progress: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        print_success("✅ Calendar API setup is ready!")
        print("You can now proceed with Calendar integration development.")
    else:
        print_warning(f"⚠️  {total_checks - passed_checks} issues need to be resolved")
        print("Please follow the instructions above to complete the setup.")


if __name__ == "__main__":
    main() 