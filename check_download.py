import os
import sys
import django
import json
import numpy as np
import pandas as pd
from io import StringIO
from pprint import pprint

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from core.models import ProcessingJob, ProcessingResult, PDFDocument

# Job ID to check
job_id = 'a4fe0af8-cd90-46c1-a8b8-3adc19d48e91'

# Recreate the DownloadResultsView logic
job = ProcessingJob.objects.get(id=job_id)
results = ProcessingResult.objects.filter(document__job=job)

print(f"Found job with {results.count()} results")

# Combine all cases from all results
all_cases = []
for result in results:
    if result.json_result and 'case_results' in result.json_result:
        # Add document metadata to each case before adding to all_cases
        for case in result.json_result['case_results']:
            # Add document filename and study author to each case
            case['document_filename'] = {
                'value': result.document.filename if result.document else 'Unknown',
                'confidence': 100
            }
            case['study_author'] = {
                'value': result.document.study_author or 'Unknown',
                'confidence': 100
            }
        all_cases.extend(result.json_result['case_results'])

print(f"Combined {len(all_cases)} total cases")

# Check for Primary field in sample cases
if all_cases:
    print("\nSample case keys:")
    pprint(list(all_cases[0].keys()))
    print(f"\nPrimary field present: {'Primary' in all_cases[0]}")
    if 'Primary' in all_cases[0]:
        print(f"Primary value: {all_cases[0]['Primary']}")

# Apply post-processing filter to remove cited cases
from core.utils import filter_cited_cases
combined_results = {'case_results': all_cases}
filtered_combined = filter_cited_cases(combined_results)

# Check if filtering removed any cases
if 'filtering_metadata' in filtered_combined:
    excluded_count = filtered_combined['filtering_metadata']['excluded_case_count']
    filtered_count = filtered_combined['filtering_metadata']['filtered_case_count']
    print(f"\nFiltered out {excluded_count} cited cases. Download will contain {filtered_count} primary cases.")
    all_cases = filtered_combined['case_results']

# Create a dataframe from the cases - THIS IS THE KEY PART
df_data = {}
for case in all_cases:
    for field_key, field_data in case.items():
        if isinstance(field_data, dict) and 'value' in field_data:
            # Create column for this field if it doesn't exist
            if field_key not in df_data:
                df_data[field_key] = []
            
            # Add this case's value
            df_data[field_key].append(field_data['value'])
            
            # Create confidence column if needed
            if 'confidence' in field_data:
                confidence_key = f"{field_key}_confidence"
                if confidence_key not in df_data:
                    df_data[confidence_key] = []
                df_data[confidence_key].append(field_data['confidence'])

# Convert to DataFrame
df = pd.DataFrame(df_data)

# Clean up the DataFrame - replace nulls with empty strings
df = df.replace({np.nan: '', None: '', 'null': '', 'None': ''})

# Check DataFrame columns
print("\nDataFrame columns:")
pprint(df.columns.tolist())

# Check for Primary column
if 'Primary' in df.columns:
    print("\nPrimary column exists in DataFrame")
    print(f"Primary column values: {df['Primary'].tolist()}")
else:
    print("\nPrimary column is MISSING in DataFrame")
    # Check for case-sensitivity issues
    variants = [col for col in df.columns if col.lower() == 'primary']
    if variants:
        print(f"Found similar columns instead: {variants}")

# Save the DataFrame to CSV for inspection
csv_path = 'simulated_download.csv'
df.to_csv(csv_path, index=False)
print(f"\nSaved simulated CSV to {csv_path}") 