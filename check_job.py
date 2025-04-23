#!/usr/bin/env python
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

# Import models
from core.models import ProcessingJob, ProcessingResult, PDFDocument, Reference

# Get job
job_id = '4d53483b-46c6-4074-8b81-f2cfee05130e'
job = ProcessingJob.objects.filter(id=job_id).first()

# Get job details
if job:
    print(f"Job: {job.name} | Status: {job.status}")
    print(f"Error message: {job.error_message}")
    print(f"Created: {job.created_at}")
    print(f"Job type: {job.job_type}")
    
    # Documents
    docs = PDFDocument.objects.filter(job=job)
    print(f"\nDocuments count: {docs.count()}")
    for doc in docs:
        print(f"\nDocument: {doc.filename}")
        print(f"Status: {doc.status}")
        print(f"Error: {doc.error}")
        
        # Results
        results = ProcessingResult.objects.filter(document=doc)
        print(f"Results count: {results.count()}")
        for result in results:
            print(f"Result error: {result.error}")
            print(f"Is complete: {result.is_complete}")
            if result.raw_result:
                print(f"Raw result preview: {result.raw_result[:500]}...")
            else:
                print("No raw result")

            # References
            refs = Reference.objects.filter(document=doc)
            print(f"References extracted: {refs.count()}")
            for i, ref in enumerate(refs[:5]):  # Show only first 5
                print(f"  Ref {i+1}: {ref.title}")
else:
    print(f"No job found with ID: {job_id}") 