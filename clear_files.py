#!/usr/bin/env python
import os
import django
import shutil

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

# Import models after Django setup
from core.models import ProcessingJob, PDFDocument, ProcessingResult

def clear_all_jobs_and_files():
    """
    Delete all jobs, documents, results from the database and PDF files from media
    """
    print("Clearing all jobs, documents, results, and PDF files...")
    
    # Delete from database with proper order to maintain referential integrity
    results_count = ProcessingResult.objects.count()
    ProcessingResult.objects.all().delete()
    print(f"Deleted {results_count} processing results")
    
    docs_count = PDFDocument.objects.count()
    PDFDocument.objects.all().delete()
    print(f"Deleted {docs_count} PDF documents from database")
    
    jobs_count = ProcessingJob.objects.count()
    ProcessingJob.objects.all().delete()
    print(f"Deleted {jobs_count} processing jobs")
    
    # Clear PDF files from media directory
    media_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media', 'pdfs')
    
    # Get list of files before deletion
    files_count = len([f for f in os.listdir(media_path) if os.path.isfile(os.path.join(media_path, f))])
    
    # Delete all files but keep the directory
    for filename in os.listdir(media_path):
        file_path = os.path.join(media_path, filename)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    
    print(f"Deleted {files_count} PDF files from media directory")
    print("All jobs and files have been cleared!")

if __name__ == "__main__":
    clear_all_jobs_and_files() 