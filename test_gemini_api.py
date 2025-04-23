import os
from dotenv import load_dotenv
import sys

print("Step 1: Loading environment variables")
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')

if not api_key:
    print("Error: No GEMINI_API_KEY found in .env file")
    sys.exit(1)

print(f"API Key found: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")

try:
    print("Step 2: Importing Google Generative AI")
    import google.generativeai as genai
    print("Step 3: Configuring API")
    genai.configure(api_key=api_key)
    
    print("Step 4: Listing available models")
    for m in genai.list_models():
        print(f"Model: {m.name}")
    
    print("Step 5: Creating Gemini model")
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    print("Step 6: Making a simple API call")
    response = model.generate_content("Say hello world")
    
    print("Step 7: Response received")
    print(f"Response type: {type(response)}")
    print(f"Response text: {response.text}")
    
    print("Test completed successfully!")
    
except Exception as e:
    print(f"Error occurred: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc() 