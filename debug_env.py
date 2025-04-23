import os
import sys
from dotenv import load_dotenv

print("Debugging .env file loading")
print("--------------------------")

# Check if .env file exists
print(f"Does .env file exist? {os.path.exists('.env')}")

# Load environment variables
print("Loading .env file...")
load_dotenv()

# Check if Perplexity API key is loaded
perplexity_key = os.getenv('PERPLEXITY_API_KEY')
print(f"PERPLEXITY_API_KEY loaded: {bool(perplexity_key)}")
print(f"Key value: {perplexity_key}")
print(f"Key length: {len(perplexity_key) if perplexity_key else 0}")

# Check if it matches the placeholder
if perplexity_key == "your-perplexity-api-key-here":
    print("ERROR: You're still using the placeholder value!")
    print("Update the .env file with your actual Perplexity API key")

# Check other environment variables for comparison
gemini_key = os.getenv('GEMINI_API_KEY')
print(f"GEMINI_API_KEY loaded: {bool(gemini_key)}")
print(f"Gemini key length: {len(gemini_key) if gemini_key else 0}")

print("\nEnvironment variables in current process:")
for key, value in os.environ.items():
    if 'KEY' in key:
        # Show only the first few characters for security
        masked_value = value[:4] + "..." if value else "None"
        print(f"{key}={masked_value}")

print("\nTIP: Make sure your Perplexity API key:")
print("1. Starts with 'pplx-'")
print("2. Is a long string of characters (typically 40+ characters)")
print("3. Was copied correctly without any extra spaces")
print("4. Was saved correctly in the .env file") 