"""
Direct test for the Perplexity API without using Django.
This will help isolate any issues with the API call itself.
"""
import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv('PERPLEXITY_API_KEY')
if not api_key:
    print("ERROR: PERPLEXITY_API_KEY not found in environment variables")
    exit(1)

print(f"Using API key: {api_key[:5]}...{api_key[-4:]}")

# Define API endpoint
api_url = "https://api.perplexity.ai/chat/completions"

# Define headers
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Define a simple test message
test_data = {
    "model": "sonar-pro",
    "messages": [
        {"role": "system", "content": "You are a helpful medical research assistant."},
        {"role": "user", "content": "Provide a brief summary of glioblastoma multiforme with 1-2 recent citations."}
    ],
    "temperature": 0.7,
    "max_tokens": 4000
}

print("\n======== Making direct API call to Perplexity ========")
print(f"URL: {api_url}")
print(f"Headers: Authorization=Bearer {api_key[:5]}..., Content-Type=application/json")
print(f"Request data: {json.dumps(test_data, indent=2)}")

try:
    # Make the API call
    response = requests.post(api_url, headers=headers, data=json.dumps(test_data))
    
    # Check status code
    print(f"\nResponse status code: {response.status_code}")
    
    if response.status_code == 200:
        # Success
        result = response.json()
        print("\n======== Success! Response: ========")
        
        # Extract the text from the first choice
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            print(f"\nResponse content:\n{content}")
        else:
            print("Warning: Unexpected response format")
            print(json.dumps(result, indent=2))
    else:
        # Error
        print("\n======== Error Response: ========")
        print(f"Status: {response.status_code}")
        try:
            error_data = response.json()
            print(f"Error message: {json.dumps(error_data, indent=2)}")
        except:
            print(f"Raw error text: {response.text}")
        
        if response.status_code == 401:
            print("\nThis is an authentication error. Your API key might be invalid or expired.")
            print("Please check the Perplexity website to verify your API key is still valid.")
        
except Exception as e:
    print(f"Exception occurred: {str(e)}") 