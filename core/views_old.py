
from django.views.generic import FormView
from django.http import JsonResponse
from django.conf import settings
import google.generativeai as genai
import pandas as pd
from django.core.paginator import Paginator
from .forms import ProcessingForm
from .models import PDFDocument, ProcessingJob, ProcessingResult
import base64
import simplejson
from json.decoder import JSONDecodeError
import re
import traceback
import logging
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)



MEDICAL_REVIEW_PROMPTS = """You are a medical reviewer..."""  # Your existing prompt text here

class ProcessorView(FormView):
    template_name = 'processor.html'
    form_class = ProcessingForm
    success_url = '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['default_prompt'] = MEDICAL_REVIEW_PROMPTS
        try:
            latest_job = ProcessingJob.objects.latest('created_at')
            latest_results = ProcessingResult.objects.filter(document__job=latest_job)
            
            if latest_results.exists():
                all_case_results = []
                for result in latest_results:
                    if result.result_data and 'case_results' in result.result_data:
                        all_case_results.extend(result.result_data['case_results'])
                
                if all_case_results:
                    df = pd.DataFrame([
                        {k: v['value'] for k, v in case.items()}
                        for case in all_case_results
                    ])
                    
                    required_columns = [str(i) for i in range(16)]
                    for col in required_columns:
                        if col not in df.columns:
                            df[col] = ''
                    
                    paginator = Paginator(df.to_dict('records'), 10)
                    page = self.request.GET.get('page', 1)
                    table_data = paginator.get_page(page)
                    
                    context.update({
                        'latest_job': latest_job,
                        'table_data': table_data,
                        'columns': required_columns,
                        'show_results': True
                    })
        except (ProcessingJob.DoesNotExist, ProcessingResult.DoesNotExist):
            context['show_results'] = False
        return context

    def process_pdf_with_gemini(self, pdf_doc, custom_prompt=None):
        try:
            if not pdf_doc.file:
                raise ValueError("No PDF file provided")

            file_size = pdf_doc.file.size
            if file_size > 20 * 1024 * 1024:
                raise ValueError("PDF file too large")

            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')

            with pdf_doc.file.open('rb') as file:
                pdf_content = file.read()
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

            prompt_text = custom_prompt if custom_prompt else MEDICAL_REVIEW_PROMPTS

            response = model.generate_content(
                [
                    {"mime_type": "application/pdf", "data": pdf_base64},
                    prompt_text
                ],
                generation_config={"temperature": 0.1, "top_p": 0.8, "top_k": 40}
            )

            # Log raw response
            logger.info(f"Raw Gemini Response:\n{response.text}")

            if not response.text:
                raise ValueError("Empty response from Gemini API")

            json_str = self.extract_json_from_text(response.text)
            logger.info(f"Extracted JSON:\n{json_str}")

            validated_json = self.validate_json_structure(json_str)
            logger.info(f"Validated JSON:\n{validated_json}")

            return {
                'success': True,
                'parsed_json': validated_json,
                'raw_text': response.text
            }
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'raw_text': getattr(response, 'text', 'No response text available')
            }

    # def process_pdf_with_gemini(self, pdf_doc, custom_prompt=None):
    #     try:
    #         if not pdf_doc.file:
    #             raise ValueError("No PDF file provided")
    #
    #         file_size = pdf_doc.file.size
    #         if file_size > 20 * 1024 * 1024:
    #             raise ValueError("PDF file too large")
    #
    #         genai.configure(api_key=settings.GEMINI_API_KEY)
    #         model = genai.GenerativeModel('gemini-1.5-pro')
    #
    #         with pdf_doc.file.open('rb') as file:
    #             pdf_content = file.read()
    #             pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
    #
    #         # Use custom prompt if provided, otherwise use default
    #         prompt_text = custom_prompt if custom_prompt else MEDICAL_REVIEW_PROMPTS
    #
    #         response = model.generate_content(
    #             [
    #                 {"mime_type": "application/pdf", "data": pdf_base64},
    #                 prompt_text
    #             ],
    #             generation_config={
    #                 "temperature": 0.1,
    #                 "top_p": 0.8,
    #                 "top_k": 40
    #             }
    #         )
    #
    #         json_str = self.extract_json_from_text(response.text)
    #         parsed_json = json.loads(json_str)
    #         validated_json = self.validate_json_structure(parsed_json)
    #
    #         return {
    #             'success': True,
    #             'parsed_json': validated_json,
    #             'raw_text': response.text
    #         }
    #     except Exception as e:
    #         logger.error(f"Error processing PDF: {str(e)}")
    #         return {
    #             'success': False,
    #             'error': str(e),
    #             'raw_text': getattr(response, 'text', 'No response text available')
    #         }
    # def process_pdf_with_gemini(self, pdf_doc, custom_prompt=None):
    #     try:
    #         if not pdf_doc.file:
    #             raise ValueError("No PDF file provided")
    #
    #         file_size = pdf_doc.file.size
    #         if file_size > 20 * 1024 * 1024:
    #             raise ValueError("PDF file too large")
    #
    #         genai.configure(api_key=settings.GEMINI_API_KEY)
    #         model = genai.GenerativeModel('gemini-2.0-flash-exp')
    #         with pdf_doc.file.open('rb') as file:
    #             pdf_content = file.read()
    #             pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
    #
    #         prompt_text = custom_prompt if custom_prompt else MEDICAL_REVIEW_PROMPTS
    #
    #         response = model.generate_content(
    #             [
    #                 {"mime_type": "application/pdf", "data": pdf_base64},
    #                 prompt_text
    #             ],
    #             generation_config={"temperature": 0.1, "top_p": 0.8, "top_k": 40})
    #
    #         if not response.text:
    #             raise ValueError("Empty response from Gemini API")
    #
    #         json_str = self.extract_json_from_text(response.text)
    #         validated_json = self.validate_json_structure(json_str)
    #
    #         return {
    #             'success': True,
    #             'parsed_json': validated_json,
    #             'raw_text': response.text
    #         }
    #     except Exception as e:
    #         logger.error(f"Error processing PDF: {str(e)}")
    #         return {
    #             'success': False,
    #             'error': str(e),
    #             'raw_text': getattr(response, 'text', 'No response text available')
    #         }
    def form_valid(self, form):
        try:
            job = form.save()
            pdf_docs = []
            results = []

            # Handle multiple files
            for pdf_file in self.request.FILES.getlist('pdf_files'):
                pdf_doc = PDFDocument.objects.create(
                    job=job,
                    file=pdf_file
                )
                logger.info(f"Processing PDF: {pdf_file.name}")
                pdf_docs.append(pdf_doc)

            custom_prompt = form.cleaned_data.get('prompt')

            for pdf_doc in pdf_docs:
                result = self.process_pdf_with_gemini(pdf_doc, custom_prompt)
                if result['success']:
                    results.append(result)

                    # Log successful processing
                    logger.info(f"Successfully processed {pdf_doc.file.name}")

                    ProcessingResult.objects.create(
                        document=pdf_doc,
                        result_data=result['parsed_json']
                    )

            if not results:
                raise ValueError("No PDFs were successfully processed")

            # Combine and process results
            all_case_results = []
            for result in results:
                if 'parsed_json' in result:
                    all_case_results.extend(result['parsed_json'].get('case_results', []))

            # Create DataFrame and log its content
            df = pd.DataFrame([
                {k: v['value'] for k, v in case.items()}
                for case in all_case_results
            ])

            logger.info(f"Generated DataFrame:\n{df.to_string()}")

            # Generate HTML and log it
            table_html = df.to_html(classes='table table-striped', index=False)
            logger.info(f"Generated HTML table:\n{table_html[:500]}...")  # Log first 500 chars

            job.status = 'completed'
            job.save()

            return JsonResponse({
                'success': True,
                'table_html': table_html,
                'job_id': job.id,
                'debug_info': {
                    'num_docs_processed': len(pdf_docs),
                    'num_successful_results': len(results),
                    'num_cases_extracted': len(all_case_results),
                    'dataframe_shape': df.shape,
                    'columns_found': list(df.columns)
                }
            })

        except Exception as e:
            logger.error(f"Error in form_valid: {str(e)}", exc_info=True)
            if 'job' in locals():
                job.status = 'failed'
                job.save()
            return JsonResponse({
                'success': False,
                'error': str(e),
                'debug_info': {
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'traceback': traceback.format_exc()
                }
            }, status=500)

    def extract_json_from_text(self, text):
        try:
            # Clean the text first
            text = text.replace('``````', '').strip()

            # Handle both array and object responses
            if text.startswith('['):
                json_array = json.loads(text)
                # Combine multiple cases into one structure
                return {
                    'case_results': [
                        case for case in json_array
                        if isinstance(case, dict) and '0' in case
                    ]
                }
            else:
                # Find and parse single object
                start_idx = text.find('{')
                end_idx = text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    return json.loads(text[start_idx:end_idx])

            raise ValueError("No valid JSON found in response")
        except Exception as e:
            logger.error(f"JSON extraction error: {str(e)}\nOriginal text: {text[:500]}")
            raise

    def clean_json_string(self, json_str):
        # Remove any trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Remove any comments
        json_str = re.sub(r'//.*?\n|/\*.*?\*/', '', json_str, flags=re.S)

        # Fix any unquoted keys
        json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)

        # Remove any ellipsis
        json_str = json_str.replace('...', '')

        return json_str

    def validate_json_structure(self, data):
        try:
            if isinstance(data, list):
                # Handle array of cases
                case_results = []
                for item in data:
                    if isinstance(item, dict):
                        if 'instruction' in item:
                            continue
                        case_results.append(item)
                return {'case_results': case_results}

            if not isinstance(data, dict):
                raise ValueError("Invalid JSON structure: root must be an object")

            # Handle flat structure
            if all(isinstance(v, dict) and 'value' in v and 'confidence' in v
                   for k, v in data.items() if k not in ['instruction', 'low confidence explanation']):
                case_results = []
                current_case = {}

                for key, value in sorted(data.items()):
                    if key in ['instruction', 'low confidence explanation']:
                        continue

                    if key in ['0', '3A', 'Article Name'] and current_case:
                        case_results.append(current_case)
                        current_case = {}

                    current_case[key] = value

                if current_case:
                    case_results.append(current_case)

                return {'case_results': case_results}

            # Check for existing case_results structure
            if 'case_results' not in data:
                if any(isinstance(v, dict) and 'value' in v for v in data.values()):
                    return {'case_results': [data]}
                raise ValueError("Missing case_results array in JSON structure")

            return data

        except Exception as e:
            logger.error(f"JSON validation error: {str(e)}\nData: {data}")
            raise

    def validate_json_structure(self, data):
        try:
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON structure: root must be an object")

            # Handle flat structure
            if all(isinstance(v, dict) and 'value' in v and 'confidence' in v
                   for k, v in data.items() if k not in ['instruction', 'low confidence explanation']):
                case_results = []
                current_case = {}

                for key, value in sorted(data.items()):  # Sort to maintain order
                    if key in ['instruction', 'low confidence explanation']:
                        continue

                    if key in ['0', '3A'] and current_case:
                        case_results.append(current_case)
                        current_case = {}

                    current_case[key] = value

                if current_case:
                    case_results.append(current_case)

                return {'case_results': case_results}

            # Check for existing case_results structure
            if 'case_results' not in data:
                raise ValueError("Missing case_results array in JSON structure")

            return data

        except Exception as e:
            logger.error(f"JSON validation error: {str(e)}\nData: {data}")
            raise

    def validate_json_structure(self, data):
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure: root must be an object")
            
        # Handle flat structure
        if all(isinstance(v, dict) and 'value' in v and 'confidence' in v 
               for k, v in data.items() if k not in ['instruction', 'low confidence explanation']):
            case_results = []
            current_case = {}
            
            for key, value in data.items():
                if key in ['instruction', 'low confidence explanation']:
                    continue
                    
                if key in ['0', '3A']:
                    if current_case:
                        case_results.append(current_case)
                    current_case = {}
                current_case[key] = value
                
            if current_case:
                case_results.append(current_case)
                
            return {'case_results': case_results}
        
        return data

MEDICAL_REVIEW_PROMPTS = """You are a medical reviewer extracting information from case studies related to meningioma patients. Extract the following information and provide a confidence rating (1-5, with 5 being most confident). If information isn't available, return an empty string and a confidence rating of 1.

Study objectives:

Meningiomas in adults (18+)
Tumor characteristics, treatment, and outcomes
Primary research articles (case reports, case series, cohort studies)
For each case, extract:
0. Article Name

DOI
First author's last name
Publication Year
3A. Case number (start with 1, increment for each case)
3B. Date of first presentation (YYYY-MM, YYYY, or YYYY if month unknown)
Patient age
Patient gender (M/F)
Duration of symptoms (months). Prioritize most recent specific timeframe.
Tumor location (Cranial or Spinal)
Extent of resection (total or subtotal)
WHO Grade
Meningioma subtype
Adjuvant therapy (y/n)
Symptom assessment after treatment (improved, resolved, other)
Recurrence (y/n)
Patient status (A=alive, D=deceased)
Tumor invasion beyond origin (y/n)
Is Original (y/n)? "Original" means the patient was treated/observed directly by the authors.
Instructions:

An "original case" is one where the authors directly managed/observed the patient. Look for detailed patient descriptions, treatment details, and follow-up. Phrases like "our patient" or "in this study" indicate original cases. Summarized cases from other studies are not original.
Prioritize information in Case Presentation/Results. If conflicting symptom durations, use the most specific, recent timeframe.
If info is unclear/unavailable, leave blank and give confidence 1. Don't guess.
Only extract data for cases directly managed/observed by the authors.
Determine the Simpson Grade based on the extent of resection and dural involvement, and record it in the "8. Extent of resection" field using the following scale:
Grade I: Complete resection including dural attachment and any abnormal bone
Grade II: Complete resection with coagulation of dural attachment
Grade III: Complete resection without resection or coagulation of dural attachment or extradural extensions
Grade IV: Subtotal resection, leaving visible tumor remnants
Grade V: Simple decompression with or without biopsy
JSON Format (per case):

{
  "0": {"value": "...", "confidence": ...}, // and so on for all fields
  "low confidence explanation": {"value": "...", "confidence": 5}
}
content_copy download
Use code with caution.
Json
For any confidence score less than 5, provide a brief explanation in the "low confidence explanation" field, detailing the reasons for the lower confidence. For example:

"low confidence explanation": {"value": "WHO Grade not explicitly stated in the article.", "confidence": 5}
content_copy download
Use code with caution.
Json
If more than two original cases are identified, extract data for only the first two and then add the following instruction within the JSON output: "instruction": {"value": "Request the next cases", "confidence": 5}. The user should then submit a new query for the remaining cases.


Prompt 2: For Case Series (Revised with Low Confidence Explanation)
You are a medical reviewer extracting information from case series related to meningioma patients. Follow the same instructions and JSON format as Prompt 1, with the following modifications:

If the series includes cases from both the authors' institution and external sources, ONLY extract data for cases directly managed/observed by the authors.
If individual patient details aren't provided for all cases, focus ONLY on those with sufficient information.
Determine the Simpson Grade based on the extent of resection and dural involvement, and record it in the "8. Extent of resection" field using the following scale:
Grade I: Complete resection including dural attachment and any abnormal bone
Grade II: Complete resection with coagulation of dural attachment
Grade III: Complete resection without resection or coagulation of dural attachment or extradural extensions
Grade IV: Subtotal resection, leaving visible tumor remnants
Grade V: Simple decompression with or without biopsy
For any confidence score less than 5, provide a brief explanation in the "low confidence explanation" field, detailing the reasons for the lower confidence.


Prompt 3: For Case Reviews (Revised with Low Confidence Explanation)
You are a medical reviewer summarizing information from a case review on meningioma patients. Extract the following information specifically for cases managed/observed at the authors' institution. Provide a confidence rating (1-5). For missing information, return an empty string and confidence 1.

Extract:
0. Article Name

DOI
First author's last name
Publication Year
Total cases from authors' institution
Age range
Gender distribution (e.g., 10M/5F)
Most common tumor location(s)
Most common treatment(s)
Overall recurrence rate
Overall patient status (e.g., 90% alive, 10% deceased)
Instructions:

Focus ONLY on cases managed/observed at the authors' institution.
Provide concise summaries based on aggregate data. Don't include information from external sources unless directly related to the authors' cases.
JSON Format:

{
   "0": {"value": "...", "confidence": ...}, // ... and so on
   "low confidence explanation": {"value": "...", "confidence": 5}
}
Json
For any confidence score less than 5, provide a brief explanation in the "low confidence explanation" field, detailing the reasons for the lower confidence.
"""

def test_gemini(request):
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
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
