from django import forms
from .models import ProcessingJob, ColumnDefinition
import re


class ColumnDefinitionForm(forms.ModelForm):
    class Meta:
        model = ColumnDefinition
        fields = ['name', 'include_confidence', 'description']

    def clean_name(self):
        name = self.cleaned_data['name']
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            raise forms.ValidationError(
                "Column name must start with a letter and contain only letters, numbers, and underscores")
        return name


class ProcessingFormWithColumns(forms.ModelForm):
    class Meta:
        model = ProcessingJob
        fields = ['name', 'prompt_template']

    columns = forms.ModelMultipleChoiceField(
        queryset=ColumnDefinition.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class ProcessingForm(forms.ModelForm):
    pdf_files = MultipleFileField(
        help_text='Select one or more PDF files',
        required=True
    )
    class Meta:
        model = ProcessingJob
        fields = ['name', 'prompt_template']  # Changed from 'prompt' to 'prompt_template'
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a name for this processing job'
            }),
            'prompt_template': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Enter your prompt here'
            })
        }

    def clean_pdf_files(self):
        files = self.files.getlist('pdf_files')
        if not files:
            raise forms.ValidationError("At least one PDF file is required.")
        for file in files:
            if not file.name.endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are allowed.")
        return files

class JobForm(forms.ModelForm):
    """Form for creating or updating a processing job"""
    class Meta:
        model = ProcessingJob
        fields = ['name', 'status', 'prompt_template']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'prompt_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
        }

class SinglePDFUploadForm(forms.Form):
    """Form for uploading a single PDF file"""
    pdf_file = forms.FileField(
        label='PDF File',
        help_text='Select a PDF file',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    
    def clean_pdf_file(self):
        file = self.cleaned_data.get('pdf_file')
        if file:
            if not file.name.endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are allowed.")
        return file

class BulkPDFUploadForm(forms.Form):
    """Form for uploading multiple PDF files"""
    pdf_files = MultipleFileField(
        label='PDF Files',
        help_text='Select one or more PDF files',
        widget=MultipleFileInput(attrs={'class': 'form-control'})
    )
    
    def clean_pdf_files(self):
        files = self.files.getlist('pdf_files')
        if not files:
            raise forms.ValidationError("At least one PDF file is required.")
        for file in files:
            if not file.name.endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are allowed.")
        return files

class CaseReportForm(forms.Form):
    # --- Optional Context Fields ---
    patient_age = forms.CharField(
        max_length=20, 
        required=False, 
        label="Patient Age (e.g., 55 years, 6 months)",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 45 years', 'class': 'form-control'})
    )
    patient_gender = forms.ChoiceField(
        choices=[('', '---'), ('M', 'Male'), ('F', 'Female'), ('O', 'Other')], 
        required=False, 
        label="Patient Gender",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    suspected_condition = forms.CharField(
        max_length=255, 
        required=False, 
        label="Suspected/Primary Condition",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Glioblastoma WHO Grade 4', 'class': 'form-control'})
    )
    key_findings_summary = forms.CharField(
        required=False, 
        label="Brief Summary of Key Findings/Reason for Report",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., Patient presented with seizures, MRI showed ring-enhancing lesion...', 'class': 'form-control'})
    )

    # --- Labeled File Uploads ---
    patient_history_pdf = forms.FileField(
        required=False, 
        label="Patient History / Admission Notes (PDF)",
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )
    clinical_findings_pdf = forms.FileField(
        required=False, 
        label="Clinical Findings / Exam Notes (PDF)",
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )
    lab_results_pdf = forms.FileField(
        required=False, 
        label="Laboratory Results (PDF)",
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )
    imaging_reports_pdf = forms.FileField(
        required=False, 
        label="Imaging Reports (Radiology, Pathology) (PDF)",
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )
    treatment_summary_pdf = forms.FileField(
        required=False, 
        label="Treatment / Procedure Notes (PDF)",
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )

    # --- Additional Instructions ---
    additional_instructions = forms.CharField(
        required=False, 
        label="Specific Instructions for AI",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., Focus on the surgical approach, compare findings to typical presentation...', 'class': 'form-control'})
    )
    
    # --- Report Name ---
    name = forms.CharField(
        max_length=255,
        required=True,
        label="Report Name",
        widget=forms.TextInput(attrs={'placeholder': 'Enter a name for this case report', 'class': 'form-control'})
    )
    
    # --- Security/Compliance Check ---
    de_identification_confirmed = forms.BooleanField(
        required=True, # Make this required to force user acknowledgement
        label="I confirm ALL uploaded data and entered text is completely DE-IDENTIFIED and contains NO Protected Health Information (PHI).",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        # Add validation: Ensure at least some data is provided
        has_text_data = any(cleaned_data.get(field) for field in ['patient_age', 'patient_gender', 'suspected_condition', 'key_findings_summary'])
        has_file_data = any(cleaned_data.get(field) for field in ['patient_history_pdf', 'clinical_findings_pdf', 'lab_results_pdf', 'imaging_reports_pdf', 'treatment_summary_pdf'])
        
        if not has_text_data and not has_file_data:
            raise forms.ValidationError("Please provide some patient information either in the text fields or by uploading at least one relevant PDF.")
            
        return cleaned_data

class ReferenceExtractionForm(forms.Form):
    """Form for uploading PDFs for reference extraction."""
    job_name = forms.CharField(
        max_length=200,
        required=True,
        label="Extraction Job Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a name for this reference extraction job'
        })
    )
    pdf_files = MultipleFileField(
        label='PDF Files for Reference Extraction',
        help_text='Select one or more PDF files containing medical literature.',
        required=True,
        widget=MultipleFileInput(attrs={'class': 'form-control'})
    )

    def clean_pdf_files(self):
        files = self.files.getlist('pdf_files')
        if not files:
            raise forms.ValidationError("At least one PDF file is required.")
        for file in files:
            if not file.name.endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are allowed.")
        return files
