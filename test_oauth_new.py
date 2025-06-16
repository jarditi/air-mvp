#!/usr/bin/env python3
"""Simple OAuth test script"""

import requests
import json

# Test the OAuth initiate endpoint
url = "http://localhost:8000/api/v1/integrations/gmail/oauth/initiate"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer fake-token-for-testing"  # This will fail but we can see the error
}
data = {
    "redirect_uri": "http://localhost:8000/auth/google/callback"
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}") 