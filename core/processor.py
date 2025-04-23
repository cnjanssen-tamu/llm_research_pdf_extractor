import logging
import base64
from django.utils import timezone
from .models import PDFDocument, ProcessingResult
from .utils import extract_json_from_text, is_response_truncated

logger = logging.getLogger(__name__)

def process_pdfs(job, documents):
    """
    Process PDFs for a job.
    
    Args:
        job: The ProcessingJob instance
        documents: QuerySet of PDFDocument instances
    """
    try:
        from .tasks import process_document
        
        for document in documents:
            # Skip already processed documents
            if document.status in ['complete', 'error']:
                continue
                
            # Update document status
            document.status = 'processing'
            document.save()
            
            # Process document asynchronously
            process_document.delay(str(document.id))
            
        return True
        
    except Exception as e:
        logger.error(f"Error in process_pdfs: {str(e)}")
        return False

def call_gemini_with_pdf(pdf_data, prompt):
    """
    Call the Gemini API with a PDF and prompt.
    
    Args:
        pdf_data (str): Base64 encoded PDF content
        prompt (str): The prompt to send to Gemini
        
    Returns:
        dict: The response from the Gemini API
    """
    import requests
    import time
    import json
    from django.conf import settings
    
    try:
        api_key = settings.GEMINI_API_KEY
        api_url = settings.GEMINI_API_URL
        
        if not api_key or not api_url:
            raise ValueError("Gemini API key or URL not configured")
            
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_data
                            }
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0.0,
                "max_output_tokens": 8192,
                "top_p": 1,
                "top_k": 32
            }
        }
        
        # Add API key as a URL parameter
        full_url = f"{api_url}?key={api_key}"
        
        # Make the request with exponential backoff
        max_retries = 3
        retry_delay = 2  # start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(full_url, headers=headers, json=data, timeout=300)
                break
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    # If not the last attempt, wait and retry
                    logger.warning(f"Gemini API request failed (attempt {attempt+1}/{max_retries}): {str(e)}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # exponential backoff
                else:
                    # Last attempt failed
                    logger.error(f"Gemini API request failed after {max_retries} attempts: {str(e)}")
                    raise
        
        # Process response
        if response.status_code != 200:
            logger.error(f"Gemini API returned non-200 status code: {response.status_code}")
            logger.error(f"Response content: {response.text[:1000]}")
            return {
                "error": f"API error: {response.status_code}",
                "raw_response": response.text[:2000]  # Limit to avoid very large error messages
            }
            
        response_data = response.json()
        
        if "error" in response_data:
            logger.error(f"Gemini API returned error: {response_data['error']}")
            return {
                "error": f"API error: {response_data['error']}",
                "raw_response": response.text[:2000]
            }
            
        # Extract the text from the response
        candidates = response_data.get("candidates", [])
        if not candidates:
            logger.error("No candidates in Gemini API response")
            return {
                "error": "No candidates in API response",
                "raw_response": response.text[:2000]
            }
            
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        
        if not parts:
            logger.error("No parts in Gemini API response content")
            return {
                "error": "No parts in API response content",
                "raw_response": response.text[:2000]
            }
            
        text_parts = [part.get("text", "") for part in parts if "text" in part]
        text_response = "".join(text_parts)
        
        return {
            "text": text_response,
            "raw_response": response.text
        }
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        return {
            "error": str(e),
            "raw_response": ""
        } 