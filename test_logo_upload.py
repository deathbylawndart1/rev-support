#!/usr/bin/env python3
"""
Test script to debug logo upload functionality
"""
import requests
import os

def test_logo_upload():
    """Test logo upload to admin settings"""
    
    # First, login to get session
    login_url = 'http://localhost:5000/login'
    settings_url = 'http://localhost:5000/settings'
    
    session = requests.Session()
    
    # Login
    login_data = {
        'username': 'admin',
        'password': 'admin123'
    }
    
    print("1. Logging in...")
    login_response = session.post(login_url, data=login_data)
    if login_response.status_code == 200:
        print("✅ Login successful")
    else:
        print(f"❌ Login failed: {login_response.status_code}")
        return
    
    # Create a test image file
    test_image_path = '/tmp/test_logo.png'
    if not os.path.exists(test_image_path):
        # Create a simple 1x1 PNG file for testing
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        with open(test_image_path, 'wb') as f:
            f.write(png_data)
        print(f"✅ Created test image: {test_image_path}")
    
    # Upload logo
    print("2. Uploading logo...")
    with open(test_image_path, 'rb') as logo_file:
        files = {
            'logo': ('test_logo.png', logo_file, 'image/png')
        }
        data = {
            'company_name': 'Test Company',
            'color_scheme': 'blue'
        }
        
        upload_response = session.post(settings_url, files=files, data=data)
        print(f"Upload response status: {upload_response.status_code}")
        print(f"Upload response headers: {dict(upload_response.headers)}")
        
        if 'successfully' in upload_response.text:
            print("✅ Logo upload appears successful")
        else:
            print("❌ Logo upload may have failed")
            print(f"Response content preview: {upload_response.text[:500]}")
    
    # Check if logo was saved
    print("3. Checking uploaded files...")
    uploads_dir = '/home/ryan/CascadeProjects/windsurf-project/static/uploads'
    if os.path.exists(uploads_dir):
        files = os.listdir(uploads_dir)
        recent_files = [f for f in files if 'test_logo' in f or f.startswith('2025')]
        print(f"Recent upload files: {recent_files}")
    
    # Clean up
    if os.path.exists(test_image_path):
        os.remove(test_image_path)
        print("🧹 Cleaned up test file")

if __name__ == '__main__':
    test_logo_upload()
