import os
import sys
import django
import pandas as pd
from io import StringIO

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import ProcessingJob

# Job ID to check
job_id = 'a4fe0af8-cd90-46c1-a8b8-3adc19d48e91'

# Create and authenticate the test client
client = Client()

# Create a test user and login
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
client.login(username='admin', password='password')

# Get the URL for the download view
url = f'/download-results/{job_id}/csv/'
print(f"Requesting URL: {url}")

# Make the request
response = client.get(url, follow=True)
print(f"Response status: {response.status_code}")

if response.status_code == 200:
    # Parse the CSV content
    content = response.content.decode('utf-8')
    
    # Save the raw CSV for inspection
    with open('real_download.csv', 'w') as f:
        f.write(content)
    print("Saved raw CSV to real_download.csv")
    
    # Parse the CSV to see the columns
    try:
        df = pd.read_csv(StringIO(content))
        print("\nColumns in downloaded CSV:")
        print(df.columns.tolist())
        
        # Check for Primary column
        if 'Primary' in df.columns:
            print("\nPrimary column exists in CSV!")
            print(f"Primary values: {df['Primary'].tolist()}")
        else:
            print("\nPrimary column is missing from CSV!")
            
            # Check for case-sensitive variants
            variants = [col for col in df.columns if col.lower() == 'primary']
            if variants:
                print(f"Found similar columns: {variants}")
                
    except Exception as e:
        print(f"Error parsing CSV: {str(e)}")
else:
    print(f"Error response: {response.content.decode('utf-8')}") 