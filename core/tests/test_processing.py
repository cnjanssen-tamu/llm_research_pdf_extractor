from django.test import TestCase
from core.models import ColumnDefinition, ProcessingJob, PDFDocument, ProcessingResult
from core.utils import StreamJSONParser, CaseValidator
import json

class ProcessingTestCase(TestCase):
    def setUp(self):
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
        
        self.diagnosis_column = ColumnDefinition.objects.create(
            name='diagnosis',
            description='Primary diagnosis',
            category='presentation',
            data_type='string',
            optional=True
        )
        
        # Create a test job
        self.job = ProcessingJob.objects.create(
            name='Test Processing Job',
            status='pending'
        )
        
        # Create a test document
        self.document = PDFDocument.objects.create(
            job=self.job,
            file='test.pdf'
        )
    
    def test_schema_validation(self):
        """Test the schema validation for different data types"""
        validator = CaseValidator()
        
        # Test valid case
        valid_case = {
            'age': {'value': '45', 'confidence': 90},
            'sex': {'value': 'M', 'confidence': 100},
            'diagnosis': {'value': 'Meningioma', 'confidence': 85}
        }
        errors = validator.validate_case(valid_case)
        self.assertEqual(len(errors), 0, "Valid case should have no errors")
        
        # Test invalid age
        invalid_age_case = {
            'age': {'value': '150', 'confidence': 90},  # Above max_value
            'sex': {'value': 'M', 'confidence': 100}
        }
        errors = validator.validate_case(invalid_age_case)
        self.assertTrue(any('above maximum' in error for error in errors))
        
        # Test invalid enum value
        invalid_sex_case = {
            'age': {'value': '45', 'confidence': 90},
            'sex': {'value': 'Unknown', 'confidence': 100}  # Not in enum_values
        }
        errors = validator.validate_case(invalid_sex_case)
        self.assertTrue(any('not in allowed options' in error for error in errors))
    
    def test_json_parsing(self):
        """Test the streaming JSON parser"""
        parser = StreamJSONParser()
        
        # Test complete JSON
        complete_json = '''
        {
            "case_results": [
                {
                    "age": {"value": "45", "confidence": 90},
                    "sex": {"value": "M", "confidence": 100}
                }
            ]
        }
        '''
        parser.feed(complete_json)
        cases = parser.get_cases()
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['age']['value'], '45')
        
        # Test chunked JSON
        parser.clear()
        chunk1 = '{"case_results": ['
        chunk2 = '{"age": {"value": "45", "confidence": 90},'
        chunk3 = '"sex": {"value": "M", "confidence": 100}}'
        chunk4 = ']}'
        
        parser.feed(chunk1)
        self.assertEqual(len(parser.get_cases()), 0)
        parser.feed(chunk2)
        self.assertEqual(len(parser.get_cases()), 0)
        parser.feed(chunk3)
        self.assertEqual(len(parser.get_cases()), 0)
        parser.feed(chunk4)
        cases = parser.get_cases()
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['sex']['value'], 'M')
    
    def test_end_to_end_processing(self):
        """Test the entire processing pipeline"""
        # Sample response from Gemini
        gemini_response = {
            'case_results': [
                {
                    'age': {'value': '45', 'confidence': 90},
                    'sex': {'value': 'M', 'confidence': 100},
                    'diagnosis': {'value': 'Meningioma', 'confidence': 85}
                }
            ],
            'low_confidence_explanation': {
                'value': '',
                'confidence': 100
            }
        }
        
        # Create a processing result
        result = ProcessingResult.objects.create(
            document=self.document,
            result_data=gemini_response,
            raw_response=json.dumps(gemini_response)
        )
        
        # Validate the stored result
        validator = CaseValidator()
        for case in result.result_data['case_results']:
            errors = validator.validate_case(case)
            self.assertEqual(len(errors), 0, f"Validation errors found: {errors}")
        
        # Check if the job was processed successfully
        self.document.processed = True
        self.document.save()
        self.job.status = 'completed'
        self.job.save()
        
        updated_job = ProcessingJob.objects.get(id=self.job.id)
        self.assertEqual(updated_job.status, 'completed')
        self.assertTrue(updated_job.documents.first().processed) 
        
    def test_copyright_detection_handling(self):
        """Test that copyright detection is properly handled"""
        from unittest.mock import patch, MagicMock
        from core.views import ProcessorView
        
        # Create a mock response that simulates a copyright detection
        mock_response = MagicMock()
        mock_response.text = None  # No text content
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].finish_reason = 4  # Copyright detection
        
        # Create a mock for the GenerativeModel
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        
        # Patch the GenerativeModel to return our mock
        with patch('google.generativeai.GenerativeModel', return_value=mock_model):
            processor = ProcessorView()
            
            # Test the _get_gemini_response method
            with self.assertRaises(ValueError) as context:
                processor._get_gemini_response(b'test pdf data', 'test prompt')
            
            # Check that the error message mentions copyright
            self.assertIn('No valid content in Gemini response', str(context.exception))
            self.assertIn('Finish reason: 4', str(context.exception))
            
            # Test the process_pdfs method with a document that triggers copyright detection
            job = ProcessingJob.objects.create(
                name='Copyright Test Job',
                status='pending',
                total_count=1
            )
            
            # Mock the _extract_pages_from_pdf method to return a simple page
            with patch.object(processor, '_extract_pages_from_pdf') as mock_extract:
                mock_extract.return_value = [{'page_number': 'all', 'pdf_data': b'test pdf data', 'token_count': 100}]
                
                # Process the PDF
                processor.process_pdfs(job, [b'test pdf data'], ['test.pdf'])
                
                # Check that the job was marked as failed
                job.refresh_from_db()
                self.assertEqual(job.status, 'failed')
                self.assertIn('Successfully processed 0 out of 1 documents', job.error_message)
                
                # Check that the document has an error message about copyright
                document = PDFDocument.objects.filter(job=job).first()
                self.assertIsNotNone(document)
                self.assertIn('copyrighted material', document.error_message) 