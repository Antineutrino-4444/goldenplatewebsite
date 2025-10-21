#!/usr/bin/env python3
"""
Test script to verify CSV access control implementation
"""

import requests
import json

# Base URL for the API
BASE_URL = "http://localhost:5000"

def test_csv_access_control():
    """Test CSV upload and preview access control"""
    
    print("Testing CSV Access Control Implementation")
    print("=" * 50)
    
    # Test 1: Check unauthenticated access
    print("\n1. Testing unauthenticated access to CSV upload...")
    response = requests.post(f"{BASE_URL}/csv/upload")
    print(f"   Status: {response.status_code}")
    if response.status_code == 403:
        print("   ✓ Correctly blocked unauthenticated upload")
    else:
        print("   ✗ Should have returned 403 for unauthenticated upload")
    
    print("\n2. Testing unauthenticated access to CSV preview...")
    response = requests.get(f"{BASE_URL}/csv/preview")
    print(f"   Status: {response.status_code}")
    if response.status_code == 403:
        print("   ✓ Correctly blocked unauthenticated preview")
    else:
        print("   ✗ Should have returned 403 for unauthenticated preview")
    
    # Note: For full testing, you would need to:
    # 1. Log in as regular user and test 403 responses
    # 2. Log in as admin/superadmin and test 200 responses with actual CSV upload
    # 3. Test that regular users can still use uploaded CSV data for recording
    
    print("\nNote: Full testing requires authentication and actual CSV files.")
    print("This basic test verifies that unauthenticated requests are properly blocked.")

if __name__ == "__main__":
    try:
        test_csv_access_control()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure the Flask app is running on localhost:5000")
    except Exception as e:
        print(f"Error: {e}")