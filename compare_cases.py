#!/usr/bin/env python
"""
Script to compare case data between multiple results for the same job
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

def compare_case_data(job_id):
    print(f"Comparing case data for job ID: {job_id}")
    
    try:
        job = ProcessingJob.objects.get(id=job_id)
        results = ProcessingResult.objects.filter(document__job=job)
        
        print(f"Found {results.count()} results for job {job_id}")
        
        all_cases = []
        
        # Extract cases from all results
        for i, result in enumerate(results):
            if result.result_data and 'case_results' in result.result_data:
                cases = result.result_data['case_results']
                print(f"Result {i+1} (Document: {result.document.file.name}, Created: {result.created_at}):")
                print(f"  Contains {len(cases)} cases")
                
                for j, case in enumerate(cases):
                    print(f"  Case {j+1}:")
                    all_cases.append({
                        'result_id': result.id,
                        'case_index': j,
                        'case_data': case
                    })
                    
                    # Print some sample data
                    if isinstance(case, dict):
                        for field in list(case.keys())[:3]:  # First 3 fields
                            if isinstance(case[field], dict) and 'value' in case[field]:
                                print(f"    {field}: {case[field]['value']} (confidence: {case[field]['confidence']})")
        
        # Compare cases across results
        if len(all_cases) > 1:
            print("\nComparing cases across results:")
            
            for i, case1 in enumerate(all_cases):
                for j, case2 in enumerate(all_cases):
                    if i >= j:  # Skip self-comparison and duplicates
                        continue
                        
                    # Only compare cases from different results
                    if case1['result_id'] != case2['result_id']:
                        print(f"\nComparing Case {case1['case_index']+1} from Result {case1['result_id']} with Case {case2['case_index']+1} from Result {case2['result_id']}:")
                        
                        are_identical = True
                        differences = []
                        
                        # Check all fields in both cases
                        all_fields = set(case1['case_data'].keys()) | set(case2['case_data'].keys())
                        
                        for field in all_fields:
                            # If field exists in both cases
                            if field in case1['case_data'] and field in case2['case_data']:
                                value1 = case1['case_data'][field]
                                value2 = case2['case_data'][field]
                                
                                if value1 != value2:
                                    are_identical = False
                                    
                                    # Format for easier comparison if they're dictionaries
                                    if isinstance(value1, dict) and isinstance(value2, dict):
                                        val1 = value1.get('value', '')
                                        val2 = value2.get('value', '')
                                        conf1 = value1.get('confidence', 0)
                                        conf2 = value2.get('confidence', 0)
                                        
                                        if val1 != val2 or conf1 != conf2:
                                            differences.append(f"Field '{field}': Value1='{val1}' (conf:{conf1}) vs Value2='{val2}' (conf:{conf2})")
                                    else:
                                        differences.append(f"Field '{field}': Different structure")
                            # If field exists in only one case
                            else:
                                are_identical = False
                                differences.append(f"Field '{field}': Only exists in {'Case 1' if field in case1['case_data'] else 'Case 2'}")
                        
                        if are_identical:
                            print("  The cases are IDENTICAL")
                        else:
                            print("  The cases are DIFFERENT")
                            print("  Differences:")
                            for diff in differences[:5]:  # Show first 5 differences
                                print(f"    - {diff}")
                            if len(differences) > 5:
                                print(f"    ... and {len(differences) - 5} more differences")
    
    except ProcessingJob.DoesNotExist:
        print(f"Job with ID {job_id} does not exist")
    except Exception as e:
        print(f"Error comparing case data: {str(e)}")

if __name__ == "__main__":
    job_id = 81  # Set the job ID to inspect
    compare_case_data(job_id) 