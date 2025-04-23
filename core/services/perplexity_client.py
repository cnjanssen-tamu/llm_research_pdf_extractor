"""
Perplexity API client for research queries.
This module handles interactions with the Perplexity AI API for medical research.
"""
import os
import json
import logging
import requests
from django.conf import settings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class PerplexityClient:
    """Client for interacting with the Perplexity AI API"""
    
    def __init__(self):
        # Get API key from environment
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not found in environment variables")
        
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.default_model = "sonar-pro"  # Updated to a valid model
    
    def generate_research_prompt(self, condition, context):
        """
        Generate a research prompt for Perplexity AI based on the condition and context.
        
        Args:
            condition (str): The medical condition to research
            context (dict): Additional context like patient age, gender, etc.
            
        Returns:
            str: A well-formatted research prompt
        """
        # Construct a prompt for medical research that will return citations
        prompt = [
            "You are a medical research assistant. Your task is to provide relevant and up-to-date information about the following medical condition or procedure.",
            f"Condition/Procedure: {condition}",
            "\nI need comprehensive information about:",
            "1. Current diagnostic approaches and criteria",
            "2. Latest treatment recommendations and guidelines",
            "3. Key clinical features and presentation",
            "4. Recent advances or changes in management",
            "5. Notable case studies or examples from literature"
        ]
        
        # Add patient context if available
        patient_context = []
        if context.get('patient_age'):
            patient_context.append(f"- Patient age: {context['patient_age']}")
        if context.get('patient_gender'):
            patient_context.append(f"- Patient gender: {context['patient_gender']}")
        if context.get('key_findings_summary'):
            patient_context.append(f"- Key findings: {context['key_findings_summary']}")
        
        if patient_context:
            prompt.append("\nPatient context (consider for relevance):")
            prompt.extend(patient_context)
        
        # Add special instructions
        prompt.append("\nImportant:")
        prompt.append("- Include SPECIFIC CITATIONS to recent medical literature (past 5 years preferred)")
        prompt.append("- For each main point, provide the source (journal name, year, authors)")
        prompt.append("- Organize information clearly with headings")
        prompt.append("- Focus on evidence-based information from reputable sources")
        prompt.append("- Include any controversies or evolving understanding in the field")
        prompt.append("- If relevant clinical guidelines exist, cite the most recent versions")
        
        if context.get('additional_instructions'):
            prompt.append("\nAdditional research focus:")
            prompt.append(context['additional_instructions'])
        
        return "\n".join(prompt)
    
    def research(self, prompt, model=None):
        """
        Send a research query to Perplexity AI and get back results with citations.
        
        Args:
            prompt (str): The research prompt
            model (str, optional): The model to use. Defaults to sonar-pro.
            
        Returns:
            dict: The response from the Perplexity API
        """
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not set in environment variables")
        
        model = model or self.default_model
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Make sure we're using the correct format for the API request
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful medical research assistant that provides accurate information with academic citations."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        try:
            logger.info(f"Sending research query to Perplexity AI using model: {model}")
            logger.debug(f"Request data: {json.dumps(data)}")
            response = requests.post(self.api_url, headers=headers, json=data)  # Changed from data=json.dumps(data) to json=data
            
            if response.status_code != 200:
                logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                
            response.raise_for_status()  # Raise exception for HTTP errors
            
            result = response.json()
            logger.info("Successfully received response from Perplexity AI")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Perplexity API: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity research: {str(e)}")
            raise
    
    def extract_research_text(self, response):
        """
        Extract the research text from the Perplexity API response.
        
        Args:
            response (dict): The response from the Perplexity API
            
        Returns:
            str: The extracted research text
        """
        try:
            if 'choices' in response and len(response['choices']) > 0:
                # Extract the content from the first choice
                content = response['choices'][0]['message']['content']
                return content
            return "Error: Unable to extract research content from response"
        except Exception as e:
            logger.error(f"Error extracting research text: {str(e)}")
            return f"Error extracting research text: {str(e)}" 