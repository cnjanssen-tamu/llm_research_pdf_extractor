import os
import json
import base64
import logging
import time
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
import re # Keep re for cleaning/parsing if needed

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO, # Use INFO for less noise, DEBUG for more detail
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ref_extraction_test')

# --- Constants (Copy from your views.py/prompts.py) ---
REFERENCE_EXTRACTION_PROMPT_TEXT_JSON = """You are an AI assistant specialized in extracting bibliographic references from academic documents. Your task is to meticulously analyze the provided PDF document, identify all cited references, and return the extracted information ONLY as a single, valid JSON object.

Instructions:
1.  **Identify References:** Locate the bibliography, references, or works cited section(s).
2.  **Extract Details:** For each distinct reference, extract:
    *   Full Citation Text (as it appears)
    *   Source Type (classify: journal, book, website, report, conference, thesis, news, other, unknown)
    *   Authors (Return as a list of strings: ["Author 1", "Author 2"])
    *   Title
    *   Source Name (Journal name, book title, website name, etc.)
    *   Publication Year (integer)
    *   Volume (string)
    *   Issue (string)
    *   Pages (string, e.g., "123-145")
    *   DOI or URL (string)
    *   Confidence (integer 0-100, overall confidence for the parsed fields of this reference)
3.  **Handle Missing Information:** If a detail is not available, use `null` for that field in the JSON (e.g., `"volume": null`). Do not omit the field key.
4.  **Output Format:** Your entire response MUST be ONLY the JSON object. It should contain a single root key "references", which holds an array of reference objects. Each reference object must contain all the fields listed above (using `null` for missing values).

**CRITICAL:**
- Your response MUST start directly with `{` and end directly with `}`.
- Do NOT include any introductory text, explanations, apologies, summaries, or markdown formatting (like ```json ```).
- Ensure the generated JSON is strictly valid.

**EXAMPLE JSON OUTPUT STRUCTURE (This is the exact format you must output):**
{
  "references": [
    {
      "citation_text": "Doe J, Smith A. A Study on Reference Extraction. Journal of Bibliometrics. 2022;15(3):205-218. doi:10.1000/jb.2022.5",
      "source_type": "journal",
      "authors": ["Doe J", "Smith A"],
      "title": "A Study on Reference Extraction",
      "source_name": "Journal of Bibliometrics",
      "publication_year": 2022,
      "volume": "15",
      "issue": "3",
      "pages": "205-218",
      "doi_or_url": "doi:10.1000/jb.2022.5",
      "confidence": 98
    },
    {
      "citation_text": "Example Org. Annual Report 2023. Published Dec 1, 2023. Accessed Feb 10, 2024. https://example.org/report2023.pdf",
      "source_type": "report",
      "authors": ["Example Org"],
      "title": "Annual Report 2023",
      "source_name": "Example Org",
      "publication_year": 2023,
      "volume": null,
      "issue": null,
      "pages": null,
      "doi_or_url": "https://example.org/report2023.pdf",
      "confidence": 90
    }
  ]
}
"""

# --- Utility Functions (Copy from your utils.py or define here) ---
def _clean_json_response(text):
    if not text: return text
    text = str(text)
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    text = re.sub(r'//.*?[\n\r]', '\n', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text.strip()

def extract_json_from_text(text):
    """Extracts the first valid JSON object found within a string."""
    if not text or not isinstance(text, str): return None
    text = _clean_json_response(text)
    try: return json.loads(text) # Try direct load first
    except json.JSONDecodeError: pass
    try: # Find first {} block
        start_index = text.find('{')
        if start_index != -1:
            brace_level = 0
            for i, char in enumerate(text[start_index:]):
                if char == '{': brace_level += 1
                elif char == '}': brace_level -= 1
                if brace_level == 0:
                    potential_json = text[start_index : start_index + i + 1]
                    try: return json.loads(potential_json)
                    except json.JSONDecodeError: pass
                    break # Found balanced block
    except Exception: pass
    logger.warning("Failed to extract valid JSON from the provided text.")
    return None

def generate_continuation_prompt(last_index):
    """Generates the prompt for continuing reference extraction."""
    start_from_number = last_index + 1 # User-friendly 1-based index
    return f"""You were previously extracting bibliographic references from the attached academic document.
Your last response was truncated after successfully extracting reference number {last_index} (using 0-based indexing, meaning the {start_from_number}th reference overall).

Please continue extracting the remaining references, starting *immediately after* the last one you provided (i.e., starting with the {start_from_number}th reference in the document's list).

Output ONLY the JSON object containing the *subsequent* references found. Maintain the required JSON structure:
{{
  "references": [
     {{
       "citation_text": "...",
       // ... include all fields ...
       "confidence": ...
     }}
     // ... only references starting from number {start_from_number} ...
   ]
}}
Do NOT include references 1 through {start_from_number-1} which were already extracted.
Ensure the response is ONLY the valid JSON object.
"""

# --- API Call Function ---
def call_gemini_text_json(pdf_data, prompt_text, model_name='gemini-2.5-flash-preview-04-17'): # Using Flash for faster testing first
    """Calls Gemini API, requesting a text-based JSON response."""
    logger.info(f"Calling Gemini API for Text JSON. Model: {model_name}")
    load_dotenv(override=True)
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key: 
        logger.error("GEMINI_API_KEY not found.")
        return {"success": False, "error": "API Key missing"}
    genai.configure(api_key=api_key)

    generation_config = GenerationConfig(
        max_output_tokens=65536,  # Increased from 1024 to real value to test properly
        temperature=0.1,
        top_p=0.95,
        top_k=40,
        response_mime_type="application/json"
    )
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        logger.info("Initializing Gemini model...")
        model = genai.GenerativeModel(
            model_name=model_name, 
            generation_config=generation_config, 
            safety_settings=safety_settings,
            system_instruction="You are an expert at extracting bibliographic references from academic documents and returning them in JSON format. You will ONLY return a valid JSON object with all extracted references, following the exact format specified in the prompt."
        )
        logger.info("Encoding PDF data...")
        encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')
        content = [{"mime_type": "application/pdf", "data": encoded_pdf}, prompt_text]
        logger.info(f"Sending request to Gemini (PDF size: {len(encoded_pdf)} chars)...")
        start_time = time.time()
        response = model.generate_content(content, stream=False)
        end_time = time.time()
        logger.info(f"Gemini response received in {end_time - start_time:.2f}s.")
    except Exception as api_err:
        logger.error(f"Error during API call: {api_err}", exc_info=True)
        return {"success": False, "error": f"Gemini API call failed: {str(api_err)}"}

    raw_response_text = ""; parsed_json = None; finish_reason_code = 0; is_truncated = False
    try:
        logger.info("Processing API response...")
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
             reason = response.prompt_feedback.block_reason.name
             logger.error(f"Blocked: {reason}")
             return {"success": False, "error": f"Blocked ({reason})"}
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason_code = candidate.finish_reason.value
                finish_reason_name = candidate.finish_reason.name
                logger.info(f"Finish Reason Code: {finish_reason_code} ({finish_reason_name})")
                if finish_reason_code == 3: 
                    is_truncated = True
                    logger.warning("TRUNCATED (MAX_TOKENS).")
                elif finish_reason_code not in [0, 1]: 
                    logger.warning(f"Unexpected finish: {finish_reason_name}")
            else:
                logger.warning("No finish_reason in candidate")
        else:
            logger.warning("No candidates in response")
        
        if hasattr(response, 'text'):
            raw_response_text = response.text
            logger.info(f"Got text response ({len(raw_response_text)} chars)")
            
            logger.info("Attempting to parse JSON...")
            parsed_json = extract_json_from_text(raw_response_text)
            
            if parsed_json:
                logger.info(f"Successfully extracted JSON. Keys: {list(parsed_json.keys()) if parsed_json else 'None'}")
            else:
                logger.warning("Could not parse JSON from text.")
                # Try direct JSON loading
                try:
                    parsed_json = json.loads(raw_response_text)
                    logger.info("Direct JSON loading succeeded")
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error: {e}")
        else: 
            logger.warning("Response missing '.text'.")

        return { 
            "success": True, 
            "raw_response": raw_response_text, 
            "parsed_json": parsed_json,
            "is_truncated": is_truncated, 
            "finish_reason": finish_reason_code 
        }
    except Exception as process_err:
        logger.error(f"Error processing response: {process_err}", exc_info=True)
        return {"success": False, "error": f"Failed to process response: {process_err}", "raw_response": raw_response_text}

# --- Main Execution ---
if __name__ == "__main__":
    # --- Configuration ---
    # !!! UPDATE THIS PATH to your test PDF !!!
    pdf_path = "/Users/chrisjanssen/Insync/cnjanssen@tamu.edu/Google Drive/COM/Research/AI_Reviewer/AI_Reviewer/pdf_processor/media/pdfs/43_sZwYqNe._Doron.pdf"
    output_dir = "test_reference_output_doron"
    max_retries = 5 # Limit continuation attempts

    # --- Setup ---
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        exit()
    os.makedirs(output_dir, exist_ok=True)

    # Write an empty test file to verify directory access permissions
    test_file_path = os.path.join(output_dir, "test_write.txt")
    try:
        with open(test_file_path, 'w') as f:
            f.write("Test write access")
        logger.info(f"Write access confirmed to {output_dir}")
        os.remove(test_file_path)
    except Exception as e:
        logger.error(f"Cannot write to output directory: {e}")
        exit(1)

    logger.info(f"Loading PDF: {pdf_path}")
    try:
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        logger.info(f"Successfully loaded PDF: {len(pdf_data)} bytes")
    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
        exit(1)

    # --- State Variables ---
    all_extracted_references = []
    last_successful_index = 0 # 0-based index
    is_complete = False
    attempt_count = 0

    # --- Processing Loop ---
    while not is_complete and attempt_count < max_retries:
        attempt_count += 1
        logger.info(f"\n--- Extraction Attempt {attempt_count} ---")

        # Determine prompt
        if last_successful_index == 0:
            prompt = REFERENCE_EXTRACTION_PROMPT_TEXT_JSON
            logger.info("Using initial prompt.")
        else:
            prompt = generate_continuation_prompt(last_successful_index)
            logger.info(f"Using continuation prompt, starting after index {last_successful_index}.")

        # Call API
        logger.info("Calling Gemini API...")
        api_result = call_gemini_text_json(pdf_data, prompt)
        logger.info(f"API call returned success: {api_result.get('success', False)}")

        # Save raw response for this attempt - whether successful or not
        raw_response = api_result.get("raw_response", "No response text returned")
        raw_filename = os.path.join(output_dir, f"attempt_{attempt_count}_raw_response.txt")
        try:
            with open(raw_filename, 'w') as f:
                f.write(raw_response)
            logger.info(f"Saved raw response ({len(raw_response)} chars) to {raw_filename}")
        except Exception as e:
            logger.error(f"Error saving raw response: {e}")

        # Debug: print first 200 chars of response
        if raw_response:
            logger.info(f"Response preview: {raw_response[:200]}...")
        else:
            logger.warning("Empty response received")

        # Handle API call failure
        if not api_result.get("success"):
            error_msg = api_result.get('error', 'Unknown error')
            logger.error(f"API call failed: {error_msg}")
            is_complete = True # Stop on API error
            break

        # Process successful API call result
        parsed_json = api_result.get("parsed_json")
        is_truncated = api_result.get("is_truncated", False)
        finish_reason = api_result.get("finish_reason")
        logger.info(f"Response truncated: {is_truncated}, Finish reason: {finish_reason}")

        # Debug info about parsing
        if parsed_json:
            logger.info(f"Successfully parsed JSON. Keys: {list(parsed_json.keys())}")
        else:
            logger.warning("Failed to parse JSON from response")

        references_this_run = []
        if parsed_json and isinstance(parsed_json.get("references"), list):
            references_this_run = parsed_json["references"]
            logger.info(f"Attempt {attempt_count}: Parsed {len(references_this_run)} references.")
            # Save parsed JSON for this attempt
            parsed_filename = os.path.join(output_dir, f"attempt_{attempt_count}_parsed.json")
            try:
                with open(parsed_filename, 'w') as f:
                    json.dump(parsed_json, f, indent=2)
                logger.info(f"Saved parsed JSON to {parsed_filename}")
            except Exception as e:
                logger.error(f"Error saving parsed JSON: {e}")
        else:
            logger.warning(f"Attempt {attempt_count}: Could not parse valid 'references' list from JSON.")
            if parsed_json:
                logger.info(f"Parsed JSON without references list: {parsed_json}")
            # If truncated, maybe continue? If not truncated, it's a real error.
            if not is_truncated:
                 logger.error("Parsing failed on a non-truncated response. Stopping.")
                 is_complete = True
                 break # Stop if parsing fails and it wasn't truncated

        # Append successfully parsed references and update index
        if references_this_run:
            all_extracted_references.extend(references_this_run)
            last_successful_index += len(references_this_run) # Increment by count found *in this run*
            logger.info(f"Total references accumulated: {len(all_extracted_references)}. Next index: {last_successful_index}")

        # Check completion status
        if not is_truncated:
            logger.info("Processing complete (response not truncated).")
            is_complete = True
        else:
            # Ask user if they want to continue
            logger.warning("Response was truncated. More references might exist.")
            user_input = input(f"Continue to fetch next batch (attempt {attempt_count + 1}/{max_retries})? (y/N): ").lower()
            if user_input != 'y':
                logger.info("User chose not to continue.")
                is_complete = True

    # --- Final Output ---
    logger.info(f"\n--- Extraction Finished ---")
    logger.info(f"Total attempts: {attempt_count}")
    logger.info(f"Total references extracted: {len(all_extracted_references)}")

    # Save combined results
    final_output_path = os.path.join(output_dir, "combined_references.json")
    final_data = {"references": all_extracted_references}
    try:
        with open(final_output_path, 'w') as f:
            json.dump(final_data, f, indent=2)
        logger.info(f"Saved combined results to {final_output_path}")
    except Exception as e:
        logger.error(f"Error saving combined results: {e}") 