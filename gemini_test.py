"""
Simple test script for calling Gemini API with structured output for reference extraction.
"""

import os
import json
import base64
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from core.reference_schema import generate_reference_schema

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gemini_test')

def test_function_calling_without_pdf():
    """
    Test A: Function Calling without PDF
    Test if function calling works without PDF content
    """
    try:
        # Load env vars and API key
        load_dotenv(override=True)
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            return
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Configure model
        generation_config = {
            "max_output_tokens": 8192,
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
        }
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Get reference schema
        reference_schema = generate_reference_schema()
        logger.debug(f"Schema: {json.dumps(reference_schema, indent=2)}")
        
        # Define tools with function for structured output
        tools = [{
            "function_declarations": [{
                "name": "extract_references",
                "description": "Extract bibliographic references from academic documents",
                "parameters": reference_schema
            }]
        }]
        
        # Create a prompt that asks for sample reference data without PDF
        prompt = """
        Generate sample bibliographic references using the extract_references function.
        
        YOU MUST USE THE extract_references FUNCTION to return structured data.
        DO NOT return the references as text or in any other format than through the function call.
        
        Please generate 5 sample academic references covering different source types (journal, book, website, conference, etc.).
        Each reference should include:
        - Full citation text
        - Source type classification
        - Authors
        - Title
        - Source name
        - Publication year
        - Other metadata where applicable
        
        YOU MUST USE THE FUNCTION CALL to return your response.
        """
        
        # Create model
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro-preview-03-25",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction="You are an expert bibliographic reference extractor. Your task is to generate sample academic references in a structured format. ALWAYS use function calling to return structured data."
        )
        
        # Make API call with just the prompt (no PDF)
        logger.info("Test A: Sending request to Gemini API (function calling without PDF)...")
        response = model.generate_content(
            prompt,  # Just sending the prompt text
            stream=False,
            tools=tools
        )
        
        logger.info("Received response from Gemini API")
        
        # Log response object details
        logger.debug(f"Response type: {type(response)}")
        logger.debug(f"Response attributes: {dir(response)}")
        
        # Try to convert whole response to dict for debugging
        try:
            response_dict = response.to_dict()
            with open('test_a_full_response.json', 'w') as f:
                json.dump(response_dict, f, indent=2)
            logger.debug("Saved full response as JSON")
        except Exception as e:
            logger.error(f"Could not convert response to dict: {e}")
        
        # Check finish reason
        finish_reason = None
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason = candidate.finish_reason
                logger.info(f"Finish reason: {finish_reason}")
        
        # Try to get structured output
        structured_data = None
        raw_text = ""
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for i, part in enumerate(candidate.content.parts):
                    if hasattr(part, 'function_call'):
                        logger.info(f"Found function call in response: {part.function_call.name}")
                        structured_data = part.function_call.args
                    elif hasattr(part, 'text'):
                        text_content = getattr(part, 'text', '')
                        if text_content:
                            raw_text += text_content
        
        # Write results to files
        if structured_data:
            logger.info("Successfully extracted structured data")
            with open('test_a_structured_output.json', 'w') as f:
                json.dump(structured_data, f, indent=2)
        else:
            logger.warning("No structured data found in response")
        
        with open('test_a_raw_response.txt', 'w') as f:
            f.write(raw_text or "No text content in response")
        
        return {
            'structured_data': structured_data,
            'raw_text': raw_text,
            'finish_reason': finish_reason
        }
    
    except Exception as e:
        logger.error(f"Error in test_function_calling_without_pdf: {e}", exc_info=True)
        return None


def test_pdf_without_function_calling(pdf_path):
    """
    Test B: PDF without Function Calling
    Test if PDF processing works without function calling
    """
    try:
        # Load env vars and API key
        load_dotenv(override=True)
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            return
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Read the PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Configure model with response_mime_type
        generation_config = {
            "max_output_tokens": 8192,
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "response_mime_type": "application/json"  # Request JSON directly
        }
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Create prompt to ask for text-based JSON
        prompt = """
        Extract all bibliographic references from the attached academic document.
        Return the result ONLY as a valid JSON object with the following structure:
        {
          "references": [
            {
              "citation_text": "Full citation text as it appears in the document",
              "source_type": "Type of source (journal, book, website, etc.)",
              "authors": "Authors of the reference",
              "title": "Title of the article/book/etc.",
              "source_name": "Name of journal/book/website",
              "publication_year": Year of publication (integer),
              "volume": "Volume information if applicable",
              "issue": "Issue number if applicable",
              "pages": "Page range if applicable",
              "doi_or_url": "DOI or URL if available",
              "confidence": Confidence score (0-100)
            }
          ]
        }
        DO NOT include any text before or after the JSON object.
        """
        
        # Create model without tools parameter
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro-preview-03-25",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction="You are an expert at extracting bibliographic references from academic documents and returning them in JSON format. You will ONLY return a valid JSON object with all extracted references."
        )
        
        # Encode PDF
        encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')
        
        # Make API call without tools parameter
        logger.info("Test B: Sending request to Gemini API (PDF without function calling)...")
        response = model.generate_content(
            [
                {"mime_type": "application/pdf", "data": encoded_pdf},
                prompt
            ],
            stream=False
            # No tools parameter
        )
        
        logger.info("Received response from Gemini API")
        
        # Log response object details
        logger.debug(f"Response type: {type(response)}")
        
        # Try to convert whole response to dict for debugging
        try:
            response_dict = response.to_dict()
            with open('test_b_full_response.json', 'w') as f:
                json.dump(response_dict, f, indent=2)
            logger.debug("Saved full response as JSON")
        except Exception as e:
            logger.error(f"Could not convert response to dict: {e}")
        
        # Check finish reason
        finish_reason = None
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason = candidate.finish_reason
                logger.info(f"Finish reason: {finish_reason}")
        
        # Get text response
        raw_text = ""
        if hasattr(response, 'text'):
            raw_text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'text'):
                            text_content = getattr(part, 'text', '')
                            if text_content:
                                raw_text += text_content
        
        logger.debug(f"Raw response preview: {raw_text[:200]}...")
        
        # Try to parse JSON from text response
        parsed_json = None
        if raw_text:
            try:
                # First, try to parse the raw text as JSON directly
                parsed_json = json.loads(raw_text)
                if 'references' in parsed_json:
                    logger.info(f"Successfully parsed JSON response with {len(parsed_json.get('references', []))} references")
                else:
                    logger.warning("Parsed JSON but missing 'references' key")
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks or similar
                logger.warning("Raw response is not valid JSON. Trying to extract JSON...")
                json_matches = re.findall(r'```json\s*([\s\S]*?)\s*```|{[\s\S]*}', raw_text)
                if json_matches:
                    for match in json_matches:
                        try:
                            candidate_json = json.loads(match.strip())
                            if 'references' in candidate_json:
                                parsed_json = candidate_json
                                logger.info(f"Extracted JSON with {len(parsed_json.get('references', []))} references")
                                break
                        except Exception as e:
                            logger.debug(f"Failed to parse JSON match: {str(e)}")
                            continue
        
        # Write results to files
        if parsed_json:
            with open('test_b_structured_output.json', 'w') as f:
                json.dump(parsed_json, f, indent=2)
        
        with open('test_b_raw_response.txt', 'w') as f:
            f.write(raw_text or "No text content in response")
        
        return {
            'parsed_json': parsed_json,
            'raw_text': raw_text,
            'finish_reason': finish_reason
        }
    
    except Exception as e:
        logger.error(f"Error in test_pdf_without_function_calling: {e}", exc_info=True)
        return None


def test_gemini_structured_output(pdf_path):
    """Test Gemini API with structured output for reference extraction."""
    try:
        # Load env vars and API key
        load_dotenv(override=True)
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            return
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Read the PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Configure model
        generation_config = {
            "max_output_tokens": 8192,
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
        }
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Get reference schema
        reference_schema = generate_reference_schema()
        logger.debug(f"Schema: {json.dumps(reference_schema, indent=2)}")
        
        # Define tools with function for structured output
        tools = [{
            "function_declarations": [{
                "name": "extract_references",
                "description": "Extract bibliographic references from academic documents",
                "parameters": reference_schema
            }]
        }]
        
        # Create more explicit prompt that emphasizes function calling
        prompt = """
        Extract all bibliographic references from the attached academic document using the extract_references function.
        
        YOU MUST USE THE extract_references FUNCTION to return structured data.
        DO NOT return the references as text or in any other format than through the function call.
        
        The function requires:
        - Full citation text for each reference
        - Source type classification (journal, book, website, etc.)
        - Additional metadata where available (authors, title, year, etc.)
        
        Remember to extract EVERY reference in the document's bibliography section.
        YOU MUST USE THE FUNCTION CALL to return your response.
        """
        
        # Create model
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro-preview-03-25",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction="You are an expert bibliographic reference extractor. Your task is to analyze academic documents and extract all references and citations, providing detailed structured information for each one. ALWAYS use function calling to return structured data."
        )
        
        # Encode PDF
        encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')
        
        # Make API call
        logger.info("Original Test: Sending request to Gemini API (PDF with function calling)...")
        response = model.generate_content(
            [
                {"mime_type": "application/pdf", "data": encoded_pdf},
                prompt
            ],
            stream=False,
            tools=tools
        )
        
        logger.info("Received response from Gemini API")
        
        # Log response object details
        logger.debug(f"Response type: {type(response)}")
        logger.debug(f"Response attributes: {dir(response)}")
        
        # Try to convert whole response to dict for debugging
        try:
            response_dict = response.to_dict()
            with open('full_response.json', 'w') as f:
                json.dump(response_dict, f, indent=2)
            logger.debug("Saved full response as JSON")
        except Exception as e:
            logger.error(f"Could not convert response to dict: {e}")
        
        # Check finish reason
        finish_reason = None
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason = candidate.finish_reason
                logger.info(f"Finish reason: {finish_reason}")
        
        # Try to get structured output
        structured_data = None
        raw_text = ""
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            logger.debug(f"Candidate attributes: {dir(candidate)}")
            
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                logger.debug(f"Number of parts in response: {len(candidate.content.parts)}")
                
                for i, part in enumerate(candidate.content.parts):
                    logger.debug(f"Part {i} type: {type(part)}, attributes: {dir(part)}")
                    
                    if hasattr(part, 'function_call'):
                        logger.info(f"Found function call in response: {part.function_call.name}")
                        logger.debug(f"Function call args: {part.function_call.args}")
                        structured_data = part.function_call.args
                    elif hasattr(part, 'text'):
                        text_content = getattr(part, 'text', '')
                        logger.debug(f"Text part content length: {len(text_content)}")
                        if text_content:
                            logger.debug(f"Text preview: {text_content[:200]}...")
                            raw_text += text_content
        
        # Write results to files
        if structured_data:
            logger.info("Successfully extracted structured data")
            with open('gemini_structured_output.json', 'w') as f:
                json.dump(structured_data, f, indent=2)
        else:
            logger.warning("No structured data found in response")
        
        with open('gemini_raw_response.txt', 'w') as f:
            f.write(raw_text or "No text content in response")
        
        return {
            'structured_data': structured_data,
            'raw_text': raw_text,
            'finish_reason': finish_reason
        }
    
    except Exception as e:
        logger.error(f"Error in test_gemini_structured_output: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    import re  # Import regex for JSON extraction
    
    # Updated path to the test PDF file
    test_pdf = "/Users/chrisjanssen/Insync/cnjanssen@tamu.edu/Google Drive/COM/Research/AI_Reviewer/AI_Reviewer/pdf_processor/media/pdfs/fneur-14-1270046.pdf"
    
    if not os.path.exists(test_pdf):
        logger.error(f"Test PDF file not found: {test_pdf}")
        # Check media/pdfs directory
        pdfs_dir = "/Users/chrisjanssen/Insync/cnjanssen@tamu.edu/Google Drive/COM/Research/AI_Reviewer/AI_Reviewer/pdf_processor/media/pdfs/"
        if os.path.exists(pdfs_dir):
            pdf_files = [f for f in os.listdir(pdfs_dir) if f.endswith('.pdf')]
            if pdf_files:
                test_pdf = os.path.join(pdfs_dir, pdf_files[0])
                logger.info(f"Using first PDF found in media/pdfs directory: {test_pdf}")
            else:
                logger.error("No PDF files found in media/pdfs directory")
                exit(1)
        else:
            logger.error(f"Media/pdfs directory not found: {pdfs_dir}")
            exit(1)
    
    # Run Test A: Function calling without PDF
    logger.info("=== RUNNING TEST A: FUNCTION CALLING WITHOUT PDF ===")
    result_a = test_function_calling_without_pdf()
    if result_a:
        logger.info(f"Test A finish reason: {result_a.get('finish_reason')}")
        if result_a.get('structured_data'):
            refs = result_a.get('structured_data', {}).get('references', [])
            logger.info(f"Test A: Successfully extracted {len(refs)} sample references with function calling")
        else:
            logger.info("Test A: No structured data extracted")
    else:
        logger.error("Test A failed")
    
    # Run Test B: PDF without function calling
    logger.info("\n=== RUNNING TEST B: PDF WITHOUT FUNCTION CALLING ===")
    result_b = test_pdf_without_function_calling(test_pdf)
    if result_b:
        logger.info(f"Test B finish reason: {result_b.get('finish_reason')}")
        if result_b.get('parsed_json'):
            refs = result_b.get('parsed_json', {}).get('references', [])
            logger.info(f"Test B: Successfully extracted {len(refs)} references without function calling")
        else:
            logger.info("Test B: No structured data extracted")
    else:
        logger.error("Test B failed")
    
    # Run original test: PDF with function calling
    logger.info("\n=== RUNNING ORIGINAL TEST: PDF WITH FUNCTION CALLING ===")
    result_orig = test_gemini_structured_output(test_pdf)
    if result_orig:
        logger.info(f"Original test finish reason: {result_orig.get('finish_reason')}")
        if result_orig.get('structured_data'):
            refs = result_orig.get('structured_data', {}).get('references', [])
            logger.info(f"Original test: Successfully extracted {len(refs)} references with function calling")
        else:
            logger.info("Original test: No structured data extracted")
    else:
        logger.error("Original test failed")
    
    # Print summary of all tests
    logger.info("\n=== TEST RESULTS SUMMARY ===")
    logger.info(f"Test A (Function calling without PDF): Finish reason = {result_a.get('finish_reason') if result_a else 'ERROR'}")
    logger.info(f"Test B (PDF without function calling): Finish reason = {result_b.get('finish_reason') if result_b else 'ERROR'}")
    logger.info(f"Original (PDF with function calling): Finish reason = {result_orig.get('finish_reason') if result_orig else 'ERROR'}")
    
    # Print recommendations based on results
    logger.info("\n=== RECOMMENDATIONS ===")
    if result_a and result_a.get('structured_data') and (result_orig and not result_orig.get('structured_data')):
        logger.info("PDF content combined with function calling appears to be the issue.")
        logger.info("Consider using the non-function calling approach (Test B) for your production application.")
    elif result_b and result_b.get('parsed_json') and (result_orig and not result_orig.get('structured_data')):
        logger.info("Function calling with PDF is problematic, but extracting JSON from PDF without function calling works.")
        logger.info("Implement the fallback approach that requests JSON directly for your production application.")
    elif (result_a and not result_a.get('structured_data')) and (result_b and not result_b.get('parsed_json')):
        logger.info("Both approaches failed. Consider reporting to Google Cloud Support.")
        logger.info("Try with a different PDF or model version as a workaround.") 