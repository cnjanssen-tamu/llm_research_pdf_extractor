"""
Test script for the Perplexity API client.
This script tests the Perplexity API integration with a sample case.
"""
import os
import sys
import django
import logging
from dotenv import load_dotenv

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_processor.settings')
django.setup()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the PerplexityClient
from core.services.perplexity_client import PerplexityClient

def test_perplexity_research():
    """Test the Perplexity API with a sample medical condition"""
    
    # Load environment variables
    load_dotenv()
    
    # Check if Perplexity API key is set
    if not os.getenv('PERPLEXITY_API_KEY'):
        logger.error("PERPLEXITY_API_KEY not found in .env file")
        print("Error: Please add your Perplexity API key to the .env file")
        print("PERPLEXITY_API_KEY=your-api-key-here")
        return
    
    # Sample case data
    condition = "Glioblastoma multiforme"
    context = {
        'patient_age': '58 years',
        'patient_gender': 'M',
        'key_findings_summary': 'Patient presented with new-onset seizures and progressive headaches. MRI showed a ring-enhancing lesion in the right temporal lobe with significant surrounding edema.',
        'additional_instructions': 'Focus on recent advances in treatment approaches, especially regarding immunotherapy and targeted treatments.'
    }
    
    # Initialize the client
    client = PerplexityClient()
    
    # Generate the research prompt
    print("\n=== Generated Research Prompt ===")
    research_prompt = client.generate_research_prompt(condition, context)
    print(research_prompt)
    
    # Make the API call
    print("\n=== Making API Call to Perplexity ===")
    try:
        response = client.research(research_prompt)
        
        # Extract and print the research text
        print("\n=== Research Results ===")
        research_text = client.extract_research_text(response)
        print(research_text)
        
        print("\n=== API Response Structure ===")
        # Print some info about the response structure (for debugging)
        if 'choices' in response:
            print(f"Number of choices: {len(response['choices'])}")
            print(f"Model used: {response.get('model', 'Not specified')}")
            print(f"Response ID: {response.get('id', 'Not specified')}")
        else:
            print("Unexpected response structure:", response.keys())
        
        return True
    
    except Exception as e:
        logger.error(f"Error during Perplexity API test: {str(e)}")
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== Testing Perplexity AI Research API ===")
    success = test_perplexity_research()
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!") 