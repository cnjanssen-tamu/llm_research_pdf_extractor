#!/usr/bin/env python
"""
Script to check the most recent processing job and identify PDFs that produced errors
"""

import os
import sys
import django

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from django.utils import timezone
from core.models import ProcessingJob, PDFDocument, ProcessingResult

# ------------------------------------------------------------------
# 1.  Get the five most‑recent jobs
# ------------------------------------------------------------------
recent_jobs = ProcessingJob.objects.order_by('-created_at')[:5]
print('Most‑recent jobs:')
for j in recent_jobs:
    print(f'  {j.created_at:%Y-%m-%d %H:%M} | {j.id} | {j.name} | {j.status}')

# ------------------------------------------------------------------
# 2.  Focus on the newest job
# ------------------------------------------------------------------
job = recent_jobs[0]
print('\nInspecting newest job:', job.id, '|', job.name, '|', job.status)

# ------------------------------------------------------------------
# 3.  Find documents that ended in an error
# ------------------------------------------------------------------
docs_in_error = PDFDocument.objects.filter(job=job, status='error')
print(f'\nDocuments with status=error: {docs_in_error.count()}')

# 4.  Also look for results that contain an error field
results_with_error = ProcessingResult.objects.filter(document__job=job)\
                                            .exclude(error__isnull=True)
print('Results with saved error strings:', results_with_error.count())

# ------------------------------------------------------------------
# 5.  Print details & stored traceback / error text
# ------------------------------------------------------------------
for doc in docs_in_error:
    print('\n—— Document in error ————————————————————————')
    print('File:', doc.filename or doc.file.name)
    print('Document‑ID:', doc.id)
    print('Saved doc.error:', getattr(doc, "error", None))

    # Look for matching result row
    res = ProcessingResult.objects.filter(document=doc).first()
    if res:
        print('Saved result.error:', getattr(res, "error", None))
        print('raw_result first 500 chars:\n', res.raw_result[:500] if res.raw_result else None)

# If error strings were empty, grep the logs for the job‑id or document‑id
print('\nNext step: grep your logs for', job.id) 