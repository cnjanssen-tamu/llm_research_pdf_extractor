#!/usr/bin/env python3
"""
Script to check which API key is loaded by Django at runtime.
This script will load the Django settings module and print the current API key.
"""

import os
import sys
import django

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

# Now we can import from Django settings
from django.conf import settings

# Check if the GEMINI_API_KEY is set in Django settings
if hasattr(settings, 'GEMINI_API_KEY'):
    api_key = settings.GEMINI_API_KEY
    print("=" * 80)
    print(f"GEMINI_API_KEY from Django settings: {api_key[:4]}...{api_key[-4:]}")
    print(f"API key length: {len(api_key)} characters")
    
    # Validate the key format to help identify obvious issues
    if api_key.startswith('AIza'):
        print("API key appears to be in the correct format (starts with 'AIza')")
    else:
        print("WARNING: API key does not start with 'AIza', which is unusual for Google API keys")
    
    # Check for common problems
    if api_key == "your-actual-api-key-from-google":
        print("ERROR: API key is still set to the placeholder value!")
    elif api_key == "your-gemini-api-key-here":
        print("ERROR: API key is still set to the placeholder value!")
    elif len(api_key) < 20:
        print("WARNING: API key seems too short to be valid")
    
    # Check the direct environment variable
    env_api_key = os.environ.get('GEMINI_API_KEY')
    if env_api_key:
        print(f"\nGEMINI_API_KEY from os.environ: {env_api_key[:4]}...{env_api_key[-4:]}")
        if api_key != env_api_key:
            print("WARNING: Django settings API key doesn't match environment variable!")
    else:
        print("\nGEMINI_API_KEY not found in os.environ!")
        print("This suggests that dotenv is not loading the .env file correctly.")
    
    # Check the .env file directly
    if os.path.exists('.env'):
        print("\nChecking .env file contents:")
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY='):
                    env_file_key = line.strip().split('=', 1)[1]
                    if env_file_key.startswith('"') and env_file_key.endswith('"'):
                        env_file_key = env_file_key[1:-1]
                    if env_file_key.startswith("'") and env_file_key.endswith("'"):
                        env_file_key = env_file_key[1:-1]
                    print(f"GEMINI_API_KEY in .env file: {env_file_key[:4]}...{env_file_key[-4:]}")
                    
                    if api_key != env_file_key:
                        print("WARNING: Django settings API key doesn't match .env file!")
                    break
            else:
                print("GEMINI_API_KEY not found in .env file!")
    else:
        print("\n.env file not found!")
else:
    print("GEMINI_API_KEY is not defined in Django settings!")

print("=" * 80) 