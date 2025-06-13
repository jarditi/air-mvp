#!/usr/bin/env python3
"""
Google Cloud Setup Script for AIR MVP

This script helps set up Google Cloud project and Gmail API credentials
for the AIR MVP application.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from lib.google_cloud_config import GoogleCloudManager
from lib.logger import setup_logging, logger


class GoogleCloudSetup:
    """Interactive Google Cloud setup assistant"""
    
    def __init__(self):
        """Initialize setup assistant"""
        self.env_file = Path(__file__).parent.parent / '.env'
        self.current_config = {}
        
    def print_header(self):
        """Print setup header"""
        print("=" * 60)
        print("🚀 AIR MVP - Google Cloud Setup Assistant")
        print("=" * 60)
        print()
        print("This script will help you set up Google Cloud project")
        print("and Gmail API credentials for the AIR MVP application.")
        print()
    
    def print_step(self, step: int, title: str):
        """Print step header"""
        print(f"\n📋 Step {step}: {title}")
        print("-" * 40)
    
    def load_current_config(self):
        """Load current environment configuration"""
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        self.current_config[key] = value
    
    def save_env_config(self, config: Dict[str, str]):
        """Save configuration to .env file"""
        # Read existing .env file
        existing_lines = []
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                existing_lines = f.readlines()
        
        # Update or add Google Cloud configuration
        google_keys = {
            'GOOGLE_CLOUD_PROJECT_ID',
            'GOOGLE_OAUTH_CLIENT_ID', 
            'GOOGLE_OAUTH_CLIENT_SECRET',
            'GOOGLE_OAUTH_REDIRECT_URI'
        }
        
        # Remove existing Google Cloud config lines
        filtered_lines = []
        for line in existing_lines:
            key = line.split('=')[0] if '=' in line else ''
            if key not in google_keys:
                filtered_lines.append(line)
        
        # Add Google Cloud configuration section
        filtered_lines.append('\n# Google Cloud Configuration\n')
        for key, value in config.items():
            filtered_lines.append(f'{key}={value}\n')
        
        # Write updated .env file
        with open(self.env_file, 'w') as f:
            f.writelines(filtered_lines)
        
        print(f"✅ Configuration saved to {self.env_file}")
    
    def get_user_input(self, prompt: str, default: str = None, required: bool = True) -> str:
        """Get user input with validation"""
        while True:
            if default:
                user_input = input(f"{prompt} [{default}]: ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{prompt}: ").strip()
            
            if user_input or not required:
                return user_input
            
            print("❌ This field is required. Please enter a value.")
    
    def validate_project_id(self, project_id: str) -> bool:
        """Validate Google Cloud project ID format"""
        if not project_id:
            return False
        
        # Basic validation - project IDs must be 6-30 characters
        # and contain only lowercase letters, digits, and hyphens
        if len(project_id) < 6 or len(project_id) > 30:
            return False
        
        if not project_id.replace('-', '').replace('_', '').isalnum():
            return False
        
        return True
    
    def validate_client_id(self, client_id: str) -> bool:
        """Validate Google OAuth client ID format"""
        return client_id and client_id.endswith('.apps.googleusercontent.com')
    
    def display_instructions(self):
        """Display detailed setup instructions"""
        try:
            manager = GoogleCloudManager()
            instructions = manager.get_setup_instructions()
            
            print("\n📖 Detailed Setup Instructions")
            print("=" * 50)
            
            # Project setup steps
            project_setup = instructions['project_setup']
            print(f"\n{project_setup['title']}")
            print("-" * len(project_setup['title']))
            
            for step in project_setup['steps']:
                print(f"\n{step['step']}. {step['title']}")
                print(f"   {step['description']}")
                if 'url' in step:
                    print(f"   🔗 {step['url']}")
                
                for detail in step['details']:
                    print(f"   • {detail}")
            
            # Security notes
            print(f"\n🔒 Security Notes")
            print("-" * 15)
            for note in instructions['security_notes']:
                print(f"• {note}")
                
        except Exception as e:
            print(f"❌ Failed to load instructions: {e}")
    
    def collect_configuration(self) -> Dict[str, str]:
        """Collect Google Cloud configuration from user"""
        config = {}
        
        self.print_step(1, "Google Cloud Project Configuration")
        
        # Project ID
        current_project = self.current_config.get('GOOGLE_CLOUD_PROJECT_ID', '')
        while True:
            project_id = self.get_user_input(
                "Enter your Google Cloud Project ID",
                default=current_project if current_project else None
            )
            
            if self.validate_project_id(project_id):
                config['GOOGLE_CLOUD_PROJECT_ID'] = project_id
                break
            else:
                print("❌ Invalid project ID. Must be 6-30 characters, lowercase letters, digits, and hyphens only.")
        
        self.print_step(2, "OAuth Client Credentials")
        
        # Client ID
        current_client_id = self.current_config.get('GOOGLE_OAUTH_CLIENT_ID', '')
        while True:
            client_id = self.get_user_input(
                "Enter your OAuth Client ID",
                default=current_client_id if current_client_id else None
            )
            
            if self.validate_client_id(client_id):
                config['GOOGLE_OAUTH_CLIENT_ID'] = client_id
                break
            else:
                print("❌ Invalid client ID. Must end with '.apps.googleusercontent.com'")
        
        # Client Secret
        current_client_secret = self.current_config.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
        client_secret = self.get_user_input(
            "Enter your OAuth Client Secret",
            default=current_client_secret if current_client_secret else None
        )
        config['GOOGLE_OAUTH_CLIENT_SECRET'] = client_secret
        
        # Redirect URI
        current_redirect = self.current_config.get('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8000/auth/google/callback')
        redirect_uri = self.get_user_input(
            "Enter OAuth Redirect URI",
            default=current_redirect,
            required=False
        )
        config['GOOGLE_OAUTH_REDIRECT_URI'] = redirect_uri or 'http://localhost:8000/auth/google/callback'
        
        return config
    
    def validate_configuration(self, config: Dict[str, str]) -> bool:
        """Validate the collected configuration"""
        self.print_step(3, "Configuration Validation")
        
        print("Validating configuration...")
        
        # Set environment variables temporarily for validation
        for key, value in config.items():
            os.environ[key] = value
        
        try:
            # Try to initialize Google Cloud manager
            manager = GoogleCloudManager()
            validation_result = manager.validate_project_setup()
            
            print(f"✅ Project ID: {validation_result['project_id']}")
            
            if validation_result['credentials_valid']:
                print("✅ Service account credentials valid")
            else:
                print("⚠️  Service account not configured (optional)")
            
            if validation_result['errors']:
                print("\n⚠️  Validation warnings:")
                for error in validation_result['errors']:
                    print(f"   • {error}")
            
            print("✅ Configuration appears valid")
            return True
            
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
            return False
    
    def display_next_steps(self):
        """Display next steps after setup"""
        print("\n🎉 Setup Complete!")
        print("=" * 20)
        print()
        print("Next steps:")
        print("1. Start your application: uvicorn main:app --reload")
        print("2. Visit http://localhost:8000/docs to see the API documentation")
        print("3. Test Gmail integration at /api/v1/integrations/gmail/setup-instructions")
        print("4. Initiate OAuth flow at /api/v1/integrations/gmail/oauth/initiate")
        print()
        print("📚 For more information, check the API documentation at /docs")
        print()
    
    async def run_setup(self):
        """Run the complete setup process"""
        try:
            self.print_header()
            
            # Load current configuration
            self.load_current_config()
            
            # Ask if user wants to see detailed instructions
            show_instructions = input("Would you like to see detailed setup instructions? (y/N): ").strip().lower()
            if show_instructions in ['y', 'yes']:
                self.display_instructions()
                input("\nPress Enter to continue with configuration...")
            
            # Collect configuration
            config = self.collect_configuration()
            
            # Display collected configuration
            print("\n📋 Configuration Summary")
            print("-" * 25)
            for key, value in config.items():
                if 'SECRET' in key:
                    print(f"{key}: {'*' * len(value)}")
                else:
                    print(f"{key}: {value}")
            
            # Confirm before saving
            confirm = input("\nSave this configuration? (Y/n): ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                # Validate configuration
                if self.validate_configuration(config):
                    # Save configuration
                    self.save_env_config(config)
                    self.display_next_steps()
                else:
                    print("❌ Configuration validation failed. Please check your settings.")
                    return False
            else:
                print("❌ Setup cancelled.")
                return False
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n❌ Setup cancelled by user.")
            return False
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            return False


async def main():
    """Main setup function"""
    setup_logging()
    
    setup = GoogleCloudSetup()
    success = await setup.run_setup()
    
    if success:
        print("✅ Google Cloud setup completed successfully!")
        sys.exit(0)
    else:
        print("❌ Google Cloud setup failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 