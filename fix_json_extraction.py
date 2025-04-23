import os
import sys
import json
import re
import django
from django.core.wsgi import get_wsgi_application

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from core.utils import extract_json_from_text

def enhanced_json_cleaning(text):
    """
    Enhanced cleaning for JSON responses that may contain comment-like text
    or other invalid JSON syntax.
    
    Args:
        text (str): The raw JSON or code block containing JSON
        
    Returns:
        str: Cleaned JSON string
    """
    # First, check if this is a code block and extract just the JSON part
    code_block_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
    code_blocks = re.findall(code_block_pattern, text)
    if code_blocks:
        text = code_blocks[0]
    
    # Remove any JavaScript-style comments
    # First, remove single line comments (// ...)
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    
    # Remove multi-line comments (/* ... */)
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    
    # Fix trailing commas before closing brackets (common JSON error)
    text = re.sub(r',(\s*[\]}])', r'\1', text)
    
    # Remove empty lines
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
    
    # Ensure we have balanced braces
    open_braces = text.count('{')
    close_braces = text.count('}')
    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    if open_brackets > close_brackets:
        text += ']' * (open_brackets - close_brackets)
    
    return text

def enhanced_extract_json_from_text(text):
    """
    An enhanced version of extract_json_from_text that applies additional
    cleaning to improve JSON parsing success rate.
    
    Args:
        text (str): Raw text response from the model
        
    Returns:
        dict: Extracted and validated JSON data
    """
    # First try the original method
    result = extract_json_from_text(text)
    
    # If there was an error, try our enhanced cleaning
    if 'error' in result:
        print("Original extraction failed with error: " + result['error'])
        print("Attempting enhanced JSON cleaning...")
        
        # Apply enhanced cleaning
        cleaned_text = enhanced_json_cleaning(text)
        
        # Try parsing again
        try:
            cleaned_result = json.loads(cleaned_text)
            print("Successfully parsed JSON after enhanced cleaning")
            
            # If successful, add a note that this was repaired
            if 'case_results' in cleaned_result:
                if not isinstance(cleaned_result['case_results'], list):
                    print("Warning: case_results is not a list")
                    return result
                
                cleaned_result['json_repaired'] = True
                cleaned_result['is_truncated'] = result.get('is_truncated', False)
                
                print(f"Extracted {len(cleaned_result['case_results'])} cases after repair")
                return cleaned_result
            else:
                print("Cleaned JSON doesn't contain case_results")
                return result
                
        except json.JSONDecodeError as e:
            print(f"Enhanced cleaning still failed: {str(e)}")
            return result
    
    return result

def patch_utils_module():
    """
    Shows how you could patch the core.utils module to improve JSON processing
    """
    print("To improve the JSON extraction in the core module, you would:")
    print("1. Add the enhanced_json_cleaning function to core/utils.py")
    print("2. Modify extract_json_from_text to use it when regular parsing fails")
    
    print("\nHere's the patch you would apply to extract_json_from_text:")
    patch = """
    # Add at the top with other imports:
    import re
    
    # Add this function:
    def _clean_json_response(text):
        \"\"\"
        Enhanced cleaning for JSON responses that may contain comment-like text
        or other invalid JSON syntax.
        \"\"\"
        # Remove any JavaScript-style comments
        # First, remove single line comments (// ...)
        text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
        
        # Remove multi-line comments (/* ... */)
        text = re.sub(r'/\\*[\\s\\S]*?\\*/', '', text)
        
        # Fix trailing commas before closing brackets (common JSON error)
        text = re.sub(r',(\\s*[\\]}])', r'\\1', text)
        
        # Remove empty lines
        text = re.sub(r'^\\s*$', '', text, flags=re.MULTILINE)
        
        # Ensure we have balanced braces
        open_braces = text.count('{')
        close_braces = text.count('}')
        if open_braces > close_braces:
            text += '}' * (open_braces - close_braces)
        
        open_brackets = text.count('[')
        close_brackets = text.count(']')
        if open_brackets > close_brackets:
            text += ']' * (open_brackets - close_brackets)
        
        return text
    
    # In extract_json_from_text, after extracting from code blocks:
    text = _clean_json_response(text)
    """
    
    print(patch)

def test_with_wu_json():
    """Test the enhanced extraction with the Wu.pdf JSON"""
    print("\nTesting with the problematic Wu.pdf JSON:")
    
    # The truncated JSON from the error message
    truncated_json = '''```json
    {
      "case_results": [
        {
          "case_number": {
            "value": "1",
            "confidence": 100
          },
          "age": {
            "value": 62,
            "confidence": 100
          },
          "gender": {
            "value": "F",
            "confidence": 100
          },
          "vignette": {
            "value": "A 62-year-old female presented with a 5-month history of bilateral leg numbness and weakness, and difficulty urinating. Preoperative imaging suggested metastasis. The tumor was located at T7-8.",
            "confidence": 100
          },
          "signs": {
            "value": "Bilateral leg numbness and weakness, difficulty urinating.",
            "confidence": 100
          },
          "recurrence": {
            "value": "no",
            "confidence": 100
          },
          "time_to_recurrence": {
            "value": "N/A",
            "confidence": 100
          },
          "additional_treatment": {
            "value": "None",
            "confidence": 100
          },
          "complications": {
            "value": "None reported",
            "confidence": 100
          },
          "imaging_modality": {
            "value": "MRI",
            "confidence": 100
          },
          "tissue_infiltration": {
            "value": "Extradural, en plaque growth along dura",
            "confidence": 100
          },
          "simpson_grade": {
            "value": "I",
            "confidence": 100
          },
          "resection_extent": {
            "value": "GTR",
            "confidence": 100
          },
          "comments": {
            "value": "Preoperative JOA score 12, last follow-up JOA score 15, 34 months follow-up.",
            "confidence": 100
          },
          "tumor_location": {
            "value": "T7-8",
            "confidence": 100
          },
          "bone_reaction": {
            "value": "N/A",
            "confidence": 80
          },
          "dural_enhancement": {
            "value": "yes",
            "confidence": 100
          },
          "sx": {
            "value": "Bilateral leg numbness and weakness, difficulty urinating.",
            "confidence": 100
          },
          "histological_type": {
            "value": "Psammomatous",
            "confidence": 100
          },
          "who_grade": {
            "value": "I",
            "confidence": 90
          },
          "dural_infiltration": {
            "value": "yes",
            "confidence": 100
          }
        },
        {
          "case_number": {
            "value": "2",
            "confidence": 100
          },
          "age": {
            "value": 42,
            "confidence": 100
          },
          "gender": {
            "value": "M",
            "confidence": 100
          },
          "vignette": {
            "value": "A 42-year-old male presented with a 1-month history of bilateral upper limb numbness and weakness. Preoperative imaging suggested cavernous angioma. The tumor was located at C3-5.",
            "confidence": 100
          },
          "signs": {
            "value": "Bilateral upper limb numbness and weakness.",
            "confidence": 100
          },
          "recurrence": {
            "value": "no",
            "confidence": 100
          },
          "time_to_recurrence": {
            "value": "N/A",
            "confidence": 100
          },
          "additional_treatment": {
            "value": "None",
            "confidence": 100
          },
          "complications": {
            "value": "None reported",
            "confidence": 100
          },
          "imaging_modality": {
            "value": "MRI",
            "confidence": 100
          },
          "tissue_infiltration": {
            "value": "Extradural, en plaque growth along dura",
            "confidence": 100
          },
          "simpson_grade": {
            "value": "N/A",
            "confidence": 80
          },
          "resection_extent": {
            "value": "STR",
            "confidence": 100
          },
          "comments": {
            "value": "Preoperative JOA score 10, last follow-up JOA score 16, 112 months follow-up.",
            "confidence": 100
          },
          "tumor_location": {
            "value": "C3-5",
            "confidence": 100
          },
          "bone_reaction": {
            "value": "N/A",
            "confidence": 80
          },
          "dural_enhancement": {
            "value": "yes",
            "confidence": 100
          },
          "sx": {
            "value": "Bilateral upper limb numbness and weakness.",
            "confidence": 100
          },
          "histological_type": {
            "value": "Psammomatous",
            "confidence": 100
          },
          "who_grade": {
            "value": "I",
            "confidence": 90
          },
          "dural_infiltration": {
            "value": "yes",
            "confidence": 100
          }
        },


         // ... (Cases 3-12 would follow here in a similar format)
      ]
    }
    ```'''
    
    # 1. First with regular extraction
    print("\nRegular extraction result:")
    regular_result = extract_json_from_text(truncated_json)
    if 'error' in regular_result:
        print(f"Error: {regular_result['error']}")
    else:
        print("Succeeded without error")
    
    # 2. With enhanced extraction
    print("\nEnhanced extraction result:")
    enhanced_result = enhanced_extract_json_from_text(truncated_json)
    if 'error' in enhanced_result:
        print(f"Error: {enhanced_result['error']}")
    else:
        print(f"Succeeded! Found {len(enhanced_result['case_results'])} cases")
        case_numbers = [case.get('case_number', {}).get('value', 'unknown') for case in enhanced_result['case_results']]
        print(f"Case numbers: {case_numbers}")
    
    # 3. Just do cleanup directly
    print("\nDirect cleanup test:")
    cleaned_json = enhanced_json_cleaning(truncated_json)
    try:
        parsed = json.loads(cleaned_json)
        if 'case_results' in parsed:
            print(f"Direct cleanup succeeded! Found {len(parsed['case_results'])} cases")
            case_numbers = [case.get('case_number', {}).get('value', 'unknown') for case in parsed['case_results']]
            print(f"Case numbers: {case_numbers}")
        else:
            print("Parsing succeeded but no case_results found")
    except json.JSONDecodeError as e:
        print(f"Cleanup failed: {str(e)}")
        print(f"First 100 chars of cleaned JSON: {cleaned_json[:100]}")
        print(f"Last 50 chars of cleaned JSON: {cleaned_json[-50:]}")

if __name__ == "__main__":
    print("=== Testing Enhanced JSON Extraction ===\n")
    test_with_wu_json()
    print("\n=== Patch Instructions ===")
    patch_utils_module() 