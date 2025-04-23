#!/usr/bin/env python
"""
Script to debug the 'list indices must be integers or slices, not str' error
that's occurring during processing of certain documents
"""

import os
import sys
import django
import json
import traceback
import re

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_processor.settings")
django.setup()

from core.models import PDFDocument, ProcessingResult, ProcessingJob

# Get the problematic job
job_id = "c8f63122-645a-4dfb-a4fd-0a4a0c88ba65"
job = ProcessingJob.objects.get(id=job_id)
print(f"Job: {job.name} (Status: {job.status})")

# Find all error documents to check for patterns
docs_in_error = PDFDocument.objects.filter(job=job, status='error')
print(f"Found {docs_in_error.count()} documents with errors")

# Load all the actual processing code to trace through it
from core.utils import filter_cited_cases, extract_json_from_text

# Store document findings
findings = []

# Process each error document
for doc in docs_in_error:
    print(f"\n{'='*60}")
    print(f"Examining document: {doc.filename}")
    
    # Get result if any
    result = ProcessingResult.objects.filter(document=doc).first()
    if not result or not result.raw_result:
        print(f"  No raw result found")
        continue
        
    # Check error message for the specific error
    error_msg = doc.error or ""
    if "list indices" in error_msg:
        print(f"  Found list indices error: {error_msg}")
    else:
        print(f"  Different error: {error_msg}")
        
    # Extract JSON manually
    try:
        json_text = None
        
        # Try code block pattern first
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, result.raw_result)
        
        if not match:
            # Try direct JSON pattern
            json_pattern = r'({[\s\S]*})'
            match = re.search(json_pattern, result.raw_result)
            
        if match:
            json_text = match.group(1)
            json_data = json.loads(json_text)
            print(f"  Successfully extracted JSON manually")
            
            # Check structure
            if 'case_results' in json_data:
                cases = json_data['case_results']
                case_type = type(cases)
                print(f"  Found case_results with {len(cases)} cases (type: {case_type})")
                
                # Check each case for the problematic field
                for i, case in enumerate(cases):
                    if not isinstance(case, dict):
                        print(f"  Case {i} is not a dictionary! Type: {type(case)}")
                        continue
                        
                    # Look for fields that are lists
                    list_fields = []
                    for key, value in case.items():
                        if isinstance(value, list):
                            list_fields.append((key, value))
                            
                    if list_fields:
                        print(f"  Found {len(list_fields)} list fields in case {i}:")
                        for key, value in list_fields:
                            print(f"    {key}: {value}")
                
                # Try the actual filter_cited_cases on this data
                try:
                    filtered = filter_cited_cases(json_data)
                    print(f"  Successfully filtered with filter_cited_cases")
                    findings.append({
                        "filename": doc.filename,
                        "manual_success": True,
                        "filter_success": True,
                        "list_fields": False
                    })
                except Exception as e:
                    print(f"  Error using filter_cited_cases: {e}")
                    findings.append({
                        "filename": doc.filename,
                        "manual_success": True,
                        "filter_success": False,
                        "error": str(e)
                    })
            else:
                print(f"  No case_results found in extracted JSON")
                print(f"  Keys found: {json_data.keys()}")
        else:
            print(f"  Could not find JSON pattern in raw result")
            # Try using the regular extraction
            try:
                extracted = extract_json_from_text(result.raw_result)
                if extracted:
                    print(f"  Successfully extracted with extract_json_from_text")
                    print(f"  Keys: {extracted.keys()}")
                    findings.append({
                        "filename": doc.filename,
                        "extract_success": True
                    })
                else:
                    print(f"  extract_json_from_text returned None")
                    findings.append({
                        "filename": doc.filename,
                        "extract_success": False
                    })
            except Exception as e:
                print(f"  Error with extract_json_from_text: {e}")
                traceback.print_exc()
                findings.append({
                    "filename": doc.filename,
                    "extract_success": False,
                    "extract_error": str(e)
                })
                
    except Exception as e:
        print(f"  Error processing document: {e}")
        traceback.print_exc()
        findings.append({
            "filename": doc.filename,
            "error": str(e)
        })

# Now try to access this code directly - load the function source to inspect it
print("\n" + "="*60)
print("Examining core.utils.filter_cited_cases function:")
import inspect

# Print the first part of the function
print(inspect.getsource(filter_cited_cases).split("\n")[:30])

# Print summary of findings
print("\n" + "="*60)
print("Error Pattern Summary:")
for finding in findings:
    print(f"- {finding.get('filename', 'Unknown')}: ", end="")
    if finding.get("manual_success", False):
        print("JSON extraction worked manually", end="")
        if finding.get("filter_success", False):
            print(", filter_cited_cases worked manually")
        else:
            print(f", filter_cited_cases failed: {finding.get('error', 'Unknown')}")
    else:
        print(f"Extraction failed: {finding.get('error', finding.get('extract_error', 'Unknown'))}")

# Look at the error directly in a clean experiment
print("\n" + "="*60)
print("Direct Experiment:")
try:
    # Simulate a list and try to use .get() on it
    test_list = [1, 2, 3]
    # This should raise the same error we're seeing in the logs
    print(f"Trying list.get() which should fail: ", end="")
    test_list.get('key')
except Exception as e:
    print(f"Got expected error: {str(e)}")
    
# Now try the "value" key access on a list
try:
    test_list = [1, 2, 3]
    print(f"Trying list['value'] which should fail: ", end="")
    test_list["value"]
except Exception as e:
    print(f"Got expected error: {str(e)}")
    
print("\nConclusion: The error 'list indices must be integers or slices, not str' occurs when:")
print("1. Code is trying to access a list using a string index (like list['key'])")
print("2. OR when trying to call .get() on a list object")
print("The most common cause would be assuming a dict but getting a list") 