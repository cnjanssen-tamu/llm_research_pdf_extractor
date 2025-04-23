from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.views.generic import FormView, UpdateView, CreateView, TemplateView, DeleteView, ListView, DetailView, View
from django.views import View
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse, HttpResponseRedirect, FileResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy, reverse
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db.models import QuerySet, Q, Max, Count
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.utils.html import escape
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
import uuid
import django.db.utils
from django.db import transaction

# Third-party imports
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import numpy as np
import base64
import simplejson
import json
import re
import traceback
import logging
import mimetypes
import time
import threading
from io import BytesIO
import tiktoken  # For token counting
from dotenv import load_dotenv
import random
import os
from .utils import extract_json_from_text, prepare_continuation_prompt, is_response_truncated, deduplicate_cases, filter_cited_cases

# Local imports
from .forms import ProcessingForm, ColumnDefinitionForm, JobForm, SinglePDFUploadForm, BulkPDFUploadForm, CaseReportForm, ReferenceExtractionForm
from .models import PDFDocument, ProcessingJob, ProcessingResult, ColumnDefinition, SavedPrompt, JobColumnMapping, CaseReport, Reference
from .tasks import process_document
from .processor import call_gemini_with_pdf
from django.contrib.auth import authenticate, login

# Configure logging
logger = logging.getLogger(__name__)

# Text extraction prompt for when no custom prompt is available
TEXT_EXTRACTION_PROMPT = """You are a medical text extractor. Your task is to extract and structure the content from medical PDFs into a clear, organized format, focusing ONLY on the primary cases presented by the authors of THIS specific document.

ABSOLUTE TOP PRIORITY INSTRUCTION:
Your MOST IMPORTANT goal is to extract information ONLY for the primary patient case(s) directly presented in this document. COMPLETELY IGNORE any literature review sections, summaries of previous studies, or tables comparing to prior published cases.

Instructions:
1. Extract text content from the PDF, preserving the logical structure and hierarchy
2. Format the content in Markdown for better readability
3. Clearly separate and label different sections (e.g., Abstract, Methods, Results, etc.)
4. Preserve tables by converting them to markdown table format
5. Maintain lists and enumerations
6. Keep all numerical values, measurements, and units exactly as presented
7. Preserve references to figures and tables
8. Include any footnotes or special annotations
9. Maintain author citations and references
10. Keep patient case information grouped together

CRITICAL: Focus ONLY on primary cases reported in this document. DO NOT extract information for patients mentioned only in literature reviews or summaries of prior studies. IGNORE ANY TABLES labeled as 'literature review', 'previous reports', or containing citations to multiple papers - these are NOT the primary cases being presented!

When in doubt about whether information describes a primary case or cited literature, ERR ON THE SIDE OF EXCLUSION. It is better to extract less information than to include data from literature reviews.

Output Format:
1. Use Markdown headers (# ## ###) to indicate section hierarchy
2. Use bullet points (- *) for lists
3. Use markdown tables for tabular data
4. Use blockquotes (>) for important quotes or highlights
5. Use code blocks (```) for structured data
6. Use bold and italic for emphasis as in the original
7. Preserve numerical formatting and units
8. Keep line breaks for logical separation
"""

# Reference extraction prompt
REFERENCE_EXTRACTION_PROMPT = """You are an AI assistant specialized in extracting bibliographic references from academic documents. Your task is to meticulously analyze the provided PDF document, identify all cited references, and extract detailed information for each one.

Instructions:
1.  **Identify References:** Locate the bibliography, references, or works cited section(s) of the document. Also, scan the document text for inline citations that might provide full reference details (though less common).
2.  **Extract All Details:** For each distinct reference identified, extract the following information if available:
    *   Full Citation Text: The complete reference string as it appears.
    *   Source Type: Classify the reference type (e.g., journal, book, website, report, conference, thesis, news, other, unknown).
    *   Authors: List all authors. Provide as a list of strings if possible.
    *   Title: The title of the article, chapter, book, or webpage.
    *   Source Name: The name of the journal, book, website, conference proceedings, etc.
    *   Publication Year: The year of publication.
    *   Volume: The journal or book volume number.
    *   Issue: The journal issue number.
    *   Pages: The page range (e.g., "123-145") or article number.
    *   DOI or URL: The Digital Object Identifier or a direct URL. Prioritize DOI if available.
3.  **Handle Missing Information:** If a specific detail (e.g., issue number, pages) is not present in the citation, represent it as `null` in the JSON output. Do not guess or omit the field.
4.  **Confidence Score:** Provide an overall confidence score (0-100) reflecting the certainty of the extracted and parsed fields for each reference. Higher confidence indicates more complete and clearly parsed information.
5.  **Output Format:** Return the extracted information as a JSON object containing a single key "references", which holds an array of reference objects. Each reference object should follow the structure specified below.

**CRITICAL:** Ensure the output is **only** the valid JSON object. Do not include any introductory text, explanations, apologies, or markdown formatting like ```json ``` before or after the JSON structure.

**EXAMPLE JSON OUTPUT STRUCTURE:**
{
  "references": [
    {
      "citation_text": "Doe J, Smith A. A Study on Reference Extraction. Journal of Bibliometrics. 2022;15(3):205-218. doi:10.1000/jb.2022.5",
      "source_type": "journal",
      "authors": ["Doe J", "Smith A"],
      "title": "A Study on Reference Extraction",
      "source_name": "Journal of Bibliometrics",
      "publication_year": 2022,
      "volume": "15",
      "issue": "3",
      "pages": "205-218",
      "doi_or_url": "doi:10.1000/jb.2022.5",
      "confidence": 98
    },
    {
      "citation_text": "Example Org. Annual Report 2023. Published Dec 1, 2023. Accessed Feb 10, 2024. https://example.org/report2023.pdf",
      "source_type": "report",
      "authors": ["Example Org"],
      "title": "Annual Report 2023",
      "source_name": "Example Org",
      "publication_year": 2023,
      "volume": null,
      "issue": null,
      "pages": null,
      "doi_or_url": "https://example.org/report2023.pdf",
      "confidence": 90
    },
    {
      "citation_text": "Johnson B. The Art of Citations. Academic Press; 2020.",
      "source_type": "book",
      "authors": ["Johnson B"],
      "title": "The Art of Citations",
      "source_name": "Academic Press",
      "publication_year": 2020,
      "volume": null,
      "issue": null,
      "pages": null,
      "doi_or_url": null,
      "confidence": 92
    }
  ]
}
"""

# NEW Prompt for Text-Based JSON Output
REFERENCE_EXTRACTION_PROMPT_TEXT_JSON = """You are an AI assistant specialized in extracting bibliographic references from academic documents. Your task is to meticulously analyze the provided PDF document, identify all cited references, and return the extracted information ONLY as a single, valid JSON object.

Instructions:
1.  **Identify References:** Locate the bibliography, references, or works cited section(s).
2.  **Extract Details:** For each distinct reference, extract:
    *   Full Citation Text (as it appears)
    *   Source Type (classify: journal, book, website, report, conference, thesis, news, other, unknown)
    *   Authors (Return as a list of strings: ["Author 1", "Author 2"])
    *   Title
    *   Source Name (Journal name, book title, website name, etc.)
    *   Publication Year (integer)
    *   Volume (string)
    *   Issue (string)
    *   Pages (string, e.g., "123-145")
    *   DOI or URL (string)
    *   Confidence (integer 0-100, overall confidence for the parsed fields of this reference)
3.  **Handle Missing Information:** If a detail is not available, use `null` for that field in the JSON (e.g., `"volume": null`). Do not omit the field key.
4.  **Output Format:** Your entire response MUST be ONLY the JSON object. It should contain a single root key "references", which holds an array of reference objects. Each reference object must contain all the fields listed above (using `null` for missing values).

**CRITICAL:**
- Your response MUST start directly with `{` and end directly with `}`.
- Do NOT include any introductory text, explanations, apologies, summaries, or markdown formatting (like ```json ```).
- Ensure the generated JSON is strictly valid.

**EXAMPLE JSON OUTPUT STRUCTURE (This is the exact format you must output):**
{
  "references": [
    {
      "citation_text": "Doe J, Smith A. A Study on Reference Extraction. Journal of Bibliometrics. 2022;15(3):205-218. doi:10.1000/jb.2022.5",
      "source_type": "journal",
      "authors": ["Doe J", "Smith A"],
      "title": "A Study on Reference Extraction",
      "source_name": "Journal of Bibliometrics",
      "publication_year": 2022,
      "volume": "15",
      "issue": "3",
      "pages": "205-218",
      "doi_or_url": "doi:10.1000/jb.2022.5",
      "confidence": 98
    },
    {
      "citation_text": "Example Org. Annual Report 2023. Published Dec 1, 2023. Accessed Feb 10, 2024. https://example.org/report2023.pdf",
      "source_type": "report",
      "authors": ["Example Org"],
      "title": "Annual Report 2023",
      "source_name": "Example Org",
      "publication_year": 2023,
      "volume": null,
      "issue": null,
      "pages": null,
      "doi_or_url": "https://example.org/report2023.pdf",
      "confidence": 90
    }
  ]
}
"""

class PromptsView(TemplateView):
    """View for managing prompts"""
    template_name = 'prompts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prompts = SavedPrompt.objects.all().order_by('-created_at')
        context['prompts'] = prompts
        return context

class ColumnDefinitionView(TemplateView):
    """View for managing column definitions"""
    template_name = 'column_definition.html'

    def get(self, request, *args, **kwargs):
        # Check if JSON format is requested
        if request.GET.get('format') == 'json':
            columns = ColumnDefinition.objects.all().order_by('category', 'order')
            columns_data = [
                {
                    'id': col.id,
                    'name': col.name,
                    'description': col.description,
                    'category': col.category,
                    'data_type': col.data_type,
                    'include_confidence': col.include_confidence,
                    'optional': col.optional,
                    'order': col.order
                }
                for col in columns
            ]
            return JsonResponse({'columns': columns_data})
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        columns = ColumnDefinition.objects.all().order_by('category', 'order')
        
        # Get categories with their names and icons
        categories = [
            (code, name, ColumnDefinition.CATEGORY_ICONS.get(code, 'bi-question-circle'))
            for code, name in ColumnDefinition.CATEGORY_CHOICES
        ]
        
        # Generate initial prompt
        initial_prompt = self.generate_prompt_template()
        
        context.update({
            'columns': columns,
            'categories': categories,
            'columns_json': json.dumps(list(columns.values()), cls=DjangoJSONEncoder),
            'generated_prompt': initial_prompt
        })
        
        return context

    @staticmethod
    def generate_prompt_template(variables=None):
        """Generate a prompt template based on column definitions"""
        columns = ColumnDefinition.objects.all().order_by('category', 'order')
        if not columns.exists():
            return ""

        # Start with the base template with enhanced instructions for study papers
        template = (
            "You are a medical data extractor specialized in retrieving individual patient case information. Your task is to extract detailed information ONLY for patients presented as PRIMARY CASES by the authors of THIS specific medical document. Focus exclusively on the case(s) being originally reported or analyzed in detail by the authors.\n\n"
            "IMPORTANT ANALYSIS INSTRUCTIONS:\n\n"
            "0. **PRIMARY FOCUS: EXTRACT ONLY PRIMARY CASES:**\n"
            "   - Your ABSOLUTE TOP PRIORITY is to extract information ONLY for the PRIMARY PATIENT CASE(S) directly presented and described in detail by the authors of THIS document.\n"
            "   - IGNORE ANY TABLES, LISTS, OR TEXT SECTIONS that summarize or review cases from PREVIOUSLY PUBLISHED LITERATURE or studies by OTHER authors. Focus *only* on the new case(s) being reported in *this* paper.\n"
            "   - If you are uncertain if a table or case description pertains to the primary case(s) of THIS paper or is from cited literature, ERR ON THE SIDE OF EXCLUSION and do NOT extract it.\n"
            "   - Quality over quantity: It is MORE important to accurately and completely extract the primary case(s) and completely AVOID cited cases, even if it means extracting slightly less data overall.\n\n"
            "1. DOCUMENT ASSESSMENT:\n"
            "   - First determine if this document is: (a) a case series with individual patient details, or (b) a summary/aggregate study\n"
            "   - For case series: Extract each patient as a separate case with unique information\n"
            "   - For summary studies: DO NOT create a single aggregate case. Instead, create multiple individual cases by disaggregating the data\n\n"
            "2. DATA DISAGGREGATION INSTRUCTIONS FOR SUMMARY STUDIES:\n"
            "   - If the primary analysis involves a cohort where only aggregate data is provided (e.g., '5 males, 7 females'), create separate entries for EACH individual patient within that primary cohort\n"
            "   - If exact details for individual patients are not provided, create the appropriate number of case entries and populate with known data\n"
            "   - Example: If study mentions '5 males, 7 females with mean age 39.9', create 12 separate case entries (5 with gender 'M', 7 with gender 'F')\n"
            "   - Use 'Patient 1', 'Patient 2', etc. as case identifiers when specific IDs are not given\n"
            "   - **Handling Aggregate Data:** For fields where only aggregated data (like means, medians, ranges) is provided for a group of patients:\n"
            "     a) **Required Method:** In the 'value' field for EACH relevant patient entry, explicitly state the aggregate statistic as reported in the source (e.g., value: 'Mean age for group: 39.9 years', value: 'Group median survival: 15 months', value: 'Follow-up range for group: 1.5-13 years').\n"
            "     b) Assign a lower confidence score (40-59) reflecting the aggregate source.\n"
            "     c) **CRITICAL:** Do **NOT** assign the numerical value of the aggregate (e.g., '39.9') directly to the patient as if it were their individual data.\n"
            "     d) Do **NOT** attempt to estimate or calculate individual values from aggregate statistics.\n\n"
            "3. EXTRACTION RULES:\n"
            "   - Extract EACH individual patient as a separate entry with a unique case number\n"
            "   - NEVER combine multiple patients into a single case entry\n"
            "   - If a patient appears multiple times, combine that specific patient's information into one entry\n"
            "   - **Scope Limitation:** Extract data ONLY for the primary patient(s) presented in detail by the authors of the current document (e.g., the main subject of a 'Case Report' or individuals in the primary cohort of a 'Case Series').\n"
            "   - **DO NOT Extract Cited/Reviewed Cases:** Explicitly IGNORE and DO NOT extract data for patients mentioned *only* in literature review sections, summaries of previous studies, or tables listing cases reported by OTHER authors in different publications. If a table is clearly summarizing external literature (e.g., titled 'Literature Review' or citing other papers per row), do not extract cases from it.\n"
            "   - **IGNORE LITERATURE REVIEW TABLES:** Completely IGNORE any tables or lists that are clearly presenting a 'literature review', 'summary of prior studies', 'comparison to previous cases', or similar. Do NOT extract data from such tables even if they mention patient characteristics, diagnoses, or treatments. Your focus is *not* on summarizing existing literature.\n"
            "   - **Footnotes/Comments Precision:** Scrutinize table footnotes, comments, legends, and associated text *meticulously*. Information found here (e.g., specific comorbidities, complications, prior treatments, recurrence details) MUST be linked *only* to the specific patient/case number it refers to. **Guard against misattributing details from comments or general text to the wrong patient.**\n"
            "   - **Handling Missing/Unknown Data:**\n"
            "     * If the source explicitly states information is 'Not Known', 'Not Reported', 'Unknown', 'Not Assessed', 'Unavailable', etc., for a specific field and patient, use that *exact term* as the 'value'. Assign confidence 100 if directly stated as unknown/not assessed.\n"
            "     * Use 'N/A' (Not Applicable / Not Available) *only* when the source provides absolutely no information pertaining to that field for that specific case, and doesn't explicitly state it's unknown.\n\n"
            "4. OUTPUT FORMAT:\n"
            "   - Return an array of case objects, with EACH PATIENT as a separate object in the array\n"
            "   - A 12-patient study should result in 12 separate entries in the output\n"
            "   - **CRITICAL REQUIREMENT: Include ALL patient cases in your response. DO NOT abbreviate, summarize, or omit any cases.**\n"
            "   - Include a case_number field to identify each unique patient (e.g., 'Patient 1', 'Case 1', etc.)\n"
            "   - Use the following JSON structure for each field:\n"
            "     {\n"
            "       \"field_name\": {\n"
            "         \"value\": \"extracted value\",\n"
            "         \"confidence\": confidence_score\n"
            "       }\n"
            "     }\n"
            "   - **CRITICAL: Do NOT include any comments in the JSON (no // comments or /* */ blocks). The output must be strictly valid JSON.**\n"
            "   - **Do NOT use ellipsis (...) or placeholders to indicate additional cases - include ALL cases in full.**\n\n"
            "5. CONFIDENCE SCORING:\n"
            "   - Use 100 for directly stated individual patient information\n"
            "   - Use 80-99 for clearly implied individual information\n"
            "   - Use 60-79 for reasonably inferred individual information\n"
            "   - Use 40-59 for information derived from aggregate data\n"
            "   - Use 0-39 for uncertain or conflicting information\n\n"
            "6. CRITICAL REQUIREMENT:\n"
            "   - You MUST create a separate entry for EACH patient. DO NOT return a single summary case.\n"
            "   - Even for studies or papers that only provide aggregate statistics, create multiple individual entries.\n\n"
            "REMINDER: Your focus is SOLELY on the primary case(s) reported by the authors of THIS document. Do not include cases from cited literature.\n\n"
        )

        # Add variables section if provided
        if variables:
            template += "CONTEXT VARIABLES:\n"
            for key, value in variables.items():
                if value:
                    template += f"- {key}: {value}\n"
            template += "\n"

        template += "FIELDS TO EXTRACT FOR EACH INDIVIDUAL PATIENT CASE:\n\n"

        # Group columns by category
        current_category = None
        for column in columns:
            if column.category != current_category:
                current_category = column.category
                category_name = dict(ColumnDefinition.CATEGORY_CHOICES)[column.category]
                template += f"\n{category_name}:\n"

            # Enhanced field descriptions for specific fields
            if column.name == "treatment":
                template += "- treatment: Describe the overall treatment approach or modalities used (e.g., 'Subtotal resection followed by radiation therapy', 'Chemotherapy regimen XYZ', 'Supportive care only'). Focus on the treatment strategy and approach.\n"
            elif column.name == "surgery":
                template += "- surgery: Detail specific surgical procedures performed. If a standardized score/grade is given (e.g., 'Simpson Grade I', 'R0 resection'), prioritize extracting that specific grade/score. Otherwise, describe the procedure (e.g., 'Left frontal craniotomy', 'T4-6 laminectomy', 'Anterior orbitotomy').\n"
            elif column.name == "pathology":
                template += "- pathology: Extract the primary pathological diagnosis, including specific histopathological type, grade if available, and molecular markers if mentioned.\n"
            elif column.name == "outcome":
                template += "- outcome: Describe the clinical outcome or response to treatment. Include survival status, response classification, or functional outcome measures if provided.\n"
            else:
                # Default field description
                template += f"- {column.name}: {column.description}\n"
            
            if column.include_confidence:
                template += "  (include confidence score)\n"

        # Add example output structure showing multiple cases - including example for study summary
        template += "\nEXAMPLE OUTPUT STRUCTURE FOR MULTIPLE PATIENTS:\n"
        template += "{\n  \"case_results\": [\n    {\n"
        
        # First case example
        template += "      \"case_number\": {\n        \"value\": \"Patient 1\",\n        \"confidence\": 100\n      },\n"
        for column in columns:
            if column.name == "case_number":
                continue
            template += f"      \"{column.name}\": {{\n"
            template += "        \"value\": \"example value for patient 1\",\n"
            template += "        \"confidence\": 100\n"
            template += "      }"
            if column != columns.last() or column == columns.last() and column.name != "case_number":
                template += ","
            template += "\n"
        
        template += "    },\n    {\n"
        
        # Second case example to demonstrate multiple cases
        template += "      \"case_number\": {\n        \"value\": \"Patient 2\",\n        \"confidence\": 100\n      },\n"
        for column in columns:
            if column.name == "case_number":
                continue
            template += f"      \"{column.name}\": {{\n"
            template += "        \"value\": \"example value for patient 2\",\n"
            template += "        \"confidence\": 90\n"
            template += "      }"
            if column != columns.last() or column == columns.last() and column.name != "case_number":
                template += ","
            template += "\n"
        
        template += "    },\n    {\n"
        
        # Third case example (for demonstration of study data)
        template += "      \"case_number\": {\n        \"value\": \"Patient 3\",\n        \"confidence\": 100\n      },\n"
        
        # Add an example of aggregate data formatting
        template += "      \"age\": {\n"
        template += "        \"value\": \"Group mean age for group: 39.9 years\",\n"
        template += "        \"confidence\": 50\n"
        template += "      },\n"
        
        # Add an example of preserved original terminology for missing data
        template += "      \"comorbidities\": {\n"
        template += "        \"value\": \"Not Reported\",\n"
        template += "        \"confidence\": 100\n"
        template += "      },\n"
        
        # Continue with other columns
        for column in columns:
            if column.name in ["case_number", "age", "comorbidities"]:
                continue
            template += f"      \"{column.name}\": {{\n"
            template += "        \"value\": \"example value for patient 3\",\n"
            template += "        \"confidence\": 70\n"
            template += "      }"
            if column != columns.last() or column == columns.last() and column.name != "case_number":
                template += ","
            template += "\n"
        
        template += "    }\n  ]\n}\n"
        
        # Add even stronger warnings about summarization
        template += "\n---\n"
        template += "CRITICAL WARNING: DO NOT COMBINE PATIENTS INTO A SINGLE CASE!\n\n"
        template += "• If you encounter a study with 12 patients, you must create 12 separate entries\n"
        template += "• For aggregate data (e.g., \"5 males, 7 females\"), create multiple entries (5 male entries, 7 female entries)\n"
        template += "• Each patient must have their own dedicated entry in the case_results array\n"
        template += "• Never create a single summary case with aggregated values like \"5 M, 7 F\" or \"mean age 39.9\"\n"
        template += "• For data like \"4 cases had GTR, 8 had STR\", create individual entries with the appropriate values\n"
        template += "• **AGGREGATE STATISTICS:** When reporting group statistics, use this exact pattern in the value field: '[Statistic type] for group: [value]' with confidence 40-59\n"
        template += "• **FOOTNOTES PRECISION:** Information from footnotes, comments, and legends MUST be linked ONLY to the specific patients they refer to\n"
        template += "• **MISSING DATA:** Use the source's exact terms ('Not Known', 'Unknown', etc.) when missing data is explicitly stated, with confidence 100\n"
        template += "• Use 'N/A' ONLY when the source provides no information for that field and doesn't state it's unknown\n"
        template += "• **JSON VALIDITY:** Do NOT include comments (// or /* */) or ellipsis (...) in your JSON output. The response must be strictly valid JSON\n"
        template += "• **PRIMARY CASES ONLY:** Extract data ONLY for the primary cases that are the focus of THIS document. DO NOT extract data from literature reviews or cited cases.\n"
        template += "• **IGNORE LITERATURE REVIEW TABLES:** Tables labeled as 'literature review', 'previous studies', 'prior cases', or those containing citations to multiple papers MUST BE COMPLETELY IGNORED. These are not the primary cases of this paper!\n\n"

        template += "\n---\n"
        template += "FINAL CRITICAL INSTRUCTIONS:\n\n"
        template += "• INCLUDE ALL CASES: If you find 16 patients in a study, you MUST include ALL 16 cases in your JSON output\n"
        template += "• NO SUMMARIZATION: NEVER replace cases with comments like '// ... other 13 cases'. Include every single case\n"
        template += "• COMPLETE JSON: Do not truncate or abbreviate your response. Return the full, complete data for all cases\n"
        template += "• VALID JSON ONLY: No comments, no placeholders, no ellipsis - only valid JSON structure\n"
        template += "• FOCUS ON COMPLETENESS: It is better to return ALL cases with fewer fields than to omit cases\n"
        template += "• PRIMARY CASES ONLY: DO NOT include cases from literature reviews or summaries of previously published work. Focus ONLY on patients directly studied in THIS document.\n"
        template += "• WHEN IN DOUBT, EXCLUDE: If you're unsure whether a table is showing literature review cases or primary cases, DO NOT extract from it. It is better to extract too few cases than to include cited cases from other papers.\n\n"
        
        template += "If the document contains only statistical summaries without individual patient details, you should STILL create one entry per patient, using available information to distinguish them where possible.\n"

        return template

@login_required
def check_job_status(request):
    """API endpoint to check the status of a job and return real-time process information."""
    job_id = request.GET.get('job_id')
    request_time = timezone.now()  # Get time of request
    request_ip = request.META.get('REMOTE_ADDR', 'unknown')
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
    logger.info(f"[JobStatusAPI] Request from {request.user.username} ({request_ip}): job_id={job_id}, time={request_time}")
    logger.debug(f"[JobStatusAPI] User agent: {user_agent}")
    
    if not job_id:
        # If no job_id provided, return active jobs list
        try:
            logger.info(f"[JobStatusAPI] No job_id provided, fetching active jobs for user {request.user.username}")
            active_jobs = ProcessingJob.objects.filter(
                status__in=['pending', 'in_progress', 'processing']
            ).order_by('-created_at')[:5]
            logger.debug(f"[JobStatusAPI] Found {active_jobs.count()} active jobs.")
            
            jobs_data = []
            for job in active_jobs:
                # Count documents for progress calculation
                documents = PDFDocument.objects.filter(job=job)
                total_count = documents.count()
                processed_count = documents.filter(status__in=['processed', 'complete', 'error']).count()
                
                # Calculate progress percentage
                progress_percent = 0
                if total_count > 0:
                    progress_percent = int((processed_count / total_count) * 100)
                
                logger.debug(f"[JobStatusAPI] Job {job.id}: {job.status}, Progress: {processed_count}/{total_count} ({progress_percent}%)")
                
                jobs_data.append({
                    'id': str(job.id),
                    'name': job.name or f"Job #{job.id}",
                    'status': job.status,
                    'started_at': job.created_at.isoformat() if job.created_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'processed_count': processed_count,
                    'total_count': total_count,
                    'progress_percent': progress_percent,
                    'processing_details': job.processing_details,
                    'last_updated': job.updated_at.isoformat() if job.updated_at else None,
                })
            
            response_payload = {'active_jobs': jobs_data}
            logger.info(f"[JobStatusAPI] Returning {len(jobs_data)} active jobs to user {request.user.username}")
            return JsonResponse(response_payload)
        except Exception as e:
            logger.error(f"[JobStatusAPI] Error retrieving active jobs: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to retrieve active jobs'}, status=500)
    
    try:
        job_query_start = timezone.now()
        job = ProcessingJob.objects.select_related('user').get(id=job_id)
        job_query_time = (timezone.now() - job_query_start).total_seconds()
        logger.info(f"[JobStatusAPI] Job {job_id} retrieved in {job_query_time:.3f}s: Status='{job.status}', Updated='{job.updated_at}'")
        
        # Check if user has access to this job
        user = request.user
        if not user.is_authenticated:
            logger.warning(f"[JobStatusAPI] Unauthenticated user attempted to access job {job_id}")
            return JsonResponse({'error': 'Authentication required.'}, status=401)
            
        if hasattr(job, 'user') and job.user and job.user != user and not user.is_staff:
            logger.warning(f"[JobStatusAPI] Permission denied for user {user.username} on job {job_id} (owned by {job.user.username if job.user else 'None'})")
            return JsonResponse({'error': 'You do not have permission to access this job'}, status=403)
        
        logger.info(f"[JobStatusAPI] Processing status request for job {job_id}, current status: {job.status}")
        
        # Count documents in each state
        doc_query_start = timezone.now()
        documents = PDFDocument.objects.filter(job=job)
        total_count = documents.count()
        processed_count = documents.filter(status__in=['processed', 'complete', 'error']).count()
        doc_statuses = documents.values('status').annotate(count=Count('status'))
        doc_query_time = (timezone.now() - doc_query_start).total_seconds()
        
        status_breakdown = {}
        for status_data in doc_statuses:
            status_breakdown[status_data['status']] = status_data['count']
        
        logger.info(f"[JobStatusAPI] Job {job_id} document status breakdown (retrieved in {doc_query_time:.3f}s): {status_breakdown}")
        
        # Calculate progress percentage
        progress_percent = 0
        if total_count > 0:
            progress_percent = int((processed_count / total_count) * 100)
        logger.info(f"[JobStatusAPI] Job {job_id}: Docs={total_count}, Processed={processed_count}, Progress={progress_percent}%")
        
        # Get total case count
        results_query_start = timezone.now()
        results = ProcessingResult.objects.filter(document__job=job)
        total_case_count = 0
        
        case_counts_by_doc = {}
        for result in results:
            doc_id = result.document.id if result.document else 'unknown'
            case_count = 0
            if result.json_result and 'case_results' in result.json_result and isinstance(result.json_result['case_results'], list):
                case_count = len(result.json_result['case_results'])
                total_case_count += case_count
            
            case_counts_by_doc[str(doc_id)] = case_count
        
        results_query_time = (timezone.now() - results_query_start).total_seconds()
        logger.info(f"[JobStatusAPI] Job {job_id}: Total cases={total_case_count} (retrieved in {results_query_time:.3f}s)")
        logger.debug(f"[JobStatusAPI] Case counts by document: {case_counts_by_doc}")
        
        # Extract current document and case if available
        current_document = None
        current_case = None
        current_phase = 'initializing'
        
        if job.status == 'completed':
            current_phase = 'completed'
        elif job.processing_details:
            import re
            # Extract current document
            doc_match = re.search(r'document[:\s]+([^-\(\)]+)', job.processing_details, re.IGNORECASE)
            if doc_match:
                current_document = doc_match.group(1).strip()
            
            # Extract current case
            case_match = re.search(r'case\s+(\d+)', job.processing_details, re.IGNORECASE)
            if case_match:
                current_case = case_match.group(1).strip()
            
            # Determine processing phase based on details
            details_lower = job.processing_details.lower()
            if 'extracting' in details_lower:
                current_phase = 'extracting'
            elif 'processing' in details_lower:
                current_phase = 'processing'
            elif 'sending' in details_lower:
                current_phase = 'sending'
            elif 'preparing' in details_lower:
                current_phase = 'preparing'
            
            logger.info(f"[JobStatusAPI] Job {job_id}: Extracted Phase='{current_phase}', Doc='{current_document}', Case='{current_case}'")
            logger.debug(f"[JobStatusAPI] Processing details: '{job.processing_details}'")
        else:
            logger.info(f"[JobStatusAPI] Job {job_id}: No processing_details found, phase defaults to '{current_phase}'")
        
        # Calculate time since job was last updated
        time_since_update = None
        if job.updated_at:
            time_since_update = (timezone.now() - job.updated_at).total_seconds()
            logger.info(f"[JobStatusAPI] Job {job_id}: Last updated {time_since_update:.1f} seconds ago")
            
            # Check for potentially stalled jobs
            if job.status in ['in_progress', 'processing'] and time_since_update > 300:  # 5 minutes
                logger.warning(f"[JobStatusAPI] Job {job_id} may be stalled: Last update was {time_since_update:.1f} seconds ago")
        
        # Build response data
        response_data = {
            'id': str(job.id),  # Convert UUID to string for JSON serialization
            'name': job.name or f"Job #{job.id}",
            'status': job.status,
            'processed_count': processed_count,
            'total_count': total_count,
            'progress_percent': progress_percent,
            'processing_details': job.processing_details,
            'error': job.error_message,
            'last_updated': job.updated_at.isoformat() if job.updated_at else None,
            'current_document': current_document,
            'current_case': current_case,
            'current_phase': current_phase,
            'total_case_count': total_case_count,
            'is_truncated': any(doc.status == 'processed' for doc in documents),
            'details_url': reverse('core:job_detail', kwargs={'pk': job.id}),
            'started_at': job.created_at.isoformat() if job.created_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None
        }
        
        # Calculate total response time
        total_response_time = (timezone.now() - request_time).total_seconds()
        logger.info(f"[JobStatusAPI] check_job_status for job {job_id}: Completed in {total_response_time:.3f}s")
        return JsonResponse(response_data)
        
    except ProcessingJob.DoesNotExist:
        logger.warning(f"[JobStatusAPI] Job {job_id} not found")
        return JsonResponse({'error': f'Job {job_id} not found'}, status=404)
    except Exception as e:
        logger.error(f"[JobStatusAPI] Error processing job {job_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class RateLimitMixin:
    """Mixin to add rate limiting to views"""
    
    def get_rate_limit_key(self, request):
        """Get the cache key for rate limiting"""
        return f"ratelimit_{self.__class__.__name__}_{request.user.id}"
    
    def get_rate_limit_period(self):
        """Get the rate limit period in seconds"""
        return getattr(settings, 'RATELIMIT_PERIOD', 60)  # Default 1 minute
    
    def get_rate_limit_count(self):
        """Get the maximum number of requests allowed in the period"""
        return getattr(settings, 'RATELIMIT_VIEW_RATELIMIT', 30)  # Lower limit for testing
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
            
        cache_key = self.get_rate_limit_key(request)
        period = self.get_rate_limit_period()
        max_requests = self.get_rate_limit_count()
        
        # Get current request count
        request_count = cache.get(cache_key, 0)
        
        # Check if rate limit exceeded
        if request_count >= max_requests:
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.'
            }, status=429)
        
        # Initialize or increment counter
        if request_count == 0:
            cache.set(cache_key, 1, period)
        else:
            cache.incr(cache_key)
            
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            # Decrement counter on error
            if request_count > 0:
                cache.decr(cache_key)
            raise


@method_decorator(require_POST, name='dispatch')
class SaveColumnsView(RateLimitMixin, View):
    """Handles saving column definitions"""

    @method_decorator(csrf_protect)
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            if data.get('action') == 'generate_prompt':
                # Generate new prompt template with variables
                template = ColumnDefinitionView.generate_prompt_template(data.get('variables', {}))
                return JsonResponse({
                    'success': True,
                    'prompt_template': template
                })
            
            # Handle column save request
            if 'columns' in data:
                # Handle array of columns
                results = []
                for column_data in data['columns']:
                    saved_column = self._save_single_column(column_data)
                    results.append({
                        'column_id': saved_column.id,
                        'name': saved_column.name
                    })
                return JsonResponse({
                    'success': True,
                    'results': results
                })
            elif 'name' in data:
                # Handle single column save
                saved_column = self._save_single_column(data)
                return JsonResponse({
                    'success': True,
                    'column_id': saved_column.id,
                    'name': saved_column.name
                })
            
            return JsonResponse({'success': False, 'error': 'Invalid request data'})
            
        except Exception as e:
            logger.error(f"Error saving column: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    def _save_single_column(self, data):
        """Helper method to save a single column"""
        column_data = {
            'name': data['name'],
            'description': data.get('description', ''),
            'category': data.get('category'),
            'include_confidence': data.get('include_confidence', True)
        }
        
        # Handle order field
        if data.get('order') is not None:
            column_data['order'] = data['order']
        
        if 'id' in data and data['id']:
            # Update existing column
            column = ColumnDefinition.objects.get(id=data['id'])
            # Keep existing order if not provided
            if 'order' not in column_data:
                column_data['order'] = column.order
            for key, value in column_data.items():
                setattr(column, key, value)
            column.save()
        else:
            # For new columns, set order to be last in its category if not provided
            if 'order' not in column_data:
                last_order = ColumnDefinition.objects.filter(category=column_data['category']).aggregate(Max('order'))['order__max']
                column_data['order'] = (last_order or 0) + 1
            # Create new column
            column = ColumnDefinition.objects.create(**column_data)
        
        return column

class DeleteColumnView(DeleteView):
    """View for deleting column definitions"""
    model = ColumnDefinition
    success_url = reverse_lazy('core:columns')

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            logger.info(f"Deleting column: {self.object.name}")

            # Check if column is being used by any jobs
            if ProcessingJob.objects.filter(columns=self.object).exists():
                raise ValidationError("Cannot delete column that is in use")

            self.object.delete()
            
            # Return JSON response for AJAX requests
            return JsonResponse({'success': True})
            
        except Exception as e:
            logger.error(f"Error deleting column: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


@require_POST
def validate_column_name(request):
    """API endpoint to validate column names"""
    try:
        name = request.POST.get('name', '').strip()
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            raise ValidationError("Invalid column name format")

        # Check for duplicates
        column_id = request.POST.get('id', None)
        query = ColumnDefinition.objects.filter(name=name)
        if column_id:
            query = query.exclude(id=column_id)
            
        if query.exists():
            raise ValidationError("Column name already exists")

        return JsonResponse({'valid': True})
    except ValidationError as e:
        return JsonResponse({'valid': False, 'error': str(e)})


@require_POST
def update_column_order(request):
    """API endpoint to update column order"""
    try:
        order_data = json.loads(request.body)
        for item in order_data:
            column = ColumnDefinition.objects.get(id=item['id'])
            column.order = item['order']
            column.save()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error updating column order: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


class JobListView(ListView):
    """View for listing all processing jobs"""
    model = ProcessingJob
    template_name = 'job_list.html'
    context_object_name = 'jobs'
    #paginate_by = 10
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['paginate_by'] = self.get_paginate_by(self.get_queryset())  # Pass paginate_by to template
        return context

    def get_paginate_by(self, queryset):
        """Dynamically determine pagination based on request parameter"""
        paginate_by_value = self.request.GET.get('paginate_by', '10')  # Default to 10

        if paginate_by_value == 'all':
            return None  # Disable pagination for 'all'
        else:
            try:
                return int(paginate_by_value)  # Use selected value as integer
            except ValueError:
                return 10  # Fallback to default if not a valid integer

    def get_queryset(self):
        logger.debug("JobListView.get_queryset called")
        queryset = ProcessingJob.objects.all()
        sort_by = self.request.GET.get('sort_by')
        order = self.request.GET.get('order', 'asc')

        logger.debug(f"  Sorting parameters - sort_by: {sort_by}, order: {order}")

        if sort_by:
            logger.debug(f"  Sorting requested by field: {sort_by}, order: {order}")
            if order == 'desc':
                sort_field = f'-{sort_by}'
            else:
                sort_field = sort_by
            queryset = queryset.order_by(sort_field)
            logger.debug(f"  Queryset ordered by: {sort_field}")
        else:
            queryset = queryset.order_by('-created_at')  # Default sort if no sort_by
            logger.debug(f"  Default ordering applied: -created_at")

        logger.debug(f"  Final queryset ordering: {queryset.query}")

        # Add job type filter if provided
        job_type = self.request.GET.get('type')
        if job_type:
            queryset = queryset.filter(job_type=job_type)

        return queryset
        # return ProcessingJob.objects.all().order_by('-created_at') # Original line


# In views.py

class JobDetailView(DetailView):
    """View for displaying job details"""
    model = ProcessingJob
    template_name = 'job_detail.html'
    context_object_name = 'job'
    
    def _get_prompt_template(self):
        """Get the prompt template used in this job"""
        # Check if job used a specific prompt
        if self.object.prompt:
            return self.object.prompt.content
        
        # Otherwise, try to get the default template
        try:
            default_template = open(os.path.join(
                settings.BASE_DIR, 'core', 'templates', 'default_prompt_template.html'
            )).read()
            return default_template
        except Exception:
            return "No prompt template available"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        
        # Count documents
        documents = PDFDocument.objects.filter(job=job)
        context['documents'] = documents
        context['total_count'] = documents.count()
        context['processed_count'] = documents.filter(status__in=['processed', 'complete', 'error']).count()
        
        # Get all results for this job
        results = ProcessingResult.objects.filter(document__job=job)
        context['results'] = results
        
        # Check if this is a reference extraction job
        if hasattr(job, 'job_type') and job.job_type == 'reference_extraction':
            # Get references for this job
            references = Reference.objects.filter(job=job).order_by('document_id', 'id') # Order for consistency
            context['references'] = references # Keep the full list for the main table
            context['is_reference_job'] = True
            context['reference_count'] = references.count()
            
            # Group references by document for the preview sections
            references_by_doc = {}
            for ref in references:
                doc_id_str = str(ref.document.id)
                if doc_id_str not in references_by_doc:
                    references_by_doc[doc_id_str] = []
                references_by_doc[doc_id_str].append(ref)
            context['references_by_doc'] = references_by_doc
            
            # Get unique source types for filtering
            context['source_types'] = references.values_list('source_type', flat=True).distinct()
        else:
            # For case extraction jobs, calculate total case count
            total_case_count = 0
            for result in results:
                if result.json_result and 'case_results' in result.json_result:
                    total_case_count += len(result.json_result['case_results'])
            context['total_case_count'] = total_case_count
            context['is_reference_job'] = False
        
        # Format job data as JSON for display
        job_data = {
            'id': str(job.id),
            'name': job.name,
            'status': job.status,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None,
            'documents': [
                {
                    'id': str(doc.id),
                    'filename': doc.filename,
                    'status': doc.status
                } for doc in documents
            ],
            'results': self._format_results_data(results)
        }
        
        # Serialize to JSON for display
        context['json_data'] = json.dumps(job_data, indent=2)
        
        # Add prompt template used for this job
        context['prompt_template'] = self._get_prompt_template()
        
        # Check if any document has truncated response
        context['is_truncated'] = any(doc.status == 'processed' for doc in documents)
        
        # If there are truncated responses, provide info for continuation
        if context['is_truncated']:
            truncated_docs = documents.filter(status='processed')
            context['truncated_doc_count'] = truncated_docs.count()
            context['total_documents'] = documents.count()
            
            # Get the first truncated document for continuation
            if truncated_docs:
                first_truncated = truncated_docs.first()
                context['continuation_document_id'] = first_truncated.id
                
                # Get info about the last case processed
                last_case_number = 0
                for result in results:
                    if (result.document.id == first_truncated.id and 
                        result.json_result and 
                        'case_results' in result.json_result):
                        case_results = result.json_result['case_results']
                        if case_results:
                            try:
                                last_case = case_results[-1]
                                if 'case_number' in last_case:
                                    case_num = last_case['case_number']
                                    if isinstance(case_num, dict) and 'value' in case_num:
                                        last_case_number = int(case_num['value'])
                                    else:
                                        last_case_number = int(case_num)
                                else:
                                    # If case_number not found, use length of array
                                    last_case_number = len(case_results)
                            except (ValueError, TypeError, IndexError):
                                # If can't parse, use the length of the array
                                last_case_number = len(case_results)
                
                context['last_case_number'] = last_case_number
                context['continuation_message'] = f"Some documents have truncated responses. Continue processing {first_truncated.filename} from case {last_case_number}."
        
        # Check if continuation processing is pending or in progress
        if job.status in ['pending_continuation', 'pending_continuation_with_errors']:
            context['pending_continuation'] = True
            context['continuation_status'] = "The system is continuing to process documents that had truncated responses."
        
        # Extract current processing details if available
        if job.status == 'processing' and job.processing_details:
            # Try to extract current document and case from processing details
            import re
            
            # Extract current document
            doc_match = re.search(r'document[:\s]+([^-\(\)]+)', job.processing_details, re.IGNORECASE)
            if doc_match:
                context['current_document'] = doc_match.group(1).strip()
            
            # Extract current case
            case_match = re.search(r'case\s+(\d+)', job.processing_details, re.IGNORECASE)
            if case_match:
                context['current_case'] = case_match.group(1).strip()
            
            # Determine processing phase
            details_lower = job.processing_details.lower()
            if 'extracting' in details_lower:
                context['processing_phase'] = 'extracting'
            elif 'processing' in details_lower:
                context['processing_phase'] = 'processing'
            elif 'sending' in details_lower:
                context['processing_phase'] = 'sending'
            elif 'preparing' in details_lower:
                context['processing_phase'] = 'preparing'
            else:
                context['processing_phase'] = 'initializing'
            
            # Calculate time since last update
            if job.updated_at:
                now = timezone.now()
                time_diff = now - job.updated_at
                context['time_since_update'] = int(time_diff.total_seconds())
        
        return context
    
    def _format_results_data(self, results):
        """Format the results data for JSON display"""
        results_data = []
        for result in results:
            result_data = {
                'id': str(result.id),
                'document_id': str(result.document.id),
                'document_name': result.document.filename,
                'created_at': result.created_at.isoformat() if result.created_at else None,
                'case_count': 0,
            }
            
            # Add case count if available
            if result.json_result and 'case_results' in result.json_result:
                result_data['case_count'] = len(result.json_result['case_results'])
            
            results_data.append(result_data)
        
        return results_data
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests for job actions"""
        self.object = self.get_object()
        job = self.object
        
        try:
            data = {}
            
            # Check if this is an AJAX request for document list refresh
            if 'action' in request.POST and request.POST['action'] == 'refresh_documents':
                return self._handle_refresh_documents_request(request, job)
                
            # Otherwise, handle regular POST JSON data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                # For form submissions
                data = request.POST.dict()
            
            action = data.get('action')
            
            if action == 'continue_processing':
                return self._handle_continue_processing(request, data)
            elif action == 'rerun_document':
                return self._handle_rerun_document(request, data)
            
            return JsonResponse({
                'error': 'Invalid action requested'
            }, status=400)
            
        except Exception as e:
            logger.exception("Error processing job action request")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _handle_refresh_documents_request(self, request, job):
        """Handle AJAX request to refresh just the document list"""
        # Prepare context with only what's needed for the document list
        documents = PDFDocument.objects.filter(job=job)
        results = ProcessingResult.objects.filter(document__job=job)
        
        context = {
            'job': job,
            'documents': documents,
            'results': results,
        }
        
        # Render just the document list table part
        html = render_to_string('job_detail_documents.html', context, request)
        
        # If it's an AJAX request, return just the HTML
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponse(html)
        
        # Otherwise fall back to full page render
        return self.get(request, *self.args, **self.kwargs)

    def _handle_continue_processing(self, request, data):
        """Handles the 'continue_processing' action for reference extraction jobs."""
        job = self.object
        document_id = data.get('document_id')
        if not document_id:
            return JsonResponse({'success': False, 'error': 'Document ID is required.'}, status=400)

        logger.info(f"Received continue processing request for Doc ID: {document_id} in Job {job.id} (Type: {job.job_type})")

        try:
            document = get_object_or_404(PDFDocument, id=document_id, job=job)

            # Check if continuation is actually needed
            if document.status not in ['processed', 'error']:  # Allow retry on error too
                logger.warning(f"Attempted to continue processing Doc ID {document.id} but status is '{document.status}'.")
                return JsonResponse({'success': False, 'error': f'Continuation not needed for document status: {document.status}.'}, status=400)

            # Read PDF data
            with document.file.open('rb') as f:
                pdf_data = f.read()

            logger.info(f"Starting background task for CONTINUATION of Doc ID: {document.id} (Last index: {document.last_successful_reference_index})")

            # Select the correct task based on job type
            task_function = None
            if job.job_type == 'reference_extraction':
                # Create an instance of the view to call the method
                view_instance = ReferenceExtractionView()
                task_function = view_instance._process_pdf_for_references_task
            else:
                logger.error(f"Unknown job type '{job.job_type}' for continuation.")
                return JsonResponse({'success': False, 'error': f"Continuation not supported for job type '{job.job_type}'."}, status=400)

            # Start the background thread
            thread = threading.Thread(
                target=task_function,
                args=(pdf_data, str(document.id), str(job.id))
            )
            thread.start()

            # Update Job status to show processing is happening again
            if job.status not in ['processing', 'processing_with_errors']:
                job.status = 'processing'
                job.save(update_fields=['status'])

            return JsonResponse({'success': True, 'message': f'Continuation processing initiated for {document.filename}.'})

        except PDFDocument.DoesNotExist:
            logger.error(f"Continue processing failed: Document {document_id} not found.")
            return JsonResponse({'success': False, 'error': 'Document not found.'}, status=404)
        except Exception as e:
            logger.exception(f"Error handling continue processing for Doc ID {document_id}")
            return JsonResponse({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}, status=500)
            
    def _handle_rerun_document(self, request, data):
        """Handles the 'rerun_document' action to reprocess a document."""
        job = self.object
        document_id = data.get('document_id')
        if not document_id:
            return JsonResponse({'success': False, 'error': 'Document ID is required.'}, status=400)
            
        logger.info(f"Received rerun document request for Doc ID: {document_id} in Job {job.id}")
        
        try:
            document = get_object_or_404(PDFDocument, id=document_id, job=job)
            
            # Reset document status and counters
            document.status = 'pending'
            document.error = None
            document.last_successful_reference_index = 0  # Reset continuation index
            document.save()
            
            # Clear any existing results for this document
            ProcessingResult.objects.filter(document=document).delete()
            
            # For reference extraction jobs, remove existing references
            if job.job_type == 'reference_extraction':
                Reference.objects.filter(document=document).delete()
            
            # Read PDF data
            with document.file.open('rb') as f:
                pdf_data = f.read()
                
            logger.info(f"Starting background task for RERUN of Doc ID: {document.id}")
            
            # Select the correct task based on job type
            task_function = None
            if job.job_type == 'reference_extraction':
                view_instance = ReferenceExtractionView()
                task_function = view_instance._process_pdf_for_references_task
            elif job.job_type == 'case_extraction':
                # This would need to call the appropriate processor for case extraction
                view_instance = ProcessorView()
                # This assumes a similar _process_document_task method exists
                task_function = lambda pdf_data, doc_id, job_id: view_instance.process_pdfs_with_gemini(
                    get_object_or_404(ProcessingJob, id=job_id), 
                    [pdf_data], 
                    [get_object_or_404(PDFDocument, id=doc_id).filename]
                )
            else:
                logger.error(f"Unknown job type '{job.job_type}' for rerun.")
                return JsonResponse({'success': False, 'error': f"Rerun not supported for job type '{job.job_type}'."}, status=400)
                
            # Start the background thread
            thread = threading.Thread(
                target=task_function,
                args=(pdf_data, str(document.id), str(job.id))
            )
            thread.start()
            
            # Update Job status
            if job.status not in ['processing', 'processing_with_errors']:
                job.status = 'processing'
                job.save(update_fields=['status'])
                
            return JsonResponse({'success': True, 'message': f'Reprocessing initiated for {document.filename}.'})
            
        except PDFDocument.DoesNotExist:
            logger.error(f"Rerun document failed: Document {document_id} not found.")
            return JsonResponse({'success': False, 'error': 'Document not found.'}, status=404)
        except Exception as e:
            logger.exception(f"Error handling rerun document for Doc ID {document_id}")
            return JsonResponse({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class JobResultsView(DetailView):
    """View for displaying job results in a more detailed format"""
    model = ProcessingJob
    template_name = 'job_results.html'
    context_object_name = 'job'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        results = ProcessingResult.objects.filter(document__job=self.object)
        
        all_cases = []
        for result in results:
            if result.json_result and 'case_results' in result.json_result:
                all_cases.extend(result.json_result['case_results'])
        
        # Add the raw cases to the context
        context['results'] = results
        context['all_cases'] = all_cases
        
        # Add prompt for reference
        context['prompt_template'] = self.object.prompt_template if self.object.prompt_template else "No prompt template saved"
        
        return context

class StorePromptView(View):
    """Handle request to store a prompt"""
    def dispatch(self, request, *args, **kwargs):
        # Handle action parameter for different methods
        if 'action' in kwargs and kwargs['action'] == 'create_from_columns':
            return self.create_from_columns(request)
        return super().dispatch(request, *args, **kwargs)
        
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Either create new or update existing prompt
            if data.get('prompt_id'):
                # Update existing prompt
                prompt = get_object_or_404(SavedPrompt, id=data['prompt_id'])
                prompt.name = data.get('name', prompt.name)
                prompt.content = data['content']
                prompt.variables = data.get('variables', {})
                prompt.save()
                logger.info(f"Updated existing prompt: {prompt.name}")
            else:
                # Create new prompt
                prompt = SavedPrompt.objects.create(
                    name=data.get('name', 'Untitled Prompt'),
                    content=data['content'],
                    variables=data.get('variables', {})
                )
                logger.info(f"Created new prompt: {prompt.name}")
            
            return JsonResponse({
                'success': True,
                'prompt_id': prompt.id,
                'message': f"Prompt '{prompt.name}' saved successfully"
            })
            
        except Exception as e:
            logger.error(f"Error storing prompt: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    @method_decorator(require_POST)
    def create_from_columns(self, request):
        """Create a new prompt based on column definitions"""
        try:
            # Generate a prompt from column definitions
            column_prompt = ColumnDefinitionView.generate_prompt_template()
            
            if not column_prompt:
                return JsonResponse({
                    'success': False,
                    'error': 'No column definitions found to generate prompt'
                }, status=400)
            
            # Get the prompt name from the request or use a default
            data = json.loads(request.body) if request.body else {}
            prompt_name = data.get('name', 'Schema-Generated Prompt')
            
            # Create the new prompt
            prompt = SavedPrompt.objects.create(
                name=prompt_name,
                content=column_prompt,
                variables=data.get('variables', {})
            )
            
            logger.info(f"Created new prompt from column definitions: {prompt.name}")
            
            return JsonResponse({
                'success': True,
                'prompt_id': prompt.id,
                'name': prompt.name,
                'content': prompt.content,
                'message': f"Prompt '{prompt.name}' created from schema columns successfully"
            })
            
        except Exception as e:
            logger.error(f"Error creating prompt from columns: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

class ProcessorView(FormView):
    """Main view for processing PDFs"""
    template_name = 'processor.html'
    form_class = ProcessingForm
    success_url = reverse_lazy('core:job_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['prompts'] = SavedPrompt.objects.all().order_by('-created_at')
        context['columns'] = ColumnDefinition.objects.all().order_by('category', 'order')
        
        # Get the most recent saved prompt
        saved_prompt = SavedPrompt.objects.order_by('-created_at').first()
        
        # Check if we have column definitions that could generate a prompt
        has_column_definitions = ColumnDefinition.objects.exists()
        
        # Get the column-definition generated prompt if available
        column_prompt = None
        if has_column_definitions:
            column_prompt = ColumnDefinitionView.generate_prompt_template()
        
        # Determine which prompt is active
        active_prompt_content = None
        if saved_prompt:
            context['active_prompt'] = saved_prompt
            context['active_prompt_source'] = 'saved'
            context['active_prompt_name'] = saved_prompt.name
            active_prompt_content = saved_prompt.content
        elif column_prompt:
            context['active_prompt'] = {'content': column_prompt}
            context['active_prompt_source'] = 'column-definition'
            context['active_prompt_name'] = 'Column-Generated Prompt'
            active_prompt_content = column_prompt
        else:
            # If no prompt at all, use the default text extraction prompt
            context['active_prompt'] = {'content': TEXT_EXTRACTION_PROMPT}
            context['active_prompt_source'] = 'default'
            context['active_prompt_name'] = 'Default Prompt'
            active_prompt_content = TEXT_EXTRACTION_PROMPT
        
        # Additionally, provide both prompt options for reference
        context['column_prompt'] = column_prompt
        context['saved_prompt'] = saved_prompt
        
        # If this is a GET request, set the initial prompt in the form
        if self.request.method == 'GET':
            # Get form from context
            form = context.get('form')
            if form:
                # Set initial prompt_template value to match active prompt
                form.initial['prompt_template'] = active_prompt_content
        
        return context
        
    def form_valid(self, form):
        try:
            # Get the submitted prompt from the form
            submitted_prompt = form.cleaned_data.get('prompt_template')
            logger.info("Processing form submission")
            logger.debug(f"Submitted prompt: {submitted_prompt[:200] if submitted_prompt else 'None'}")

            # Create the job
            job = form.save(commit=False)
            
            # Log all fields for debugging
            logger.debug(f"Job fields before save: id={job.id}, name={job.name}, prompt_template={job.prompt_template[:50] if job.prompt_template else 'None'}, " +
                         f"status={job.status}, processed_count={job.processed_count}, total_count={job.total_count}, " +
                         f"error_message={job.error_message}, prompt_id={job.prompt_id if job.prompt_id else 'None'}")
            
            # Use the most recent prompt if no prompt was submitted
            if not submitted_prompt:
                saved_prompt = SavedPrompt.objects.order_by('-created_at').first()
                if saved_prompt:
                    logger.info(f"Using saved prompt: {saved_prompt.name}")
                    job.prompt_template = saved_prompt.content
                else:
                    logger.warning("No saved prompts found, using form prompt")
                    job.prompt_template = form.cleaned_data['prompt_template']
            else:
                logger.info("Using submitted prompt")
                job.prompt_template = submitted_prompt

            # Set the total count of PDFs to process
            pdf_files = form.cleaned_data.get('pdf_files', [])
            job.total_count = len(pdf_files)
            logger.info(f"Total PDFs to process: {job.total_count}")
            
            # Explicitly set empty error_message to avoid NULL issues
            if job.error_message is None:
                job.error_message = ""
                
            # Ensure all required fields have values to avoid NULL issues
            job.status = job.status or 'pending'
            job.processed_count = job.processed_count or 0
            job.total_count = job.total_count or 0
            job.error_message = job.error_message or ""
            
            # Try a workaround to avoid the datatype mismatch - create a new job from scratch
            try:
                # Try to save with default method first
                job.save()
            except django.db.utils.IntegrityError as e:
                if "datatype mismatch" in str(e):
                    logger.warning("Attempting workaround for datatype mismatch error")
                    
                    # Create a new job manually
                    from django.db import connection
                    
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO core_processingjob 
                            (id, name, prompt_template, created_at, updated_at, status, processed_count, total_count, error_message, prompt_id, processing_details)
                            VALUES (?, ?, ?, datetime('now'), datetime('now'), ?, ?, ?, ?, ?, ?)
                        """, [
                            str(uuid.uuid4()),
                            job.name,
                            job.prompt_template,
                            job.status,
                            job.processed_count,
                            job.total_count,
                            job.error_message or '',  # Use empty string if None
                            job.prompt_id,
                            job.processing_details or ''  # Use empty string if None
                        ])
                        
                        # Get the last inserted ID
                        cursor.execute("SELECT last_insert_rowid()")
                        last_id = cursor.fetchone()[0]
                        
                        # Get the job we just created
                        job = ProcessingJob.objects.get(pk=last_id)
                        logger.info(f"Created job {job.id} using raw SQL workaround")
                else:
                    # If it's a different type of error, raise it
                    raise

            # Get the file data for report names and study authors from the POST data
            file_data = []
            if 'file_data' in self.request.POST:
                try:
                    file_data = json.loads(self.request.POST.get('file_data', '[]'))
                    logger.info(f"Received file data: {file_data}")
                except json.JSONDecodeError:
                    file_data = []
                    logger.warning("Failed to parse file_data JSON")

            # Process the PDFs
            pdf_file_data_list = []
            pdf_file_name_list = []
            pdf_metadata_list = []
            
            for idx, pdf_file in enumerate(pdf_files):
                # Find metadata for this file
                metadata = {}
                for item in file_data:
                    if item.get('index') == idx:
                        metadata = {
                            'report_name': item.get('report_name', pdf_file.name),
                            'study_author': item.get('study_author', '')
                        }
                        break
                
                if not metadata:
                    # Default metadata if not found
                    filename_without_ext = pdf_file.name.replace('.pdf', '')
                    metadata = {
                        'report_name': pdf_file.name,
                        'study_author': filename_without_ext
                    }
                
                pdf_file_data_list.append(pdf_file.read())
                pdf_file_name_list.append(pdf_file.name)
                pdf_metadata_list.append(metadata)

            # Process PDFs with direct Gemini API calls
            return self.process_pdfs_with_gemini(job, pdf_file_data_list, pdf_file_name_list, pdf_metadata_list)

        except Exception as e:
            logger.error(f"Error in form processing: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    def process_pdfs_with_gemini(self, job, pdf_file_data_list, pdf_file_name_list, pdf_metadata_list=None):
        """Process PDFs by sending them directly to Gemini with vision capabilities"""
        try:
            if not pdf_file_data_list or not pdf_file_name_list:
                raise ValueError("No PDF files provided")
            
            if len(pdf_file_data_list) != len(pdf_file_name_list):
                raise ValueError("Mismatched PDF data and filenames")
            
            # If no metadata provided, create empty list
            if pdf_metadata_list is None:
                pdf_metadata_list = [{'report_name': name, 'study_author': name.replace('.pdf', '')} 
                                     for name in pdf_file_name_list]
            
            # Update total file count if not already set
            if job.total_count == 0:
                job.total_count = len(pdf_file_data_list)
                job.save()
            
            # Set job status to processing
            job.status = 'processing'
            job.save()
            
            # Get prompt template
            prompt_template = self._get_prompt_template(job)
            
            # Process each PDF
            successful_count = 0
            docs_requiring_continuation = []
            errors_encountered = []
            
            for pdf_idx, (pdf_data, pdf_name, metadata) in enumerate(zip(pdf_file_data_list, pdf_file_name_list, pdf_metadata_list)):
                try:
                    # Update processing details to show which document we're working on
                    job.processing_details = f"Processing document {pdf_idx + 1}/{len(pdf_file_data_list)}: {pdf_name}"
                    job.save()
                    
                    logger.info(f"Processing PDF {pdf_idx + 1}/{len(pdf_file_data_list)}: {pdf_name}")
                    print(f"\nProcessing PDF {pdf_idx + 1}/{len(pdf_file_data_list)}: {pdf_name}")
                    
                    # Create document record with metadata
                    document = PDFDocument.objects.create(
                        job=job,
                        file=ContentFile(pdf_data, name=pdf_name),
                        filename=metadata.get('report_name', pdf_name),
                        study_author=metadata.get('study_author', ''),
                        status='pending'
                    )
                    
                    # Process with Gemini directly
                    result = self._process_pdf_with_gemini(pdf_data, document, prompt_template, job)
                    
                    if result.get('success'):
                        # Mark document as processed (even if truncated)
                        document.status = 'complete' if not result.get('is_truncated', False) else 'processed'
                        document.save()
                        successful_count += 1
                        
                        # Check if continuation is needed
                        if result.get('is_truncated', False):
                            docs_requiring_continuation.append(document.id)
                            logger.info(f"Document {document.id} ({pdf_name}) needs continuation processing")
                        
                        # Update job progress
                        job.processed_count = successful_count
                        job.save()
                    else:
                        logger.error(f"Error processing {pdf_name}: {result.get('error', 'Unknown error')}")
                        document.error = result.get('error', 'Unknown error')
                        document.status = 'error'
                        document.save()
                        errors_encountered.append(pdf_name)
                    
                except Exception as e:
                    logger.error(f"Error processing PDF {pdf_name}: {str(e)}")
                    errors_encountered.append(pdf_name)
                    continue
            
            # Update final job status based on results
            job.refresh_from_db()
            needs_continuation = len(docs_requiring_continuation) > 0
            has_errors = len(errors_encountered) > 0
            
            # Determine appropriate status based on results
            if successful_count == 0:
                # All documents failed
                job.status = 'failed'
                job.error_message = f"Failed to process all {job.total_count} documents"
            elif not has_errors and not needs_continuation:
                # All successful, no truncation
                job.status = 'completed'
                job.error_message = ""  # Use empty string instead of None
                job.processing_details = f"Successfully processed {successful_count} documents"
            elif not has_errors and needs_continuation:
                # Some need continuation but no errors
                job.status = 'pending_continuation'
                job.error_message = ""  # Use empty string instead of None
                job.processing_details = f"{len(docs_requiring_continuation)} documents need continuation processing"
            elif has_errors and not needs_continuation:
                # Some errors but no truncation
                job.status = 'completed_with_errors'
                job.error_message = f"Completed with {len(errors_encountered)} errors: {', '.join(errors_encountered[:3])}" + ("..." if len(errors_encountered) > 3 else "")
                job.processing_details = f"Processed {successful_count}/{job.total_count} documents with errors"
            else:
                # Both errors and truncation
                job.status = 'pending_continuation_with_errors'
                job.error_message = f"{len(errors_encountered)} errors; {len(docs_requiring_continuation)} documents require continuation"
                job.processing_details = f"Processed {successful_count}/{job.total_count} documents; {len(docs_requiring_continuation)} need continuation"
            
            job.save()
            
            logger.info(f"Job {job.id} processed. Status: {job.status}, Processed: {successful_count}/{job.total_count}, Requiring continuation: {len(docs_requiring_continuation)}")
            return JsonResponse({
                'success': True, 
                'job_id': job.id, 
                'status': job.status,
                'needs_continuation': needs_continuation
            })
            
        except Exception as e:
            logger.error(f"Error in process_pdfs: {str(e)}", exc_info=True)
            job.status = 'failed'
            job.error_message = str(e)
            job.processing_details = f"Error: {str(e)}"
            job.save()
            return JsonResponse({'success': False, 'error': str(e)})
    
    def _get_prompt_template(self, job=None):
        """Get the appropriate prompt template"""
        # If job has a prompt template, use that
        if job and job.prompt_template:
            logger.info("Using job-specific prompt template")
            return job.prompt_template
            
        # Otherwise, get the most recent saved prompt
        saved_prompt = SavedPrompt.objects.order_by('-created_at').first()
        if saved_prompt:
            logger.info(f"Using saved prompt: {saved_prompt.name}")
            
            # Debug: Print out a sample of the prompt template
            print("\n" + "="*80)
            print("PROMPT TEMPLATE SAMPLE (first 500 chars):")
            print(saved_prompt.content[::] + "...")
            print("="*80)
            
            return saved_prompt.content
            
        # If no saved prompts exist, generate from column definitions
        columns = ColumnDefinition.objects.all().order_by('category', 'order')
        if not columns.exists():
            return TEXT_EXTRACTION_PROMPT
            
        # Generate a prompt template using the column definitions
        template = ColumnDefinitionView.generate_prompt_template()
        if template:
            return template
            
        return TEXT_EXTRACTION_PROMPT

    def _process_pdf_with_gemini(self, pdf_data, document_record, prompt_template, job):
        """Process a PDF by sending it directly to Gemini with vision capabilities"""
        try:
            # Get Gemini API key
            load_dotenv(os.path.join(os.getcwd(), '.env'), override=True)
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment variables")
            
            # Initialize Gemini API
            genai.configure(api_key=api_key)
            
            # Update job status to show we're preparing the document
            job.processing_details = f"Preparing document: {document_record.filename} for processing"
            job.save()
            
            # Log that we're using Gemini's vision capabilities directly
            logger.info("Using Gemini's vision capabilities to process PDF")
            print("Using Gemini's vision capabilities to process PDF")
            
            # Encode the PDF data for sending to Gemini
            encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')

            # Send the PDF and prompt to Gemini with a generation config
            generation_config = {
                "max_output_tokens": 30720,  # Increase token limit to maximum allowed
                "temperature": 0.1,         # Lower temperature for more deterministic outputs
                "top_p": 0.95,              # High top_p ensures more comprehensive results
                "top_k": 40,                # Reasonable top_k for diversity without going off-topic
            }

            # Import the schema integration utility and generate the schema for structured output  
            from core.utils.schema_integration import generate_gemini_schema
            
            # Create a model with structured output using our schema
            try:
                # Use structured output with schema
                schema = generate_gemini_schema()
                
                # Create Gemini model with vision capabilities and structured output
                model = genai.GenerativeModel(
                    model_name='gemini-2.5-flash-preview-04-17',
                    generation_config=generation_config, 
                    system_instruction="You are an expert medical data extractor that carefully reads clinical case documents and extracts structured information according to the provided schema. Always be thorough and extract all available information.",
                    tools=[{"schema_format": "json-schema", "schema": schema}]
                )
                
                # Log that we're using structured output
                logger.info("Using Gemini with structured output format")
                print("Using Gemini with structured output format")
                
            except Exception as e:
                logger.error(f"Error creating structured model: {e}")
                # Fall back to regular model if structured output fails
                model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
                logger.warning("Falling back to regular Gemini model without structured output")
                print("Falling back to regular Gemini model without structured output")
            
            # Log the prompt being sent to Gemini
            logger.info("SENDING PROMPT TO GEMINI:")
            print("\n" + "="*80)
            print("PROMPT SENT TO GEMINI (first 500 chars):")
            print(prompt_template[:500] + "...")
            print("="*80)
            logger.debug(f"Full prompt: {prompt_template}")
            
            # Update job status to show we're sending the request
            job.processing_details = f"Sending document: {document_record.filename} to Gemini for analysis"
            job.save()
            
            # Track timing
            start_time = time.time()
            
            # Set safety settings to minimize content filtering
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Update job status to show we're waiting for response
            job.processing_details = f"Waiting for Gemini to analyze document: {document_record.filename}"
            job.save()
            
            # Define a response handler to provide real-time updates as cases are processed
            def response_handler(response):
                if hasattr(response, 'text'):
                    # Look for indications of case extraction in the response
                    text = response.text
                    case_matches = re.findall(r'case_number.*?value.*?patient\s*(\d+)', text.lower())
                    if case_matches:
                        latest_case = max([int(x) for x in case_matches if x.isdigit()])
                        job.processing_details = f"Processing document: {document_record.filename} - Extracting case {latest_case}"
                        job.save()
                        
            # Determine if we're using structured output or not
            structured_output = 'tools' in model.__dict__ and model.tools
            
            if structured_output:
                # With structured output, the model will return a properly structured JSON directly
                response = model.generate_content(
                    [
                        {"mime_type": "application/pdf", "data": encoded_pdf},
                        prompt_template
                    ],
                    safety_settings=safety_settings,
                    stream=False  # Can't stream with structured output
                )
                
                # Structured output doesn't support streaming, so we get the full response at once
                raw_response = ""
                case_count = 0
                
                # Check if the response is in the expected structured format
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    # Check if structured content was returned
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call.name == 'schema':
                                try:
                                    # Extract the JSON directly from the function call
                                    structured_data = json.loads(part.function_call.args['schema'])
                                    raw_response = json.dumps(structured_data, indent=2)
                                    if 'case_results' in structured_data:
                                        case_count = len(structured_data['case_results'])
                                except Exception as e:
                                    logger.error(f"Error parsing structured output: {e}")
                                    raw_response = str(part.function_call.args)
                            elif hasattr(part, 'text'):
                                # Append any text parts to the raw response
                                raw_response += part.text
            else:
                # Without structured output, stream the response as before
                response = model.generate_content(
                    [
                        {"mime_type": "application/pdf", "data": encoded_pdf},
                        prompt_template
                    ],
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    stream=True
                )
                
                # Collect the full response while updating status
                raw_response = ""
                case_count = 0
                
                for chunk in response:
                    if hasattr(chunk, 'text'):
                        raw_response += chunk.text
                        
                        # Check for case numbers in this chunk
                        chunk_text = chunk.text.lower()
                        case_matches = re.findall(r'case_number.*?value.*?(?:patient|case)\s*(\d+)', chunk_text)
                        
                        if case_matches:
                            # Get the highest case number found
                            try:
                                new_cases = [int(x) for x in case_matches if x.isdigit()]
                                if new_cases:
                                    case_count = max(case_count, max(new_cases))
                                    # Update job status with the current case
                                    job.processing_details = f"Processing document: {document_record.filename} - Extracting case {case_count}"
                                    job.save()
                            except ValueError:
                                pass
            
            # Log timing information
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"Gemini response received in {elapsed_time:.2f} seconds")
            
            # Update job status to show we're processing the response
            job.processing_details = f"Processing Gemini response for document: {document_record.filename}"
            job.save()
            
            # Get the finish reason (for detecting truncation)
            finish_reason = None
            is_truncated = False
            if hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                finish_reason = response.candidates[0].finish_reason
                logger.info(f"Gemini response finish reason: {finish_reason}")
                print(f"Gemini response finish reason: {finish_reason}")
            
            # Determine if the response was truncated based on finish_reason
            if finish_reason == 'MAX_TOKENS':
                is_truncated = True
                logger.warning("Response was truncated due to MAX_TOKENS limit")
                print("WARNING: Response was truncated due to MAX_TOKENS limit")
            
            # Log the raw response
            logger.info("="*50)
            logger.info("RAW RESPONSE FROM GEMINI:")
            print("\n" + "="*80)
            print("RAW RESPONSE FROM GEMINI (first 500 chars):")
            print(raw_response[:500] + "...")
            print("="*80)
            logger.debug(f"Full response: {raw_response}")
            
            # Update job status to show we're extracting JSON
            job.processing_details = f"Extracting JSON data from response for document: {document_record.filename}"
            job.save()
            
            # Extract JSON from the response with error handling
            try:
                # For structured output, use the already parsed JSON
                if structured_output and 'structured_data' in locals() and structured_data:
                    result_data = structured_data
                else:
                    # Extract JSON from text response
                    result_data = extract_json_from_text(raw_response)
                
                # Log information about extracted JSON
                if result_data and isinstance(result_data, dict) and 'case_results' in result_data:
                    case_count = len(result_data['case_results'])
                    logger.info(f"Successfully extracted JSON with {case_count} cases")
                    print(f"Successfully extracted JSON with {case_count} cases")
                    
                    # Update job status with final case count
                    job.processing_details = f"Extracted {case_count} cases from document: {document_record.filename}"
                    job.save()
                    
                    # Apply post-processing filter to remove cited cases
                    from .utils import filter_cited_cases
                    original_count = case_count
                    
                    # Add defensive handling for filter_cited_cases
                    try:
                        filtered_data = filter_cited_cases(result_data)
                        
                        # Verify the returned structure is as expected
                        if isinstance(filtered_data, dict) and 'case_results' in filtered_data:
                            result_data = filtered_data
                            new_count = len(result_data['case_results'])
                            
                            if new_count < original_count:
                                logger.info(f"Filtered out {original_count - new_count} cited cases")
                                print(f"Filtered out {original_count - new_count} cited cases")
                        else:
                            # If filter_cited_cases returns unexpected structure, log and use original
                            logger.warning(f"filter_cited_cases returned unexpected structure: {type(filtered_data)}")
                            print(f"WARNING: filter_cited_cases returned unexpected structure, using original data")
                            new_count = original_count
                    except Exception as filter_err:
                        # Log error but continue with original data
                        logger.error(f"Error in filter_cited_cases: {str(filter_err)}", exc_info=True)
                        print(f"Error filtering cited cases: {str(filter_err)}")
                        new_count = original_count
                else:
                    logger.warning(f"No valid case results found in JSON response")
                    print("WARNING: No valid case results found in JSON response")
                
                # Add truncation info if not already present
                if 'truncation_info' not in result_data:
                    result_data['truncation_info'] = {
                        'is_truncated': is_truncated,
                        'last_complete_case': case_count if case_count > 0 else 0
                    }
                else:
                    # Update truncation info with the finish reason
                    result_data['truncation_info']['is_truncated'] = is_truncated
                
                # Create a result record
                result_record = ProcessingResult.objects.create(
                    document=document_record,
                    json_result=result_data,
                    raw_result=raw_response,
                    is_complete=not is_truncated
                )
                
                # Update document status
                document_record.status = 'completed' if not is_truncated else 'completed_with_truncation'
                document_record.save()
                
                # Increment processed count
                job.processed_count += 1
                job.save()
                
                # Return success
                return {
                    "success": True,
                    "document_id": str(document_record.id),
                    "result_id": str(result_record.id),
                    "is_truncated": is_truncated,
                    "case_count": case_count
                }
                
            except Exception as e:
                logger.error(f"Error extracting JSON from response: {str(e)}", exc_info=True)
                print(f"Error extracting JSON from response: {str(e)}")
                
                # Create a result record with the error
                result_record = ProcessingResult.objects.create(
                    document=document_record,
                    raw_result=raw_response,
                    error=str(e),
                    is_complete=False
                )
                
                # Update document status
                document_record.status = 'failed'
                document_record.error = str(e)
                document_record.save()
                
                return {
                    "success": False,
                    "error": str(e),
                    "document_id": str(document_record.id),
                    "result_id": str(result_record.id)
                }
        except Exception as e:
            logger.error(f"Error processing PDF with Gemini: {str(e)}", exc_info=True)
            # Update job status with error
            job.processing_details = f"Error processing document: {document_record.filename} - {str(e)[:100]}"
            job.save()
            
            # Update document status with error
            document_record.status = 'failed'
            document_record.error = str(e)
            document_record.save()
            
            return {
                "success": False,
                "error": str(e),
                "document_id": str(document_record.id),
                "result_id": None
            }

class AddColumnView(CreateView):
    """View for adding a new column definition"""
    model = ColumnDefinition
    form_class = ColumnDefinitionForm
    template_name = 'column_form.html'
    success_url = reverse_lazy('core:columns')

class EditColumnView(UpdateView):
    """View for editing a column definition"""
    model = ColumnDefinition
    form_class = ColumnDefinitionForm
    template_name = 'column_form.html'
    success_url = reverse_lazy('core:columns')

@require_POST
def apply_default_columns(request):
    """Apply default column definitions"""
    try:
        # Clear existing columns
        ColumnDefinition.objects.all().delete()
        
        # Define default columns
        default_columns = [
            # Demographics
            {'name': 'case_number', 'description': 'Unique identifier for the case', 'category': 'demographics', 'order': 1},
            {'name': 'gender', 'description': 'Patient gender (M/F)', 'category': 'demographics', 'order': 2},
            {'name': 'age', 'description': 'Patient age in years', 'category': 'demographics', 'order': 3},
            
            # Clinical
            {'name': 'symptoms', 'description': 'Primary symptoms reported', 'category': 'clinical', 'order': 1},
            {'name': 'duration', 'description': 'Duration of symptoms', 'category': 'clinical', 'order': 2},
            {'name': 'comorbidities', 'description': 'Existing medical conditions', 'category': 'clinical', 'order': 3},
            
            # Pathology
            {'name': 'pathology', 'description': 'Primary pathological diagnosis', 'category': 'pathology', 'order': 1},
            {'name': 'staging', 'description': 'Disease staging if applicable', 'category': 'pathology', 'order': 2},
            {'name': 'histology', 'description': 'Histological findings', 'category': 'pathology', 'order': 3},
            
            # Treatment
            {'name': 'treatment', 'description': 'Treatment approach', 'category': 'treatment', 'order': 1},
            {'name': 'medication', 'description': 'Medications administered', 'category': 'treatment', 'order': 2},
            {'name': 'surgery', 'description': 'Surgical procedures if any', 'category': 'treatment', 'order': 3},
            
            # Outcome
            {'name': 'outcome', 'description': 'Patient outcome', 'category': 'outcome', 'order': 1},
            {'name': 'follow_up', 'description': 'Follow-up period', 'category': 'outcome', 'order': 2},
            {'name': 'complications', 'description': 'Complications if any', 'category': 'outcome', 'order': 3},
        ]
        
        # Create default columns
        for col_data in default_columns:
            ColumnDefinition.objects.create(
                name=col_data['name'],
                description=col_data['description'],
                category=col_data['category'],
                order=col_data['order'],
                include_confidence=True
            )
        
        return JsonResponse({
            'success': True, 
            'message': f'Successfully created {len(default_columns)} default columns'
        })
        
    except Exception as e:
        logger.error(f"Error applying default columns: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

class EditPromptView(UpdateView):
    """View for editing a saved prompt"""
    model = SavedPrompt
    fields = ['name', 'content', 'variables']
    template_name = 'prompt_form.html'
    success_url = reverse_lazy('core:prompts')

@require_GET
def get_prompt(request, pk):
    """Get a specific prompt by ID"""
    try:
        prompt = get_object_or_404(SavedPrompt, pk=pk)
        return JsonResponse({
            'success': True,
            'prompt': {
                'id': prompt.id,
                'name': prompt.name,
                'content': prompt.content,
                'variables': prompt.variables
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=404)

@require_GET
def list_prompts(request):
    """List all saved prompts"""
    prompts = SavedPrompt.objects.all().order_by('-created_at')
    prompt_list = [{
        'id': p.id,
        'name': p.name,
        'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for p in prompts]
    return JsonResponse({'prompts': prompt_list})

@require_POST
def save_prompt(request):
    """Save a prompt"""
    try:
        data = json.loads(request.body)
        name = data.get('name', 'Untitled Prompt')
        content = data.get('content')
        variables = data.get('variables', {})
        
        if not content:
            return JsonResponse({
                'success': False,
                'error': 'Prompt content is required'
            }, status=400)
        
        prompt_id = data.get('id')
        if prompt_id:
            # Update existing
            prompt = get_object_or_404(SavedPrompt, id=prompt_id)
            prompt.name = name
            prompt.content = content
            prompt.variables = variables
            prompt.save()
        else:
            # Create new
            prompt = SavedPrompt.objects.create(
                name=name,
                content=content,
                variables=variables
            )
        
        return JsonResponse({
            'success': True,
            'prompt_id': prompt.id
        })
    except Exception as e:
        logger.error(f"Error saving prompt: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_GET
def load_prompts(request):
    """Load all prompts for the dropdown"""
    prompts = SavedPrompt.objects.all().order_by('-created_at')
    return JsonResponse({
        'prompts': [{'id': p.id, 'name': p.name} for p in prompts]
    })

@require_GET
def get_default_prompt(request):
    """Get the default prompt"""
    latest_prompt = SavedPrompt.objects.order_by('-created_at').first()
    if latest_prompt:
        return JsonResponse({
            'success': True,
            'prompt': latest_prompt.content
        })
    else:
        return JsonResponse({
            'success': True,
            'prompt': TEXT_EXTRACTION_PROMPT
        })

def manage_prompt(request, prompt_id):
    """View for managing a specific prompt"""
    prompt = get_object_or_404(SavedPrompt, id=prompt_id)
    
    if request.method == 'GET':
        # Return prompt details in JSON format for editing
        return JsonResponse({
            'id': prompt.id,
            'name': prompt.name,
            'content': prompt.content,
            'variables': prompt.variables
        })
    elif request.method == 'POST':
        # Update prompt with submitted data
        try:
            data = json.loads(request.body)
            prompt.name = data.get('name', prompt.name)
            prompt.content = data.get('content', prompt.content)
            prompt.variables = data.get('variables', {})
            prompt.save()
            return JsonResponse({
                'success': True,
                'prompt_id': prompt.id,
                'message': f"Prompt '{prompt.name}' updated successfully"
            })
        except Exception as e:
            logger.error(f"Error updating prompt: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False, 
                'error': str(e)
            }, status=400)
    elif request.method == 'DELETE':
        # Delete the prompt
        try:
            prompt_name = prompt.name
            prompt.delete()
            return JsonResponse({
                'success': True,
                'message': f"Prompt '{prompt_name}' deleted successfully"
            })
        except Exception as e:
            logger.error(f"Error deleting prompt: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    # Fallback for other HTTP methods
    return JsonResponse({
        'success': False,
        'error': 'Unsupported HTTP method'
    }, status=405)

@require_GET
def download_raw_markdown(request, result_id):
    """Download raw response as markdown"""
    try:
        result = get_object_or_404(ProcessingResult, id=result_id)
        response = HttpResponse(result.raw_response, content_type='text/markdown')
        response['Content-Disposition'] = f'attachment; filename="result_{result_id}.md"'
        return response
    except Exception as e:
        logger.error(f"Error downloading markdown: {str(e)}", exc_info=True)
        return HttpResponse(f"Error: {str(e)}", status=500)

class JsonResponseDetailView(DetailView):
    """View for displaying JSON response"""
    model = ProcessingResult
    template_name = 'json_detail.html'
    context_object_name = 'result'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object
        
        context['json_formatted'] = json.dumps(result.json_result, indent=2)
        return context

class DownloadResultsView(View):
    """View for downloading job results in different formats"""
    
    def get(self, request, job_id, format):
        job = get_object_or_404(ProcessingJob, id=job_id)
        
        if job.job_type == 'reference_extraction':
            # Handle reference extraction jobs
            references = Reference.objects.filter(job=job)
            if not references.exists():
                return HttpResponse("No reference data available for download", status=404)
            
            # Define fields to include in the export
            fields = [
                'id', 'document__filename', 'citation_text', 'source_type', 'authors',
                'title', 'source_name', 'publication_year', 'volume', 'issue', 'pages',
                'doi_or_url', 'confidence', 'reference_index'
            ]
            # Convert queryset to a list of dictionaries
            data = list(references.values(*fields))
            
            # Rename document__filename to document_filename for clarity
            for item in data:
                item['document_filename'] = item.pop('document__filename')
            
            df = pd.DataFrame(data)
            # Reorder columns to put reference_index near the beginning
            if 'reference_index' in df.columns:
                cols = df.columns.tolist()
                cols.insert(cols.index('document_filename') + 1, cols.pop(cols.index('reference_index')))
                df = df[cols]
            
            # Clean up DataFrame
            df = df.replace({np.nan: '', None: '', 'null': '', 'None': ''})
            
        else:
            # Handle case extraction jobs (existing logic)
            results = ProcessingResult.objects.filter(document__job=job)
            all_cases = []
            for result in results:
                if result.json_result and 'case_results' in result.json_result:
                    for case in result.json_result['case_results']:
                        case['document_filename'] = {
                            'value': result.document.filename,
                            'confidence': 100
                        }
                        case['study_author'] = {
                            'value': result.document.study_author or 'Unknown',
                            'confidence': 100
                        }
                    all_cases.extend(result.json_result['case_results'])
            
            # Apply post-processing filter to remove cited cases before download
            from .utils import filter_cited_cases
            combined_results = {'case_results': all_cases}
            filtered_combined = filter_cited_cases(combined_results)
            
            if 'filtering_metadata' in filtered_combined and filtered_combined['filtering_metadata']['excluded_case_count'] > 0:
                excluded_count = filtered_combined['filtering_metadata']['excluded_case_count']
                filtered_count = filtered_combined['filtering_metadata']['filtered_case_count']
                logger.info(f"DownloadResultsView: Filtered out {excluded_count} cited cases. Download will contain {filtered_count} primary cases.")
                all_cases = filtered_combined['case_results']
            
            if not all_cases:
                return HttpResponse("No case data available for download", status=404)
            
            # Create a dataframe from the cases
            df_data = {}
            all_fields = set()
            for case in all_cases:
                for field_key, field_data in case.items():
                    if isinstance(field_data, dict) and 'value' in field_data:
                        all_fields.add(field_key)
                        if 'confidence' in field_data:
                            all_fields.add(f"{field_key}_confidence")
            
            for field in all_fields:
                df_data[field] = []
            
            for case in all_cases:
                for field in all_fields:
                    if field.endswith('_confidence'):
                        base_field = field[:-11]
                        if base_field in case and isinstance(case[base_field], dict) and 'confidence' in case[base_field]:
                            df_data[field].append(case[base_field]['confidence'])
                        else:
                            df_data[field].append(100)
                    else:
                        if field in case and isinstance(case[field], dict) and 'value' in case[field]:
                            df_data[field].append(case[field]['value'])
                        else:
                            df_data[field].append('')
            
            lengths = [len(values) for values in df_data.values()]
            if len(set(lengths)) > 1:
                logger.error(f"Inconsistent array lengths in DataFrame: {lengths}")
                min_length = min(lengths)
                for field, values in df_data.items():
                    if len(values) > min_length:
                        df_data[field] = values[:min_length]
            
            df = pd.DataFrame(df_data)
            df = df.replace({np.nan: '', None: '', 'null': '', 'None': ''})

        # Generate response based on format
        if format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename=\"job_{job_id}_{job.job_type}_results.csv\"'
            df.to_csv(response, index=False)
            
        elif format == 'xlsx':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=\"job_{job_id}_{job.job_type}_results.xlsx\"'
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            output.seek(0)
            response.write(output.getvalue())
            
        elif format == 'json':
            response = HttpResponse(content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename=\"job_{job_id}_{job.job_type}_results.json\"'
            
            if job.job_type == 'reference_extraction':
                # Dump list of dicts directly for references
                json.dump(df.to_dict('records'), response, indent=2)
            else:
                # Keep original structure for case extraction
                cases_json = []
                for _, row in df.iterrows():
                    case = {}
                    for col in df.columns:
                        if not col.endswith('_confidence'):
                            confidence_col = f"{col}_confidence"
                            case[col] = {
                                'value': row[col],
                                'confidence': float(row[confidence_col]) if confidence_col in df.columns and pd.notna(row[confidence_col]) else 100
                            }
                    cases_json.append(case)
                json.dump({'case_results': cases_json}, response, indent=2)
            
        else:
            return HttpResponse(f"Unsupported format: {format}", status=400)
        
        return response

@require_GET
def test_api(request):
    """Test API endpoint"""
    try:
        # Test Gemini API
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'GEMINI_API_KEY not found in environment variables'
            })
        
        # Configure genai
        genai.configure(api_key=api_key)
        
        # Create a simple test prompt
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        response = model.generate_content("Respond with 'API connection successful' if you can read this message.")
        
        return JsonResponse({
            'success': True,
            'response': response.text,
        })
    except Exception as e:
        logger.error(f"API test error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_GET
def test_gemini(request):
    """Test Gemini PDF processing capabilities"""
    try:
        # Check if API key is available
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'GEMINI_API_KEY not found in environment variables'
            })
        
        # Configure genai
        genai.configure(api_key=api_key)
        
        # Create a simple test prompt
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        response = model.generate_content("Generate a sample JSON with 3 medical cases in the following structure: { 'case_results': [ {'case_number': {'value': '1', 'confidence': 100}, 'gender': {'value': 'M', 'confidence': 100}, 'age': {'value': '45', 'confidence': 100}, 'pathology': {'value': 'Example', 'confidence': 100}}, ... ] }")
        
        return JsonResponse({
            'success': True,
            'response': response.text,
        })
    except Exception as e:
        logger.error(f"Gemini test error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@method_decorator(csrf_exempt, name='dispatch')
class ContinueProcessingView(View):
    """View to continue processing a document that has truncated results."""
    
    def post(self, request, document_id):
        try:
            # Get the document and its latest result
            document = get_object_or_404(PDFDocument, id=document_id)
            latest_result = document.results.order_by('-continuation_number').first()
            
            if not latest_result:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No previous processing results found for this document'
                }, status=400)
                
            if latest_result.is_complete:
                return JsonResponse({
                    'status': 'error',
                    'message': 'This document already has complete results'
                }, status=400)
                
            # Read the PDF file
            with open(document.file.path, 'rb') as file:
                pdf_content = file.read()
                
            # Encode the PDF content as base64
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # Get the job's prompt
            job = document.job
            prompt_text = job.prompt.text if job.prompt else "Please analyze this PDF document and extract all relevant information."
            
            # Prepare the continuation prompt
            continuation_prompt = prepare_continuation_prompt(
                original_prompt=prompt_text,
                previous_response=latest_result.raw_result
            )
            
            # Call the Gemini API
            api_response = call_gemini_with_pdf(pdf_base64, continuation_prompt)
            
            if 'error' in api_response:
                # Save the error
                new_result = ProcessingResult.objects.create(
                    document=document,
                    error=api_response.get('error'),
                    raw_result=api_response.get('raw_response', ''),
                    continuation_number=latest_result.continuation_number + 1,
                    is_complete=False
                )
                
                document.status = 'error'
                document.error = api_response.get('error')
                document.save()
                
                return JsonResponse({
                    'status': 'error',
                    'message': api_response.get('error')
                }, status=500)
                
            # Get the text response
            response_text = api_response.get('text', '')
            
            # Check if the response is truncated
            is_complete = not is_response_truncated(response_text)
            
            # Extract JSON from the text
            json_data = extract_json_from_text(response_text)
            
            # Save the new result
            new_result = ProcessingResult.objects.create(
                document=document,
                json_result=json_data,
                raw_result=response_text,
                continuation_number=latest_result.continuation_number + 1,
                is_complete=is_complete
            )
            
            # Update document status
            document.status = 'complete' if is_complete else 'processed'
            document.save()
            
            # Return success response
            return JsonResponse({
                'status': 'success',
                'message': 'Document processing continued successfully',
                'is_complete': is_complete,
                'result_id': str(new_result.id)
            })
            
        except Exception as e:
            logger.error(f"Error continuing processing: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f"Error continuing processing: {str(e)}"
            }, status=500)

    def _process_continuation(self, model, model_input, continuation_document, last_case_number):
        """Process a document continuation in a background thread"""
        job = continuation_document.job
        
        try:
            # Log the processing start
            logger.info(f"Starting continuation processing for job {job.id}, document {continuation_document.id}")
            
            # Update job status to reflect continuation
            job.status = 'processing'
            job.processing_details = f"Continuing processing for document: {continuation_document.filename} from case {last_case_number}"
            job.save()
            
            # Call the model with enhanced generation config
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=8192,  # Set a high token limit
                temperature=0.3,  # Lower temperature for more deterministic outputs
            )
            
            # Set safety settings to minimize content filtering
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Update job status to show we're waiting for response
            job.processing_details = f"Waiting for Gemini to continue analyzing document: {continuation_document.filename} from case {last_case_number}"
            job.save()
            
            # Add the generation config to the model call with streaming
            response = model.generate_content(
                model_input,
                generation_config=generation_config,
                safety_settings=safety_settings,
                stream=True
            )
            
            # Process streaming response
            raw_response = ""
            case_count = last_case_number
            
            for chunk in response:
                if hasattr(chunk, 'text'):
                    raw_response += chunk.text
                    
                    # Check for case numbers in this chunk
                    chunk_text = chunk.text.lower()
                    case_matches = re.findall(r'case_number.*?value.*?(?:patient|case)\s*(\d+)', chunk_text)
                    
                    if case_matches:
                        # Get the highest case number found
                        try:
                            new_cases = [int(x) for x in case_matches if x.isdigit()]
                            if new_cases:
                                highest_case = max(new_cases)
                                if highest_case > case_count:
                                    case_count = highest_case
                                    # Update job status with the current case
                                    job.processing_details = f"Continuing document: {continuation_document.filename} - Extracting case {case_count}"
                                    job.save()
                        except ValueError:
                            pass
            
            # Get the finish reason (for detecting truncation)
            finish_reason = None
            is_truncated = False
            if hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                finish_reason = response.candidates[0].finish_reason
                logger.info(f"Response finish reason: {finish_reason}")
                # Check if truncated
                if finish_reason == 'MAX_TOKENS':
                    is_truncated = True
                    logger.warning("Response was truncated (MAX_TOKENS)")
            
            # Log the raw response
            logger.info(f"Received raw continuation response of length {len(raw_response)}")
            
            # Update job status to show we're extracting JSON
            job.processing_details = f"Extracting JSON data from continuation response for document: {continuation_document.filename}"
            job.save()
            
            # Extract JSON from the response with error handling
            try:
                # Parse the response JSON
                result_data = extract_json_from_text(raw_response)
                
                # Log information about extracted JSON
                if result_data and isinstance(result_data, dict) and 'case_results' in result_data:
                    extracted_cases = len(result_data['case_results'])
                    logger.info(f"Successfully extracted JSON with {extracted_cases} new cases from continuation")
                    
                    # Update job status with case counts
                    job.processing_details = f"Extracted {extracted_cases} additional cases (up to case {case_count}) from document: {continuation_document.filename}"
                    job.save()
                    
                    # Apply post-processing filter to remove cited cases
                    from .utils import filter_cited_cases
                    original_count = extracted_cases
                    
                    # Add defensive handling for filter_cited_cases
                    try:
                        filtered_data = filter_cited_cases(result_data)
                        
                        # Verify the returned structure is as expected
                        if isinstance(filtered_data, dict) and 'case_results' in filtered_data:
                            result_data = filtered_data
                            new_count = len(result_data['case_results'])
                            
                            if new_count < original_count:
                                logger.info(f"Filtered out {original_count - new_count} cited cases")
                                print(f"Filtered out {original_count - new_count} cited cases")
                        else:
                            # If filter_cited_cases returns unexpected structure, log and use original
                            logger.warning(f"filter_cited_cases returned unexpected structure: {type(filtered_data)}")
                            print(f"WARNING: filter_cited_cases returned unexpected structure, using original data")
                            new_count = original_count
                    except Exception as filter_err:
                        # Log error but continue with original data
                        logger.error(f"Error in filter_cited_cases: {str(filter_err)}", exc_info=True)
                        print(f"Error filtering cited cases: {str(filter_err)}")
                        new_count = original_count
                else:
                    logger.warning("Extracted JSON does not contain case_results")
                    job.processing_details = f"No valid cases extracted from continuation for document: {continuation_document.filename}"
                    job.save()
            except Exception as json_err:
                # Handle JSON extraction errors
                logger.error(f"Error extracting JSON from continuation response: {str(json_err)}", exc_info=True)
                
                # Create an error result but preserve the raw response
                result_data = {
                    "error": f"Failed to parse JSON from continuation response: {str(json_err)}",
                    "is_truncated": is_truncated
                }
                
                job.processing_details = f"Error extracting JSON from continuation response for document: {continuation_document.filename}"
                job.save()
            
            # Create a new processing result for the continuation
            result = ProcessingResult.objects.create(
                document=continuation_document,
                json_result=result_data,
                raw_result=raw_response,
                is_complete=not is_truncated
            )
            
            # Update the document status
            continuation_document.status = 'complete' if not is_truncated else 'processed'
            if 'error' in result_data:
                continuation_document.status = 'error'
            continuation_document.save()
            
            # Check how many cases were processed
            cases_count = 0
            if 'case_results' in result_data and isinstance(result_data['case_results'], list):
                cases_count = len(result_data['case_results'])
            
            # Log completion status
            if 'error' in result_data:
                logger.error(f"Continuation processing encountered errors for job {job.id}, document {continuation_document.id}: {result_data['error']}")
                # If the job status isn't already failed, update it
                if job.status != 'failed':
                    job.status = 'processing_with_errors'
                    job.error_message = result_data['error']
                    job.processing_details = f"Error processing continuation for document: {continuation_document.filename}"
            else:
                # Log successful completion
                logger.info(f"Continuation processing complete for job {job.id}, document {continuation_document.id}, extracted {cases_count} additional cases")
                
                # Update job status if appropriate
                if ProcessingResult.objects.filter(document__job=job, is_complete=False).count() == 0:
                    # All documents processed
                    if ProcessingResult.objects.filter(document__job=job, document__status='error').exists():
                        job.status = 'completed_with_errors'
                    else:
                        job.status = 'completed'
                    job.error_message = ""
                    job.processing_details = f"Completed processing all documents with {job.get_total_case_count()} total cases"
                else:
                    # Some documents still need processing
                    job.status = 'processing'
                    job.error_message = ""
                    job.processing_details = f"Completed continuation for document: {continuation_document.filename}, still processing other documents"
            
            job.save()
            logger.info(f"Job {job.id} updated with status: {job.status}")
            
            return {"success": True, "is_truncated": is_truncated}
        
        except Exception as e:
            # Log the error
            error_message = f"Error in continuation processing: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Update document and job status
            continuation_document.status = 'error'
            continuation_document.save()
            
            # Only update job status if it's not already failed
            if job.status != 'failed':
                job.status = 'processing_with_errors'
                job.error_message = error_message
                job.processing_details = f"Error in continuation processing for document: {continuation_document.filename}"
                job.save()
            
            return {"success": False, "error": str(e)}

def login_view(request):
    """Basic login view for authentication"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirect to the requested next page or default to home
            next_url = request.GET.get('next', 'core:processor')
            return redirect(next_url)
        else:
            # Return an error message
            context = {'error': 'Invalid username or password'}
            return render(request, 'login.html', context)
            
    return render(request, 'login.html')

class CaseReportGeneratorView(FormView):
    """View for generating case reports using AI"""
    template_name = 'core/case_report_generator.html'
    form_class = CaseReportForm
    success_url = None  # Will be set dynamically in form_valid
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'AI Case Report Generator'
        context['subtitle'] = 'Generate a draft case report from de-identified patient data'
        
        # If we have a saved case report ID in the session, try to load it
        if self.request.session.get('case_report_id'):
            try:
                case_report = CaseReport.objects.get(id=self.request.session['case_report_id'])
                context['case_report'] = case_report
                context['research_prompt'] = case_report.research_prompt
                context['research_response'] = case_report.research_response
                context['draft_prompt'] = case_report.draft_prompt
                context['draft_response'] = case_report.draft_response
            except CaseReport.DoesNotExist:
                # Clear the session variable if the report doesn't exist
                self.request.session.pop('case_report_id', None)
        
        return context
    
    def form_valid(self, form):
        from .services.perplexity_client import PerplexityClient
        from .services.gemini_client import GeminiClient
        import logging
        import uuid
        
        logger = logging.getLogger(__name__)
        
        # Create a new CaseReport instance
        case_report = CaseReport(
            name=form.cleaned_data['name'],
            patient_age=form.cleaned_data['patient_age'],
            patient_gender=form.cleaned_data['patient_gender'],
            suspected_condition=form.cleaned_data['suspected_condition'],
            key_findings_summary=form.cleaned_data['key_findings_summary'],
            additional_instructions=form.cleaned_data['additional_instructions'],
            status='pending'
        )
        
        # Save PDFs if provided
        pdf_fields = [
            'patient_history_pdf', 
            'clinical_findings_pdf', 
            'lab_results_pdf', 
            'imaging_reports_pdf', 
            'treatment_summary_pdf'
        ]
        
        for field_name in pdf_fields:
            pdf_file = form.cleaned_data.get(field_name)
            if pdf_file:
                # Set the file on the model
                setattr(case_report, field_name, pdf_file)
        
        # Save the case report to get an ID
        case_report.save()
        
        # Save the ID in the session
        self.request.session['case_report_id'] = str(case_report.id)
        
        # Initialize our API clients
        perplexity_client = PerplexityClient()
        gemini_client = GeminiClient()
        
        # Extract text from PDFs
        pdf_texts = {}
        for field_name in pdf_fields:
            pdf_file = getattr(case_report, field_name, None)
            if pdf_file and pdf_file.name:
                # Get the file field's label for display
                label = form.fields[field_name].label
                pdf_field_file = pdf_file.file if hasattr(pdf_file, 'file') else pdf_file
                pdf_texts[label] = gemini_client.extract_text_from_pdf(pdf_field_file)
        
        # Generate research with Perplexity if a condition is specified
        research_text = None
        if case_report.suspected_condition:
            try:
                case_report.status = 'researching'
                case_report.save()
                
                # Create the context dictionary for the research prompt
                context_dict = {
                    'patient_age': case_report.patient_age,
                    'patient_gender': case_report.patient_gender,
                    'key_findings_summary': case_report.key_findings_summary,
                    'additional_instructions': case_report.additional_instructions
                }
                
                # Generate the research prompt
                research_prompt = perplexity_client.generate_research_prompt(
                    case_report.suspected_condition, 
                    context_dict
                )
                case_report.research_prompt = research_prompt
                case_report.save()
                
                # Get research from Perplexity
                research_response = perplexity_client.research(research_prompt)
                research_text = perplexity_client.extract_research_text(research_response)
                case_report.research_response = research_text
                case_report.save()
                
            except Exception as e:
                logger.error(f"Error generating research: {str(e)}")
                case_report.error_message = f"Research error: {str(e)}"
                case_report.status = 'failed'
                case_report.save()
                
                # Continue with draft generation even if research fails
        
        # Generate the draft with Gemini
        try:
            case_report.status = 'drafting'
            case_report.save()
            
            # Prepare the text data
            text_data = {
                'patient_age': case_report.patient_age,
                'patient_gender': case_report.patient_gender,
                'suspected_condition': case_report.suspected_condition,
                'key_findings_summary': case_report.key_findings_summary,
                'additional_instructions': case_report.additional_instructions
            }
            
            # Construct the generation prompt
            draft_prompt = gemini_client.construct_generation_prompt(
                text_data, 
                pdf_texts, 
                research_text
            )
            case_report.draft_prompt = draft_prompt
            case_report.save()
            
            # Generate the draft
            draft_text = gemini_client.generate_draft(draft_prompt)
            case_report.draft_response = draft_text
            
            # Mark as completed
            case_report.status = 'completed'
            case_report.save()
            
        except Exception as e:
            logger.error(f"Error generating draft: {str(e)}")
            case_report.error_message = f"Draft generation error: {str(e)}"
            case_report.status = 'failed'
            case_report.save()
        
        # Get the updated context data with the generation results
        context = self.get_context_data(form=form)
        
        # Render the template with the results
        return self.render_to_response(context)
    
    def get_success_url(self):
        return self.request.path  # Return to the same page

def _process_pdf_with_gemini(job, pdf_data):
    """
    Process a PDF using Gemini with vision capabilities and structured output.
    
    Args:
        job: ProcessingJob instance
        pdf_data: Binary PDF data
        
    Returns:
        dict: Processing results
    """
    from .utils import generate_gemini_json_schema
    
    # Load Gemini API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    # Configure the model
    genai.configure(api_key=api_key)
    
    # Select the model based on job configuration
    model_name = job.model_name or "gemini-2.5-flash-preview-04-17"
    if model_name not in ["gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash-preview-04-17"]:
        logger.warning(f"Unsupported model {model_name}, falling back to gemini-2.5-flash-preview-04-17")
        model_name = "gemini-2.5-flash-preview-04-17"
    
    model = genai.GenerativeModel(model_name)
    
    # Generate the JSON schema for structured output
    output_schema = generate_gemini_json_schema(job)
    
    # Prepare the document for processing
    try:
        # Convert PDF data to base64
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
        
        # Create the prompt with structured output instructions
        prompt = f"""
        You are an AI assistant tasked with extracting information from medical documents.
        Please analyze the provided PDF document and extract the following information in a structured format.
        
        For each case found in the document:
        1. Extract all relevant fields according to the schema
        2. Provide a confidence score (0-100) for each extracted field
        3. Ensure all required fields are present
        4. Format dates as ISO 8601 strings (YYYY-MM-DD)
        5. Use null for missing optional fields
        
        The output must strictly follow the provided JSON schema.
        """
        
        # Update job status
        job.status = 'processing'
        job.current_stage = 'Analyzing document with Gemini'
        job.save()
        
        # Log the prompt
        logger.info(f"Sending prompt to Gemini for job {job.id}")
        
        # Generate content with structured output
        response = model.generate_content(
            contents=[
                prompt,
                {"mime_type": "application/pdf", "data": pdf_base64}
            ],
            generation_config={
                "max_output_tokens": 8192,
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40
            },
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ],
            stream=False,
            tools=[{
                "function_declarations": [{
                    "name": "extract_cases",
                    "description": "Extract case information from the document",
                    "parameters": output_schema
                }]
            }]
        )
        
        # Check for response
        if not response or not response.text:
            raise ValueError("Empty response from Gemini")
        
        # Log the raw response
        logger.info(f"Raw Gemini response for job {job.id}: {response.text}")
        
        # Extract JSON from the response
        try:
            # The response should be in JSON format due to structured output
            result_data = json.loads(response.text)
            
            # Validate the response structure
            if 'case_results' not in result_data:
                raise ValueError("Response missing 'case_results' field")
            
            # Log the number of cases extracted
            logger.info(f"Extracted {len(result_data['case_results'])} cases from job {job.id}")
            
            # Filter out cited cases if needed
            if job.filter_cited_cases:
                from .utils import filter_cited_cases
                result_data['case_results'] = filter_cited_cases(result_data['case_results'])
                logger.info(f"Filtered to {len(result_data['case_results'])} cases after removing cited cases")
            
            # Create ProcessingResult
            processing_result = ProcessingResult.objects.create(
                job=job,
                raw_result=response.text,
                json_result=json.dumps(result_data),
                is_truncated=False
            )
            
            # Update job status
            job.status = 'completed'
            job.current_stage = 'Processing complete'
            job.save()
            
            return {
                'success': True,
                'result': processing_result,
                'cases': result_data['case_results']
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON for job {job.id}: {str(e)}")
            # Try to clean the response and extract JSON
            cleaned_text = response.text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            
            try:
                result_data = json.loads(cleaned_text)
                # Process the cleaned result as above
                # ... (rest of the processing code)
            except json.JSONDecodeError:
                raise ValueError("Failed to parse Gemini response as JSON after cleaning")
    
    except Exception as e:
        logger.error(f"Error processing PDF with Gemini for job {job.id}: {str(e)}")
        job.status = 'failed'
        job.error_message = str(e)
        job.save()
        raise

@require_GET
def test_gemini_structured_output(request):
    """
    Test endpoint to verify Gemini's structured output functionality.
    Tests both schema generation and response parsing.
    """
    try:
        # Create a test job with some columns
        from .models import ProcessingJob, ColumnDefinition, JobColumnMapping
        
        # Create test columns if they don't exist
        test_columns = [
            ('case_number', 'string', False),
            ('patient_age', 'integer', True),
            ('diagnosis', 'string', False),
            ('treatment_date', 'date', True),
            ('outcome', 'enum', False, ['positive', 'negative', 'neutral'])
        ]
        
        columns = []
        for name, data_type, optional, *args in test_columns:
            col, created = ColumnDefinition.objects.get_or_create(
                name=name,
                defaults={
                    'data_type': data_type,
                    'optional': optional,
                    'description': f'Test column for {name}'
                }
            )
            if len(args) > 0:
                col.enum_values = args[0]
                col.save()
            columns.append(col)
        
        # Create a test job
        job = ProcessingJob.objects.create(
            name="Test Structured Output",
            status='pending',
            model_name='gemini-2.5-flash-preview-04-17'
        )
        
        # Create column mappings
        for i, col in enumerate(columns):
            JobColumnMapping.objects.create(
                job=job,
                column=col,
                order=i
            )
        
        # Generate the schema
        from .utils import generate_gemini_json_schema
        schema = generate_gemini_json_schema(job)
        
        # Test the schema structure
        schema_validation = {
            'has_case_results': 'case_results' in schema.get('properties', {}),
            'has_items': 'items' in schema.get('properties', {}).get('case_results', {}),
            'has_required': 'required' in schema,
            'column_count': len(schema.get('properties', {}).get('case_results', {}).get('items', {}).get('properties', {}))
        }
        
        # Test with a simple PDF
        import base64
        from pathlib import Path
        
        # Create a simple test PDF
        test_pdf_path = Path(__file__).parent / 'static' / 'test.pdf'
        if not test_pdf_path.exists():
            # Create a minimal PDF for testing
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(str(test_pdf_path))
            c.drawString(100, 750, "Test Patient Case")
            c.drawString(100, 730, "Case Number: 1")
            c.drawString(100, 710, "Age: 45")
            c.drawString(100, 690, "Diagnosis: Test Condition")
            c.drawString(100, 670, "Treatment Date: 2024-03-20")
            c.drawString(100, 650, "Outcome: positive")
            c.save()
        
        # Read the test PDF
        with open(test_pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Process with Gemini
        result = _process_pdf_with_gemini(job, pdf_data)
        
        # Validate the response
        response_validation = {
            'success': result.get('success', False),
            'has_cases': bool(result.get('cases', [])),
            'case_count': len(result.get('cases', [])),
            'has_required_fields': all(
                'case_number' in case and 'value' in case['case_number']
                for case in result.get('cases', [])
            )
        }
        
        # Clean up test data
        job.delete()
        for col in columns:
            if not JobColumnMapping.objects.filter(column=col).exists():
                col.delete()
        
        return JsonResponse({
            'success': True,
            'schema_validation': schema_validation,
            'response_validation': response_validation,
            'schema': schema,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error testing Gemini structured output: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_POST
def load_schema_from_file(request):
    """
    Load extraction schema from a file and create column definitions.
    Similar to the management command but available via web interface.
    """
    try:
        # Get file path from request, or use default
        data = json.loads(request.body) if request.body else {}
        file_path = data.get('file_path', 
            '/Users/chrisjanssen/Insync/cnjanssen@tamu.edu/Google Drive/COM/Research/human_vs_llm/human_reviewer_django/extraction_schema_dump.json')
        
        clear_existing = data.get('clear_existing', False)
        
        if not os.path.exists(file_path):
            return JsonResponse({
                'success': False,
                'error': f'File not found: {file_path}'
            }, status=404)
        
        # Clear existing columns if requested
        if clear_existing:
            ColumnDefinition.objects.all().delete()
            logger.info("Cleared existing column definitions")
        
        # Load the schema file - similar to the management command
        with open(file_path, 'r') as f:
            # The file might be a list of objects or just a JSON object
            try:
                # First try to read as JSON array with objects
                data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
            except json.JSONDecodeError:
                # If that fails, try to read line by line
                f.seek(0)
                data = []
                for line in f:
                    try:
                        obj = json.loads(line.strip())
                        data.append(obj)
                    except json.JSONDecodeError:
                        continue
        
        # Category mappings based on field descriptions and contexts
        category_mappings = {
            # Presenting Symptoms
            'loss_of_bladder_control': 'presentation',
            'parasthesia': 'presentation',
            'neruopathyradiculopathy': 'presentation',
            'mass': 'presentation',
            'headache': 'presentation',
            'ue_pain': 'presentation',
            'ue_weakness': 'presentation',
            'le_weakness': 'presentation',
            'tetraparesis': 'presentation',
            'neck_pain': 'presentation',
            'facial_pain': 'presentation',
            'gait_disturbance': 'presentation',
            'nausea': 'presentation',
            'duration_of_symptoms_in_months': 'clinical',
            
            # Co-morbidities
            'co_morbidities': 'symptoms',
            'spastiicty': 'symptoms',
            'muscle_atrophy': 'symptoms',
            'proptosis_1': 'symptoms',
            'visual_deficits': 'symptoms',
            'abnormal_reflexes': 'symptoms',
            'sensory_deficits': 'symptoms',
            'ue_weakness_1': 'symptoms',
            'le_weakness_1': 'symptoms',
            'hemiparesis': 'symptoms',
            'hyperreflexia': 'symptoms',
            'hoffman': 'symptoms',
            'babinski': 'symptoms',
            
            # Imaging
            'imaging_modalities_for_workup': 'imaging',
            'cranial_vs_spinal': 'imaging',
            'location': 'imaging',
            'level': 'imaging',
            'single_vs_multi': 'imaging',
            'contrast_enhancment_pattern': 'imaging',
            'adjacent_bone': 'imaging',
            'bone_yesno': 'imaging',
            'invasion_of': 'imaging',
            'invasion_yn': 'imaging',
            'location_of_invasion': 'imaging',
            'intradural_extension': 'imaging',
            'intradural_compnent': 'imaging',
            'post_op_imaging': 'imaging',
            
            # Workup
            'preoperation_biopsy': 'workup',
            
            # Treatment
            'neoadjuvant_therapy_yn': 'treatment',
            'if_yes_what_kind_chemo_radiation_both': 'treatment',
            'surgery_type': 'treatment',
            'surgical_approach': 'treatment',
            'resection_amount': 'treatment',
            'adjuvant_therapy_yn': 'treatment',
            'what_therapy_chemo_radiation_both_srs_etc': 'treatment',
            
            # Post-op
            'surgical_complications': 'postop',
            'postop_complications': 'postop',
            'residual': 'postop',
            
            # Pathology/IHC staining
            'ema': 'pathology',
            'vimentin': 'pathology',
            'ck': 'pathology',
            'progesterone': 'pathology',
            'sstr2': 'pathology',
            'cd99': 'pathology',
            'cd34': 'pathology',
            'ck_1': 'pathology',
            'sox10': 'pathology',
            's100': 'pathology',
            'gfap': 'pathology',
            'vimentin_1': 'pathology',
            'ki67': 'pathology',
            'who_grade': 'pathology',
            'subtype': 'pathology',
            
            # Follow-up
            'follow_up_intervention_repeat_surgery_etc': 'followup',
            'if_yes_what_procedure': 'followup',
            
            # Last follow-up
            'last_follow_up_months': 'lastfollowup',
            'symptom_assessment': 'lastfollowup',
            'recurrence': 'lastfollowup',
            'recurrance': 'outcome',
            'progression': 'outcome',
            'progression_free_survival': 'outcome',
            'disease_free_survival_months': 'outcome',
            'status_ad': 'outcome'
        }

        # Data type mappings
        data_type_mappings = {
            'BOOLEAN': 'boolean',
            'TEXT': 'string',
            'TEXTAREA': 'string',
            'NUMBER': 'float',
            'SELECT': 'enum'
        }

        # Process each schema item
        created_count = 0
        updated_count = 0
        for item in data:
            # Extract fields from the extraction schema
            if "fields" not in item:
                continue
                
            fields = item['fields']
            field_name = fields.get('field_name', '')
            field_label = fields.get('field_label', '')
            field_type = fields.get('field_type', '')
            description = fields.get('description', '')
            choices = fields.get('choices', '')
            is_required = not fields.get('is_required', True)  # Invert for 'optional'
            order = fields.get('order', 0)
            
            # Skip if field_name is empty
            if not field_name:
                continue
                
            # Map to appropriate category and data type
            category = category_mappings.get(field_name, 'clinical')  # Default to clinical
            data_type = data_type_mappings.get(field_type, 'string')  # Default to string
            
            # Prepare enum_values if applicable
            enum_values = None
            if choices and data_type == 'enum':
                enum_values = choices.split(',')
            
            # Create or update the column definition
            column, created = ColumnDefinition.objects.update_or_create(
                name=field_name,
                defaults={
                    'description': f"{field_label}: {description}" if description else field_label,
                    'include_confidence': True,
                    'optional': is_required,
                    'category': category,
                    'data_type': data_type,
                    'enum_values': enum_values,
                    'order': order
                }
            )
            
            if created:
                created_count += 1
                logger.info(f"Created column: {field_name}")
            else:
                updated_count += 1
                logger.info(f"Updated column: {field_name}")
        
        # Create a new prompt from the schema after loading it
        try:
            # Generate a prompt template based on the newly created columns
            column_prompt = ColumnDefinitionView.generate_prompt_template()
            
            if column_prompt:
                # Create a new prompt with the generated template
                prompt_name = f"Schema Prompt ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                prompt = SavedPrompt.objects.create(
                    name=prompt_name,
                    content=column_prompt
                )
                logger.info(f"Created new prompt from schema: {prompt_name}")
                prompt_id = prompt.id
            else:
                prompt_id = None
                logger.warning("Could not generate prompt from columns")
        except Exception as e:
            logger.error(f"Error creating prompt from columns: {e}")
            prompt_id = None
            
        return JsonResponse({
            'success': True,
            'created_count': created_count,
            'updated_count': updated_count,
            'total_columns': created_count + updated_count,
            'prompt_created': prompt_id is not None,
            'prompt_id': prompt_id,
            'message': f"Successfully loaded schema from file. Created {created_count} columns, updated {updated_count} columns."
        })
        
    except Exception as e:
        logger.error(f"Error loading schema from file: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# ------------------------------------------------------------------
# 1.  Get the five most‑recent jobs
# ------------------------------------------------------------------
recent_jobs = ProcessingJob.objects.order_by('-created_at')[:5]
print('Most‑recent jobs:')
for j in recent_jobs:
    print(f'  {j.created_at:%Y-%m-%d %H:%M} | {j.id} | {j.name} | {j.status}')

# ------------------------------------------------------------------
# 2.  Focus on the newest job
# ------------------------------------------------------------------
if recent_jobs:
    job = recent_jobs[0]
    print('\nInspecting newest job:', job.id, '|', job.name, '|', job.status)

    # ------------------------------------------------------------------
    # 3.  Find documents that ended in an error
    # ------------------------------------------------------------------
    try:
        docs_in_error = PDFDocument.objects.filter(job=job, status='error')
        print(f'\nDocuments with status=error: {docs_in_error.count()}')

        # 4.  Also look for results that contain an error field
        results_with_error = ProcessingResult.objects.filter(document__job=job)\
                                            .exclude(error__isnull=True)
        print('Results with saved error strings:', results_with_error.count())

        # ------------------------------------------------------------------
        # 5.  Print details & stored traceback / error text
        # ------------------------------------------------------------------
        for doc in docs_in_error:
            print('\n—— Document in error ————————————————————————')
            print('File:', doc.filename or doc.file.name)
            print('Document‑ID:', doc.id)
            print('Saved doc.error:', getattr(doc, "error", None))

            # Look for matching result row
            res = ProcessingResult.objects.filter(document=doc).first()
            if res:
                print('Saved result.error:', getattr(res, "error", None))
                print('raw_result first 500 chars:\n', res.raw_result[:500])
    except Exception as e:
        print(f"Could not process error information: {str(e)}")

    # If error strings were empty, grep the logs for the job‑id or document‑id
else:
    print('\nNo recent jobs found in the database.')

class ReferenceExtractionView(FormView):
    template_name = 'core/reference_extraction.html'
    form_class = ReferenceExtractionForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Reference Extraction"
        # Optionally list recent reference extraction jobs
        if self.request.user.is_authenticated:
            context['recent_ref_jobs'] = ProcessingJob.objects.filter(
                job_type='reference_extraction',
                user=self.request.user
            ).order_by('-created_at')[:10]
        return context
    
    def form_valid(self, form):
        user = self.request.user if self.request.user.is_authenticated else None
        job_name = form.cleaned_data['job_name']
        pdf_files = form.cleaned_data['pdf_files']
        
        # 1. Create the ProcessingJob
        job = ProcessingJob.objects.create(
            name=job_name,
            job_type='reference_extraction',
            status='pending',
            total_count=len(pdf_files),
            user=user,
            prompt_template=REFERENCE_EXTRACTION_PROMPT_TEXT_JSON
        )
        logger.info(f"Created Reference Extraction Job {job.id} for user {user.username if user else 'anonymous'} using Text JSON Prompt")
        
        # 2. Create PDFDocument entries and start background processing
        all_docs_created = True
        for pdf_file in pdf_files:
            try:
                doc = PDFDocument.objects.create(
                    job=job,
                    file=pdf_file,
                    filename=pdf_file.name,
                    status='pending',
                    study_author="Reference Extraction"
                )
                logger.debug(f"Created PDFDocument {doc.id} for job {job.id}, file: {doc.filename}")
                
                # Read data for background task
                pdf_data = pdf_file.read()
                
                # Process asynchronously using threading
                thread = threading.Thread(
                    target=self._process_pdf_for_references_task,
                    args=(str(doc.id), str(job.id)) # Removed pdf_data
                )
                thread.start()
                logger.info(f"Started background thread for document {doc.id}")
                
            except Exception as e:
                logger.error(f"Error creating PDFDocument or starting thread for {pdf_file.name} in job {job.id}: {str(e)}")
                job.error_message = f"Failed to process {pdf_file.name}: {str(e)}"
                job.status = 'failed'
                all_docs_created = False
        
        if not all_docs_created:
            job.save()
            messages.error(self.request, f"Error occurred processing some files for job '{job.name}'.")
        else:
            job.status = 'processing'
            job.save()
            messages.success(self.request, f"Reference extraction job '{job.name}' started successfully for {len(pdf_files)} files.")
        
        # Redirect to the job detail page for this new job
        return redirect(reverse('core:job_detail', kwargs={'pk': job.id}))
    
    def _process_pdf_for_references_task(self, document_id, job_id): # Removed pdf_data argument
        """Wrapper to run the processing logic in a thread."""
        logger.info(f"Background task started for Doc ID: {document_id}, Job ID: {job_id}")
        try:
            # Fetch objects within the thread using IDs
            document = PDFDocument.objects.get(id=document_id)
            job = ProcessingJob.objects.get(id=job_id)

            # --- Read PDF data within the thread ---
            try:
                with document.file.open('rb') as f:
                    pdf_data_in_thread = f.read()
                logger.info(f"Successfully re-read PDF data ({len(pdf_data_in_thread)} bytes) for Doc ID: {document_id} within thread.")
            except Exception as read_err:
                logger.error(f"Failed to read PDF file {document.file.name} for Doc ID {document_id} within thread: {read_err}")
                # Update status and return if file can't be read
                document.status = 'error'
                document.error = f"Failed to read file from storage: {read_err}"
                document.save()
                # Optionally update job status
                job = ProcessingJob.objects.select_for_update().get(id=job_id) # Re-fetch job for atomic update
                job.processed_count += 1
                job.status = 'processing_with_errors' if job.status not in ['failed'] else job.status
                job.save(update_fields=['processed_count', 'status'])
                return # Stop processing this document
            # -----------------------------------------

            self._process_pdf_for_references(pdf_data_in_thread, document, job) # Pass the newly read data
            logger.info(f"Background task finished successfully for Doc ID: {document_id}")
        except PDFDocument.DoesNotExist:
            logger.error(f"Background task failed: PDFDocument {document_id} not found.")
        except ProcessingJob.DoesNotExist:
            logger.error(f"Background task failed: ProcessingJob {job_id} not found.")
        except Exception as e:
            logger.error(f"Background task failed for Doc ID: {document_id}: {str(e)}")
            # Optionally update document/job status to error here
            try:
                doc = PDFDocument.objects.get(id=document_id)
                doc.status = 'error'
                doc.error = str(e)
                doc.save()
                # Update job progress/status cautiously
                job = ProcessingJob.objects.get(id=job_id)
                job.processed_count += 1  # Increment even on error
                if job.status not in ['failed', 'completed_with_errors']:
                    job.status = 'processing_with_errors'
                    job.error_message = (job.error_message or "") + f"\nError on {doc.filename}: {str(e)}"
                job.save()
            except Exception as update_err:
                logger.error(f"Failed to update status after task error: {update_err}")
    
    def _process_pdf_for_references(self, pdf_data, document_record, job):
        """Processes a single PDF for references, handling automatic continuation for truncated responses."""
        logger.info(f"Starting reference extraction for Doc ID: {document_record.id} (Current index: {document_record.last_successful_reference_index})")
        original_status = document_record.status
        document_record.status = 'processing'
        document_record.error = None
        document_record.save()
        job.processing_details = f"Extracting references from: {document_record.filename}"
        job.save()  # Update job details

        # --- State Variables for Processing Loop ---
        all_extracted_references = []
        is_complete = False
        attempt_count = 0
        max_retries = 5  # Maximum number of continuation attempts

        # --- Processing Loop ---
        while not is_complete and attempt_count < max_retries:
            attempt_count += 1
            logger.info(f"Reference extraction attempt {attempt_count} for Doc ID: {document_record.id}")
            
            # Determine the correct prompt (initial or continuation)
            if document_record.last_successful_reference_index == 0:
                prompt_to_use = REFERENCE_EXTRACTION_PROMPT_TEXT_JSON
                logger.info("Using initial reference extraction prompt.")
            else:
                # Generate continuation prompt dynamically
                prompt_to_use = self._generate_continuation_prompt(
                    document_record.last_successful_reference_index
                )
                logger.info(f"Using continuation prompt starting after index {document_record.last_successful_reference_index}.")

            api_result = {}
            saved_count_this_run = 0
            processing_error = None
            
            try:
                # Call Gemini API with the text-based JSON prompt
                # Use gemini-1.5-pro for production for best results
                model_name = 'gemini-2.5-flash-preview-04-17'  # Fast preview model
                api_result = self._call_gemini_api_text_json(pdf_data, prompt_to_use, model_name=model_name)
                
                if not api_result.get("success"):
                    # API call itself failed (network, auth, safety block before generation etc.)
                    raise Exception(api_result.get("error", "Unknown API error"))
                
                raw_response = api_result.get("raw_response", "")
                parsed_json = api_result.get("parsed_json")
                is_truncated = api_result.get("is_truncated", False)
                finish_reason_code = api_result.get("finish_reason")
                
                # Save ProcessingResult for this attempt, regardless of JSON parsing success
                result = ProcessingResult.objects.create(
                    document=document_record,
                    json_result=parsed_json,  # Store None if parsing failed
                    raw_result=raw_response,
                    is_complete=not is_truncated,
                    # Store error only if JSON parsing failed after a seemingly successful API call
                    error="Failed to parse valid JSON from response." if not parsed_json and raw_response else None,
                    continuation_number=document_record.last_successful_reference_index  # Store starting index for this result
                )
                
                # Now, process the parsed JSON if it exists and is valid
                if parsed_json and isinstance(parsed_json.get("references"), list):
                    extracted_references = parsed_json["references"]
                    logger.info(f"Attempt {attempt_count}: Parsed {len(extracted_references)} references from text response for Doc ID: {document_record.id}")
                    
                    saved_count_this_run = 0
                    for i, ref_data in enumerate(extracted_references):
                        # Basic validation
                        if not isinstance(ref_data, dict):
                            logger.warning(f"Skipping invalid reference item (not a dict) at index {i} for Doc ID: {document_record.id}")
                            continue
                        
                        try:
                            # Prepare data for Reference model
                            authors_data = ref_data.get("authors")
                            authors_str = json.dumps(authors_data) if isinstance(authors_data, list) else (authors_data if isinstance(authors_data, str) else None)
                            
                            # Handle publication year properly
                            pub_year = ref_data.get("publication_year")
                            if pub_year and isinstance(pub_year, (int, float, str)):
                                # Convert to int if it's a string digit
                                if isinstance(pub_year, str) and pub_year.isdigit():
                                    pub_year = int(pub_year)
                                # Keep if already int, otherwise None
                                elif not isinstance(pub_year, int):
                                    pub_year = None
                            else:
                                pub_year = None
                            
                            # Handle confidence similarly
                            confidence_val = ref_data.get("confidence")
                            if confidence_val and isinstance(confidence_val, (int, float, str)):
                                # Convert to int if it's a string digit
                                if isinstance(confidence_val, str) and confidence_val.isdigit():
                                    confidence_val = int(confidence_val)
                                # Keep if already int, otherwise None
                                elif not isinstance(confidence_val, int):
                                    confidence_val = None
                            else:
                                confidence_val = None
                            
                            # Create the reference object with more robust handling of fields
                            Reference.objects.create(
                                job=job,
                                document=document_record,
                                reference_index=document_record.last_successful_reference_index + i + 1, # Calculate 1-based index
                                citation_text=str(ref_data.get("citation_text", "")),
                                source_type=str(ref_data.get("source_type", "unknown"))[:20],  # Ensure fits length
                                authors=authors_str,
                                title=str(ref_data.get("title", "")),
                                source_name=str(ref_data.get("source_name", ""))[:512] if ref_data.get("source_name") else None,
                                publication_year=pub_year,
                                volume=str(ref_data.get("volume", ""))[:50] if ref_data.get("volume") else None,
                                issue=str(ref_data.get("issue", ""))[:50] if ref_data.get("issue") else None,
                                pages=str(ref_data.get("pages", ""))[:50] if ref_data.get("pages") else None,
                                doi_or_url=str(ref_data.get("doi_or_url", ""))[:512] if ref_data.get("doi_or_url") else None,
                                confidence=confidence_val,
                                raw_response_part=json.dumps(ref_data)  # Store the dict that created this ref
                            )
                            saved_count_this_run += 1
                        except Exception as e:
                            logger.error(f"Error saving reference item {i} for Doc ID {document_record.id}: {str(e)} - Data: {ref_data}")
                            processing_error = f"Error saving reference {i+1}: {str(e)}"  # Store first error
                    
                    logger.info(f"Saved {saved_count_this_run}/{len(extracted_references)} reference records this run for Doc ID: {document_record.id}")
                    
                    # Update the last successful index
                    document_record.last_successful_reference_index += saved_count_this_run
                    document_record.error = processing_error  # Store saving error if any
                    document_record.save()  # Important: Save after each batch to persist the index
                    
                    # Add to the running total for this document
                    all_extracted_references.extend(extracted_references)
                    
                else:
                    # Handle case where parsing failed or structure was wrong
                    err_msg = "Invalid JSON structure: Missing 'references' list." if parsed_json else "Failed to parse JSON from text response."
                    logger.error(f"{err_msg} for Doc ID: {document_record.id}")
                    document_record.error = err_msg
                    
                    # If we couldn't parse JSON and it's not truncated, stop trying
                    if not is_truncated:
                        logger.error("Parsing failed on a non-truncated response. Stopping.")
                        is_complete = True
                
                # Check completion status for this iteration
                if not is_truncated:
                    logger.info(f"Document {document_record.id} processing complete (response not truncated).")
                    is_complete = True
                    document_record.status = 'complete'  # Finished successfully
                else:
                    # Continue only if we successfully saved references this run
                    if saved_count_this_run > 0:
                        logger.info(f"Response truncated, continuing to next batch (attempt {attempt_count+1}/{max_retries})")
                        document_record.status = 'processing'  # Still processing
                    else:
                        # If truncated but we couldn't save any refs, don't retry further
                        logger.warning(f"Response truncated but no references saved. Stopping after attempt {attempt_count}.")
                        document_record.status = 'error'
                        document_record.error = "Truncated response with no extractable references."
                        is_complete = True
                
                document_record.save()
                
            except Exception as e:
                # This catches errors from _call_gemini_api_text_json or other unexpected issues
                logger.error(f"Error during attempt {attempt_count} for Doc ID {document_record.id}: {str(e)}")
                document_record.status = 'error'
                document_record.error = str(e)[:1000]  # Truncate if error is very long
                document_record.save()
                
                # Ensure a ProcessingResult exists even if API call failed before response
                if not ProcessingResult.objects.filter(document=document_record, continuation_number=document_record.last_successful_reference_index).exists():
                    raw_response_on_error = api_result.get("raw_response", f"Processing error: {e}")
                    ProcessingResult.objects.create(
                        document=document_record,
                        raw_result=raw_response_on_error,
                        is_complete=False,
                        error=document_record.error,
                        continuation_number=document_record.last_successful_reference_index
                    )
                
                # Stop the loop on error
                is_complete = True
        
        # --- Final Document Status After Loop Completes ---
        try:
            # Set final document status based on outcome of all attempts
            if document_record.status == 'processing':
                # If we're still in 'processing' state, it means we hit max_retries
                # but were potentially able to extract more references
                document_record.status = 'processed'  # Can be continued later
                document_record.error = f"Maximum retry attempts ({max_retries}) reached. Extracted {document_record.last_successful_reference_index} references so far."
                logger.info(f"Document {document_record.id} marked as 'processed' after {attempt_count} attempts.")
            
            # Final save with accumulated results
            document_record.save()
            logger.info(f"Final status for Doc ID {document_record.id}: {document_record.status}, References: {document_record.last_successful_reference_index}, Attempts: {attempt_count}")
            
            # --- Update Job Status Atomically ---
            # Only update job progress if this was the *initial* run for the doc (not a continuation)
            is_initial_run = (original_status == 'pending')
            
            with transaction.atomic():
                # Get fresh job instance to prevent race conditions
                job = ProcessingJob.objects.select_for_update().get(id=job.id)
                
                if is_initial_run:
                    # Only increment the job's processed count for initial runs, not continuations
                    job.processed_count += 1
                
                # Update job status based on all document statuses
                if job.processed_count >= job.total_count:
                    # All documents have been processed at least once, so check final job status
                    # Get all documents for this job and check their status
                    documents = PDFDocument.objects.filter(job=job)
                    has_errors = any(doc.status == 'error' for doc in documents)
                    needs_continuation = any(doc.status == 'processed' for doc in documents)
                    
                    if has_errors and needs_continuation:
                        job.status = 'pending_continuation_with_errors'
                        job.error_message = (job.error_message or "") + "\nSome documents failed and some need continuation."
                    elif has_errors:
                        job.status = 'completed_with_errors'
                        job.error_message = (job.error_message or "") + "\nSome documents failed."
                    elif needs_continuation:
                        job.status = 'pending_continuation'
                        job.error_message = (job.error_message or "") + "\nSome documents need continuation."
                    else:
                        # All complete
                        job.status = 'completed'
                        job.error_message = ""  # Clear errors if fully complete
                    
                    logger.info(f"Job {job.id} updated to status: {job.status}")
                else:
                    # Still processing other initial documents
                    if document_record.status == 'error' and job.status not in ['failed', 'processing_with_errors', 'completed_with_errors']:
                        job.status = 'processing_with_errors'
                    elif document_record.status == 'processed' and job.status not in ['failed', 'processing_with_errors', 'pending_continuation', 'pending_continuation_with_errors']:
                        # Mark job as pending continuation early if one doc needs it
                        job.status = 'pending_continuation'
                    
                    logger.info(f"Job {job.id} progress: {job.processed_count}/{job.total_count}. Status: {job.status}")
                
                # Update job details with total references count
                total_refs = Reference.objects.filter(job=job).count()
                job.processing_details = f"Processed {job.processed_count}/{job.total_count} files. Extracted {total_refs} references."
                job.save(update_fields=['processed_count', 'status', 'processing_details', 'error_message'])
        
        except Exception as e:
            logger.error(f"Error updating final status for job {job.id}: {str(e)}")
            # Try a basic update to job as a fallback
            try:
                if is_initial_run:
                    job.processed_count += 1
                    job.save(update_fields=['processed_count'])
            except Exception:
                pass

    def _call_gemini_api_text_json(self, pdf_data, prompt_text, model_name='gemini-2.5-flash-preview-04-17'):
        """Helper function to call Gemini API, requesting a text-based JSON response."""
        logger.info(f"Calling Gemini API for Text JSON. Model: {model_name}")
        try:
            from dotenv import load_dotenv
            import google.generativeai as genai
            from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
            
            load_dotenv(override=True)  # Ensure latest API key
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.error("GEMINI_API_KEY not found.")
                raise ValueError("GEMINI_API_KEY not found.")
            genai.configure(api_key=api_key)

            # Configs
            generation_config = GenerationConfig(
                max_output_tokens=65536,  # Increased from 8192 to handle large reference lists
                temperature=0.1,
                top_p=0.95,
                top_k=40,
                response_mime_type="application/json"  # Explicitly ask for JSON in text response
            )
            
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            # --- Prepare Model (No Tools) ---
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    system_instruction="You are an expert at extracting bibliographic references from academic documents and returning them in JSON format. You will ONLY return a valid JSON object with all extracted references, following the exact format specified in the prompt."
                )
                logger.debug("Gemini Model Initialized for Text JSON.")
            except Exception as model_err:
                logger.error(f"Error initializing Gemini Model: {model_err}", exc_info=True)
                return {"success": False, "error": f"Failed to initialize model: {model_err}"}

            # --- Prepare Content & Call API ---
            try:
                encoded_pdf = base64.b64encode(pdf_data).decode('utf-8')
                content = [
                    {"mime_type": "application/pdf", "data": encoded_pdf},
                    prompt_text  # Use the prompt asking for text JSON
                ]
                logger.info("Sending request to Gemini...")
                logger.debug(f"Prompt Snippet: {prompt_text[:500]}...")
                start_time = time.time()
                response = model.generate_content(content, stream=False)
                end_time = time.time()
                logger.info(f"Gemini response received in {end_time - start_time:.2f} seconds.")
            except Exception as api_err:
                logger.error(f"Error during model.generate_content: {api_err}", exc_info=True)
                error_details = str(api_err)
                if hasattr(api_err, 'message'): error_details = api_err.message
                return {"success": False, "error": f"Gemini API call failed: {error_details}"}

            # --- Process Response ---
            raw_response_text = ""
            parsed_json = None
            finish_reason_code = 0
            is_truncated = False

            try:
                # Check for safety blocks first
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                    reason = response.prompt_feedback.block_reason.name
                    logger.error(f"Gemini request blocked by safety settings. Reason: {reason}")
                    return {"success": False, "error": f"Content blocked by safety settings ({reason})"}

                # Get finish reason
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason_code = candidate.finish_reason.value
                        finish_reason_name = candidate.finish_reason.name
                        logger.info(f"Gemini Finish Reason Code: {finish_reason_code} ({finish_reason_name})")
                        if finish_reason_code == 3: is_truncated = True; logger.warning("Gemini response truncated (MAX_TOKENS).")
                        elif finish_reason_code == 2: logger.warning("Gemini response stopped due to SAFETY.")
                        elif finish_reason_code == 4: logger.warning("Gemini response stopped due to RECITATION.")
                        elif finish_reason_code not in [0, 1]: logger.warning(f"Unexpected finish reason: {finish_reason_name}")
                    else:
                        logger.warning("No finish_reason in candidate")
                else:
                    logger.warning("No candidates in response")

                # Get text response
                if hasattr(response, 'text'):
                    raw_response_text = response.text
                    logger.info(f"Raw text response received (length {len(raw_response_text)})")
                    logger.debug(f"Raw Text Response Sample: {raw_response_text[:1000]}...")
                    
                    # Attempt to parse the text directly as JSON
                    try:
                        parsed_json = json.loads(raw_response_text)
                        logger.info("Successfully parsed raw text response as JSON.")
                    except json.JSONDecodeError:
                        logger.warning("Direct JSON parsing failed. Attempting to extract JSON from text.")
                        # Use the utility function
                        from core.utils import extract_json_from_text
                        parsed_json = extract_json_from_text(raw_response_text)
                        if parsed_json:
                            logger.info("Successfully extracted JSON from text response.")
                        else:
                            logger.warning("Could not extract valid JSON from text response.")
                            # If the finish reason was SAFETY or RECITATION, treat this as a failure
                            if finish_reason_code in [2, 4]:
                                error_msg = f"Response stopped due to {finish_reason_name} and text could not be parsed as JSON."
                                logger.error(error_msg)
                                return {"success": False, "error": error_msg, "raw_response": raw_response_text}
                else:
                    # This case is less likely when response_mime_type="application/json" is set,
                    # but handle it just in case.
                    logger.warning("Response object missing '.text' attribute.")
                    raw_response_text = ""
                    # If the finish reason indicates an issue, report failure
                    if finish_reason_code not in [0, 1]:  # Not UNSPECIFIED or STOP
                        error_msg = f"Received no text content and finish reason was {finish_reason_name}."
                        logger.error(error_msg)
                        return {"success": False, "error": error_msg, "raw_response": ""}

                # Return results
                return {
                    "success": True,  # Success means API call completed, even if JSON parsing failed here
                    "raw_response": raw_response_text,
                    "parsed_json": parsed_json,  # This will be None if parsing failed
                    "is_truncated": is_truncated,
                    "finish_reason": finish_reason_code
                }

            except Exception as process_err:
                # Catch errors during response processing
                logger.error(f"Error processing Gemini response: {process_err}", exc_info=True)
                return {"success": False, "error": f"Failed to process response: {process_err}", "raw_response": raw_response_text}
                
        except Exception as e:
            error_message = f"Error in Gemini API Text JSON: {str(e)}"
            logger.error(error_message, exc_info=True)
            return {
                "success": False,
                "error": error_message,
                "raw_response": str(e)
            }

    def _generate_continuation_prompt(self, last_index):
        """Generates the prompt for continuing reference extraction."""
        # It's important that the model understands 0-based vs 1-based indexing.
        # Let's use 1-based for clarity in the prompt.
        start_from_number = last_index + 1
        return f"""You were previously extracting bibliographic references from the attached academic document.
Your last response was truncated after successfully extracting reference number {last_index} (using 0-based indexing, so the {start_from_number}th reference overall).

Please continue extracting the remaining references, starting *immediately after* the last one you provided (i.e., starting with the {start_from_number}th reference in the document's list).

Output ONLY the JSON object containing the *subsequent* references found. Maintain the required JSON structure:
{{
  "references": [
     {{
       "citation_text": "...",
       // ... include all fields ...
     }}
     // ... only references starting from number {start_from_number} ...
   ]
}}
Do NOT include references 1 through {start_from_number-1} which were already extracted.
Ensure the response is ONLY the valid JSON object.
"""

# Wrap the code at the end of the file to avoid early access to job_type field
# Find where it tries to print recent jobs and modify it

# For example, if there's code like this at the bottom:
# for j in recent_jobs:
#     print(f"{j.id}: {j.name} ({j.status}) - {j.job_type}")

# Modify it to:
try:
    for j in recent_jobs:
        print(f"{j.id}: {j.name} ({j.status})")
        # Don't access job_type until migrations are applied
except Exception as e:
    print(f"Error accessing recent jobs: {e}")
    recent_jobs = []

@require_GET
def test_reference_extraction(request):
    """Test route for reference extraction using the updated Gemini API with text-JSON approach."""
    # Restore security check for production
    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    # Check for a valid PDF file ID in the request
    pdf_id = request.GET.get('pdf_id')
    if not pdf_id:
        return JsonResponse({"error": "No PDF ID provided"}, status=400)
    
    try:
        # Get the document
        document = PDFDocument.objects.get(id=pdf_id)
        
        # Access the PDF data
        pdf_file = document.file
        pdf_data = pdf_file.read()
        
        # Initialize the view to access its methods
        view = ReferenceExtractionView()
        
        # Use our updated API call function
        api_result = view._call_gemini_api_text_json(
            pdf_data, 
            REFERENCE_EXTRACTION_PROMPT_TEXT_JSON,
            model_name='gemini-2.5-flash-preview-04-17'
        )
        
        # Check if the API call succeeded
        if not api_result.get("success"):
            return JsonResponse({
                "error": "API call failed", 
                "details": api_result.get("error"),
                "timestamp": datetime.now().isoformat()
            }, status=500)
        
        # Get the data
        raw_response = api_result.get("raw_response", "")
        parsed_json = api_result.get("parsed_json")
        is_truncated = api_result.get("is_truncated", False)
        finish_reason = api_result.get("finish_reason")
        
        # Check if we got valid references
        references = []
        if parsed_json and isinstance(parsed_json.get("references"), list):
            references = parsed_json["references"]
        
        # Return a summary
        return JsonResponse({
            "success": True,
            "document_id": document.id,
            "document_name": document.filename,
            "is_truncated": is_truncated,
            "finish_reason": finish_reason,
            "references_count": len(references),
            "first_reference": references[0] if references else None,
            "last_reference": references[-1] if references else None,
            "response_length": len(raw_response),
            "timestamp": datetime.now().isoformat()
        })
    
    except PDFDocument.DoesNotExist:
        return JsonResponse({"error": f"PDF document with ID {pdf_id} not found"}, status=404)
    except Exception as e:
        logger.error(f"Error in test_reference_extraction: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "Server error", 
            "details": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=500)