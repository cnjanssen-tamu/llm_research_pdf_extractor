from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from django.utils import timezone
import json
import os
import uuid

from core.models import ProcessingJob, PDFDocument, ProcessingResult, SavedPrompt
from core.utils import extract_json_from_text, is_response_truncated, prepare_continuation_prompt
from core.views import JobDetailView

class TruncationHandlingTestCase(TestCase):
    def setUp(self):
        """Set up test data for truncation handling tests"""
        self.client = Client()
        
        # Create a test prompt
        self.test_prompt = SavedPrompt.objects.create(
            name='Test Prompt',
            content='Extract the following information from the PDF: age, gender, diagnosis',
            variables={}
        )
        
        # Create a test job
        self.job = ProcessingJob.objects.create(
            name='Test Truncation Job',
            status='processing',
            processed_count=1,
            total_count=1,
            prompt_template=self.test_prompt.content,
            error_message=""
        )
        
        # Create a test PDF document
        self.document = PDFDocument.objects.create(
            job=self.job,
            file='test.pdf',
            filename='test.pdf',
            status='processed'
        )
    
    def test_truncation_detection(self):
        """Test detection of truncated responses"""
        # Test various types of truncated responses
        truncated_text = 'Here is the JSON: {"case_results": [{"age": {"value": "45", "confidence": 90}, "gender": {"val'
        self.assertTrue(is_response_truncated(truncated_text))
        
        incomplete_json = '{"case_results": [{"age": {"value": "45", "confidence": 90}}}, {"gender": {'
        self.assertTrue(is_response_truncated(incomplete_json))
        
        # Test a complete response
        complete_text = '{"case_results": [{"age": {"value": "45", "confidence": 90}, "gender": {"value": "M", "confidence": 100}}]}'
        self.assertFalse(is_response_truncated(complete_text))
        
    def test_extract_json_from_truncated_text(self):
        """Test extraction of JSON from truncated text"""
        truncated_text = 'Here is the JSON: {"case_results": [{"age": {"value": "45", "confidence": 90}, "gender": {"val'
        result = extract_json_from_text(truncated_text)
        
        # Verify that truncation is detected and flagged in the result
        self.assertIn('is_truncated', result)
        self.assertTrue(result['is_truncated'])
        self.assertIn('error', result)  # Should have an error due to invalid JSON
    
    def test_truncated_result_view(self):
        """Test that the job detail view correctly shows truncation status"""
        # Create a truncated result
        truncated_result = ProcessingResult.objects.create(
            document=self.document,
            is_complete=False,  # Mark as incomplete/truncated
            json_result={
                'case_results': [
                    {'case_number': {'value': '1', 'confidence': 100}, 
                     'age': {'value': '45', 'confidence': 90}}
                ],
                'is_truncated': True,
                'truncation_info': {'last_complete_case': 1}
            },
            raw_result='{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "45", "confidence": 90}}], "is_truncated": true}'
        )
        
        # Update job status to reflect truncation
        self.job.status = 'pending_continuation'
        self.job.save()
        
        # View job details
        response = self.client.get(reverse('core:job_detail', kwargs={'pk': self.job.id}))
        
        # Check that truncation alert is shown
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Truncated Response Detected')
        self.assertContains(response, 'Continue Processing')
    
    def test_continuation_prompt_generation(self):
        """Test generation of continuation prompts"""
        original_prompt = "Extract the following information from the PDF: age, gender, diagnosis"
        previous_response = '{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "45", "confidence": 90}}], "is_truncated": true}'
        
        continuation_prompt = prepare_continuation_prompt(original_prompt, previous_response)
        
        # Verify the continuation prompt has the right elements
        self.assertIn('CONTINUATION REQUEST', continuation_prompt)
        self.assertIn('original prompt', continuation_prompt.lower())
        self.assertIn('Start with case', continuation_prompt)
    
    @patch('core.views.JobDetailView._process_continuation')
    def test_continuation_processing(self, mock_process_continuation):
        """Test the continuation processing flow"""
        # Setup mock to simulate successful processing
        mock_process_continuation.return_value = {"success": True, "is_truncated": False}
        
        # Create a truncated result
        truncated_result = ProcessingResult.objects.create(
            document=self.document,
            is_complete=False,
            json_result={
                'case_results': [
                    {'case_number': {'value': '1', 'confidence': 100}, 
                     'age': {'value': '45', 'confidence': 90}}
                ],
                'is_truncated': True,
                'truncation_info': {'last_complete_case': 1}
            },
            raw_result='{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "45", "confidence": 90}}], "is_truncated": true}'
        )
        
        # Update job status
        self.job.status = 'pending_continuation'
        self.job.save()
        
        # Call the continuation endpoint
        response = self.client.post(
            reverse('core:job_detail', kwargs={'pk': self.job.id}),
            json.dumps({
                'action': 'continue_processing',
                'last_case_number': 1,
                'document_id': str(self.document.id)
            }),
            content_type='application/json'
        )
        
        # Check that the continuation was initiated
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify mock was called
        mock_process_continuation.assert_called_once()

class ContinuationProcessingTestCase(TestCase):
    def setUp(self):
        """Set up test data for continuation processing tests"""
        self.client = Client()
        
        # Create a test job with multiple documents
        self.job = ProcessingJob.objects.create(
            name='Multi-Document Truncation Test',
            status='processing',
            processed_count=2,
            total_count=3,
            prompt_template="Extract medical case information",
            error_message=""
        )
        
        # Create multiple documents
        self.doc1 = PDFDocument.objects.create(
            job=self.job,
            file='doc1.pdf',
            filename='doc1.pdf',
            status='complete'
        )
        
        self.doc2 = PDFDocument.objects.create(
            job=self.job,
            file='doc2.pdf',
            filename='doc2.pdf',
            status='processed'  # Not complete
        )
        
        self.doc3 = PDFDocument.objects.create(
            job=self.job,
            file='doc3.pdf',
            filename='doc3.pdf',
            status='pending'
        )
        
        # Create results for first two documents
        self.result1 = ProcessingResult.objects.create(
            document=self.doc1,
            is_complete=True,
            json_result={
                'case_results': [
                    {'case_number': {'value': '1', 'confidence': 100}, 
                     'age': {'value': '45', 'confidence': 90}}
                ]
            },
            raw_result='{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "45", "confidence": 90}}]}'
        )
        
        self.result2 = ProcessingResult.objects.create(
            document=self.doc2,
            is_complete=False,  # Truncated result
            json_result={
                'case_results': [
                    {'case_number': {'value': '1', 'confidence': 100}, 
                     'age': {'value': '30', 'confidence': 90}}
                ],
                'is_truncated': True,
                'truncation_info': {'last_complete_case': 1}
            },
            raw_result='{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "30", "confidence": 90}}], "is_truncated": true}'
        )
    
    def test_job_status_with_mixed_completion(self):
        """Test job status detection with mixed document completion states"""
        # Update job status to pending continuation
        self.job.status = 'pending_continuation'
        self.job.save()
        
        view = JobDetailView()
        view.object = self.job
        context = view.get_context_data()
        
        # Check truncation status
        self.assertTrue(context['is_truncated'])
        
        # One document should need continuation
        self.assertEqual(len(context['docs_needing_continuation']), 1)
        self.assertEqual(context['docs_needing_continuation'][0], self.doc2.id)
        
        # The continuation document ID should be set to doc2
        self.assertEqual(context['continuation_document_id'], self.doc2.id)
    
    @patch('core.views.call_gemini_with_pdf')
    def test_sequential_document_processing(self, mock_gemini_call):
        """Test that documents are processed sequentially when one is truncated"""
        # Mock the Gemini API response for continuing doc2
        mock_gemini_call.return_value = {
            'text': '{"case_results": [{"case_number": {"value": "2", "confidence": 100}, "age": {"value": "35", "confidence": 90}}]}'
        }
        
        # Setup the third document to be processed after continuing doc2
        with patch('core.views.process_document') as mock_process:
            mock_process.return_value = {
                'success': True,
                'result': '{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "25", "confidence": 90}}]}'
            }
            
            # Continue processing doc2
            response = self.client.post(
                reverse('core:continue_processing', kwargs={'document_id': self.doc2.id})
            )
            
            # Check response
            self.assertEqual(response.status_code, 200)
            
            # Verify that continuation was successful
            doc2 = PDFDocument.objects.get(id=self.doc2.id)
            self.assertEqual(doc2.status, 'complete')
            
            # Verify that process_document was called for doc3
            mock_process.assert_called_with(self.doc3)
    
    def test_job_completion_after_all_documents(self):
        """Test that job status is updated correctly after all documents are processed"""
        # Mark all documents as complete
        self.doc2.status = 'complete'
        self.doc2.save()
        
        self.doc3.status = 'complete'
        self.doc3.save()
        
        # Create a complete result for doc2
        ProcessingResult.objects.create(
            document=self.doc2,
            is_complete=True,
            json_result={
                'case_results': [
                    {'case_number': {'value': '2', 'confidence': 100}, 
                     'age': {'value': '35', 'confidence': 90}}
                ]
            },
            raw_result='{"case_results": [{"case_number": {"value": "2", "confidence": 100}, "age": {"value": "35", "confidence": 90}}]}'
        )
        
        # Create a result for doc3
        ProcessingResult.objects.create(
            document=self.doc3,
            is_complete=True,
            json_result={
                'case_results': [
                    {'case_number': {'value': '1', 'confidence': 100}, 
                     'age': {'value': '25', 'confidence': 90}}
                ]
            },
            raw_result='{"case_results": [{"case_number": {"value": "1", "confidence": 100}, "age": {"value": "25", "confidence": 90}}]}'
        )
        
        # Update job status programmatically the way the view would
        self.job.processed_count = 3  # All documents processed
        self.job.status = 'completed'
        self.job.save()
        
        # Check that job is marked as completed
        view = JobDetailView()
        view.object = self.job
        context = view.get_context_data()
        
        # Verify no truncation flags
        self.assertFalse(context['is_truncated'])
        self.assertEqual(len(context['docs_needing_continuation']), 0)
        
        # Verify the total case count is correct (3 total cases)
        all_cases = []
        for result in ProcessingResult.objects.filter(document__job=self.job):
            if result.json_result and 'case_results' in result.json_result:
                all_cases.extend(result.json_result['case_results'])
        
        self.assertEqual(len(all_cases), 3) 