#!/usr/bin/env python
"""
Script to clear all jobs from the database without asking for confirmation
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from core.models import ProcessingJob, PDFDocument, ProcessingResult
from django.db import transaction

def clear_all_jobs():
    """Delete all jobs and associated documents/results"""
    
    with transaction.atomic():
        # Count before deletion
        job_count = ProcessingJob.objects.count()
        doc_count = PDFDocument.objects.count()
        result_count = ProcessingResult.objects.count()
        
        # Delete all results first (to maintain referential integrity)
        ProcessingResult.objects.all().delete()
        print(f"Deleted {result_count} processing results")
        
        # Delete all documents
        PDFDocument.objects.all().delete()
        print(f"Deleted {doc_count} PDF documents")
        
        # Delete all jobs
        ProcessingJob.objects.all().delete()
        print(f"Deleted {job_count} processing jobs")
        
        print("All jobs and related data successfully cleared from the database")

if __name__ == "__main__":
    # No confirmation, just run it
    clear_all_jobs() 