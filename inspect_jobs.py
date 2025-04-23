#!/usr/bin/env python
"""
Script to inspect processing jobs, including the most recent one and jobs with errors
"""

import os
import sys
import django
from datetime import datetime

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from core.models import ProcessingJob, PDFDocument, ProcessingResult
from django.db.models import Q

def inspect_jobs():
    """Inspect jobs with errors and the most recent job"""
    
    # Get total count of jobs
    total_jobs = ProcessingJob.objects.count()
    print(f"\nTotal jobs in database: {total_jobs}")
    
    # Get the most recent job
    try:
        most_recent_job = ProcessingJob.objects.order_by('-created_at')[0]
        print("\n--- MOST RECENT JOB ---")
        print(f"Job ID: {most_recent_job.id}")
        print(f"Created: {most_recent_job.created_at}")
        print(f"Status: {most_recent_job.status}")
        print(f"Name: {most_recent_job.name}")
        print(f"Processing details: {most_recent_job.processing_details}")
        
        # Get associated documents
        documents = PDFDocument.objects.filter(job=most_recent_job)
        print(f"Number of documents: {documents.count()}")
        
        # Count documents by status
        status_count = {}
        for doc in documents:
            status_count[doc.status] = status_count.get(doc.status, 0) + 1
        
        for status, count in status_count.items():
            print(f"  - {status}: {count} documents")
        
        # Get error documents
        error_docs = documents.filter(status='error')
        if error_docs.exists():
            print(f"\nDocuments with errors: {error_docs.count()}")
            for i, doc in enumerate(error_docs):
                print(f"  {i+1}. {doc.filename}")
                print(f"     Error: {doc.error or 'None'}")
        
        # Get results
        results = ProcessingResult.objects.filter(document__job=most_recent_job)
        print(f"\nNumber of results: {results.count()}")
        
        # Look for results with errors
        error_results = results.exclude(error__isnull=True).exclude(error='')
        if error_results.exists():
            print(f"\nResults with error messages: {error_results.count()}")
            for i, result in enumerate(error_results):
                print(f"  {i+1}. Document: {result.document.filename}")
                print(f"     Error: {result.error}")
    except IndexError:
        print("No jobs found in the database")
    
    # Find jobs with errors
    error_jobs = ProcessingJob.objects.filter(Q(status__contains='error') | Q(status='failed'))
    print(f"\n--- JOBS WITH ERRORS ({error_jobs.count()}) ---")
    
    for job in error_jobs:
        print(f"\nJob ID: {job.id}")
        print(f"Created: {job.created_at}")
        print(f"Status: {job.status}")
        print(f"Name: {job.name}")
        
        # Get associated documents
        documents = PDFDocument.objects.filter(job=job)
        print(f"Documents: {documents.count()}")
        
        # List documents with errors
        error_docs = documents.filter(status='error')
        if error_docs.exists():
            print(f"Documents with errors: {error_docs.count()}")
            for i, doc in enumerate(error_docs):
                print(f"  {i+1}. {doc.filename}")
                print(f"     Error: {doc.error or 'None'}")
    
    # Look for specific files mentioned by the user (3, 5, 14, 39, 44)
    mentioned_files = [3, 5, 14, 39, 44]
    print("\n--- SPECIFIC FILES MENTIONED ---")
    
    for file_num in mentioned_files:
        # Try to find documents that might match this file number
        matching_docs = PDFDocument.objects.filter(
            Q(filename__startswith=f"{file_num}_") | 
            Q(filename__startswith=f"{file_num}.") |
            Q(filename__contains=f"file{file_num}")
        )
        
        if matching_docs.exists():
            print(f"\nFile {file_num} matches:")
            for doc in matching_docs:
                print(f"  {doc.filename}")
                print(f"  Status: {doc.status}")
                print(f"  Job ID: {doc.job.id}, Job Status: {doc.job.status}")
                if doc.error:
                    print(f"  Error: {doc.error}")
        else:
            # Get documents by index
            all_docs = PDFDocument.objects.all().order_by('id')
            if all_docs.count() >= file_num and file_num > 0:
                # Get the file_num-th document (zero-indexed)
                doc = all_docs[file_num-1]
                print(f"\nFile {file_num} (by index):")
                print(f"  {doc.filename}")
                print(f"  Status: {doc.status}")
                print(f"  Job ID: {doc.job.id}, Job Status: {doc.job.status}")
                if doc.error:
                    print(f"  Error: {doc.error}")
            else:
                print(f"\nFile {file_num}: No matching documents found")

if __name__ == "__main__":
    inspect_jobs() 