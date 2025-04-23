import os
import sys
import json
import django
from django.core.wsgi import get_wsgi_application

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from core.utils import extract_json_from_text, prepare_continuation_prompt

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

def test_truncated_json():
    print("Testing the truncated JSON from the Wu.pdf error...")
    
    # Process the JSON using our extract_json_from_text function
    result = extract_json_from_text(truncated_json)
    
    # Check the results
    print(f"Extraction result type: {type(result)}")
    print(f"Is error present: {'error' in result}")
    
    if 'error' in result:
        print(f"Error message: {result['error']}")
    
    print(f"Is truncated: {result.get('is_truncated', False)}")
    
    if 'case_results' in result:
        print(f"Number of cases extracted: {len(result['case_results'])}")
        # Print the case numbers for verification
        case_numbers = [case.get('case_number', {}).get('value', 'unknown') for case in result['case_results']]
        print(f"Case numbers found: {case_numbers}")
    
    # Check if it's properly identified as truncated
    if result.get('is_truncated', False):
        print("✓ Correctly identified as a truncated response")
        
        # Check for truncation info
        if 'truncation_info' in result:
            print(f"Truncation info: {result['truncation_info']}")
            
            # Test continuation prompt generation
            if 'last_complete_case' in result.get('truncation_info', {}):
                original_prompt = "Please extract all cases from this PDF..."
                continuation_prompt = prepare_continuation_prompt(result, original_prompt)
                print(f"Continuation prompt generated (length: {len(continuation_prompt)})")
                print("First 100 chars of continuation prompt:", continuation_prompt[:100])
        else:
            print("❌ No truncation info found")
    else:
        print("❌ Failed to identify as truncated response")
        
    return result

def fix_json_issue():
    """Try to manually fix the specific JSON issue with the comment-like line"""
    
    # Replace the problematic comment line with proper JSON syntax
    fixed_json = truncated_json.replace('// ... (Cases 3-12 would follow here in a similar format)', 
                                       '{"value": "Comment indicating more cases would follow", "confidence": 0}')
    
    # Try with the fixed JSON
    print("\nTesting with manually fixed JSON...")
    result = extract_json_from_text(fixed_json)
    
    if 'error' in result:
        print(f"Error still present: {result['error']}")
    else:
        print("✓ Fixed JSON parsed successfully")
        if 'case_results' in result:
            print(f"Number of cases in fixed JSON: {len(result['case_results'])}")
    
    return result

def fix_json_by_trimming():
    """Fix the JSON by trimming at the problematic point"""
    
    # Find the position of the problematic line
    problem_position = truncated_json.find('//')
    
    if problem_position > 0:
        # Get the content up to the problematic line
        content_before = truncated_json[:problem_position].rstrip()
        
        # Check if it ends with a comma that needs to be removed
        if content_before.endswith(','):
            content_before = content_before[:-1]
        
        # Build a valid JSON with proper closing brackets
        clean_json = content_before + "\n  ]\n}\n```"
        
        # Try with the trimmed JSON
        print("\nTesting with trimmed JSON...")
        result = extract_json_from_text(clean_json)
        
        if 'error' in result:
            print(f"Error still present: {result['error']}")
            
            # Print the JSON for inspection
            print("\nDebug - Clean JSON content (first 100 chars):")
            print(clean_json[:100])
            print("Last 50 chars:")
            print(clean_json[-50:])
        else:
            print("✓ Trimmed JSON parsed successfully")
            if 'case_results' in result:
                print(f"Number of cases in trimmed JSON: {len(result['case_results'])}")
        
        return result
    else:
        print("Couldn't find the problematic position")
        return None

if __name__ == "__main__":
    # First test with the original truncated JSON
    original_result = test_truncated_json()
    
    if 'error' in original_result:
        # Try with different fixing approaches
        fix_json_issue()
        fix_json_by_trimming() 