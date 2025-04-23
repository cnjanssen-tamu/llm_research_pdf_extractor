from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from core.tasks import process_pdfs_task
from core.models import ProcessingJob, PDFDocument
from core.views import ProcessorView
import logging
from celery import shared_task

class ProcessPDFsTaskTests(TestCase):
    def setUp(self):
        # Create a test job
        self.job = ProcessingJob.objects.create(
            name='Test Job',
            status='pending',
            prompt_template='Test template'
        )
        
        # Create some test PDF documents
        self.pdf_content = b'%PDF-1.4 Test PDF content'
        for i in range(3):
            pdf_file = SimpleUploadedFile(
                f'test{i}.pdf',
                self.pdf_content,
                content_type='application/pdf'
            )
            PDFDocument.objects.create(
                job=self.job,
                file=pdf_file
            )
        
        # Update job counts
        self.job.total_count = 3
        self.job.save()

    @patch('core.tasks.ProcessorView')
    def test_successful_processing(self, mock_processor_view):
        """Test successful PDF processing"""
        # Mock the processor view
        mock_processor = MagicMock()
        mock_processor_view.return_value = mock_processor
        
        # Configure the mock to simulate successful processing
        def process_pdfs(job, files):
            job.processed_count = job.total_count
            job.save()
        mock_processor.process_pdfs.side_effect = process_pdfs
        
        # Run the task
        process_pdfs_task(self.job.id)
        
        # Verify the job was processed successfully
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        self.assertEqual(self.job.processed_count, self.job.total_count)
        self.assertEqual(self.job.error_message, '')

    @patch('core.tasks.ProcessorView')
    def test_partial_processing(self, mock_processor_view):
        """Test partially successful PDF processing"""
        # Mock the processor view
        mock_processor = MagicMock()
        mock_processor_view.return_value = mock_processor
        
        # Configure the mock to simulate partial processing
        def process_pdfs(job, files):
            job.processed_count = 1  # Only process one file
            job.save()
        mock_processor.process_pdfs.side_effect = process_pdfs
        
        # Run the task
        process_pdfs_task(self.job.id)
        
        # Verify the job was marked as failed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertEqual(self.job.processed_count, 1)
        self.assertIn('Processed 1/3', self.job.error_message)

    @patch('core.tasks.ProcessorView')
    def test_processing_error(self, mock_processor_view):
        """Test error handling during PDF processing"""
        # Mock the processor view
        mock_processor = MagicMock()
        mock_processor_view.return_value = mock_processor
        
        # Configure the mock to raise an exception
        mock_processor.process_pdfs.side_effect = Exception('Processing error')
        
        # Run the task and expect it to handle the error
        with self.assertRaises(Exception):
            process_pdfs_task(self.job.id)
        
        # Verify the job was marked as failed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertEqual(self.job.error_message, 'Processing error')

    def test_invalid_job_id(self):
        """Test task behavior with invalid job ID"""
        # Run the task with an invalid job ID
        process_pdfs_task(999)  # Non-existent job ID
        
        # No exception should be raised, but an error should be logged
        # We can't verify the logging here as it's not mocked in this test

    @patch('core.tasks.ProcessorView')
    @patch('core.tasks.logger')
    def test_logging(self, mock_logger, mock_processor_view):
        """Test that errors are properly logged"""
        # Mock the processor view to raise an exception
        mock_processor = MagicMock()
        mock_processor_view.return_value = mock_processor
        mock_processor.process_pdfs.side_effect = Exception('Test error')
        
        # Run the task and expect it to log the error
        with self.assertRaises(Exception):
            process_pdfs_task(self.job.id)
        
        # Verify the error was logged
        mock_logger.error.assert_called_once_with(
            f"Error processing job {self.job.id}: Test error"
        )

    def tearDown(self):
        # Clean up any created files
        for doc in PDFDocument.objects.all():
            doc.file.delete()
        PDFDocument.objects.all().delete()
        ProcessingJob.objects.all().delete() 