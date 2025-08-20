#!/usr/bin/env python3
import requests
import json
from bs4 import BeautifulSoup

# Login first
login_url = "http://localhost:5000/login"
api_url = "http://localhost:5000/api/create_telegram_group"

session = requests.Session()

# First, get the login page to obtain CSRF token
print("Getting login page...")
login_page = session.get(login_url)
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
print(f"CSRF token obtained: {csrf_token[:20]}...")

# Login as admin with CSRF token
login_data = {
    'username': 'admin',
    'password': 'admin123',  # default password
    'csrf_token': csrf_token
}

print("\nLogging in...")
login_response = session.post(login_url, data=login_data, allow_redirects=True)
print(f"Login response: {login_response.status_code}")

# Check if login was successful
if "Dashboard" in login_response.text or login_response.url != login_url:
    print("✅ Login successful!")
else:
    print("❌ Login failed!")
    exit(1)

# Test the API endpoint
test_data = {
    'name': 'Test Group',
    'description': 'Test Description',
    'add_saved_users': False,
    'is_active': True
}

print("\nCalling API endpoint...")
headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
}

response = session.post(api_url, json=test_data, headers=headers)
print(f"API Response Status: {response.status_code}")
print(f"API Response: {response.text}")

if response.status_code == 200 or response.status_code == 201:
    result = response.json()
    print("\n✅ Success!")
    print(f"Setup Code: {result.get('setup_code')}")
    print(f"Bot Username: {result.get('bot_username')}")
    print(f"Instructions: {result.get('instructions')}")
else:
    print(f"\n❌ Error: {response.status_code}")
    try:
        error_data = response.json()
        print(f"Error message: {error_data.get('message')}")
    except:
        print(f"Raw response: {response.text}")
