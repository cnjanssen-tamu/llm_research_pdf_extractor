from django.test import TestCase, Client
from django.urls import reverse
from core.models import ProcessingJob, PDFDocument, ProcessingResult
import json
import pandas as pd
import io

class DownloadResultsTestCase(TestCase):
    def setUp(self):
        """Set up test data for download results tests"""
        self.client = Client()
        
        # Create a test job
        self.job = ProcessingJob.objects.create(
            name='Test Download Job',
            status='completed',
            processed_count=2,
            total_count=2
        )
        
        # Create test documents
        self.doc1 = PDFDocument.objects.create(
            job=self.job,
            file='test1.pdf',
            processed=True
        )
        
        self.doc2 = PDFDocument.objects.create(
            job=self.job,
            file='test2.pdf',
            processed=True
        )
        
        # Create test results
        result_data1 = {
            'case_results': [
                {
                    'case_number': {'value': '1', 'confidence': 100},
                    'age': {'value': '45', 'confidence': 90},
                    'sex': {'value': 'M', 'confidence': 100}
                }
            ]
        }
        
        result_data2 = {
            'case_results': [
                {
                    'case_number': {'value': '2', 'confidence': 100},
                    'age': {'value': '32', 'confidence': 85},
                    'sex': {'value': 'F', 'confidence': 100}
                }
            ]
        }
        
        self.result1 = ProcessingResult.objects.create(
            document=self.doc1,
            result_data=result_data1,
            raw_response=json.dumps(result_data1)
        )
        
        self.result2 = ProcessingResult.objects.create(
            document=self.doc2,
            result_data=result_data2,
            raw_response=json.dumps(result_data2)
        )
    
    def test_download_csv(self):
        """Test downloading results in CSV format"""
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': self.job.id, 'format': 'csv'})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        # Parse CSV content
        content = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(content))
        
        # Check for duplicates
        self.assertEqual(len(df), 2, "CSV should contain exactly 2 rows (no duplicates)")
        
        # Check content
        self.assertIn('case_number', df.columns)
        self.assertIn('age', df.columns)
        self.assertIn('sex', df.columns)
        
        # Verify values
        case_numbers = df['case_number'].tolist()
        self.assertIn('1', case_numbers)
        self.assertIn('2', case_numbers)
        
        ages = df['age'].tolist()
        self.assertIn('45', ages)
        self.assertIn('32', ages)
    
    def test_download_excel(self):
        """Test downloading results in Excel format"""
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': self.job.id, 'format': 'excel'})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # Parse Excel content
        df = pd.read_excel(io.BytesIO(response.content))
        
        # Check for duplicates
        self.assertEqual(len(df), 2, "Excel should contain exactly 2 rows (no duplicates)")
        
        # Check content
        self.assertIn('case_number', df.columns)
        self.assertIn('age', df.columns)
        self.assertIn('sex', df.columns)
        
        # Verify values
        case_numbers = df['case_number'].tolist()
        self.assertIn('1', case_numbers)
        self.assertIn('2', case_numbers)
        
        ages = df['age'].tolist()
        self.assertIn('45', ages)
        self.assertIn('32', ages)
    
    def test_download_json(self):
        """Test downloading results in JSON format"""
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': self.job.id, 'format': 'json'})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Parse JSON content
        content = json.loads(response.content)
        
        # Check for duplicates
        self.assertEqual(len(content), 2, "JSON should contain exactly 2 cases (no duplicates)")
        
        # Check content
        case_numbers = [case['case_number']['value'] for case in content]
        self.assertIn('1', case_numbers)
        self.assertIn('2', case_numbers)
        
        ages = [case['age']['value'] for case in content]
        self.assertIn('45', ages)
        self.assertIn('32', ages)
    
    def test_multiple_cases_per_document(self):
        """Test downloading results with multiple cases per document"""
        # Create a document with multiple cases
        doc3 = PDFDocument.objects.create(
            job=self.job,
            file='test3.pdf',
            processed=True
        )
        
        result_data3 = {
            'case_results': [
                {
                    'case_number': {'value': '3', 'confidence': 100},
                    'age': {'value': '28', 'confidence': 95},
                    'sex': {'value': 'M', 'confidence': 100}
                },
                {
                    'case_number': {'value': '4', 'confidence': 100},
                    'age': {'value': '56', 'confidence': 90},
                    'sex': {'value': 'F', 'confidence': 100}
                }
            ]
        }
        
        ProcessingResult.objects.create(
            document=doc3,
            result_data=result_data3,
            raw_response=json.dumps(result_data3)
        )
        
        # Update job counts
        self.job.processed_count = 3
        self.job.total_count = 3
        self.job.save()
        
        # Download CSV
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': self.job.id, 'format': 'csv'})
        )
        
        # Parse CSV content
        content = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(content))
        
        # Check for duplicates
        self.assertEqual(len(df), 4, "CSV should contain exactly 4 rows (no duplicates)")
        
        # Check content
        case_numbers = df['case_number'].tolist()
        self.assertIn('1', case_numbers)
        self.assertIn('2', case_numbers)
        self.assertIn('3', case_numbers)
        self.assertIn('4', case_numbers)
    
    def test_empty_results(self):
        """Test downloading results when there are no valid results"""
        # Create a job with no results
        empty_job = ProcessingJob.objects.create(
            name='Empty Job',
            status='completed',
            processed_count=0,
            total_count=0
        )
        
        # Try to download results
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': empty_job.id, 'format': 'csv'})
        )
        
        # Check response
        self.assertEqual(response.status_code, 404)
        self.assertIn('No results available for this job', response.content.decode('utf-8')) 