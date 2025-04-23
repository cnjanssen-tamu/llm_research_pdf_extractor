#!/usr/bin/env python
"""
Script to test how the Gemini API processes a PDF and returns JSON
This will help identify if duplication occurs at the API response level
"""

import os
import sys
import json
import base64
from dotenv import load_dotenv
import pandas as pd

# Load environment variables to get API key
print("Loading environment variables...")
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("Error: GEMINI_API_KEY not found in environment variables")
    sys.exit(1)

print(f"API key loaded: {api_key[:4]}...{api_key[-4:]}")

# Import Google Generative AI
try:
    import google.generativeai as genai
    print("Successfully imported google.generativeai")
except ImportError as e:
    print(f"Error importing google.generativeai: {e}")
    print("Install with: pip install google-generativeai")
    sys.exit(1)

# Configure the API
genai.configure(api_key=api_key)

def generate_prompt():
    """Generate a simplified prompt for extracting case data"""
    prompt = """
You are a medical data extractor. Extract patient case information from this medical document into a structured format.

For each case found in the document:
- Extract all available information
- Focus on patient details, symptoms, treatments, and outcomes

Return the data as a JSON object with this structure:
{
  "case_results": [
    {
      "case_number": {"value": "1", "confidence": 100},
      "age": {"value": "patient age", "confidence": confidence_score},
      "gender": {"value": "patient gender", "confidence": confidence_score},
      "symptoms": {"value": "symptoms description", "confidence": confidence_score},
      "treatment": {"value": "treatment details", "confidence": confidence_score},
      "outcome": {"value": "patient outcome", "confidence": confidence_score}
    }
    // Additional cases if found
  ]
}

Important instructions:
1. Each case should be a separate object in the case_results array
2. Use empty strings for missing values
3. Assign confidence scores from 0-100
4. Provide detailed information when available
5. Only include case_results in your response (no other text)
"""
    return prompt

def process_pdf(pdf_path):
    """Process a PDF file with Gemini API and return structured data"""
    print(f"Processing PDF: {pdf_path}")
    
    # Read the PDF file
    try:
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
    except Exception as e:
        print(f"Error reading PDF file: {e}")
        return None
    
    # Encode the PDF data
    encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')
    
    # Get prompt template
    prompt = generate_prompt()
    
    # Initialize the model
    print("Initializing Gemini model...")
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        print(f"Error initializing model: {e}")
        return None
    
    # Call Gemini API
    print("Calling Gemini API...")
    try:
        response = model.generate_content([
            {"mime_type": "application/pdf", "data": encoded_pdf},
            prompt
        ])
        print("API call successful")
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None
    
    # Extract JSON from response
    print("\nRaw response:")
    print("-" * 80)
    print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
    print("-" * 80)
    
    # Try to extract JSON
    json_data = extract_json_from_text(response.text)
    if not json_data:
        print("Failed to extract valid JSON from response")
        return None
    
    # Parse the JSON
    try:
        data = json.loads(json_data)
        print("\nSuccessfully parsed JSON data")
        return data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"Invalid JSON: {json_data[:200]}...")
        return None

def extract_json_from_text(text):
    """Extract JSON from text that might contain markdown or other content"""
    # Remove markdown code blocks if present
    text = text.replace('```json', '').replace('```', '').strip()
    
    # Find the start and end of the JSON object
    start_idx = text.find('{')
    end_idx = text.rfind('}') + 1
    
    if start_idx >= 0 and end_idx > start_idx:
        return text[start_idx:end_idx]
    return None

def analyze_results(data):
    """Analyze the results to check for duplicates and structure"""
    if not data or 'case_results' not in data:
        print("No case results found in the data")
        return
    
    cases = data['case_results']
    print(f"\nFound {len(cases)} cases in the response")
    
    # Check if there are duplicate cases
    case_hashes = set()
    duplicates = []
    
    for i, case in enumerate(cases):
        # Create a hash of the case to detect duplicates
        case_str = json.dumps(case, sort_keys=True)
        case_hash = hash(case_str)
        
        if case_hash in case_hashes:
            duplicates.append(i)
        else:
            case_hashes.add(case_hash)
    
    if duplicates:
        print(f"Found {len(duplicates)} duplicate cases at indices: {duplicates}")
    else:
        print("No duplicates found in the cases")
    
    # Print summary of each case
    for i, case in enumerate(cases):
        print(f"\nCase {i+1} summary:")
        for key, value in case.items():
            if isinstance(value, dict) and 'value' in value:
                val = value['value']
                conf = value.get('confidence', 'N/A')
                display_val = (val[:50] + '...') if isinstance(val, str) and len(val) > 50 else val
                print(f"  {key}: {display_val} (confidence: {conf})")

def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = '/Users/chrisjanssen/Insync/cnjanssen@tamu.edu/Google Drive - Shared with me/ExDM/2. Crene.pdf'
        
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    # Process the PDF and get results
    results = process_pdf(pdf_path)
    
    if results:
        # Analyze the results
        analyze_results(results)
        
        # Save results to a file for reference
        output_file = 'gemini_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved results to {output_file}")

if __name__ == "__main__":
    main() 