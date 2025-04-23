"""
Gemini API client for draft generation.
This module handles interactions with Google's Gemini API for generating case report drafts.
"""
import os
import json
import logging
import google.generativeai as genai
from django.conf import settings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GeminiClient:
    """Client for interacting with the Google Gemini API"""
    
    def __init__(self):
        # Get API key from environment
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
        else:
            # Configure the Gemini API
            genai.configure(api_key=self.api_key)
        
        # Default to Gemini 2.5 Flash Preview
        self.default_model = "gemini-2.5-flash-preview-04-17"
    
    def extract_text_from_pdf(self, pdf_file, max_chars=3000):
        """
        Extract text from a PDF file and truncate if it's too long.
        This is a simplified version, consider using a more robust PDF extraction 
        library like PyMuPDF (fitz) in production.
        
        Args:
            pdf_file: The PDF file object
            max_chars: Maximum number of characters to extract
            
        Returns:
            str: The extracted text
        """
        try:
            import PyPDF2
            import io
            
            # Ensure the file pointer is at the beginning
            pdf_file.seek(0)
            
            # Use BytesIO to handle the in-memory file
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
            text = ""
            
            # Extract text from each page
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text() or ""
                text += page_text + "\n\n"
                
                # If we've extracted enough text, stop
                if len(text) > max_chars:
                    text = text[:max_chars] + "..."
                    break
            
            # Reset file pointer
            pdf_file.seek(0)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return f"[Error extracting text: {str(e)}]"
    
    def construct_generation_prompt(self, text_data, pdf_data, research_data=None):
        """
        Construct a prompt for the Gemini API to generate a case report draft.
        
        Args:
            text_data (dict): Text data from the form
            pdf_data (dict): Extracted text from PDF files
            research_data (str, optional): Research data from Perplexity
            
        Returns:
            str: The constructed prompt
        """
        prompt_parts = [
            "You are a medical expert tasked with drafting a case report based on the provided de-identified patient information. Structure the report logically with sections like Introduction, Case Presentation, Discussion, and Conclusion.",
            "IMPORTANT: All provided information is de-identified. Do NOT include any real patient names, specific dates (use relative terms like 'Day 5 of admission' if available), or other potential identifiers.",
            "Synthesize the information provided below and leverage your knowledge of published medical literature to create a comprehensive and plausible draft case report.",
            "Use appropriate medical terminology and maintain a formal, objective tone.",
            "\n--- Provided Information ---",
        ]

        # Add text fields data
        prompt_parts.append("\n**Summary Information:**")
        for key, value in text_data.items():
            if value and key not in ['name', 'de_identification_confirmed']:  # Skip non-medical fields
                # Format the key by replacing underscores with spaces and capitalizing
                formatted_key = " ".join(word.capitalize() for word in key.split('_'))
                prompt_parts.append(f"- {formatted_key}: {value}")

        # Add extracted PDF data
        if pdf_data:
            prompt_parts.append("\n**Detailed Information from Documents:**")
            for label, text in pdf_data.items():
                prompt_parts.append(f"\n*--- {label} ---*")
                prompt_parts.append(text)
                prompt_parts.append(f"*--- End {label} ---*")

        # Add research data if available
        if research_data:
            prompt_parts.append("\n**Research Information:**")
            prompt_parts.append("The following research information has been gathered to help inform this case report:")
            prompt_parts.append(research_data)

        # Add specific instructions
        if text_data.get("additional_instructions"):
            prompt_parts.append("\n**Specific Instructions:**")
            prompt_parts.append(text_data["additional_instructions"])

        prompt_parts.append("\n--- Draft Case Report Generation ---")
        prompt_parts.append("Please generate a professional medical case report draft that synthesizes the information provided above. Format it with clear sections and use appropriate medical terminology.")

        return "\n".join(prompt_parts)
    
    def generate_draft(self, prompt, model=None):
        """
        Generate a case report draft using the Gemini API.
        
        Args:
            prompt (str): The prompt for generation
            model (str, optional): The model to use. Defaults to the default model.
            
        Returns:
            str: The generated draft
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in environment variables")
        
        model_name = model or self.default_model
        
        try:
            logger.info(f"Generating draft with Gemini model: {model_name}")
            
            # Configure generation parameters
            generation_config = {
                "temperature": 0.7,  # Creativity versus determinism (0.0-1.0)
                "top_p": 0.95,       # Token selection strategy
                "top_k": 40,         # Token selection parameter
                "max_output_tokens": 4096,  # Maximum length of the response
            }
            
            # Create the model instance
            model = genai.GenerativeModel(model_name)
            
            # Generate the content
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Check if there was a response
            if not response.parts:
                logger.error("No content generated by Gemini API")
                return "[Error: No content generated by the API]"
            
            # Extract and return the text
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating draft with Gemini: {str(e)}")
            return f"[Error generating report: {str(e)}]" 