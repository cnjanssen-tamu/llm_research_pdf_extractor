import logging
from celery import shared_task
from .models import ProcessingJob, PDFDocument, ProcessingResult
from .processor import process_pdfs, call_gemini_with_pdf
from django.utils import timezone
import os
import json
import base64
import time
from .utils import extract_json_from_text, is_response_truncated
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def process_pdfs_task(job_id):
    """Process PDFs for a given job ID."""
    job = None
    try:
        job = ProcessingJob.objects.get(id=job_id)
        
        # Process PDFs
        success = process_pdfs(job, job.documents.all())

        # Update job status
        job.refresh_from_db()
        if job.processed_count == job.total_count:
            job.status = 'completed'
        else:
            job.status = 'failed'
            job.error_message = f"Processed {job.processed_count}/{job.total_count} files"
        job.save()

    except ProcessingJob.DoesNotExist:
        logger.error(f"Error processing job {job_id}: ProcessingJob matching query does not exist.")
        return

    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        if job:
            job.status = 'failed'
            job.error_message = str(e)
            job.save()
        raise


@shared_task
def process_document(document_id, pdf_data=None, prompt=None):
    """
    Process a single document with the Gemini API.
    
    Args:
        document_id (str): The ID of the PDFDocument to process
        pdf_data (str, optional): Base64 encoded PDF data. If not provided, will be read from the file.
        prompt (str, optional): Custom prompt to use. If not provided, will use the job's prompt.
        
    Returns:
        dict: Processing result information
    """
    try:
        # Get the document and its job
        document = PDFDocument.objects.get(id=document_id)
        job = document.job
        
        # If PDF data not provided, read it from the file
        if not pdf_data:
            with open(document.file.path, 'rb') as file:
                file_content = file.read()
                pdf_data = base64.b64encode(file_content).decode('utf-8')
                
        # If prompt not provided, use the job's prompt
        if not prompt:
            prompt = job.prompt.text if job.prompt else "Please analyze this PDF document and extract all relevant information."
            
        logger.info(f"Processing document {document_id}")
        
        # Call the Gemini API
        api_response = call_gemini_with_pdf(pdf_data, prompt)
        
        if 'error' in api_response:
            # Save the error
            ProcessingResult.objects.create(
                document=document,
                error=api_response.get('error'),
                raw_result=api_response.get('raw_response', ''),
                is_complete=False
            )
            
            # Update document status
            document.status = 'error'
            document.error = api_response.get('error')
            document.save()
            
            # Update job counts
            job.processed_count += 1
            job.save()
            
            return {
                "status": "error",
                "error": api_response.get('error'),
                "document_id": document_id
            }
            
        # Get the text response
        response_text = api_response.get('text', '')
        
        # Check if the response is truncated
        is_complete = not is_response_truncated(response_text)
        
        # Extract JSON from the text
        json_data = extract_json_from_text(response_text)
        
        # Save the result
        result = ProcessingResult.objects.create(
            document=document,
            json_result=json_data,
            raw_result=response_text,
            is_complete=is_complete
        )
        
        # Update document status
        document.status = 'complete' if is_complete else 'processed'
        document.save()
        
        # Update job counts
        job.processed_count += 1
        if job.processed_count >= job.total_count:
            job.status = 'completed'
        job.save()
        
        return {
            "status": "success",
            "document_id": document_id,
            "result_id": str(result.id),
            "is_complete": is_complete
        }
        
    except PDFDocument.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        return {"status": "error", "error": f"Document not found: {document_id}"}
    except Exception as e:
        logger.error(f"Error in process_document task: {str(e)}")
        return {"status": "error", "error": str(e)}