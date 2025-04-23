from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django import forms
from core.forms import (
    ColumnDefinitionForm,
    ProcessingForm,
    ProcessingFormWithColumns,
    MultipleFileField
)
from core.models import ColumnDefinition

class ColumnDefinitionFormTests(TestCase):
    def test_valid_form(self):
        """Test form with valid data"""
        form_data = {
            'name': 'valid_column',
            'description': 'Test Description',
            'include_confidence': True,
            'category': 'demographics'
        }
        form = ColumnDefinitionForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_name_format(self):
        """Test form with invalid column name format"""
        # Test name starting with number
        form_data = {
            'name': '1invalid_name',
            'description': 'Test Description'
        }
        form = ColumnDefinitionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

        # Test name with special characters
        form_data['name'] = 'invalid@name'
        form = ColumnDefinitionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_blank_name(self):
        """Test form with blank name"""
        form_data = {
            'name': '',
            'description': 'Test Description'
        }
        form = ColumnDefinitionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_duplicate_name(self):
        """Test form with duplicate column name"""
        ColumnDefinition.objects.create(
            name='existing_column',
            description='Existing Column'
        )
        form_data = {
            'name': 'existing_column',
            'description': 'Test Description'
        }
        form = ColumnDefinitionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

class ProcessingFormTests(TestCase):
    def setUp(self):
        self.pdf_content = b'%PDF-1.4 Test PDF content'
        self.valid_pdf = SimpleUploadedFile(
            'test.pdf',
            self.pdf_content,
            content_type='application/pdf'
        )
        self.invalid_file = SimpleUploadedFile(
            'test.txt',
            b'Not a PDF file',
            content_type='text/plain'
        )

    def test_valid_form(self):
        """Test form with valid data"""
        data = QueryDict('', mutable=True)
        data.update({
            'name': 'Test Job',
            'prompt_template': 'Test prompt'
        })
        files = QueryDict('', mutable=True)
        files.setlist('pdf_files', [self.valid_pdf])
        form = ProcessingForm(data=data, files=files)
        self.assertTrue(form.is_valid())

    def test_invalid_file_type(self):
        """Test form with non-PDF file"""
        data = QueryDict('', mutable=True)
        data.update({
            'name': 'Test Job',
            'prompt_template': 'Test prompt'
        })
        files = QueryDict('', mutable=True)
        files.setlist('pdf_files', [self.invalid_file])
        form = ProcessingForm(data=data, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('pdf_files', form.errors)

    def test_multiple_files(self):
        """Test form with multiple PDF files"""
        data = QueryDict('', mutable=True)
        data.update({
            'name': 'Test Job',
            'prompt_template': 'Test prompt'
        })
        second_pdf = SimpleUploadedFile(
            'test2.pdf',
            self.pdf_content,
            content_type='application/pdf'
        )
        files = QueryDict('', mutable=True)
        files.setlist('pdf_files', [self.valid_pdf, second_pdf])
        form = ProcessingForm(data=data, files=files)
        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.cleaned_data['pdf_files']), 2)

    def test_no_files(self):
        """Test form without any files"""
        data = QueryDict('', mutable=True)
        data.update({
            'name': 'Test Job',
            'prompt_template': 'Test prompt'
        })
        files = QueryDict('', mutable=True)
        form = ProcessingForm(data=data, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('pdf_files', form.errors)

    def test_blank_name(self):
        """Test form with blank job name"""
        data = QueryDict('', mutable=True)
        data.update({
            'name': '',
            'prompt_template': 'Test prompt'
        })
        files = QueryDict('', mutable=True)
        files.setlist('pdf_files', [self.valid_pdf])
        form = ProcessingForm(data=data, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

class ProcessingFormWithColumnsTests(TestCase):
    def setUp(self):
        self.column1 = ColumnDefinition.objects.create(
            name='column1',
            description='First Column'
        )
        self.column2 = ColumnDefinition.objects.create(
            name='column2',
            description='Second Column'
        )

    def test_valid_form(self):
        """Test form with valid data"""
        form_data = {
            'name': 'Test Job',
            'prompt_template': 'Test prompt',
            'columns': [self.column1.id, self.column2.id]
        }
        form = ProcessingFormWithColumns(data=form_data)
        self.assertTrue(form.is_valid())

    def test_no_columns_selected(self):
        """Test form with no columns selected"""
        form_data = {
            'name': 'Test Job',
            'prompt_template': 'Test prompt',
            'columns': []
        }
        form = ProcessingFormWithColumns(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('columns', form.errors)

    def test_invalid_column_id(self):
        """Test form with invalid column ID"""
        form_data = {
            'name': 'Test Job',
            'prompt_template': 'Test prompt',
            'columns': [999]  # Non-existent column ID
        }
        form = ProcessingFormWithColumns(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('columns', form.errors)

class MultipleFileFieldTests(TestCase):
    def setUp(self):
        self.field = MultipleFileField()
        self.pdf_content = b'%PDF-1.4 Test PDF content'

    def test_single_file(self):
        """Test field with single file"""
        file = SimpleUploadedFile(
            'test.pdf',
            self.pdf_content,
            content_type='application/pdf'
        )
        cleaned = self.field.clean(file)
        self.assertIsInstance(cleaned, list)
        self.assertEqual(len(cleaned), 1)

    def test_multiple_files(self):
        """Test field with multiple files"""
        files = [
            SimpleUploadedFile(
                f'test{i}.pdf',
                self.pdf_content,
                content_type='application/pdf'
            )
            for i in range(3)
        ]
        cleaned = self.field.clean(files)
        self.assertIsInstance(cleaned, list)
        self.assertEqual(len(cleaned), 3)

    def test_empty_value(self):
        """Test field with empty value"""
        with self.assertRaises(forms.ValidationError):
            self.field.clean(None) 