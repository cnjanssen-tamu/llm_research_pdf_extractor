from django.test import TestCase, Client
from django.urls import reverse
from core.models import ColumnDefinition
import json

class ColumnDefinitionTestCase(TestCase):
    def setUp(self):
        """Set up test data for column definition tests"""
        self.client = Client()
        
        # Create some test columns
        self.age_column = ColumnDefinition.objects.create(
            name='age',
            description='Patient age in years',
            category='demographics',
            data_type='integer',
            min_value=0,
            max_value=120,
            include_confidence=True,
            order=1
        )
        
        self.sex_column = ColumnDefinition.objects.create(
            name='sex',
            description='Patient sex',
            category='demographics',
            data_type='enum',
            enum_values=['M', 'F', 'Other'],
            include_confidence=True,
            order=2
        )
    
    def test_column_creation(self):
        """Test creating a new column definition"""
        # Count columns before
        initial_count = ColumnDefinition.objects.count()
        
        # Create a new column via the API
        column_data = {
            'columns': [{
                'name': 'diagnosis',
                'description': 'Primary diagnosis',
                'category': 'presentation',
                'include_confidence': True
            }]
        }
        
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps(column_data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify column was created
        self.assertEqual(ColumnDefinition.objects.count(), initial_count + 1)
        new_column = ColumnDefinition.objects.get(name='diagnosis')
        self.assertEqual(new_column.description, 'Primary diagnosis')
        self.assertEqual(new_column.category, 'presentation')
        self.assertTrue(new_column.include_confidence)
    
    def test_column_update(self):
        """Test updating an existing column definition"""
        # Update the age column
        column_data = {
            'columns': [{
                'id': self.age_column.id,
                'name': 'age',
                'description': 'Updated description',
                'category': 'demographics',
                'include_confidence': False
            }]
        }
        
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps(column_data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify column was updated
        self.age_column.refresh_from_db()
        self.assertEqual(self.age_column.description, 'Updated description')
        self.assertFalse(self.age_column.include_confidence)
    
    def test_column_deletion(self):
        """Test deleting a column definition"""
        # Count columns before
        initial_count = ColumnDefinition.objects.count()
        
        # Delete the sex column
        response = self.client.post(
            reverse('core:delete_column', kwargs={'pk': self.sex_column.id})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify column was deleted
        self.assertEqual(ColumnDefinition.objects.count(), initial_count - 1)
        with self.assertRaises(ColumnDefinition.DoesNotExist):
            ColumnDefinition.objects.get(id=self.sex_column.id)
    
    def test_column_order_update(self):
        """Test updating column order"""
        # Create a third column
        diagnosis_column = ColumnDefinition.objects.create(
            name='diagnosis',
            description='Primary diagnosis',
            category='presentation',
            order=3
        )
        
        # Update column order
        order_data = {
            'columns': [
                {'id': diagnosis_column.id, 'order': 1},
                {'id': self.age_column.id, 'order': 2},
                {'id': self.sex_column.id, 'order': 3}
            ]
        }
        
        response = self.client.post(
            reverse('core:update_column_order'),
            data=json.dumps(order_data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify order was updated
        self.age_column.refresh_from_db()
        self.sex_column.refresh_from_db()
        diagnosis_column.refresh_from_db()
        
        self.assertEqual(diagnosis_column.order, 1)
        self.assertEqual(self.age_column.order, 2)
        self.assertEqual(self.sex_column.order, 3)
    
    def test_column_name_validation(self):
        """Test validation of column names"""
        # Test invalid name (starts with number)
        column_data = {
            'columns': [{
                'name': '1invalid',
                'description': 'Invalid name',
                'category': 'demographics',
                'include_confidence': True
            }]
        }
        
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps(column_data),
            content_type='application/json'
        )
        
        # Check response indicates failure
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        
        # Test duplicate name
        column_data = {
            'columns': [{
                'name': 'age',  # Already exists
                'description': 'Duplicate name',
                'category': 'demographics',
                'include_confidence': True
            }]
        }
        
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps(column_data),
            content_type='application/json'
        )
        
        # Check response indicates failure
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
    
    def test_generate_prompt_template(self):
        """Test generating a prompt template from columns"""
        from core.views import ColumnDefinitionView
        
        # Generate prompt template
        prompt_template = ColumnDefinitionView.generate_prompt_template()
        
        # Verify prompt contains column information
        self.assertIn('age', prompt_template)
        self.assertIn('sex', prompt_template)
        self.assertIn('Patient age in years', prompt_template)
        self.assertIn('Patient sex', prompt_template) 