#!/usr/bin/env python3
"""
Script to fix Gmail client OAuth integration issues
"""

import re

def fix_gmail_client():
    """Fix the Gmail client OAuth integration issues"""
    
    # Read the file
    with open('backend/lib/gmail_client.py', 'r') as f:
        content = f.read()
    
    # Fix 1: Replace client config access in handle_oauth_callback
    old1 = "client_id=self.oauth_client._providers[OAuthProvider.GOOGLE].config.client_id,\n                client_secret=self.oauth_client._providers[OAuthProvider.GOOGLE].config.client_secret,"
    new1 = "client_id=google_provider.config.client_id,\n                client_secret=google_provider.config.client_secret,"
    
    if old1 in content:
        content = content.replace(old1, new1)
        content = content.replace(
            "# Create credentials object\n            credentials = Credentials(",
            "# Create credentials object\n            google_provider = self.oauth_client.get_provider(OAuthProvider.GOOGLE)\n            credentials = Credentials("
        )
    
    # Fix 2: Replace client config access in _get_credentials
    old2 = "client_id=self.oauth_client.get_client_config('google')['client_id'],\n                client_secret=self.oauth_client.get_client_config('google')['client_secret'],"
    new2 = "client_id=google_provider.config.client_id,\n                client_secret=google_provider.config.client_secret,"
    
    if old2 in content:
        content = content.replace(old2, new2)
        content = content.replace(
            "# Create credentials from integration data\n            credentials = Credentials(",
            "# Create credentials from integration data\n            from lib.oauth_client import OAuthProvider\n            google_provider = self.oauth_client.get_provider(OAuthProvider.GOOGLE)\n            credentials = Credentials("
        )
    
    # Write the fixed content back
    with open('backend/lib/gmail_client.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed Gmail client OAuth integration issues")

if __name__ == "__main__":
    fix_gmail_client() 