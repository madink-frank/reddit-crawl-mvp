#!/usr/bin/env python3
"""
Test script for Slack webhook integration
Usage: python scripts/test-slack-webhook.py
"""

import os
import json
import requests
from datetime import datetime

def test_slack_webhook():
    """Test Slack webhook with sample alert"""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    
    if not webhook_url:
        print("❌ SLACK_WEBHOOK_URL environment variable not set")
        return False
    
    # Sample alert payload
    test_payload = {
        "text": "🧪 Test Alert from Reddit Publisher",
        "attachments": [
            {
                "color": "good",
                "title": "Test Alert - System Check",
                "fields": [
                    {
                        "title": "Service",
                        "value": "reddit-publisher",
                        "short": True
                    },
                    {
                        "title": "Severity",
                        "value": "info",
                        "short": True
                    },
                    {
                        "title": "Description",
                        "value": "This is a test alert to verify Slack webhook integration",
                        "short": False
                    },
                    {
                        "title": "Timestamp",
                        "value": datetime.now().isoformat(),
                        "short": True
                    }
                ],
                "footer": "Reddit Publisher Monitoring",
                "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png"
            }
        ]
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Slack webhook test successful!")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"❌ Slack webhook test failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing Slack webhook: {e}")
        return False

def test_alertmanager_webhook():
    """Test Alertmanager-style webhook payload"""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    
    if not webhook_url:
        print("❌ SLACK_WEBHOOK_URL environment variable not set")
        return False
    
    # Alertmanager-style payload
    alertmanager_payload = {
        "text": "🚨 Alertmanager Test",
        "attachments": [
            {
                "color": "danger",
                "title": "High Queue Depth Alert",
                "fields": [
                    {
                        "title": "Alert",
                        "value": "HighQueueDepth",
                        "short": True
                    },
                    {
                        "title": "Severity",
                        "value": "warning",
                        "short": True
                    },
                    {
                        "title": "Service",
                        "value": "reddit-publisher",
                        "short": True
                    },
                    {
                        "title": "Status",
                        "value": "firing",
                        "short": True
                    },
                    {
                        "title": "Description",
                        "value": "Queue depth is 1500 which exceeds the threshold of 1000",
                        "short": False
                    }
                ],
                "footer": "Alertmanager",
                "ts": int(datetime.now().timestamp())
            }
        ]
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=alertmanager_payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Alertmanager webhook test successful!")
            return True
        else:
            print(f"❌ Alertmanager webhook test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing Alertmanager webhook: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Slack webhook integration...")
    print("=" * 50)
    
    # Test basic webhook
    print("\n1. Testing basic Slack webhook...")
    basic_test = test_slack_webhook()
    
    # Test Alertmanager-style webhook
    print("\n2. Testing Alertmanager-style webhook...")
    alertmanager_test = test_alertmanager_webhook()
    
    print("\n" + "=" * 50)
    if basic_test and alertmanager_test:
        print("✅ All webhook tests passed!")
        exit(0)
    else:
        print("❌ Some webhook tests failed!")
        exit(1)