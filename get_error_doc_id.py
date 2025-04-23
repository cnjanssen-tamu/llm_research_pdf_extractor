#!/usr/bin/env python
"""
Script to get the ID of a specific document with an error
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from core.models import PDFDocument

def get_doc_id(filename):
    """Get the ID of a document with the given filename"""
    try:
        document = PDFDocument.objects.get(filename=filename)
        print(f"Document ID for '{filename}': {document.id}")
        return document.id
    except PDFDocument.DoesNotExist:
        print(f"No document found with filename '{filename}'")
        return None
    except PDFDocument.MultipleObjectsReturned:
        print(f"Multiple documents found with filename '{filename}'")
        docs = PDFDocument.objects.filter(filename=filename)
        for i, doc in enumerate(docs):
            print(f"{i+1}. ID: {doc.id}, Status: {doc.status}, Job: {doc.job.id}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python get_error_doc_id.py <filename>")
        print("\nExample filenames with errors:")
        error_docs = PDFDocument.objects.filter(status='error')
        for i, doc in enumerate(error_docs[:5]):  # Show first 5
            print(f"{i+1}. {doc.filename}")
        sys.exit(1)
    
    filename = sys.argv[1]
    get_doc_id(filename) 