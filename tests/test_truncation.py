import json
import base64
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from core.models import ProcessingJob, PDFDocument, ProcessingResult
from core.utils import is_response_truncated, prepare_continuation_prompt, extract_json_from_text
from core.tasks import call_gemini_with_pdf
from core.views import ContinueProcessingView

class TruncationDetectionTests(TestCase):
    """Tests for truncation detection logic"""
    
    def test_detect_truncation_mid_sentence(self):
        """Test truncation detection for responses ending mid-sentence"""
        text = "This is a response that ends abruptly and"
        self.assertTrue(is_response_truncated(text))
        
    def test_detect_complete_response(self):
        """Test truncation detection for complete responses"""
        text = "This is a complete response."
        self.assertFalse(is_response_truncated(text))
        
    def test_detect_truncated_json(self):
        """Test truncation detection for truncated JSON responses"""
        text = "```json\n{\n  \"case_results\": [\n    {\n      \"field\": \"value\","
        self.assertTrue(is_response_truncated(text))
        
    def test_detect_truncated_code_block(self):
        """Test truncation detection for truncated code blocks"""
        text = "Here is the result:\n```json\n{\n  \"data\": \"value\"\n"
        self.assertTrue(is_response_truncated(text))
        
    def test_detect_unbalanced_braces(self):
        """Test truncation detection for responses with unbalanced braces"""
        text = "{\n  \"data\": {\n    \"nested\": \"value\"\n  "
        self.assertTrue(is_response_truncated(text))

class ContinuationPromptTests(TestCase):
    """Tests for continuation prompt generation"""
    
    def test_continuation_prompt_generation(self):
        """Test that continuation prompts are correctly generated"""
        original_prompt = "Please analyze this document"
        previous_response = "Here is the analysis for the first 10 cases. Case 1: blah blah blah"
        
        continuation_prompt = prepare_continuation_prompt(original_prompt, previous_response)
        
        # Verify the continuation prompt contains required elements
        self.assertIn(original_prompt, continuation_prompt)
        self.assertIn("truncated", continuation_prompt.lower())
        self.assertIn("continue", continuation_prompt.lower())
        self.assertIn(previous_response[-500:], continuation_prompt)

class MockGeminiResponseTests(TestCase):
    """Tests for handling Gemini API responses with mocks"""
    
    @patch('core.tasks.requests.post')
    def test_gemini_api_call_complete(self, mock_post):
        """Test Gemini API call with a complete response"""
        # Mock a complete response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "This is a complete response with proper JSON:\n```json\n{\"data\": \"value\"}\n```"
                            }
                        ]
                    }
                }
            ]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_post.return_value = mock_response
        
        # Call the function
        result = call_gemini_with_pdf("base64pdf", "test prompt")
        
        # Verify the result
        self.assertIn("text", result)
        self.assertNotIn("error", result)
        
        # Verify the response is not truncated
        self.assertFalse(is_response_truncated(result["text"]))
    
    @patch('core.tasks.requests.post')
    def test_gemini_api_call_truncated(self, mock_post):
        """Test Gemini API call with a truncated response"""
        # Mock a truncated response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "This is a truncated response with unfinished JSON:\n```json\n{\"data\": {"
                            }
                        ]
                    }
                }
            ]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_post.return_value = mock_response
        
        # Call the function
        result = call_gemini_with_pdf("base64pdf", "test prompt")
        
        # Verify the result
        self.assertIn("text", result)
        self.assertNotIn("error", result)
        
        # Verify the response is truncated
        self.assertTrue(is_response_truncated(result["text"]))

class ContinuationWorkflowTests(TestCase):
    """Tests for the end-to-end continuation workflow"""
    
    def setUp(self):
        """Set up test data"""
        # Create a job
        self.job = ProcessingJob.objects.create(
            status='processing'
        )
        
        # Create a document
        self.document = PDFDocument.objects.create(
            job=self.job,
            filename='test.pdf',
            status='processed'
        )
        
        # Create a truncated result
        self.truncated_result = ProcessingResult.objects.create(
            document=self.document,
            raw_result="This is a truncated response with incomplete JSON:\n```json\n{\"data\": {",
            json_result={"partial": True},
            is_complete=False,
            continuation_number=0
        )
        
        # Set up the client
        self.client = Client()
    
    @patch('core.views.call_gemini_with_pdf')
    def test_continuation_workflow(self, mock_call_gemini):
        """Test the continuation workflow with a mock Gemini API response"""
        # Mock the Gemini API call to return a complete response
        mock_call_gemini.return_value = {
            "text": "This is the continuation response with complete JSON:\n```json\n{\"data\": {\"field\": \"value\"}}\n```",
            "raw_response": "raw response"
        }
        
        # Mock the file reading (document.file.path)
        with patch('builtins.open', unittest.mock.mock_open(read_data=b'pdf data')):
            # Call the continue processing endpoint
            response = self.client.post(
                reverse('continue_processing'), 
                data={'document_id': self.document.id}
            )
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['is_complete'])
        
        # Refresh the document from the database
        self.document.refresh_from_db()
        
        # Verify the document status
        self.assertEqual(self.document.status, 'complete')
        
        # Verify we have a new ProcessingResult
        new_result = ProcessingResult.objects.filter(
            document=self.document,
            continuation_number=1
        ).first()
        
        self.assertIsNotNone(new_result)
        self.assertTrue(new_result.is_complete)
    
    @patch('core.views.call_gemini_with_pdf')
    def test_continuation_still_truncated(self, mock_call_gemini):
        """Test the continuation workflow with a still truncated response"""
        # Mock the Gemini API call to return another truncated response
        mock_call_gemini.return_value = {
            "text": "This is still a truncated response with incomplete JSON:\n```json\n{\"more_data\": {",
            "raw_response": "raw response"
        }
        
        # Mock the file reading (document.file.path)
        with patch('builtins.open', unittest.mock.mock_open(read_data=b'pdf data')):
            # Call the continue processing endpoint
            response = self.client.post(
                reverse('continue_processing'),
                data={'document_id': self.document.id}
            )
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['is_complete'])
        
        # Refresh the document from the database
        self.document.refresh_from_db()
        
        # Verify the document status is still processed (not complete)
        self.assertEqual(self.document.status, 'processed')
        
        # Verify we have a new ProcessingResult
        new_result = ProcessingResult.objects.filter(
            document=self.document,
            continuation_number=1
        ).first()
        
        self.assertIsNotNone(new_result)
        self.assertFalse(new_result.is_complete)
    
    @patch('core.views.call_gemini_with_pdf')
    def test_continuation_api_error(self, mock_call_gemini):
        """Test the continuation workflow with an API error"""
        # Mock the Gemini API call to return an error
        mock_call_gemini.return_value = {
            "error": "API error",
            "raw_response": "error response"
        }
        
        # Mock the file reading (document.file.path)
        with patch('builtins.open', unittest.mock.mock_open(read_data=b'pdf data')):
            # Call the continue processing endpoint
            response = self.client.post(
                reverse('continue_processing'),
                data={'document_id': self.document.id}
            )
        
        # Verify the response
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('API error', data['message'])
        
        # Refresh the document from the database
        self.document.refresh_from_db()
        
        # Verify the document status is error
        self.assertEqual(self.document.status, 'error')
        
        # Verify we have a new ProcessingResult with the error
        new_result = ProcessingResult.objects.filter(
            document=self.document,
            continuation_number=1
        ).first()
        
        self.assertIsNotNone(new_result)
        self.assertFalse(new_result.is_complete)
        self.assertEqual(new_result.error, "API error")

if __name__ == '__main__':
    unittest.main() 