#!/usr/bin/env python3
"""
Test the Gemini API key loaded from .env file
"""

import os
from dotenv import load_dotenv
import sys

print("Testing Gemini API with .env key")
print("================================")

# Get current directory
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

# Find .env file
env_path = os.path.join(current_dir, '.env')
print(f"Looking for .env file at: {env_path}")

if not os.path.exists(env_path):
    print(f"ERROR: .env file not found at {env_path}")
    sys.exit(1)

# Load environment variables
print("\nLoading environment variables from .env...")
load_dotenv(env_path)
api_key = os.getenv('GEMINI_API_KEY')

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env file")
    sys.exit(1)

print(f"API Key found: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
print(f"Key length: {len(api_key)}")

# Print the exact key for debugging (be careful with this in production)
print(f"Full API key: {api_key}")

# Try to import Google Generative AI
try:
    print("\nImporting google.generativeai...")
    import google.generativeai as genai
    print("Successfully imported google.generativeai")
except ImportError as e:
    print(f"Error importing google.generativeai: {e}")
    print("Try installing it with: pip install google-generativeai")
    sys.exit(1)

# Configure API
try:
    print("\nConfiguring Gemini API...")
    genai.configure(api_key=api_key)
    print("API configured successfully")
except Exception as e:
    print(f"Error configuring API: {e}")
    sys.exit(1)

# Test API with a simple request
try:
    print("\nTesting Gemini API with a simple request...")
    model = genai.GenerativeModel('gemini-2.0-flash')
    print("Model created successfully")
    
    print("Generating content...")
    response = model.generate_content("Say hello world")
    
    print("Response received:")
    print(f"Response type: {type(response)}")
    print(f"Response text: {response.text}")
    
    print("\nTest completed successfully!")
except Exception as e:
    print(f"Error testing API: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 