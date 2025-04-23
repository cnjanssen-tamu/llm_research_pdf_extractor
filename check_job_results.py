import os
import sys
import json

# Add the directory containing the Django project to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
# Remove the nested 'pdf_processor' path as we've flattened the structure
sys.path.insert(0, current_dir)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')

import django
django.setup()

# Now import Django models
from core.models import ProcessingJob, ProcessingResult

def main():
    # Get latest job
    try:
        job = ProcessingJob.objects.latest('created_at')
        print(f'Latest job ID: {job.id}, created at: {job.created_at}')
        
        # Get results for this job
        results = ProcessingResult.objects.filter(document__job=job)
        print(f'Number of results: {results.count()}')
        
        # Examine each result
        for r in results:
            case_count = 0
            if r.result_data and 'case_results' in r.result_data:
                case_count = len(r.result_data['case_results'])
                # Print first few cases to see structure
                if case_count > 0:
                    first_case = r.result_data['case_results'][0]
                    print(f"First case fields: {', '.join(first_case.keys())}")
                    # Print a few specific fields to check data
                    if 'case_number' in first_case:
                        print(f"  case_number: {first_case['case_number'].get('value', 'N/A')}")
                    if 'gender' in first_case:
                        print(f"  gender: {first_case['gender'].get('value', 'N/A')}")
                    
                    # If there are multiple cases, check if they differ
                    if case_count > 1:
                        print("Comparing cases for uniqueness:")
                        common_fields = {'gender', 'age', 'pathology', 'location'}
                        common_fields = common_fields.intersection(set(first_case.keys()))
                        
                        values_by_field = {field: [] for field in common_fields}
                        
                        for case in r.result_data['case_results'][:5]:  # Check up to 5 cases
                            for field in common_fields:
                                if field in case and 'value' in case[field]:
                                    values_by_field[field].append(case[field]['value'])
                        
                        for field, values in values_by_field.items():
                            unique_values = set(values)
                            print(f"  {field}: {len(unique_values)} unique values out of {len(values)}")
                            print(f"    Values: {', '.join(str(v) for v in values[:5])}")
            
            print(f'Result ID: {r.id}, cases: {case_count} case(s)')
    
    except ProcessingJob.DoesNotExist:
        print("No jobs found in database")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 