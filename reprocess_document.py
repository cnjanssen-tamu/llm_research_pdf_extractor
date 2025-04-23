#!/usr/bin/env python
"""
Script to reprocess a specific document that previously failed
"""

import os
import sys
import django
import json
import logging
import base64

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from core.models import ProcessingJob, PDFDocument, ProcessingResult
from core.views import ProcessorView
from django.core.files.base import ContentFile

def reprocess_document(document_id):
    """Reprocess a specific document"""
    try:
        # Get the document
        document = PDFDocument.objects.get(id=document_id)
        
        print(f"\nReprocessing document: {document.filename}")
        print(f"Original status: {document.status}")
        print(f"Original error: {document.error or 'None'}")
        
        # Create a processor view instance
        processor = ProcessorView()
        
        # Get the job and prompt template
        job = document.job
        prompt_template = processor._get_prompt_template(job)
        
        # Read the PDF data
        with document.file.open('rb') as f:
            pdf_data = f.read()
        
        # Before reprocessing, rename original results for comparison
        old_results = ProcessingResult.objects.filter(document=document)
        for result in old_results:
            result.error = f"[ARCHIVED] {result.error}"
            result.save()
        
        print(f"\nStarting reprocessing with fixed filter_cited_cases...")
        
        # Process the document with gemini
        result = processor._process_pdf_with_gemini(pdf_data, document, prompt_template, job)
        
        print(f"\nReprocessing result: {result}")
        print(f"New document status: {document.status}")
        print(f"New error (if any): {document.error or 'None'}")
        
        # Get the latest result
        latest_result = ProcessingResult.objects.filter(document=document).order_by('-created_at').first()
        if latest_result:
            print(f"\nLatest result ID: {latest_result.id}")
            print(f"Result has error: {'Yes' if latest_result.error else 'No'}")
            
            # Check structure of JSON result
            if latest_result.json_result:
                if isinstance(latest_result.json_result, dict):
                    print("\nJSON result structure:")
                    if 'case_results' in latest_result.json_result:
                        cases = latest_result.json_result['case_results']
                        print(f"  - Number of cases: {len(cases)}")
                        if cases:
                            first_case = cases[0]
                            print(f"  - First case type: {type(first_case)}")
                            # Print a few fields to check structure
                            if isinstance(first_case, dict):
                                for key in list(first_case.keys())[:5]:  # First 5 keys
                                    value = first_case[key]
                                    print(f"    - {key}: {type(value)}")
                            else:
                                print(f"    - Raw value: {first_case}")
                    else:
                        print(f"  - Keys at root level: {list(latest_result.json_result.keys())}")
                else:
                    print(f"\nJSON result is not a dict: {type(latest_result.json_result)}")
                    print(f"Value: {latest_result.json_result}")
        
        return result
        
    except Exception as e:
        print(f"Error reprocessing document: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reprocess_document.py <document_id>")
        # If no ID provided, list documents with errors
        error_docs = PDFDocument.objects.filter(status='error')
        if error_docs:
            print("\nDocuments with errors:")
            for i, doc in enumerate(error_docs[:10]):  # Show first 10
                print(f"{i+1}. {doc.filename} (ID: {doc.id})")
                print(f"   Error: {doc.error or 'None'}")
        sys.exit(1)
    
    document_id = sys.argv[1]
    reprocess_document(document_id) 