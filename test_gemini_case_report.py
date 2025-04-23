"""
Test script for the Gemini API client for case report generation.
This script tests the Gemini API integration with a sample case.
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

# Import the GeminiClient
from core.services.gemini_client import GeminiClient

def test_gemini_draft_generation():
    """Test the Gemini API with a sample case report draft generation"""
    
    # Load environment variables
    load_dotenv()
    
    # Check if Gemini API key is set
    if not os.getenv('GEMINI_API_KEY'):
        logger.error("GEMINI_API_KEY not found in .env file")
        print("Error: Please add your Gemini API key to the .env file")
        print("GEMINI_API_KEY=your-api-key-here")
        return
    
    # Sample text data
    text_data = {
        'patient_age': '58 years',
        'patient_gender': 'M',
        'suspected_condition': 'Glioblastoma multiforme',
        'key_findings_summary': 'Patient presented with new-onset seizures and progressive headaches. MRI showed a ring-enhancing lesion in the right temporal lobe with significant surrounding edema.',
        'additional_instructions': 'Focus on recent advances in treatment approaches, especially regarding immunotherapy and targeted treatments.'
    }
    
    # Sample PDF data (simulated extracted text)
    pdf_data = {
        'Patient History / Admission Notes': """
        The patient is a 58-year-old male who presented to the emergency department with a first-time generalized tonic-clonic seizure. 
        He reported a 3-week history of progressive headaches, initially intermittent but becoming constant in the last week. 
        The headaches were mainly right-sided and associated with nausea and photophobia. 
        He also noted some recent memory lapses and word-finding difficulties.
        Past medical history is significant for hypertension and hyperlipidemia, both well-controlled on medication.
        No history of seizures or neurological disorders.
        No family history of brain tumors.
        """,
        
        'Imaging Reports': """
        MRI Brain w/ & w/o contrast:
        A large (4.2 x 3.5 x 3.8 cm) heterogeneously enhancing mass is identified in the right temporal lobe, 
        demonstrating central necrosis and peripheral ring enhancement. Significant surrounding vasogenic edema extending 
        to the right parietal lobe. There is mass effect with 5mm rightward midline shift and compression of the right lateral ventricle.
        The lesion shows restricted diffusion peripherally. 
        Spectroscopy demonstrates elevated choline:NAA ratio and decreased NAA peak.
        Perfusion imaging shows increased relative cerebral blood volume.
        Impression: Findings are consistent with high-grade glioma, most likely glioblastoma multiforme.
        """
    }
    
    # Sample research results (simulated from Perplexity)
    research_text = """
    # Glioblastoma Multiforme (GBM): Current Research and Treatment Approaches

    ## Current Diagnostic Approaches and Criteria
    
    Glioblastoma multiforme (GBM) is the most aggressive primary brain tumor, classified as a WHO grade IV astrocytoma. Current diagnostic approaches combine imaging, histopathology, and molecular testing (Tan et al., 2020, Nature Reviews Neurology). The 2021 WHO Classification of CNS Tumors has updated the diagnostic criteria to emphasize molecular characteristics, particularly IDH mutation status, which divides GBMs into IDH-wildtype (90%) and IDH-mutant (10%) subtypes (Louis et al., 2021, Neuro-Oncology).

    MRI with gadolinium contrast remains the gold standard imaging modality, typically showing a heterogeneously enhancing mass with central necrosis, surrounding edema, and often multifocal or infiltrative appearance (Ellingson et al., 2021, JAMA Oncology).

    ## Latest Treatment Recommendations and Guidelines
    
    The standard of care for newly diagnosed GBM established by the Stupp protocol continues to include maximal safe surgical resection followed by concurrent radiation therapy (60 Gy in 30 fractions) with temozolomide (TMZ), then adjuvant TMZ for 6-12 cycles (Stupp et al., 2005; reaffirmed in NCCN Guidelines 2023).

    Recent advances include:

    1. **Tumor Treating Fields (TTFields)**: The addition of TTFields to maintenance TMZ has shown to improve both progression-free and overall survival, as demonstrated in the EF-14 trial (Taphoorn et al., 2023, Journal of Clinical Oncology).

    2. **Immunotherapy Approaches**: Although checkpoint inhibitors as monotherapy have shown limited efficacy in unselected GBM patients, several trials are exploring their use in specific molecular subgroups. The CheckMate-143 trial with nivolumab did not meet its primary endpoint, but ongoing trials are focusing on hypermutated tumors and combination approaches (Reardon et al., 2020, Neuro-Oncology).

    3. **Targeted Therapies**: Several targeted agents are in clinical trials, including:
       - EGFR inhibitors for EGFR-amplified tumors
       - BRAF inhibitors for BRAF-mutant tumors
       - MEK inhibitors
       - CDK4/6 inhibitors (Molenaar et al., 2022, Cancer Discovery)

    ## Recent Advances in Treatment

    Exciting developments in GBM treatment include:

    1. **CAR-T Cell Therapy**: EGFRvIII-directed CAR-T cells and IL13Rα2-targeted CAR-T cells have shown promising results in early clinical trials (O'Rourke et al., 2022, Science Translational Medicine).

    2. **Personalized Neoantigen Vaccines**: The phase I/Ib trial of personalized neoantigen vaccines combined with pembrolizumab showed encouraging survival data in newly diagnosed GBM patients (Keskin et al., 2021, Nature).

    3. **Convection-Enhanced Delivery (CED)**: This technique allows direct delivery of therapeutic agents to the tumor, bypassing the blood-brain barrier. Recent trials with immunotoxins and chemotherapeutics delivered via CED have shown promising results (Souweidane et al., 2022, Lancet Oncology).

    4. **PARP Inhibitors**: For patients with MGMT-unmethylated GBM, PARP inhibitors such as olaparib are showing potential in clinical trials, particularly when combined with TMZ (Coleman et al., 2022, Journal of Clinical Oncology).

    5. **Oncolytic Virus Therapy**: DNX-2401, a replication-competent adenovirus, has demonstrated anti-tumor activity and survival benefit in recurrent GBM patients in phase I trials (Lang et al., 2023, Science Translational Medicine).

    ## Notable Case Studies

    A notable case study published in the New England Journal of Medicine (Aguilera et al., 2023) reported a 62-year-old patient with recurrent GBM who had an exceptional response to a combination of pembrolizumab and the PARP inhibitor olaparib. The patient's tumor harbored both a high tumor mutational burden and BRCA2 mutation, highlighting the importance of comprehensive molecular testing in identifying potential responders to specific therapies.

    Another important case series by Johnson et al. (2022, Nature Medicine) described three patients with hypermutated, mismatch repair-deficient GBMs who had durable responses to immune checkpoint inhibition, suggesting this molecular subset may particularly benefit from immunotherapy.
    """
    
    # Initialize the client
    client = GeminiClient()
    
    # Construct the generation prompt
    print("\n=== Generated Draft Prompt ===")
    draft_prompt = client.construct_generation_prompt(text_data, pdf_data, research_text)
    print(draft_prompt)
    
    # Make the API call
    print("\n=== Making API Call to Gemini ===")
    try:
        # Generate the draft
        draft_text = client.generate_draft(draft_prompt)
        
        # Print the results
        print("\n=== Generated Draft Case Report ===")
        print(draft_text)
        
        return True
    
    except Exception as e:
        logger.error(f"Error during Gemini API test: {str(e)}")
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== Testing Gemini AI Case Report Generation ===")
    success = test_gemini_draft_generation()
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!") 