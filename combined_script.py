# .\combined_script.py


# .\manage.py
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?\n"
            "Did you forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

# .\core\admin.py
from django.contrib import admin

# Register your models here.


# .\core\apps.py
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"


# .\core\forms.py
# core/forms.py
from django import forms
from .models import ProcessingJob

class ProcessingForm(forms.ModelForm):
    pdf_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf'}),
        help_text='Select a PDF file'
    )
    
    class Meta:
        model = ProcessingJob
        fields = ['name', 'prompt']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a name for this processing job'
            }),
            'prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Enter your prompt here'
            })
        }

    def clean_pdf_file(self):
        file = self.cleaned_data['pdf_file']
        if not file.name.endswith('.pdf'):
            raise forms.ValidationError('Only PDF files are allowed.')
        return file
    


# .\core\middleware.py
# middleware.py
import json
from django.http import JsonResponse

class JSONErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({
                'success': False,
                'error': str(exception)
            }, status=500)
        return None
    



# .\core\models.py
# core/models.py
from django.db import models



class ProcessingJob(models.Model):
    name = models.CharField(max_length=200)
    prompt = models.TextField(blank=True)  # Make prompt optional since we'll generate it
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    columns = models.JSONField(null=True, blank=True)  # Add this field

    def __str__(self):
        return self.name

class PDFDocument(models.Model):
    job = models.OneToOneField(ProcessingJob, on_delete=models.CASCADE, related_name='document')
    file = models.FileField(upload_to='pdfs/')
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job.name} - {self.file.name}"

class ProcessingResult(models.Model):
    document = models.OneToOneField(PDFDocument, on_delete=models.CASCADE, related_name='result')
    result_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.document}"

# .\core\urls.py
# core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.ProcessorView.as_view(), name='home'),
    path('process-pdf/', views.ProcessorView.as_view(), name='process-pdf'),
    path('test-api/', views.


         test_gemini, name='test_api'),
]

# .\core\views.py
from django.views.generic import FormView
from django.http import JsonResponse
from django.conf import settings
import google.generativeai as genai
import logging
import json
import pandas as pd
from django.core.paginator import Paginator
from .forms import ProcessingForm
from .models import PDFDocument, ProcessingJob, ProcessingResult
import base64

logger = logging.getLogger(__name__)

MEDICAL_REVIEW_PROMPT = """You are a medical reviewer tasked with extracting specific information from case studies or case series related to meningioma patients. Your goal is to extract the following information and provide a confidence rating (1-5, with 5 being most confident) for each item. If information is not available, return an empty string for that item and a confidence rating of 1.

For each case, extract:
0. Article Name
1. Document Object Identifier (DOI)
2. Study author (last name of first author)
3. Year of publication
4. Patient age
5. Patient gender (M/F)
6. Duration of symptoms (in months)
7. Tumor location (Cranial or Spinal)
8. Extent of resection (total or subtotal)
9. WHO Grade
10. Meningioma subtype
11. Adjuvant therapy (y/n)
12. Symptom assessment
13. Recurrence (y/n)
14. Patient status (A/D)
15. Tumor invasion (y/n)

Return the data in JSON format:
{
  "case_results": [
    {
      "0": {"value": "", "confidence": 1},
      "1": {"value": "", "confidence": 1},
      ...
    }
  ]
}"""

class ProcessorView(FormView):
    template_name = 'processor.html'
    form_class = ProcessingForm
    success_url = '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            latest_job = ProcessingJob.objects.latest('created_at')
            latest_result = ProcessingResult.objects.get(document__job=latest_job)
            
            if latest_result.result_data and isinstance(latest_result.result_data, dict):
                df = pd.DataFrame(latest_result.result_data.get('case_results', []))
                paginator = Paginator(df.to_dict('records'), 10)
                page = self.request.GET.get('page', 1)
                table_data = paginator.get_page(page)
                
                context.update({
                    'latest_job': latest_job,
                    'table_data': table_data,
                    'columns': df.columns.tolist() if not df.empty else [],
                    'show_results': True
                })
        except (ProcessingJob.DoesNotExist, ProcessingResult.DoesNotExist):
            context['show_results'] = False
        return context

    def extract_json_from_text(self, text):
        text = text.replace('```json\n', '').replace('\n```', '')
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            return text[start_idx:end_idx]
        raise ValueError("No valid JSON found in response")

    def validate_and_normalize_json(self, json_str):
        try:
            data = json.loads(json_str)
            if 'case_results' not in data:
                data = {'case_results': [data]}
                
            for case in data['case_results']:
                for i in range(16):
                    key = str(i)
                    if key not in case:
                        case[key] = {"value": "", "confidence": 1}
                    elif isinstance(case[key], (str, int, float)):
                        case[key] = {"value": str(case[key]), "confidence": 1}
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")

    def process_pdf_with_gemini(self, pdf_doc):
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            with pdf_doc.file.open('rb') as file:
                pdf_content = file.read()
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            response = model.generate_content(
                [{"mime_type": "application/pdf", "data": pdf_base64}, MEDICAL_REVIEW_PROMPT],
                generation_config={"temperature": 0.1, "top_p": 0.8, "top_k": 40}
            )
            
            try:
                json_str = self.extract_json_from_text(response.text)
                parsed_json = self.validate_and_normalize_json(json_str)
                return {
                    'success': True,
                    'parsed_json': parsed_json,
                    'raw_text': response.text
                }
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"JSON parsing error: {e}")
                return {
                    'success': False,
                    'error': f"Failed to parse response as JSON: {str(e)}",
                    'raw_text': response.text
                }
        except Exception as e:
            logger.error(f"Error in process_pdf_with_gemini: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'raw_text': getattr(response, 'text', 'No response text available')
            }

    def form_valid(self, form):
        try:
            job = form.save()
            pdf_doc = PDFDocument.objects.create(
                job=job,
                file=self.request.FILES['pdf_file']
            )

            result = self.process_pdf_with_gemini(pdf_doc)
            print(result)
            if not result.get('success'):
                raise ValueError(result.get('error', 'Unknown processing error'))

            parsed_data = result['parsed_json']
            
            try:
                df = pd.json_normalize(parsed_data['case_results'])
                for col in [str(i) for i in range(16)]:
                    if col not in df.columns:
                        df[col] = pd.NA

                ProcessingResult.objects.create(
                    document=pdf_doc,
                    result_data=parsed_data
                )

                job.status = 'completed'
                job.save()

                return JsonResponse({
                    'success': True,
                    'table_html': df.to_html(classes='table table-striped', index=False),
                    'raw_text': result['raw_text'],
                    'job_id': job.id
                })

            except Exception as e:
                logger.error(f"DataFrame creation error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f"Error processing results: {str(e)}",
                    'raw_text': result.get('raw_text', '')
                })

        except Exception as e:
            logger.error(f"Error in form_valid: {str(e)}", exc_info=True)
            if 'job' in locals():
                job.status = 'failed'
                job.save()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

def test_gemini(request):
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro')
        test_response = model.generate_content("Test connection")
        return JsonResponse({
            'success': True,
            'response': test_response.text
        })
    except Exception as e:
        logger.error(f"Gemini API test failed: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# .\core\__init__.py


# .\core\migrations\0001_initial.py
# Generated by Django 5.1.2 on 2024-10-26 21:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProcessingJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("prompt", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PDFDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("file", models.FileField(upload_to="pdfs/")),
                ("processed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document",
                        to="core.processingjob",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProcessingResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("result_data", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="result",
                        to="core.pdfdocument",
                    ),
                ),
            ],
        ),
    ]


# .\core\migrations\0002_processingjob_columns.py
# Generated by Django 5.1.2 on 2024-10-30 01:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="processingjob",
            name="columns",
            field=models.JSONField(blank=True, null=True),
        ),
    ]


# .\core\migrations\0003_alter_processingjob_prompt.py
# Generated by Django 5.1.2 on 2024-10-30 01:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_processingjob_columns"),
    ]

    operations = [
        migrations.AlterField(
            model_name="processingjob",
            name="prompt",
            field=models.TextField(blank=True),
        ),
    ]


# .\core\migrations\__init__.py


# .\core\services\llm_service.py


# .\core\services\pdf_service.py


# .\core\services\__init__.py


# .\core\templatetags\custom_filters.py
# core/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

# .\core\templatetags\_init_.py


# .\pdf_processor\asgi.py
# pdf_processor/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')

application = get_asgi_application()

# .\pdf_processor\settings.py
# pdf_processor/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'your-default-secret-key-for-development')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'pdf_processor.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pdf_processor.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'core' / 'static']

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Add this to your existing settings
DEFAULT_PROMPT = """You are a medical reviewer tasked with extracting specific information..."""

# settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# .\pdf_processor\urls.py
# pdf_processor/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls', namespace='core')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# .\pdf_processor\wsgi.py
# pdf_processor/wsgi.py
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')

application = get_wsgi_application()

# .\pdf_processor\__init__.py


