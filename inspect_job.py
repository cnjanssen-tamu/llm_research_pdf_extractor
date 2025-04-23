#!/usr/bin/env python
"""
Script to inspect the contents of a job in the database
"""

import os
import sys
import django
import json

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

# Import models
from core.models import ProcessingJob, ProcessingResult, PDFDocument

# Inspect job
def inspect_job(job_id):
    print(f"Inspecting job ID: {job_id}")
    
    try:
        job = ProcessingJob.objects.get(id=job_id)
        print(f"Job: {job.name} (Status: {job.status})")
        print(f"Created: {job.created_at}")
        print(f"Processed: {job.processed_count}/{job.total_count} documents")
        
        # Get documents and results
        documents = PDFDocument.objects.filter(job=job)
        print(f"Documents count: {documents.count()}")
        
        results = ProcessingResult.objects.filter(document__job=job)
        print(f"Results count: {results.count()}")
        
        # Examine each result
        for i, result in enumerate(results):
            print(f"\nResult {i+1}:")
            print(f"  Document: {result.document.file.name}")
            print(f"  Created: {result.created_at}")
            
            if not result.result_data:
                print("  No result data available")
                continue
                
            # Get case results
            cases = result.result_data.get('case_results', [])
            print(f"  Number of cases: {len(cases)}")
            
            # Print case details
            for j, case in enumerate(cases):
                print(f"    Case {j+1}:")
                
                # Print a few keys for identification
                print(f"      Keys: {list(case.keys())[:5] if case else []}")
                
                # If the case has identifiable fields, print them
                for field in ['patient_id', 'case_number', 'id', 'name']:
                    if field in case and isinstance(case[field], dict) and 'value' in case[field]:
                        print(f"      {field}: {case[field]['value']}")
                
                # Compare cases for duplication
                if j > 0:
                    is_same = True
                    for key, value in case.items():
                        if key in cases[0] and cases[0][key] != value:
                            is_same = False
                            break
                    print(f"      Duplicate of Case 1? {'Yes' if is_same else 'No'}")
                    
    except ProcessingJob.DoesNotExist:
        print(f"Job with ID {job_id} does not exist")
    except Exception as e:
        print(f"Error inspecting job: {str(e)}")

if __name__ == "__main__":
    job_id = 81  # Set the job ID to inspect
    inspect_job(job_id) 