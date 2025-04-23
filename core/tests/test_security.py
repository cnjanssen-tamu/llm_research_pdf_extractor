from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import SavedPrompt, ProcessingJob, PDFDocument
import json

class SecurityTests(TestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user('user1', 'user1@test.com', 'password123')
        self.user2 = User.objects.create_user('user2', 'user2@test.com', 'password123')
        self.client = Client()
        
        # Create test data
        self.prompt = SavedPrompt.objects.create(
            user=self.user1,
            name="Test Prompt",
            content="Test content",
            variables={"test": "value"}
        )
        
        self.job = ProcessingJob.objects.create(
            prompt=self.prompt,
            name="Test Job",
            prompt_template="Test template"
        )

    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access protected views"""
        # Test accessing protected view without login
        response = self.client.get(reverse('core:prompts'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Test accessing with wrong user
        self.client.login(username='user2', password='password123')
        response = self.client.get(reverse('core:get_prompt', args=[self.prompt.id]))
        self.assertEqual(response.status_code, 404)  # Should not find other user's prompt

    def test_csrf_protection(self):
        """Test CSRF protection on forms"""
        self.client.login(username='user1', password='password123')
        
        # Get CSRF token from a GET request first
        response = self.client.get(reverse('core:prompts'))
        csrf_token = response.cookies['csrftoken'].value
        
        # Test with CSRF token
        response = self.client.post(
            reverse('core:save_prompt'),
            data=json.dumps({'name': 'Test', 'content': 'Test'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 200)  # Should succeed
        
        # Test without CSRF token
        response = self.client.post(
            reverse('core:save_prompt'),
            data=json.dumps({'name': 'Test', 'content': 'Test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)  # Should be forbidden

    def test_file_upload_security(self):
        """Test secure file upload handling"""
        self.client.login(username='user1', password='password123')
        
        # Get CSRF token
        response = self.client.get(reverse('core:process'))
        csrf_token = response.cookies['csrftoken'].value
        
        # Test invalid file type
        invalid_file = SimpleUploadedFile(
            "test.exe",
            b"malicious content",
            content_type="application/x-msdownload"
        )
        
        response = self.client.post(
            reverse('core:process'),
            {
                'name': 'Test Job',
                'pdf_files': [invalid_file],
                'prompt_template': 'Test template'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 400)
        
        # Test oversized file
        large_file = SimpleUploadedFile(
            "large.pdf",
            b"x" * (10 * 1024 * 1024 + 1),  # Slightly over 10MB
            content_type="application/pdf"
        )
        
        response = self.client.post(
            reverse('core:process'),
            {
                'name': 'Test Job',
                'pdf_files': [large_file],
                'prompt_template': 'Test template'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 400)
        
        # Test path traversal attempt
        malicious_file = SimpleUploadedFile(
            "../../../etc/passwd",
            b"test content",
            content_type="application/pdf"
        )
        
        response = self.client.post(
            reverse('core:process'),
            {
                'name': 'Test Job',
                'pdf_files': [malicious_file],
                'prompt_template': 'Test template'
            },
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(response.status_code, 400)

    def test_data_access_control(self):
        """Test that users can only access their own data"""
        # Login as user2
        self.client.login(username='user2', password='password123')
        
        # Try to access user1's prompt
        response = self.client.get(reverse('core:get_prompt', args=[self.prompt.id]))
        self.assertEqual(response.status_code, 404)
        
        # Try to modify user1's prompt
        response = self.client.post(
            reverse('core:edit_prompt', args=[self.prompt.id]),
            data=json.dumps({'content': 'Modified content'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        
        # Verify prompt wasn't modified
        self.prompt.refresh_from_db()
        self.assertEqual(self.prompt.content, "Test content")

    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection attacks"""
        self.client.login(username='user1', password='password123')
        
        # Test SQL injection in prompt name
        response = self.client.post(
            reverse('core:save_prompt'),
            data=json.dumps({
                'name': "test' OR '1'='1",
                'content': 'Test content'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test SQL injection in JSON data
        response = self.client.post(
            reverse('core:save_prompt'),
            data=json.dumps({
                'name': 'Test',
                'content': 'Test content',
                'variables': "'; DROP TABLE core_savedprompt; --"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_rate_limiting(self):
        """Test rate limiting on API endpoints"""
        self.client.login(username='user1', password='password123')
        
        # Make multiple rapid requests
        for _ in range(50):
            response = self.client.get(reverse('core:get_prompt', args=[self.prompt.id]))
        
        # The last request should be rate limited
        response = self.client.get(reverse('core:get_prompt', args=[self.prompt.id]))
        self.assertEqual(response.status_code, 429)  # Too Many Requests

    def test_secure_file_paths(self):
        """Test prevention of path traversal attacks"""
        self.client.login(username='user1', password='password123')
        
        # Test path traversal in file upload
        malicious_file = SimpleUploadedFile(
            "../../../etc/passwd",
            b"malicious content",
            content_type="application/pdf"
        )
        
        response = self.client.post(reverse('core:process'), {
            'file': malicious_file,
            'name': 'Test Job'
        })
        self.assertEqual(response.status_code, 400)
        
        # Verify file wasn't saved with malicious path
        self.assertFalse(PDFDocument.objects.filter(
            file__contains="../"
        ).exists())

    def test_api_key_security(self):
        """Test secure handling of API keys"""
        self.client.login(username='user1', password='password123')
        
        # Test API key exposure in responses
        response = self.client.get(reverse('core:test_api'))
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        # Ensure API keys are not exposed in response
        self.assertNotIn('api_key', str(response_data))
        self.assertNotIn('secret', str(response_data))
        self.assertNotIn('token', str(response_data))
        
        # Test API key validation
        response = self.client.post(
            reverse('core:test_api'),
            data=json.dumps({'api_key': 'invalid_key'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_session_security(self):
        """Test session security features"""
        self.client.login(username='user1', password='password123')
        
        # Test session cookie settings
        response = self.client.get(reverse('core:prompts'))
        session_cookie = response.cookies.get('sessionid')
        
        self.assertTrue(session_cookie['secure'])  # Ensure secure flag is set
        self.assertTrue(session_cookie['httponly'])  # Ensure HttpOnly flag is set
        
        # Test session expiry
        session = self.client.session
        session.set_expiry(300)  # 5 minutes
        session.save()
        
        # Verify session expires
        session.set_expiry(-1)
        response = self.client.get(reverse('core:prompts'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login

    def test_xss_prevention(self):
        """Test prevention of Cross-Site Scripting (XSS) attacks"""
        self.client.login(username='user1', password='password123')
        
        # Test XSS in prompt content
        xss_content = '<script>alert("xss")</script>'
        response = self.client.post(
            reverse('core:save_prompt'),
            data=json.dumps({
                'name': 'Test XSS',
                'content': xss_content
            }),
            content_type='application/json'
        )
        
        # Get the saved prompt
        saved_prompt = SavedPrompt.objects.get(name='Test XSS')
        self.assertNotEqual(saved_prompt.content, xss_content)
        self.assertIn('&lt;script&gt;', saved_prompt.content)

    def test_secure_headers(self):
        """Test security-related HTTP headers"""
        self.client.login(username='user1', password='password123')
        
        response = self.client.get(reverse('core:prompts'))
        
        # Test security headers
        self.assertEqual(
            response.headers.get('X-Content-Type-Options'),
            'nosniff'
        )
        self.assertEqual(
            response.headers.get('X-Frame-Options'),
            'DENY'
        )
        self.assertIn(
            'same-origin',
            response.headers.get('Referrer-Policy', '')
        )
        
        # Test Content Security Policy
        csp = response.headers.get('Content-Security-Policy', '')
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp) 