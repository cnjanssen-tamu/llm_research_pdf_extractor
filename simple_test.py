#!/usr/bin/env python3
"""
Simple test for the Gemini API key.
"""

import os
import sys

# Print Python version
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# Check for .env file
env_file = os.path.join(os.getcwd(), '.env')
print(f"Checking for .env file at: {env_file}")
if os.path.exists(env_file):
    print(".env file exists")
    
    # Manually read the .env file
    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                api_key = line.strip().split('=', 1)[1]
                if api_key.startswith('"') and api_key.endswith('"'):
                    api_key = api_key[1:-1]
                if api_key.startswith("'") and api_key.endswith("'"):
                    api_key = api_key[1:-1]
                print(f"Found API key: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
                break
        else:
            print("No API key found in .env file")
else:
    print(".env file not found")

# Try to import required packages
try:
    print("\nImporting google.generativeai...")
    import google.generativeai as genai
    print("Successfully imported google.generativeai")
except ImportError as e:
    print(f"Error importing google.generativeai: {e}")
    print("Try installing it with: pip install google-generativeai")
    sys.exit(1)

# Try to configure the API
try:
    print("\nConfiguring API...")
    genai.configure(api_key=api_key)
    print("API configured successfully")
except Exception as e:
    print(f"Error configuring API: {e}")
    sys.exit(1)

# Try to get model list
try:
    print("\nGetting model list...")
    models = genai.list_models()
    print(f"Found {len(list(models))} models:")
    for m in models:
        if 'gemini' in m.name.lower():
            print(f"  - {m.name}")
except Exception as e:
    print(f"Error getting model list: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try to create a model
try:
    print("\nCreating model...")
    model = genai.GenerativeModel('gemini-2.0-flash')
    print("Model created successfully")
except Exception as e:
    print(f"Error creating model: {e}")
    sys.exit(1)

# Try to generate content
try:
    print("\nGenerating content...")
    response = model.generate_content("Hello, how are you?")
    print("Content generated successfully")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error generating content: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTest completed successfully!") 