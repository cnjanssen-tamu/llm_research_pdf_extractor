from django.test import TestCase, Client
from django.urls import reverse
from core.models import SavedPrompt
import json

class PromptManagementTestCase(TestCase):
    def setUp(self):
        """Set up test data for prompt management tests"""
        self.client = Client()
        
        # Create a test prompt
        self.test_prompt = SavedPrompt.objects.create(
            name='Test Prompt',
            content='This is a test prompt template',
            variables={
                'disease_condition': 'Meningioma',
                'population_age': 'Adult',
                'grading_of_lesion': 'Grade I'
            }
        )
    
    def test_prompt_creation(self):
        """Test creating a new prompt"""
        # Count prompts before
        initial_count = SavedPrompt.objects.count()
        
        # Create a new prompt
        prompt_data = {
            'name': 'New Prompt',
            'content': 'This is a new prompt template',
            'variables': {
                'disease_condition': 'Glioblastoma',
                'population_age': 'Elderly',
                'grading_of_lesion': 'Grade IV'
            }
        }
        
        response = self.client.post(
            reverse('core:save_prompt'),
            data=json.dumps(prompt_data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify prompt was created
        self.assertEqual(SavedPrompt.objects.count(), initial_count + 1)
        new_prompt = SavedPrompt.objects.get(name='New Prompt')
        self.assertEqual(new_prompt.content, 'This is a new prompt template')
        self.assertEqual(new_prompt.variables['disease_condition'], 'Glioblastoma')
        self.assertEqual(new_prompt.variables['population_age'], 'Elderly')
        self.assertEqual(new_prompt.variables['grading_of_lesion'], 'Grade IV')
    
    def test_prompt_update(self):
        """Test updating an existing prompt"""
        # Update the test prompt
        prompt_data = {
            'name': 'Updated Prompt',
            'content': 'This is an updated prompt template',
            'variables': {
                'disease_condition': 'Updated Condition',
                'population_age': 'Updated Age',
                'grading_of_lesion': 'Updated Grade'
            }
        }
        
        response = self.client.post(
            reverse('core:manage_prompt', kwargs={'prompt_id': self.test_prompt.id}),
            data=json.dumps(prompt_data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify prompt was updated
        self.test_prompt.refresh_from_db()
        self.assertEqual(self.test_prompt.name, 'Updated Prompt')
        self.assertEqual(self.test_prompt.content, 'This is an updated prompt template')
        self.assertEqual(self.test_prompt.variables['disease_condition'], 'Updated Condition')
        self.assertEqual(self.test_prompt.variables['population_age'], 'Updated Age')
        self.assertEqual(self.test_prompt.variables['grading_of_lesion'], 'Updated Grade')
    
    def test_prompt_deletion(self):
        """Test deleting a prompt"""
        # Count prompts before
        initial_count = SavedPrompt.objects.count()
        
        # Delete the test prompt
        response = self.client.delete(
            reverse('core:manage_prompt', kwargs={'prompt_id': self.test_prompt.id}),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify prompt was deleted
        self.assertEqual(SavedPrompt.objects.count(), initial_count - 1)
        with self.assertRaises(SavedPrompt.DoesNotExist):
            SavedPrompt.objects.get(id=self.test_prompt.id)
    
    def test_get_prompt(self):
        """Test retrieving a prompt"""
        # Get the test prompt
        response = self.client.get(
            reverse('core:get_prompt', kwargs={'pk': self.test_prompt.id})
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], self.test_prompt.id)
        self.assertEqual(response_data['name'], 'Test Prompt')
        self.assertEqual(response_data['content'], 'This is a test prompt template')
        self.assertEqual(response_data['variables']['disease_condition'], 'Meningioma')
        self.assertEqual(response_data['variables']['population_age'], 'Adult')
        self.assertEqual(response_data['variables']['grading_of_lesion'], 'Grade I')
    
    def test_list_prompts(self):
        """Test listing all prompts"""
        # Create a second prompt
        SavedPrompt.objects.create(
            name='Second Prompt',
            content='This is another prompt template',
            variables={}
        )
        
        # Get all prompts
        response = self.client.get(reverse('core:list_prompts'))
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data['prompts']), 2)
        
        # Verify prompts are ordered by created_at (newest first)
        self.assertEqual(response_data['prompts'][0]['name'], 'Second Prompt')
        self.assertEqual(response_data['prompts'][1]['name'], 'Test Prompt')
    
    def test_get_default_prompt(self):
        """Test getting the default prompt template"""
        # Get default prompt
        response = self.client.get(reverse('core:get_default_prompt'))
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn('prompt', response_data)
        self.assertIsInstance(response_data['prompt'], str)
        self.assertGreater(len(response_data['prompt']), 0)
    
    def test_store_prompt_in_session(self):
        """Test storing a prompt in the session"""
        # Store a prompt in the session
        prompt_data = {
            'prompt': 'This is a session prompt'
        }
        
        response = self.client.post(
            reverse('core:store_prompt'),
            data=json.dumps(prompt_data),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify prompt is in session
        self.assertEqual(self.client.session['user_prompt'], 'This is a session prompt') 