#!/usr/bin/env python
"""
Local setup validation script.
Tests that all dependencies are installed and configuration loads correctly.
"""

import sys
import os

def test_imports():
    """Test that all required packages are installed."""
    print("\n" + "="*70)
    print("TESTING IMPORTS")
    print("="*70)
    
    packages = [
        ('flask', 'Flask'),
        ('google.cloud.storage', 'Google Cloud Storage'),
        ('google.cloud.secretmanager', 'Google Cloud Secret Manager'),
        ('azure.identity', 'Azure Identity'),
        ('jinja2', 'Jinja2'),
        ('dotenv', 'python-dotenv'),
        ('requests', 'Requests'),
    ]
    
    missing = []
    for module, name in packages:
        try:
            __import__(module)
            print(f"✓ {name} ({module})")
        except ImportError as e:
            print(f"✗ {name} ({module}): {e}")
            missing.append(name)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("\n✅ All imports successful!")
    return True

def test_config_loading():
    """Test that configuration loads correctly."""
    print("\n" + "="*70)
    print("TESTING CONFIGURATION LOADING")
    print("="*70)
    
    try:
        from src.config import (
            GCP_PROJECT_ID, FROM_EMAIL, FROM_NAME, PORT,
            AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET,
            RECIPIENTS
        )
        
        print(f"✓ GCP_PROJECT_ID: {GCP_PROJECT_ID}")
        print(f"✓ FROM_EMAIL: {FROM_EMAIL}")
        print(f"✓ FROM_NAME: {FROM_NAME}")
        print(f"✓ PORT: {PORT}")
        print(f"✓ RECIPIENTS loaded: {len(RECIPIENTS.get('weekly_alerts_recipients', []))} weekly, {len(RECIPIENTS.get('monthly_built_area_recipients', []))} monthly")
        
        # Check Azure credentials
        print("\n--- Azure Credentials ---")
        if AZURE_CLIENT_ID:
            print(f"✓ AZURE_CLIENT_ID: {AZURE_CLIENT_ID[:20]}...")
        else:
            print("✗ AZURE_CLIENT_ID: NOT SET")
        
        if AZURE_TENANT_ID:
            print(f"✓ AZURE_TENANT_ID: {AZURE_TENANT_ID[:20]}...")
        else:
            print("✗ AZURE_TENANT_ID: NOT SET")
        
        if AZURE_CLIENT_SECRET:
            print(f"✓ AZURE_CLIENT_SECRET: {AZURE_CLIENT_SECRET[:20]}...")
        else:
            print("✗ AZURE_CLIENT_SECRET: NOT SET")
        
        # Warn if credentials are placeholder values
        if AZURE_CLIENT_ID == "your-client-id":
            print("\n⚠️  WARNING: Azure credentials are placeholder values!")
            print("Update your .env file with real Azure AD credentials:")
            print("  AZURE_CLIENT_ID=<from Azure Portal>")
            print("  AZURE_TENANT_ID=<from Azure Portal>")
            print("  AZURE_CLIENT_SECRET=<from Azure Portal>")
            return False
        
        print("\n✅ Configuration loaded successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_email_service():
    """Test that EmailService initializes correctly."""
    print("\n" + "="*70)
    print("TESTING EMAIL SERVICE")
    print("="*70)
    
    try:
        from src.config import (
            AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET,
            FROM_EMAIL, FROM_NAME
        )
        from src.email_service import EmailService
        
        # Check if credentials are set
        if not AZURE_CLIENT_ID or AZURE_CLIENT_ID == "your-client-id":
            print("⚠️  Skipping EmailService initialization test (Azure credentials not set)")
            print("Set Azure credentials in .env to test email service")
            return True  # Not a failure, just can't test
        
        print("Initializing EmailService...")
        email_service = EmailService(
            client_id=AZURE_CLIENT_ID,
            tenant_id=AZURE_TENANT_ID,
            client_secret=AZURE_CLIENT_SECRET,
            from_email=FROM_EMAIL,
            from_name=FROM_NAME
        )
        
        print(f"✓ EmailService initialized successfully")
        print(f"  From: {FROM_NAME} <{FROM_EMAIL}>")
        print(f"  Using Azure AD client: {AZURE_CLIENT_ID[:20]}...")
        
        print("\n✅ Email service ready!")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing EmailService: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gcs_connection():
    """Test Google Cloud Storage connection."""
    print("\n" + "="*70)
    print("TESTING GCS CONNECTION")
    print("="*70)
    
    try:
        from src.config import GCP_PROJECT_ID, RECIPIENTS_CSV_URI
        from google.cloud import storage
        
        print(f"GCP Project: {GCP_PROJECT_ID}")
        print(f"Recipients CSV URI: {RECIPIENTS_CSV_URI}")
        
        # Try to access GCS
        client = storage.Client(project=GCP_PROJECT_ID)
        print("✓ GCS client initialized")
        
        if RECIPIENTS_CSV_URI and RECIPIENTS_CSV_URI.startswith("gs://"):
            bucket_name, blob_name = RECIPIENTS_CSV_URI[5:].split("/", 1)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if blob.exists():
                print(f"✓ Recipients CSV found: gs://{bucket_name}/{blob_name}")
                size = blob.size
                print(f"  File size: {size} bytes")
            else:
                print(f"⚠️  Recipients CSV not found: gs://{bucket_name}/{blob_name}")
        
        print("\n✅ GCS connection working!")
        return True
        
    except Exception as e:
        print(f"⚠️  Warning with GCS: {e}")
        print("Note: This may fail if GOOGLE_APPLICATION_CREDENTIALS is not set for local dev")
        return True  # Not a critical failure

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("SIMBYP EMAIL NOTIFICATIONS - LOCAL SETUP TEST")
    print("="*70)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config_loading),
        ("Email Service", test_email_service),
        ("GCS Connection", test_gcs_connection),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! Your setup is ready.")
        print("\nYou can now run:")
        print("  python main.py")
        return 0
    else:
        print("\n⚠️  Some tests failed or need attention.")
        print("Please check the output above and fix any issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
