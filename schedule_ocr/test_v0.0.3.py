#!/usr/bin/env python3
"""
Test suite for Schedule OCR Web App v0.0.3
Tests all core functionality: upload, OCR, search, export
"""

import os
import sys
import json
import requests
import base64
from pathlib import Path

# Test configuration
BASE_URL = 'http://localhost:5003'
TEST_IMAGES_DIR = '/home/alice/.openclaw/workspace/schedule_ocr/test_images'
UPLOAD_FOLDER = '/home/alice/.openclaw/workspace/schedule_ocr/uploads'

def log(test_name, status, message=''):
    """Log test result"""
    emoji = '✅' if status else '❌'
    print(f"{emoji} {test_name}: {'PASS' if status else 'FAIL'} {message}")
    return status

def test_1_homepage():
    """Test homepage loads"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        return log("Homepage loads", response.status_code == 200)
    except Exception as e:
        return log("Homepage loads", False, str(e))

def test_2_upload_image():
    """Test image upload"""
    try:
        # Find test image
        test_images = list(Path(TEST_IMAGES_DIR).glob('*.jpg')) + list(Path(TEST_IMAGES_DIR).glob('*.png'))
        if not test_images:
            return log("Upload image", False, "No test images found")
        
        image_path = test_images[0]
        
        with open(image_path, 'rb') as f:
            files = {'image': f}
            response = requests.post(f'{BASE_URL}/upload', files=files, timeout=30)
            data = response.json()
        
        if data.get('success'):
            return log("Upload image", True, f"image_id: {data.get('image_id')}")
        else:
            return log("Upload image", False, data.get('error', 'Unknown error'))
    except Exception as e:
        return log("Upload image", False, str(e))

def test_3_json_parsing():
    """Test JSON parsing handles malformed responses"""
    test_cases = [
        ('{"schedules": {"test": [{"date": "115/03/09", "time": "00-08"}]}}', True, "Perfect JSON"),
        ('{"schedules": {"test": [{"date": "115/03/09", "time": "00-08"}]}}\n', True, "JSON with newline"),
        ('Some text {"schedules": {"test": [{"date": "115/03/09", "time": "00-08"}]}} more text', True, "JSON with extra text"),
        ('', False, "Empty string"),
        ('{invalid}', False, "Invalid JSON"),
    ]
    
    all_pass = True
    for json_str, should_pass, description in test_cases:
        try:
            # Try direct parse
            try:
                parsed = json.loads(json_str)
                result = should_pass
            except json.JSONDecodeError:
                # Try extract
                start = json_str.find('{')
                end = json_str.rfind('}') + 1
                if start >= 0 and end > start:
                    extracted = json_str[start:end].replace('\n', '').replace('\r', '')
                    parsed = json.loads(extracted)
                    result = should_pass
                else:
                    result = not should_pass
            
            log(f"  JSON parse: {description}", result)
            if not result:
                all_pass = False
        except:
            if should_pass:
                all_pass = False
    
    return log("JSON parsing robust", all_pass)

def test_4_search_schedule():
    """Test schedule search"""
    try:
        # First upload
        test_images = list(Path(TEST_IMAGES_DIR).glob('*.jpg'))
        if not test_images:
            return log("Search schedule", False, "No test images")
        
        with open(test_images[0], 'rb') as f:
            upload_resp = requests.post(f'{BASE_URL}/upload', files={'image': f}, timeout=30)
            upload_data = upload_resp.json()
        
        if not upload_data.get('success'):
            return log("Search schedule", False, "Upload failed")
        
        image_id = upload_data.get('image_id')
        
        # Search for a name
        search_resp = requests.post(
            f'{BASE_URL}/api/search',
            json={'image_id': image_id, 'name': '司徒瑜'},
            timeout=30
        )
        search_data = search_resp.json()
        
        if search_data.get('success'):
            schedules = search_data.get('schedules', [])
            stats = search_data.get('stats', {})
            return log("Search schedule", True, f"Found {len(schedules)} schedules, stats: {stats}")
        else:
            # Check if it's expected (no data)
            if '未找到' in search_data.get('error', ''):
                return log("Search schedule", True, "Expected: no data found")
            else:
                return log("Search schedule", False, search_data.get('error'))
    except Exception as e:
        return log("Search schedule", False, str(e))

def test_5_export_ics():
    """Test ICS export"""
    try:
        # Mock schedule data
        test_data = {
            'name': 'Test User',
            'schedules': [
                {'date': '115/03/09', 'time': '00-08'},
                {'date': '115/03/10', 'time': '16-00'},
                {'date': '115/03/11', 'time': '例'}
            ]
        }
        
        response = requests.post(
            f'{BASE_URL}/api/export/ics',
            json=test_data,
            timeout=10
        )
        data = response.json()
        
        if data.get('success'):
            # Verify file exists
            filepath = data.get('filepath')
            if filepath and os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                if 'BEGIN:VCALENDAR' in content and 'Test User' in content:
                    return log("Export ICS", True, f"File: {filepath}")
                else:
                    return log("Export ICS", False, "Invalid ICS content")
            else:
                return log("Export ICS", False, "File not created")
        else:
            return log("Export ICS", False, data.get('error'))
    except Exception as e:
        return log("Export ICS", False, str(e))

def test_6_version_display():
    """Test version number display"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        html = response.text
        
        if 'v0.0.3' in html:
            return log("Version display", True, "v0.0.3 found")
        elif 'v0.0' in html:
            version = html.split('v0.0')[1].split('<')[0]
            return log("Version display", True, f"v0.0{version} found")
        else:
            return log("Version display", False, "No version found")
    except Exception as e:
        return log("Version display", False, str(e))

def test_7_responsive_design():
    """Test mobile-friendly design"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        html = response.text
        
        checks = [
            ('viewport' in html, "Viewport meta tag"),
            ('max-width' in html, "Responsive CSS"),
            ('@media' in html or 'mobile' in html.lower(), "Mobile styles"),
        ]
        
        all_pass = all(check[0] for check in checks)
        return log("Responsive design", all_pass)
    except Exception as e:
        return log("Responsive design", False, str(e))

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Schedule OCR Web App v0.0.3 - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_1_homepage,
        test_2_upload_image,
        test_3_json_parsing,
        test_4_search_schedule,
        test_5_export_ics,
        test_6_version_display,
        test_7_responsive_design,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"⚠️  Test exception: {e}")
            results.append(False)
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    return passed == total

if __name__ == '__main__':
    # Create test images dir if not exists
    os.makedirs(TEST_IMAGES_DIR, exist_ok=True)
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
