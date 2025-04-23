import os
import sys
import django
import pandas as pd
import requests
from io import StringIO

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from core.models import ProcessingJob

# Job ID to check
job_id = 'a4fe0af8-cd90-46c1-a8b8-3adc19d48e91'

# Create a test client with authenticated user
client = Client()

# Get or create a test user
username = 'testuser'
password = 'testpassword'

try:
    user = User.objects.get(username=username)
except User.DoesNotExist:
    user = User.objects.create_user(username=username, password=password)

# Log in
client.login(username=username, password=password)

# Get the CSV download URL
csv_url = f'/download-results/{job_id}/csv/'
print(f"Fetching CSV from URL: {csv_url}")

# Make the request
response = client.get(csv_url)
print(f"Response status code: {response.status_code}")

if response.status_code == 200:
    # Parse the CSV content
    csv_content = response.content.decode('utf-8')
    df = pd.read_csv(StringIO(csv_content))
    
    # Check the columns
    print(f"\nColumns in CSV: {df.columns.tolist()}")
    
    # Check for Primary column
    if 'Primary' in df.columns:
        print(f"\nPrimary column exists in CSV")
        # Show sample values
        print(f"Primary column values: {df['Primary'].tolist()}")
    else:
        print(f"\nPrimary column is MISSING in CSV")
        # Check for case-sensitive variants
        variants = [col for col in df.columns if col.lower() == 'primary']
        if variants:
            print(f"Found similar columns: {variants}")
    
    # Save the CSV for inspection
    df.to_csv('downloaded_csv.csv', index=False)
    print("Saved CSV to downloaded_csv.csv for inspection")
else:
    print(f"Error fetching CSV: {response.content.decode('utf-8')}") 