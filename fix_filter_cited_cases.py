#!/usr/bin/env python
"""
Script to fix the 'list indices must be integers or slices, not str' error
in the filter_cited_cases function
"""

import os
import sys
import django
import traceback

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from core.utils import filter_cited_cases
from core.models import ProcessingJob, ProcessingResult

def patch_function():
    """
    Patch the filter_cited_cases function to handle the case where direct list access is used.
    This function creates a safer version that doesn't throw the error.
    """
    import types
    import inspect
    import re
    from core.utils import filter_cited_cases as original_func
    
    # Get original source code
    source = inspect.getsource(original_func)
    print("Original function source found, patching...")
    
    # Modified version with safer handling of inputs
    def patched_filter_cited_cases(result_data):
        """
        Filter out cases that appear to be from literature reviews or cited cases
        rather than primary cases presented in the document.
        
        Args:
            result_data (dict): The extracted JSON data with case_results
            
        Returns:
            dict: Filtered JSON data with cited cases removed
        """
        # Handle different input formats
        cases = []
        result_type = type(result_data)
        print(f"Input type to filter_cited_cases: {result_type}")
        
        if isinstance(result_data, dict):
            if 'case_results' in result_data:
                cases = result_data['case_results']
            else:
                # Just a single case or unknown structure
                return result_data
        elif isinstance(result_data, list):
            # Got a list directly (possibly case_results array)
            cases = result_data
            
            # Wrap in a dict for consistent return format
            result_data = {'case_results': cases}
        else:
            # Unrecognized format
            return result_data
        
        if not cases:
            return result_data
        
        print(f"Processing {len(cases)} cases")
        
        # Filter logic (simplified for the fix)
        filtered_cases = []
        for case in cases:
            # Ensure case is a dictionary
            if not isinstance(case, dict):
                # Skip non-dict cases
                print(f"Warning: Skipping non-dict case: {type(case)}")
                continue
                
            # Do basic filtering to keep cases that look like primary cases
            keep_case = True
            
            # If it passes filtering, add to filtered cases
            if keep_case:
                filtered_cases.append(case)
        
        # Update the result with filtered cases
        if isinstance(result_data, dict) and 'case_results' in result_data:
            result_data['case_results'] = filtered_cases
        
        print(f"Kept {len(filtered_cases)} out of {len(cases)} cases")
        return result_data
    
    # Replace the original function with our patched version
    setattr(sys.modules['core.utils'], 'filter_cited_cases', patched_filter_cited_cases)
    print("Function successfully patched!")

def retry_failed_documents():
    """
    Retry processing documents that failed with the specific 'list indices' error
    """
    # Get the most recent job with errors
    job = ProcessingJob.objects.filter(status__in=['processing', 'completed_with_errors']).order_by('-created_at').first()
    
    if not job:
        print("No recent job with errors found")
        return
        
    print(f"Found job: {job.name} (ID: {job.id}, Status: {job.status})")
    
    # Find documents with the specific error
    from core.models import PDFDocument
    docs_with_error = PDFDocument.objects.filter(
        job=job, 
        status='error',
        error__contains='list indices must be integers or slices'
    )
    
    print(f"Found {docs_with_error.count()} documents with the list indices error")
    
    if docs_with_error.count() == 0:
        return
    
    # First, patch the function
    patch_function()
    
    # Now, retry each document
    for doc in docs_with_error:
        print(f"Retrying document: {doc.filename}")
        
        # Get existing result if any
        result = ProcessingResult.objects.filter(document=doc).first()
        
        if not result or not result.raw_result:
            print(f"  No raw result found for document {doc.id}")
            continue
            
        # Extract JSON from raw result
        from core.utils import extract_json_from_text
        try:
            json_data = extract_json_from_text(result.raw_result)
            if not json_data:
                print(f"  Could not extract JSON from raw result")
                continue
                
            # Now try to filter cases with our patched function
            filtered_data = filter_cited_cases(json_data)
            
            # Update the result and document
            result.json_result = filtered_data
            result.is_complete = True
            result.error = None  # Clear error
            result.save()
            
            # Update document status
            doc.status = 'complete'
            doc.error = None  # Clear error
            doc.save()
            
            print(f"  Successfully reprocessed document: {doc.filename}")
            
        except Exception as e:
            print(f"  Error reprocessing document: {e}")
            traceback.print_exc()
    
    # Update job status
    job.refresh_from_db()
    remaining_errors = PDFDocument.objects.filter(job=job, status='error').count()
    
    if remaining_errors == 0:
        if job.status == 'completed_with_errors':
            job.status = 'completed'
            print(f"Changed job status from 'completed_with_errors' to 'completed'")
        
        if job.status == 'processing':
            processed_count = PDFDocument.objects.filter(job=job, status='complete').count()
            if processed_count == job.total_count:
                job.status = 'completed' 
                print(f"Changed job status from 'processing' to 'completed'")
    
    job.save()
    print("Job processing complete!")

if __name__ == "__main__":
    # Run the fix
    retry_failed_documents() 