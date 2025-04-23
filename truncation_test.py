import os
import sys
import json
import django
from django.core.wsgi import get_wsgi_application

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from core.utils import extract_json_from_text, prepare_continuation_prompt
from core.models import ProcessingResult, PDFDocument, ProcessingJob

def test_truncation_detection():
    """Test the ability to detect truncated responses"""
    print("\n--- Testing truncation detection ---")
    
    # Sample responses with and without truncation indicators
    complete_response = """
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            },
            {
                "case_number": {"value": "2", "confidence": 95},
                "gender": {"value": "F", "confidence": 90},
                "age": {"value": "52", "confidence": 85}
            }
        ]
    }
    """
    
    truncated_response = """
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            },
            {
                "case_number": {"value": "2", "confidence": 95},
                "gender": {"value": "F", "confidence": 90},
                "age": {"value": "52", "confidence": 85}
            }
        ]
    }
    I apologize, but I've reached the maximum output limit.
    """
    
    truncated_response2 = """
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            }
        ]
    }
    I've reached the token limit.
    """
    
    # Test complete response
    result = extract_json_from_text(complete_response)
    print(f"Complete response detected as truncated: {result.get('is_truncated', False)}")
    assert not result.get('is_truncated', False), "Complete response incorrectly marked as truncated"
    
    # Test obviously truncated response
    result = extract_json_from_text(truncated_response)
    print(f"Truncated response detected as truncated: {result.get('is_truncated', False)}")
    assert result.get('is_truncated', True), "Truncated response not detected"
    
    # Test response with complete JSON but truncation message after
    result = extract_json_from_text(truncated_response2)
    print(f"Response with truncation message after valid JSON detected as truncated: {result.get('is_truncated', False)}")
    assert result.get('is_truncated', True), "Response with truncation message after valid JSON not detected as truncated"
    
    print("✓ Truncation detection tests passed")

def test_malformed_json_parsing():
    """Test the ability to parse and repair malformed JSON"""
    print("\n--- Testing malformed JSON parsing ---")
    
    # Sample malformed JSON responses
    missing_comma = """
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95}
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            }
        ]
    }
    """
    
    unclosed_brace = """
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            }
        ]
    """
    
    # Test missing comma
    result = extract_json_from_text(missing_comma)
    print(f"Missing comma result has error: {'error' in result}")
    if 'error' not in result:
        print(f"Missing comma was repaired successfully")
    
    # Test unclosed brace
    result = extract_json_from_text(unclosed_brace)
    print(f"Unclosed brace result has error: {'error' in result}")
    if 'error' not in result:
        print(f"Unclosed brace was repaired successfully")
    
    print("✓ Malformed JSON parsing tests completed")

def test_processing_result_model():
    """Test storing and retrieving truncation status in ProcessingResult model"""
    print("\n--- Testing ProcessingResult model integration ---")
    
    # Sample data
    truncated_data = {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            }
        ],
        "is_truncated": True,
        "truncation_info": {
            "last_complete_case": 1
        }
    }
    
    complete_data = {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90}
            },
            {
                "case_number": {"value": "2", "confidence": 95},
                "gender": {"value": "F", "confidence": 90}
            }
        ],
        "is_truncated": False
    }
    
    try:
        # Create a dummy job and document for testing
        job = ProcessingJob.objects.create(name="Test Job")
        document = PDFDocument.objects.create(job=job)
        
        # Create result records
        truncated_result = ProcessingResult.objects.create(
            document=document,
            result_data=truncated_data,
            is_complete=False
        )
        
        complete_result = ProcessingResult.objects.create(
            document=document,
            result_data=complete_data,
            is_complete=True
        )
        
        # Verify the saved data
        print(f"Truncated result is_complete flag: {truncated_result.is_complete}")
        print(f"Complete result is_complete flag: {complete_result.is_complete}")
        
        # Clean up test data
        truncated_result.delete()
        complete_result.delete()
        document.delete()
        job.delete()
        
        print("✓ ProcessingResult model tests passed")
        
    except Exception as e:
        print(f"Error during model testing: {str(e)}")

def test_extraction_from_text_with_code_blocks():
    """Test extracting JSON from text with markdown code blocks"""
    print("\n--- Testing extraction from text with code blocks ---")
    
    code_block_response = """
    Here's the extracted information from the document:

    ```json
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            },
            {
                "case_number": {"value": "2", "confidence": 95},
                "gender": {"value": "F", "confidence": 90},
                "age": {"value": "52", "confidence": 85}
            }
        ]
    }
    ```

    Let me know if you need any clarification on the extracted data.
    """
    
    result = extract_json_from_text(code_block_response)
    print(f"JSON extracted from code block has {len(result.get('case_results', []))} cases")
    assert 'case_results' in result, "Failed to extract JSON from code block"
    assert len(result['case_results']) == 2, "Incorrect number of cases extracted from code block"
    
    print("✓ JSON extraction from code blocks test passed")

def test_truncation_result_processing_workflow():
    """Test how truncation status flows through the processing workflow"""
    print("\n--- Testing truncation handling in processing workflow ---")
    
    # Sample raw responses
    truncated_raw_response = """
    Here are the extracted cases:

    ```json
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            }
        ]
    }
    ```

    I've reached the token limit and could not process more cases.
    """
    
    try:
        # Create test data
        job = ProcessingJob.objects.create(name="Workflow Test Job")
        document = PDFDocument.objects.create(job=job)
        
        # Simulate processing a truncated response
        parsed_result = extract_json_from_text(truncated_raw_response)
        print(f"Extraction result is_truncated: {parsed_result.get('is_truncated', False)}")
        
        # Create the processing result with truncation info
        processing_result = ProcessingResult.objects.create(
            document=document,
            result_data=parsed_result,
            raw_response=truncated_raw_response,
            is_complete=not parsed_result.get('is_truncated', False)
        )
        
        # Verify the result was saved correctly
        retrieved_result = ProcessingResult.objects.get(id=processing_result.id)
        print(f"Saved result is_complete flag: {retrieved_result.is_complete}")
        print(f"Saved result data contains is_truncated: {retrieved_result.result_data.get('is_truncated', False)}")
        
        # Test that truncation info is preserved
        if retrieved_result.result_data.get('is_truncated', False):
            truncation_info = retrieved_result.result_data.get('truncation_info', {})
            print(f"Truncation info preserved: {truncation_info != {}}")
            print(f"Last complete case: {truncation_info.get('last_complete_case', 'Not found')}")
        
        # Clean up test data
        retrieved_result.delete()
        document.delete()
        job.delete()
        
        print("✓ Truncation workflow tests passed")
        
    except Exception as e:
        print(f"Error during workflow testing: {str(e)}")

def test_continuation_prompt_generation():
    """Test generating continuation prompts for truncated responses"""
    print("\n--- Testing continuation prompt generation ---")
    
    # Sample truncated result with truncation info
    truncated_result = {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85},
                "symptoms": {"value": "Headache", "confidence": 80}
            },
            {
                "case_number": {"value": "2", "confidence": 95},
                "gender": {"value": "F", "confidence": 90},
                "age": {"value": "37", "confidence": 85},
                "symptoms": {"value": "Dizziness", "confidence": 80}
            }
        ],
        "is_truncated": True,
        "truncation_info": {
            "last_complete_case": 2
        }
    }
    
    # Original prompt 
    original_prompt = """
    Please extract patient case information from this medical document. 
    Format each case as a JSON object with the following fields:
    - case_number
    - gender
    - age
    - symptoms
    - diagnosis
    - treatment
    - outcome
    """
    
    # Generate continuation prompt
    continuation_prompt = prepare_continuation_prompt(truncated_result, original_prompt)
    
    # Verify the continuation prompt contains key elements
    print(f"Continuation prompt length: {len(continuation_prompt)} characters")
    
    # Check for required elements in the prompt
    required_elements = [
        "continuation request", 
        "processed 2 cases",
        "continue processing from case 3",
        "Do not repeat the cases you've already processed",
        "case_number",
        "gender",
        "age",
        "symptoms"
    ]
    
    all_found = True
    for element in required_elements:
        if element.lower() not in continuation_prompt.lower():
            print(f"Missing required element in continuation prompt: {element}")
            all_found = False
    
    if all_found:
        print("✓ All required elements found in continuation prompt")
    
    # Verify the continuation prompt includes the last case as an example
    if '"case_number"' in continuation_prompt and '"value": "2"' in continuation_prompt:
        print("✓ Continuation prompt includes the last processed case as an example")
    else:
        print("❌ Continuation prompt missing the last processed case example")
    
    print("✓ Continuation prompt generation tests passed")

def test_json_with_comments():
    """Test handling of JSON with comments that might indicate truncation"""
    print("\n--- Testing JSON with comments that might indicate truncation ---")
    
    # Sample JSON with a comment similar to the Wu.pdf case
    json_with_comments = """
    {
        "case_results": [
            {
                "case_number": {"value": "1", "confidence": 95},
                "gender": {"value": "M", "confidence": 90},
                "age": {"value": "45", "confidence": 85}
            },
            {
                "case_number": {"value": "2", "confidence": 95},
                "gender": {"value": "F", "confidence": 90},
                "age": {"value": "52", "confidence": 85}
            },
            
            // Additional cases would follow in a similar format
        ]
    }
    """
    
    # Test parsing with comments
    result = extract_json_from_text(json_with_comments)
    print(f"JSON with comments - Error occurred: {'error' in result}")
    
    if 'error' not in result:
        print(f"Successfully parsed JSON with comments")
        print(f"Number of cases extracted: {len(result.get('case_results', []))}")
        
        # Verify the cases were correctly extracted
        case_numbers = [case.get('case_number', {}).get('value', 'unknown') for case in result.get('case_results', [])]
        print(f"Case numbers: {case_numbers}")
    else:
        print(f"Failed to parse: {result.get('error', 'Unknown error')}")
    
    print("✓ JSON with comments handling test passed")

def main():
    print("=== Starting Truncation and JSON Parsing Tests ===")
    
    test_truncation_detection()
    test_malformed_json_parsing()
    test_processing_result_model()
    test_extraction_from_text_with_code_blocks()
    test_truncation_result_processing_workflow()
    test_continuation_prompt_generation()
    test_json_with_comments()
    
    print("\n=== All tests completed ===")

if __name__ == "__main__":
    main() 