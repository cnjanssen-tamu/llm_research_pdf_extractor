# core/models.py
from django.db import models
from django.conf import settings
import uuid
import json  # Add import for json

class ColumnDefinition(models.Model):
    # Data type choices for validation
    DATA_TYPE_CHOICES = [
        ('string', 'Text String'),
        ('integer', 'Integer Number'),
        ('float', 'Decimal Number'),
        ('date', 'Date'),
        ('boolean', 'True/False'),
        ('enum', 'Enumerated Values')
    ]

    # Regular choices for the field
    CATEGORY_CHOICES = [
        ('demographics', 'Demographics'),
        ('clinical', 'Clinical'),
        ('pathology', 'Pathology'),
        ('treatment', 'Treatment'),
        ('outcome', 'Outcome'),
        ('presentation', 'Presentation'),
        ('symptoms', 'Signs and Symptoms'),
        ('imaging', 'Imaging'),
        ('workup', 'Workup'),
        ('intervention', 'Intervention'),
        ('postop', 'Immediate Post-op Outcomes'),
        ('followup', 'Follow-up'),
        ('lastfollowup', 'Last Follow-up'),
    ]

    # Separate mapping for icons
    CATEGORY_ICONS = {
        'demographics': 'bi-person',
        'clinical': 'bi-clipboard-check',
        'pathology': 'bi-microscope',
        'treatment': 'bi-thermometer',
        'outcome': 'bi-check-circle',
        'presentation': 'bi-clipboard-pulse',
        'symptoms': 'bi-activity',
        'imaging': 'bi-image',
        'workup': 'bi-clipboard2-pulse',
        'intervention': 'bi-bandaid',
        'postop': 'bi-hospital',
        'followup': 'bi-calendar-check',
        'lastfollowup': 'bi-flag-fill'
    }

    name = models.CharField(max_length=100, unique=True)
    include_confidence = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    optional = models.BooleanField(default=False)
    category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES,
        default='demographics'
    )
    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES,
        default='string'
    )
    enum_values = models.JSONField(
        null=True,
        blank=True,
        help_text='List of allowed values for enum type'
    )
    validation_regex = models.CharField(
        max_length=500,
        blank=True,
        help_text='Regular expression for validating string values'
    )
    min_value = models.FloatField(
        null=True,
        blank=True,
        help_text='Minimum value for numeric types'
    )
    max_value = models.FloatField(
        null=True,
        blank=True,
        help_text='Maximum value for numeric types'
    )

    def get_icon(self):
        """Get the icon for this category"""
        return self.CATEGORY_ICONS.get(self.category, '')

    def validate_value(self, value):
        """Validate a value against this column's data type and constraints."""
        import re
        from datetime import datetime
        
        if value is None or value == '':
            return not self.optional, "Field is required"
            
        try:
            if self.data_type == 'string':
                if not isinstance(value, str):
                    return False, f"Expected string, got {type(value)}"
                if self.validation_regex and not re.match(self.validation_regex, value):
                    return False, f"Value does not match pattern: {self.validation_regex}"
                    
            elif self.data_type == 'integer':
                try:
                    num = int(value)
                    if self.min_value is not None and num < self.min_value:
                        return False, f"Value below minimum: {self.min_value}"
                    if self.max_value is not None and num > self.max_value:
                        return False, f"Value above maximum: {self.max_value}"
                except ValueError:
                    return False, "Not a valid integer"
                    
            elif self.data_type == 'float':
                try:
                    num = float(value)
                    if self.min_value is not None and num < self.min_value:
                        return False, f"Value below minimum: {self.min_value}"
                    if self.max_value is not None and num > self.max_value:
                        return False, f"Value above maximum: {self.max_value}"
                except ValueError:
                    return False, "Not a valid decimal number"
                    
            elif self.data_type == 'date':
                try:
                    datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    return False, "Not a valid date (YYYY-MM-DD)"
                    
            elif self.data_type == 'boolean':
                if not isinstance(value, bool) and value.lower() not in ['true', 'false', 'yes', 'no']:
                    return False, "Not a valid boolean value"
                    
            elif self.data_type == 'enum':
                if self.enum_values and value not in self.enum_values:
                    return False, f"Value not in allowed options: {', '.join(self.enum_values)}"
                    
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order', 'name']


class SavedPrompt(models.Model):
    name = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    variables = models.JSONField(default=dict)  # Stores disease_condition, population_age etc.
    
    # Make user optional
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )

    class Meta:
        ordering = ['-created_at']


class ProcessingJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prompt = models.ForeignKey(SavedPrompt, on_delete=models.SET_NULL, null=True)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('pending_continuation', 'Pending Continuation'),
        ('pending_continuation_with_errors', 'Pending Continuation With Errors'),
        ('completed_with_errors', 'Completed With Errors')
    ]
    
    # Add job type field
    JOB_TYPE_CHOICES = [
        ('case_extraction', 'Case Extraction'),
        ('reference_extraction', 'Reference Extraction'),
    ]
    job_type = models.CharField(
        max_length=50,
        choices=JOB_TYPE_CHOICES,
        default='case_extraction',
        help_text="The type of processing performed by this job."
    )

    # Add user field if not already present
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=200)
    prompt_template = models.TextField(blank=True)
    columns = models.ManyToManyField('ColumnDefinition', through='JobColumnMapping')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, default='pending')
    error_message = models.TextField(blank=True, null=True)
    processed_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    processing_details = models.TextField(blank=True, null=True, help_text="Additional processing details or progress information")

    def __str__(self):
        return f"Job {self.id} - {self.status}"

    def get_progress(self):
        if self.total_count == 0:
            return 0
        return (self.processed_count / self.total_count) * 100
        
    def get_total_case_count(self):
        """Calculate the total number of cases across all processing results for this job"""
        from django.db.models import Sum
        
        # Get all processing results associated with this job
        case_count = 0
        
        # Find all results associated with documents from this job
        results = ProcessingResult.objects.filter(document__job=self)
        
        # Count cases in each result
        for result in results:
            if result.json_result and 'case_results' in result.json_result:
                case_count += len(result.json_result['case_results'])
                
        return case_count

class JobColumnMapping(models.Model):
    job = models.ForeignKey('ProcessingJob', on_delete=models.CASCADE)
    column = models.ForeignKey('ColumnDefinition', on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    include_confidence = models.BooleanField(default=True)
    custom_prompt = models.TextField(blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ['job', 'column']

    def __str__(self):
        return f"{self.name} ({self.status}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def get_progress(self):
        if self.total_count == 0:
            return 0
        return (self.processed_count / self.total_count) * 100


class PDFDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ProcessingJob, related_name='documents', on_delete=models.CASCADE)
    file = models.FileField(upload_to='pdfs/')
    filename = models.CharField(max_length=255, blank=True, null=True, default='unnamed.pdf')
    study_author = models.CharField(max_length=255, blank=True, null=True, help_text="Author or source of the study")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, default='pending')
    error = models.TextField(blank=True, null=True)
    # Add tracking for continuation of reference extraction
    last_successful_reference_index = models.IntegerField(
        default=0,
        help_text="Index of the last successfully extracted and saved reference (0-based)."
    )

    def __str__(self):
        return self.filename or "Unnamed PDF"
    
    @property
    def needs_continuation(self):
        """Helper property to check if status indicates continuation needed"""
        return self.status == 'processed'  # Use 'processed' to mean 'partially processed, needs continuation'


class ProcessingResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(PDFDocument, related_name='results', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    json_result = models.JSONField(null=True, blank=True)
    raw_result = models.TextField(null=True, blank=True)
    error = models.TextField(blank=True, null=True)
    is_complete = models.BooleanField(default=True)
    continuation_number = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Result for {self.document.filename} ({self.id})"
        
    class Meta:
        ordering = ['continuation_number']


class CaseReport(models.Model):
    """Model for storing case report generation requests and results"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic information
    name = models.CharField(max_length=255, help_text="A name for this case report")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Patient context fields
    patient_age = models.CharField(max_length=50, blank=True, null=True)
    patient_gender = models.CharField(max_length=10, blank=True, null=True)
    suspected_condition = models.CharField(max_length=255, blank=True, null=True)
    key_findings_summary = models.TextField(blank=True, null=True)
    additional_instructions = models.TextField(blank=True, null=True)
    
    # Storage for PDF files (using FileField directly saves to disk)
    patient_history_pdf = models.FileField(upload_to='case_reports/patient_history/', blank=True, null=True)
    clinical_findings_pdf = models.FileField(upload_to='case_reports/clinical_findings/', blank=True, null=True)
    lab_results_pdf = models.FileField(upload_to='case_reports/lab_results/', blank=True, null=True)
    imaging_reports_pdf = models.FileField(upload_to='case_reports/imaging_reports/', blank=True, null=True)
    treatment_summary_pdf = models.FileField(upload_to='case_reports/treatment_summary/', blank=True, null=True)
    
    # Storage for the AI responses
    research_prompt = models.TextField(blank=True, null=True, help_text="The prompt sent to the research model")
    research_response = models.TextField(blank=True, null=True, help_text="The response from the research model")
    draft_prompt = models.TextField(blank=True, null=True, help_text="The prompt sent to the drafting model")
    draft_response = models.TextField(blank=True, null=True, help_text="The draft case report generated by the AI")
    
    # Processing status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('researching', 'Researching'),
        ('drafting', 'Drafting'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Case Report: {self.name} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Case Report"
        verbose_name_plural = "Case Reports"

class Reference(models.Model):
    """Stores an extracted reference from a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ProcessingJob, related_name='references', on_delete=models.CASCADE)
    document = models.ForeignKey(PDFDocument, related_name='references', on_delete=models.CASCADE)
    # New field for per-document reference index
    reference_index = models.IntegerField(
        blank=True, null=True,
        help_text="1-based index of the reference within its document"
    )

    SOURCE_TYPE_CHOICES = [
        ('journal', 'Journal Article'),
        ('book', 'Book/Book Chapter'),
        ('website', 'Website/Webpage'),
        ('report', 'Report'),
        ('conference', 'Conference Proceeding'),
        ('thesis', 'Thesis/Dissertation'),
        ('news', 'News Article'),
        ('other', 'Other'),
        ('unknown', 'Unknown')
    ]

    citation_text = models.TextField(
        blank=True,
        help_text="The full citation text as extracted."
    )
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default='unknown',
        blank=True
    )
    authors = models.TextField(
        blank=True, null=True,
        help_text="List of authors (e.g., stored as comma-separated string or JSON list)"
    )
    title = models.TextField(blank=True, null=True)
    source_name = models.CharField(
        max_length=512, blank=True, null=True,
        help_text="Journal name, book title, website name, etc."
    )
    publication_year = models.IntegerField(blank=True, null=True)
    volume = models.CharField(max_length=50, blank=True, null=True)
    issue = models.CharField(max_length=50, blank=True, null=True)
    pages = models.CharField(max_length=50, blank=True, null=True)
    doi_or_url = models.CharField(max_length=512, blank=True, null=True)
    confidence = models.IntegerField(
        blank=True, null=True,
        help_text="Overall confidence score (0-100) for the parsed reference fields."
    )
    raw_response_part = models.TextField(
        blank=True, null=True,
        help_text="The specific part of the LLM's raw response that generated this reference."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'created_at']
        indexes = [
            models.Index(fields=['job']),
            models.Index(fields=['document']),
        ]

    def __str__(self):
        # Provide a concise string representation
        author_part = ""
        if self.authors:
            # Try parsing as JSON list, fallback to first few chars
            try:
                author_list = json.loads(self.authors)
                if author_list:
                    author_part = f"{author_list[0]}{' et al.' if len(author_list) > 1 else ''}"
            except:
                author_part = self.authors[:30] + ('...' if len(self.authors) > 30 else '')
        title_part = (self.title[:40] + ('...' if len(self.title or '') > 40 else '')) if self.title else "No Title"
        return f"Ref ({self.source_type}): {author_part} - {title_part} ({self.publication_year or 'N/A'})"