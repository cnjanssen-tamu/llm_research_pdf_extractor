from django.test import TestCase, RequestFactory
from django.http import JsonResponse, HttpResponse
from core.middleware import JSONErrorMiddleware
import json

class JSONErrorMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = JSONErrorMiddleware(get_response=lambda r: HttpResponse())

    def test_process_exception_json_request(self):
        """Test middleware handles exceptions for JSON requests"""
        request = self.factory.get('/test/')
        request.headers = {'Accept': 'application/json'}
        
        # Test with a simple exception
        response = self.middleware.process_exception(
            request,
            Exception('Test error')
        )
        
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 500)
        
        content = json.loads(response.content)
        self.assertFalse(content['success'])
        self.assertEqual(content['error'], 'Test error')

    def test_process_exception_non_json_request(self):
        """Test middleware ignores exceptions for non-JSON requests"""
        request = self.factory.get('/test/')
        request.headers = {'Accept': 'text/html'}
        
        response = self.middleware.process_exception(
            request,
            Exception('Test error')
        )
        
        self.assertIsNone(response)

    def test_process_exception_complex_error(self):
        """Test middleware handles complex error messages"""
        request = self.factory.get('/test/')
        request.headers = {'Accept': 'application/json'}
        
        # Create a more complex error with nested information
        try:
            raise ValueError('Outer error') from TypeError('Inner error')
        except Exception as e:
            response = self.middleware.process_exception(request, e)
        
        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content)
        self.assertIn('Outer error', content['error'])

    def test_normal_response(self):
        """Test middleware allows normal responses to pass through"""
        request = self.factory.get('/test/')
        response = self.middleware(request)
        
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)

    def test_process_exception_empty_error(self):
        """Test middleware handles empty error messages"""
        request = self.factory.get('/test/')
        request.headers = {'Accept': 'application/json'}
        
        response = self.middleware.process_exception(
            request,
            Exception()
        )
        
        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content)
        self.assertEqual(content['error'], '')

    def test_process_exception_unicode_error(self):
        """Test middleware handles unicode error messages"""
        request = self.factory.get('/test/')
        request.headers = {'Accept': 'application/json'}
        
        response = self.middleware.process_exception(
            request,
            Exception('Test error with unicode: 你好')
        )
        
        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content)
        self.assertIn('你好', content['error']) 