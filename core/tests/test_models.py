from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from core.models import (
    ColumnDefinition,
    SavedPrompt,
    ProcessingJob,
    JobColumnMapping,
    PDFDocument,
    ProcessingResult
)
import json
from datetime import datetime
import time

class ColumnDefinitionTests(TestCase):
    def setUp(self):
        self.column = ColumnDefinition.objects.create(
            name='test_column',
            description='Test Description',
            category='demographics',
            order=1,
            include_confidence=True
        )

    def test_column_creation(self):
        """Test basic column creation and field values"""
        self.assertEqual(self.column.name, 'test_column')
        self.assertEqual(self.column.description, 'Test Description')
        self.assertEqual(self.column.category, 'demographics')
        self.assertEqual(self.column.order, 1)
        self.assertTrue(self.column.include_confidence)
        self.assertFalse(self.column.optional)

    def test_unique_name_constraint(self):
        """Test that column names must be unique"""
        with self.assertRaises(ValidationError):
            duplicate = ColumnDefinition(
                name='test_column',
                description='Duplicate Column'
            )
            duplicate.full_clean()

    def test_category_choices(self):
        """Test that only valid categories are accepted"""
        with self.assertRaises(ValidationError):
            invalid = ColumnDefinition(
                name='invalid_category',
                category='invalid'
            )
            invalid.full_clean()

    def test_string_representation(self):
        """Test the string representation of the model"""
        self.assertEqual(str(self.column), 'test_column')

    def test_ordering(self):
        """Test that columns are ordered correctly"""
        ColumnDefinition.objects.create(
            name='second_column',
            order=2
        )
        columns = ColumnDefinition.objects.all()
        self.assertEqual(columns[0].name, 'test_column')
        self.assertEqual(columns[1].name, 'second_column')

class SavedPromptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.prompt = SavedPrompt.objects.create(
            user=self.user,
            name='Test Prompt',
            content='Test content',
            variables={
                'disease_condition': 'Test Disease',
                'population_age': 'Adult'
            }
        )

    def test_prompt_creation(self):
        """Test basic prompt creation and field values"""
        self.assertEqual(self.prompt.name, 'Test Prompt')
        self.assertEqual(self.prompt.content, 'Test content')
        self.assertEqual(self.prompt.user, self.user)
        self.assertIsInstance(self.prompt.created_at, datetime)
        self.assertEqual(
            self.prompt.variables,
            {'disease_condition': 'Test Disease', 'population_age': 'Adult'}
        )

    def test_prompt_ordering(self):
        """Test that prompts are ordered by created_at in descending order"""
        # Create first prompt
        first_prompt = self.prompt  # This was created in setUp
        time.sleep(0.1)  # Add a small delay
        
        # Create second prompt
        second_prompt = SavedPrompt.objects.create(
            user=self.user,
            name='Second Prompt',
            content='Second content'
        )
        
        prompts = SavedPrompt.objects.all()
        self.assertEqual(prompts[0], second_prompt)  # Most recent should be first
        self.assertEqual(prompts[1], first_prompt)   # Older should be second

class ProcessingJobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.prompt = SavedPrompt.objects.create(
            user=self.user,
            name='Test Prompt',
            content='Test content'
        )
        self.job = ProcessingJob.objects.create(
            name='Test Job',
            prompt=self.prompt,
            prompt_template='Test template',
            status='pending'
        )

    def test_job_creation(self):
        """Test basic job creation and field values"""
        self.assertEqual(self.job.name, 'Test Job')
        self.assertEqual(self.job.prompt, self.prompt)
        self.assertEqual(self.job.prompt_template, 'Test template')
        self.assertEqual(self.job.status, 'pending')
        self.assertEqual(self.job.processed_count, 0)
        self.assertEqual(self.job.total_count, 0)

    def test_progress_calculation(self):
        """Test progress calculation method"""
        # Test with zero total count
        self.assertEqual(self.job.get_progress(), 0)

        # Test with some progress
        self.job.total_count = 10
        self.job.processed_count = 5
        self.job.save()
        self.assertEqual(self.job.get_progress(), 50.0)

        # Test with complete progress
        self.job.processed_count = 10
        self.job.save()
        self.assertEqual(self.job.get_progress(), 100.0)

    def test_status_choices(self):
        """Test that only valid status choices are accepted"""
        with self.assertRaises(ValidationError):
            invalid_job = ProcessingJob(
                name='Invalid Status',
                status='invalid'
            )
            invalid_job.full_clean()

class JobColumnMappingTests(TestCase):
    def setUp(self):
        self.column = ColumnDefinition.objects.create(
            name='test_column',
            description='Test Description'
        )
        self.job = ProcessingJob.objects.create(
            name='Test Job',
            status='pending'
        )
        self.mapping = JobColumnMapping.objects.create(
            job=self.job,
            column=self.column,
            order=1,
            include_confidence=True
        )

    def test_mapping_creation(self):
        """Test basic mapping creation and field values"""
        self.assertEqual(self.mapping.job, self.job)
        self.assertEqual(self.mapping.column, self.column)
        self.assertEqual(self.mapping.order, 1)
        self.assertTrue(self.mapping.include_confidence)

    def test_unique_constraint(self):
        """Test that job-column combinations must be unique"""
        with self.assertRaises(ValidationError):
            duplicate = JobColumnMapping(
                job=self.job,
                column=self.column,
                order=2
            )
            duplicate.full_clean()

class PDFDocumentTests(TestCase):
    def setUp(self):
        self.job = ProcessingJob.objects.create(
            name='Test Job',
            status='pending'
        )
        self.pdf_content = b'%PDF-1.4 Test PDF content'
        self.pdf_file = SimpleUploadedFile(
            'test.pdf',
            self.pdf_content,
            content_type='application/pdf'
        )
        self.document = PDFDocument.objects.create(
            job=self.job,
            file=self.pdf_file
        )

    def test_document_creation(self):
        """Test basic document creation and field values"""
        self.assertEqual(self.document.job, self.job)
        self.assertFalse(self.document.processed)
        # Check that the file is stored in the pdfs directory and has a .pdf extension
        self.assertTrue(self.document.file.name.startswith('pdfs/'))
        self.assertTrue(self.document.file.name.endswith('.pdf'))
        self.assertIsInstance(self.document.created_at, datetime)

    def test_string_representation(self):
        """Test the string representation of the model"""
        expected = f"{self.job.name} - {self.document.file.name}"
        self.assertEqual(str(self.document), expected)

class ProcessingResultTests(TestCase):
    def setUp(self):
        self.job = ProcessingJob.objects.create(
            name='Test Job',
            status='pending'
        )
        self.document = PDFDocument.objects.create(
            job=self.job,
            file=SimpleUploadedFile('test.pdf', b'Test content')
        )
        self.result_data = {
            'test_field': 'test_value',
            'confidence': 0.95
        }
        self.result = ProcessingResult.objects.create(
            document=self.document,
            result_data=self.result_data
        )

    def test_result_creation(self):
        """Test basic result creation and field values"""
        self.assertEqual(self.result.document, self.document)
        self.assertEqual(self.result.result_data, self.result_data)
        self.assertIsInstance(self.result.created_at, datetime)

    def test_string_representation(self):
        """Test the string representation of the model"""
        expected = f"Result for {self.document}"
        self.assertEqual(str(self.result), expected)

    def test_one_to_one_constraint(self):
        """Test that only one result can exist per document"""
        with self.assertRaises(ValidationError):
            duplicate = ProcessingResult(
                document=self.document,
                result_data={'another': 'result'}
            )
            duplicate.full_clean() 