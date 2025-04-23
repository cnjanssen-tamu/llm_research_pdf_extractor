from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from core.models import ProcessingJob, PDFDocument, ProcessingResult, SavedPrompt, ColumnDefinition
import json
import os

class PDFProcessingTestCase(TestCase):
    def setUp(self):
        """Set up test data for PDF processing tests"""
        self.client = Client()
        
        # Create test column definitions
        self.age_column = ColumnDefinition.objects.create(
            name='age',
            description='Patient age in years',
            category='demographics',
            data_type='integer',
            min_value=0,
            max_value=120,
            optional=False
        )
        
        self.sex_column = ColumnDefinition.objects.create(
            name='sex',
            description='Patient sex',
            category='demographics',
            data_type='enum',
            enum_values=['M', 'F', 'Other'],
            optional=False
        )
        
        # Create a test prompt
        self.test_prompt = SavedPrompt.objects.create(
            name='Test Prompt',
            content='Extract the following information from the PDF: age, sex',
            variables={
                'disease_condition': 'Test Condition',
                'population_age': 'Adult',
                'grading_of_lesion': 'Grade I'
            }
        )
        
        # Create a test job
        self.job = ProcessingJob.objects.create(
            name='Test Processing Job',
            status='pending',
            prompt_template=self.test_prompt.content
        )
        
        # Create a test PDF file
        self.test_pdf_path = os.path.join(os.path.dirname(__file__), 'test_files', 'test.pdf')
        if not os.path.exists(os.path.dirname(self.test_pdf_path)):
            os.makedirs(os.path.dirname(self.test_pdf_path))
        
        # Create a simple PDF file for testing if it doesn't exist
        if not os.path.exists(self.test_pdf_path):
            with open(self.test_pdf_path, 'wb') as f:
                f.write(b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n')
    
    def test_job_creation(self):
        """Test creating a processing job"""
        # Create a mock PDF file
        with open(self.test_pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        pdf_file = SimpleUploadedFile('test.pdf', pdf_content, content_type='application/pdf')
        
        # Create a job via the API
        with patch('core.views.ProcessorView._get_gemini_response') as mock_gemini:
            # Mock the Gemini response
            mock_gemini.return_value = json.dumps({
                'case_results': [
                    {
                        'age': {'value': '45', 'confidence': 90},
                        'sex': {'value': 'M', 'confidence': 100}
                    }
                ]
            })
            
            # Also mock _extract_pages_from_pdf to avoid actual PDF processing
            with patch('core.views.ProcessorView._extract_pages_from_pdf') as mock_extract:
                mock_extract.return_value = [{'page_number': 'all', 'pdf_data': pdf_content, 'token_count': 100}]
                
                response = self.client.post(
                    reverse('core:process'),
                    {
                        'name': 'Test Job',
                        'prompt_template': self.test_prompt.content,
                        'pdf_files': [pdf_file]
                    },
                    format='multipart'
                )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify job was created
        job_id = response_data['job_id']
        job = ProcessingJob.objects.get(id=job_id)
        self.assertEqual(job.name, 'Test Job')
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.prompt_template, self.test_prompt.content)
        
        # Verify document was created
        document = PDFDocument.objects.get(job=job)
        self.assertTrue(document.processed)
        
        # Verify result was created
        result = ProcessingResult.objects.get(document=document)
        self.assertIn('case_results', result.result_data)
        self.assertEqual(result.result_data['case_results'][0]['age']['value'], '45')
        self.assertEqual(result.result_data['case_results'][0]['sex']['value'], 'M')
    
    def test_job_detail_view(self):
        """Test viewing job details"""
        # Create a document and result
        document = PDFDocument.objects.create(
            job=self.job,
            file='test.pdf',
            processed=True
        )
        
        result_data = {
            'case_results': [
                {
                    'age': {'value': '45', 'confidence': 90},
                    'sex': {'value': 'M', 'confidence': 100}
                }
            ]
        }
        
        ProcessingResult.objects.create(
            document=document,
            result_data=result_data,
            raw_response=json.dumps(result_data)
        )
        
        # Update job status
        self.job.status = 'completed'
        self.job.processed_count = 1
        self.job.total_count = 1
        self.job.save()
        
        # View job details
        response = self.client.get(reverse('core:job_detail', kwargs={'pk': self.job.id}))
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Processing Job')
        self.assertContains(response, 'completed')
        self.assertContains(response, '100%')  # Progress
    
    def test_download_results(self):
        """Test downloading job results"""
        # Create a document and result
        document = PDFDocument.objects.create(
            job=self.job,
            file='test.pdf',
            processed=True
        )
        
        result_data = {
            'case_results': [
                {
                    'age': {'value': '45', 'confidence': 90},
                    'sex': {'value': 'M', 'confidence': 100}
                }
            ]
        }
        
        ProcessingResult.objects.create(
            document=document,
            result_data=result_data,
            raw_response=json.dumps(result_data)
        )
        
        # Update job status
        self.job.status = 'completed'
        self.job.processed_count = 1
        self.job.total_count = 1
        self.job.save()
        
        # Download results in CSV format
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': self.job.id, 'format': 'csv'})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="results_', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        self.assertIn('age', content)
        self.assertIn('sex', content)
        self.assertIn('45', content)
        self.assertIn('M', content)
        
        # Download results in JSON format
        response = self.client.get(
            reverse('core:download_results', kwargs={'job_id': self.job.id, 'format': 'json'})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Check JSON content
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]['age']['value'], '45')
        self.assertEqual(content[0]['sex']['value'], 'M')
    
    def test_extract_json_from_text(self):
        """Test extracting JSON from text response"""
        from core.views import ProcessorView
        
        processor = ProcessorView()
        
        # Test valid JSON
        valid_json_text = '```json\n{"case_results": [{"age": {"value": "45", "confidence": 90}}]}\n```'
        result = processor.extract_json_from_text(valid_json_text)
        self.assertIn('case_results', result)
        self.assertEqual(result['case_results'][0]['age']['value'], '45')
        
        # Test JSON with extra text
        mixed_text = 'Here is the result:\n```json\n{"case_results": [{"age": {"value": "45", "confidence": 90}}]}\n```\nEnd of result.'
        result = processor.extract_json_from_text(mixed_text)
        self.assertIn('case_results', result)
        self.assertEqual(result['case_results'][0]['age']['value'], '45')
        
        # Test invalid JSON
        invalid_json = 'This is not JSON'
        result = processor.extract_json_from_text(invalid_json)
        self.assertIn('error', result)
        self.assertIn('is_truncated', result)
        self.assertFalse(result['is_truncated'])
        
        # Test truncated JSON
        truncated_json = '{"case_results": [{"age": {"value": "45", "confidence": 90'
        result = processor.extract_json_from_text(truncated_json)
        self.assertIn('error', result)
        self.assertIn('is_truncated', result)
        self.assertTrue(result['is_truncated'])
    
    def test_process_pdfs_with_extraction(self):
        """Test processing PDFs with text extraction"""
        # Create a mock PDF file
        with open(self.test_pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        pdf_file = SimpleUploadedFile('test.pdf', pdf_content, content_type='application/pdf')
        
        # Create a job via the API
        with patch('core.views.ProcessorView._process_extracted_text') as mock_process:
            # Mock the text processing
            mock_process.return_value = {
                'case_results': [
                    {
                        'age': {'value': '45', 'confidence': 90},
                        'sex': {'value': 'M', 'confidence': 100}
                    }
                ]
            }
            
            # Also mock _extract_pages_from_pdf to avoid actual PDF processing
            with patch('core.views.ProcessorView._extract_pages_from_pdf') as mock_extract:
                mock_extract.return_value = [{'page_number': 'all', 'pdf_data': pdf_content, 'token_count': 100}]
                
                response = self.client.post(
                    reverse('core:process'),
                    {
                        'name': 'Test Extraction Job',
                        'prompt_template': self.test_prompt.content,
                        'pdf_files': [pdf_file],
                        'process_type': 'with_extraction'
                    },
                    format='multipart'
                )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify job was created
        job_id = response_data['job_id']
        job = ProcessingJob.objects.get(id=job_id)
        self.assertEqual(job.name, 'Test Extraction Job')
        
        # Verify document was created
        document = PDFDocument.objects.get(job=job)
        
        # Verify result was created
        result = ProcessingResult.objects.get(document=document)
        self.assertIn('case_results', result.result_data)
        self.assertEqual(result.result_data['case_results'][0]['age']['value'], '45')
        self.assertEqual(result.result_data['case_results'][0]['sex']['value'], 'M') 