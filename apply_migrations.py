#!/usr/bin/env python
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

# Create migrations and apply them
from django.core.management import call_command

print("Creating migrations for the Reference model and job_type field...")
call_command('makemigrations')

print("\nApplying migrations...")
call_command('migrate')

print("\nMigrations applied successfully!") 