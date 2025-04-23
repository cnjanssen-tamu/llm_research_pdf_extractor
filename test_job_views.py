#!/usr/bin/env python
"""
Script to test JobDetailView and DownloadResultsView for job ID 81
"""

import os
import sys
import django
import pandas as pd
import io

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

# Import models
from core.models import ProcessingJob, ProcessingResult
from core.views import JobDetailView, DownloadResultsView
from core.utils import deduplicate_cases, validate_case_structure
from django.http import HttpRequest
from django.test import RequestFactory

def test_job_views(job_id):
    print(f"Testing views for job ID: {job_id}")
    
    try:
        job = ProcessingJob.objects.get(id=job_id)
        print(f"Found job: {job.name} (Status: {job.status})")
        
        # Create request factory for testing views
        factory = RequestFactory()
        
        # Test JobDetailView
        print("\n=== Testing JobDetailView ===")
        request = factory.get(f'/jobs/{job_id}/')
        view = JobDetailView()
        view.object = job
        view.request = request
        context = view.get_context_data()
        
        # Check if table_html is in the context
        if 'table_html' in context:
            print("JobDetailView generated table_html successfully")
            # Check if stats are in the context
            if 'stats' in context:
                print(f"Statistics from JobDetailView:")
                print(f"  Total cases: {context['stats']['total_cases']}")
                print(f"  Valid cases: {context['stats']['valid_cases']}")
                print(f"  Unique cases: {context['stats']['unique_cases']}")
                print(f"  Duplicates removed: {context['stats']['duplicates_removed']}")
        else:
            print("JobDetailView did not generate table_html")
            if 'error' in context:
                print(f"Error: {context['error']}")
                
        # Test manual deduplication
        print("\n=== Testing Manual Deduplication ===")
        results = ProcessingResult.objects.filter(document__job=job)
        all_cases = []
        
        for result in results:
            if result.result_data and 'case_results' in result.result_data:
                all_cases.extend(result.result_data['case_results'])
                
        print(f"Found {len(all_cases)} total cases across all results")
        valid_cases = [case for case in all_cases if validate_case_structure(case)]
        print(f"Found {len(valid_cases)} valid cases")
        unique_cases = deduplicate_cases(valid_cases)
        print(f"Found {len(unique_cases)} unique cases after deduplication")
        
        # Test DownloadResultsView's dataframe creation directly
        print("\n=== Testing DownloadResultsView _create_dataframe_from_results ===")
        download_view = DownloadResultsView()
        df = download_view._create_dataframe_from_results(results)
        
        if not df.empty:
            print(f"DataFrame created successfully with {len(df)} rows")
            print(f"DataFrame columns: {df.columns.tolist()[:5]}...")
            
            # Check for duplicates
            print(f"Checking for duplicates in the output...")
            print(f"  Row count matches unique cases: {'YES' if len(df) == len(unique_cases) else 'NO'}")
            
            # Print the first row of data
            if len(df) > 0:
                print("\nFirst row data:")
                for col in df.columns[:5]:  # First 5 columns
                    print(f"  {col}: {df.iloc[0][col]}")
        else:
            print("DataFrame is empty")
    
    except ProcessingJob.DoesNotExist:
        print(f"Job with ID {job_id} does not exist")
    except Exception as e:
        print(f"Error testing job views: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    job_id = 81  # Set the job ID to test
    test_job_views(job_id) 