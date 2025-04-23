# middleware.py
import json
from django.http import JsonResponse

class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )
        response['Content-Security-Policy'] = csp
        
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Add CSRF protection for all POST requests
        if request.method == 'POST':
            csrf_token = request.META.get('HTTP_X_CSRFTOKEN') or request.POST.get('csrfmiddlewaretoken')
            if not csrf_token and not getattr(view_func, 'csrf_exempt', False):
                return JsonResponse({
                    'error': 'CSRF token missing or invalid'
                }, status=403)
        return None

class JSONErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'success': False,
                'error': str(exception) or ''
            }, status=500)
        return None
    

