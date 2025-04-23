import os
import sys
import json
import django
from django.core.wsgi import get_wsgi_application

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from core.utils import extract_json_from_text

def test_with_problematic_json():
    """Test various problematic JSON formats to ensure our parser can handle them"""
    
    # Test case 1: JSON with comments
    print("\n===== Test Case 1: JSON with comments =====")
    json_with_comments = '''```json
    {
      "case_results": [
        {
          "case_number": {"value": "1", "confidence": 95},
          "gender": {"value": "M", "confidence": 90},
          // This is a comment about age
          "age": {"value": "45", "confidence": 85}
        },
        {
          "case_number": {"value": "2", "confidence": 95},
          "gender": {"value": "F", "confidence": 90},
          "age": {"value": "52", "confidence": 85}
          /* This is a multi-line comment
             about the second case */
        }
      ]
    }
    ```'''
    
    result = extract_json_from_text(json_with_comments)
    print(f"Success: {'error' not in result}")
    if 'case_results' in result:
        print(f"Number of cases: {len(result['case_results'])}")
    
    # Test case 2: JSON with trailing commas
    print("\n===== Test Case 2: JSON with trailing commas =====")
    json_with_trailing_commas = '''```json
    {
      "case_results": [
        {
          "case_number": {"value": "1", "confidence": 95},
          "gender": {"value": "M", "confidence": 90},
          "age": {"value": "45", "confidence": 85},
        },
        {
          "case_number": {"value": "2", "confidence": 95},
          "gender": {"value": "F", "confidence": 90},
          "age": {"value": "52", "confidence": 85},
        },
      ]
    }
    ```'''
    
    result = extract_json_from_text(json_with_trailing_commas)
    print(f"Success: {'error' not in result}")
    if 'case_results' in result:
        print(f"Number of cases: {len(result['case_results'])}")
    
    # Test case 3: JSON that is truly truncated in the middle of a case
    print("\n===== Test Case 3: Truly truncated JSON =====")
    truly_truncated_json = '''```json
    {
      "case_results": [
        {
          "case_number": {"value": "1", "confidence": 95},
          "gender": {"value": "M", "confidence": 90},
          "age": {"value": "45", "confidence": 85}
        },
        {
          "case_number": {"value": "2", "confidence": 95},
          "gender": {"value": "F",
    ```
    I apologize, but I've reached the maximum output limit.'''
    
    result = extract_json_from_text(truly_truncated_json)
    print(f"Success: {'error' not in result}")
    print(f"Detected as truncated: {result.get('is_truncated', False)}")
    if 'case_results' in result:
        print(f"Number of cases: {len(result['case_results'])}")
    
    # Test case 4: JSON with mixed issues (comments, truncation indicator, trailing commas)
    print("\n===== Test Case 4: JSON with mixed issues =====")
    mixed_issues_json = '''```json
    {
      "case_results": [
        {
          "case_number": {"value": "1", "confidence": 95},
          "gender": {"value": "M", "confidence": 90},
          "age": {"value": "45", "confidence": 85},
        },
        // Case 2 has some interesting features
        {
          "case_number": {"value": "2", "confidence": 95},
          "gender": {"value": "F", "confidence": 90},
          "age": {"value": "52", "confidence": 85},
        },
      ]
    }
    ```
    I've reached the token limit and couldn't continue.'''
    
    result = extract_json_from_text(mixed_issues_json)
    print(f"Success: {'error' not in result}")
    print(f"Detected as truncated: {result.get('is_truncated', False)}")
    if 'case_results' in result:
        print(f"Number of cases: {len(result['case_results'])}")
    
    # Test case 5: Real-world example from Wu.pdf with "more cases would follow" comment
    print("\n===== Test Case 5: Wu.pdf JSON with 'more cases would follow' comment =====")
    wu_json = '''```json
    {
      "case_results": [
        {
          "case_number": {"value": "1", "confidence": 100},
          "age": {"value": 62, "confidence": 100},
          "gender": {"value": "F", "confidence": 100}
        },
        {
          "case_number": {"value": "2", "confidence": 100},
          "age": {"value": 42, "confidence": 100},
          "gender": {"value": "M", "confidence": 100}
        },
        
        // ... (Cases 3-12 would follow here in a similar format)
      ]
    }
    ```'''
    
    result = extract_json_from_text(wu_json)
    print(f"Success: {'error' not in result}")
    print(f"Detected as truncated: {result.get('is_truncated', False)}")
    if 'case_results' in result:
        print(f"Number of cases: {len(result['case_results'])}")
        case_numbers = [case.get('case_number', {}).get('value', 'unknown') for case in result['case_results']]
        print(f"Case numbers: {case_numbers}")

if __name__ == "__main__":
    print("=== Testing Advanced JSON Handling ===")
    test_with_problematic_json() 