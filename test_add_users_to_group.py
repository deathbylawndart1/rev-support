#!/usr/bin/env python3
"""Test script for the new add users to existing group functionality"""

import requests
import json
import re

# Configuration
BASE_URL = 'http://localhost:5000'
USERNAME = 'admin'
PASSWORD = 'admin123'

def login():
    """Login and get session with CSRF token"""
    session = requests.Session()
    
    # First get the login page
    print("Accessing login page...")
    response = session.get(f'{BASE_URL}/login')
    if response.status_code != 200:
        print(f"Failed to get login page: {response.status_code}")
        return None
    
    # Find the CSRF token in the login form
    csrf_match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', response.text)
    if not csrf_match:
        # Try alternative pattern
        csrf_match = re.search(r'name="csrf_token".*?value="([^"]+)"', response.text, re.DOTALL)
    
    if not csrf_match:
        print("Could not find CSRF token in login page")
        print("Login page snippet:", response.text[:500])
        return None
    
    csrf_token = csrf_match.group(1)
    print(f"Found CSRF token: {csrf_token[:10]}...")
    
    # Login with credentials and CSRF token
    login_data = {
        'username': USERNAME,
        'password': PASSWORD,
        'csrf_token': csrf_token
    }
    
    response = session.post(f'{BASE_URL}/login', data=login_data, allow_redirects=True)
    
    # Check if login was successful by looking at the response
    if 'Dashboard' in response.text or 'Logout' in response.text:
        print("✓ Login successful")
    else:
        print(f"Login may have failed. Status: {response.status_code}")
        if response.status_code == 200:
            print("Still on login page - invalid credentials?")
        return None
    
    # Get CSRF token from settings page
    response = session.get(f'{BASE_URL}/settings')
    if response.status_code == 200:
        # Extract CSRF token from the settings page
        csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text)
        if csrf_match:
            csrf_token = csrf_match.group(1)
            print(f"✓ CSRF token obtained from settings page")
            return session, csrf_token
        else:
            print("Could not find CSRF token in settings page")
    else:
        print(f"Failed to access settings page: {response.status_code}")
    
    return None

def test_add_users_to_group(session, csrf_token):
    """Test the add users to group endpoint"""
    
    # Test data - you'll need to replace this with a real group ID
    test_data = {
        'group_id': '-1001234567890',  # Replace with your actual group ID
        'user_ids': ['123456789', '987654321']  # Replace with actual user IDs
    }
    
    print(f"\nTesting add users to group with:")
    print(f"  Group ID: {test_data['group_id']}")
    print(f"  User IDs: {test_data['user_ids']}")
    
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token,
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    response = session.post(
        f'{BASE_URL}/api/add_users_to_group',
        json=test_data,
        headers=headers
    )
    
    print(f"\nResponse status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success!")
        print(f"  Status: {result.get('status')}")
        print(f"  Users added: {result.get('users_added')}")
        print(f"  Failed count: {result.get('failed_count')}")
        print(f"  Message: {result.get('message')}")
    else:
        print(f"✗ Error: {response.text}")

def main():
    print("Testing 'Add Users to Group' functionality\n")
    print("=" * 50)
    
    # Login
    login_result = login()
    if not login_result:
        print("Failed to login")
        return
    
    session, csrf_token = login_result
    
    # Test the endpoint
    test_add_users_to_group(session, csrf_token)
    
    print("\n" + "=" * 50)
    print("\nNote: Make sure to:")
    print("1. Replace the group_id with a real Telegram group ID where the bot is admin")
    print("2. Replace user_ids with real Telegram user IDs that have interacted with the bot")
    print("3. Ensure the bot is running and connected to Telegram")

if __name__ == '__main__':
    main()
