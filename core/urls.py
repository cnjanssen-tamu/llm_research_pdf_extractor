# core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Main processor paths
    path('', views.ProcessorView.as_view(), name='processor'),  # This will serve as both processor and home
    path('process/', views.ProcessorView.as_view(), name='process'),

    # Column management paths (no login required)
    path('columns/', views.ColumnDefinitionView.as_view(), name='columns'),
    path('columns/add/', views.AddColumnView.as_view(), name='add_column'),
    path('columns/<int:pk>/edit/', views.EditColumnView.as_view(), name='edit_column'),
    path('columns/<int:pk>/delete/', views.DeleteColumnView.as_view(), name='delete_column'),
    path('columns/save/', views.SaveColumnsView.as_view(), name='save_columns'),
    path('columns/validate-name/', views.validate_column_name, name='validate_column_name'),
    path('columns/apply-defaults/', views.apply_default_columns, name='apply_default_columns'),
    path('columns/load-schema-from-file/', views.load_schema_from_file, name='load_schema_from_file'),

    # API endpoints
    path('test-api/', views.test_api, name='test_api'),
    path('test-gemini/', views.test_gemini, name='test_gemini'),  # New URL for testing Gemini API
    path('test-structured-output/', views.test_gemini_structured_output, name='test_structured_output'),
    path('test-reference-extraction/', views.test_reference_extraction, name='test_reference_extraction'),  # New URL for testing reference extraction
    path('api/columns/validate/', views.validate_column_name, name='validate_column'),
    path('api/columns/order/', views.update_column_order, name='update_column_order'),

    # Results and debugging
    path('jobs/', views.JobListView.as_view(), name='job_list'),
    path('jobs/<uuid:pk>/', views.JobDetailView.as_view(), name='job_detail'),
    path('jobs/<uuid:pk>/results/', views.JobResultsView.as_view(), name='job_results'),
    path('jobs/results/<uuid:pk>/json/', views.JsonResponseDetailView.as_view(), name='job_json_detail'),
    path('check-job-status/', views.check_job_status, name='check_job_status'),
    path('download-results/<uuid:job_id>/<str:format>/', views.DownloadResultsView.as_view(), name='download_results'),
    path('continue-processing/<uuid:document_id>/', views.ContinueProcessingView.as_view(), name='continue_processing'),

    # Prompts
    path('prompts/', views.PromptsView.as_view(), name='prompts'),
    path('prompts/list/', views.list_prompts, name='list_prompts'),
    path('prompts/<int:prompt_id>/', views.manage_prompt, name='manage_prompt'),
    path('prompts/<int:pk>/edit/', views.EditPromptView.as_view(), name='edit_prompt'),
    path('save_prompt/', views.save_prompt, name='save_prompt'),
    path('get_prompt/<int:pk>/', views.get_prompt, name='get_prompt'),
    path('load_prompts/', views.load_prompts, name='load_prompts'),
    path('columns/store-prompt/', views.StorePromptView.as_view(), name='store_prompt'),
    path('create_prompt_from_columns/', views.StorePromptView.as_view(http_method_names=['post']), {'action': 'create_from_columns'}, name='create_prompt_from_columns'),
    path('get_default_prompt/', views.get_default_prompt, name='get_default_prompt'),
    path('download-raw-markdown/<uuid:result_id>/', views.download_raw_markdown, name='download_raw_markdown'),

    # Update to make job_id optional for the job status API
    path('api/check-job-status/', views.check_job_status, name='api_check_job_status'),
    path('api/check-job-status/<int:job_id>/', views.check_job_status, name='api_check_specific_job_status'),
    path('api/active-jobs/', views.check_job_status, name='api_active_jobs'),  # For compatibility with banner code

    # Login (handled by Django's built-in auth)
    path('login/', views.login_view, name='login'),

    # Case Report Generator
    path('generate-case-report/', views.CaseReportGeneratorView.as_view(), name='generate_case_report'),

    # Reference Extraction
    path('extract-references/', views.ReferenceExtractionView.as_view(), name='extract_references'),
]

# urlpatterns = [
#     #calls the views.ProcessView and renders it
#     path('', views.ProcessorView.as_view(), name='home'),
#     path('process-pdf/', views.ProcessorView.as_view(), name='process-pdf'),
#     path('test-api/', views.test_gemini, name='test_api'),
# ]


# urlpatterns = [
#     # Original PDF processor paths
#     path('', views.ProcessorView.as_view(), name='processor'),
#     path('test-gemini/', views.test_gemini, name='test_gemini'),
#
#     # Main processor paths
#     path('', views.ProcessorView.as_view(), name='home'),
#     path('process/', views.ProcessorView.as_view(), name='processor'),
#
#     # Column management paths
#     path('columns/', views.ColumnDefinitionView.as_view(), name='columns'),
#     path('columns/add/', views.AddColumnView.as_view(), name='add_column'),
#     path('columns/<int:pk>/edit/', views.EditColumnView.as_view(), name='edit_column'),
#     path('columns/<int:pk>/delete/', views.DeleteColumnView.as_view(), name='delete_column'),
#
#     # API endpoints
#     path('test-gemini/', views.test_gemini, name='test_gemini'),
#     path('api/columns/validate/', views.validate_column_name, name='validate_column'),
#     path('api/columns/order/', views.update_column_order, name='update_column_order'),
#
#     # Results and debugging
#     path('jobs/', views.JobListView.as_view(), name='job_list'),
#     path('jobs/<int:pk>/', views.JobDetailView.as_view(), name='job_detail'),
#     path('jobs/<int:pk>/results/', views.JobResultsView.as_view(), name='job_results'),
#     path('debug/', views.test_gemini, name='debug'),
#
#     # Dynamic processor with custom columns
#     path('custom-processor/', views.CustomProcessorView.as_view(), name='custom_processor'),
# ]
