# Schema Integration for Human vs. LLM Extraction Comparison

This document explains how we've integrated the extraction schema from the human_vs_llm project into our AI_Reviewer system, enabling direct comparison between human annotation and LLM extraction.

## Overview

We've created a system to:

1. Import the extraction schema fields from the human_vs_llm project
2. Map these fields to our existing column definition structure
3. Generate structured output schemas for Gemini AI model
4. Process PDFs with structured output according to the schema

## Using the Schema Integration

### Loading Column Definitions

To load the extraction schema fields as column definitions:

```bash
python manage.py load_default_columns --clear
```

This will:
- Clear existing column definitions (if --clear is used)
- Load all extraction fields from the human_vs_llm project
- Map fields to appropriate categories (demographics, clinical, pathology, etc.)
- Set up proper data types and validation

### Processing PDFs with Structured Output

The system will now automatically use structured output with Gemini when processing PDFs:

1. When a PDF is uploaded, the system will use the column definitions to construct a schema
2. This schema is passed to Gemini using its structured output capability
3. Gemini will return results that precisely match the defined schema
4. Results are stored with the same format as the human annotation tool

### Schema Structure

The extraction schema includes fields in these categories:

- **Presentation**: Symptoms like headache, neck pain, gait disturbance
- **Clinical**: Duration of symptoms, WHO grade, subtype
- **Pathology**: IHC staining results (EMA, vimentin, CD99, etc.)
- **Imaging**: Contrast enhancement pattern, location, invasion details
- **Treatment**: Neoadjuvant therapy, surgical approach, resection amount
- **Outcome**: Recurrence, progression-free survival, disease-free survival
- **Workup**: Preoperative biopsy
- **Post-op**: Surgical and post-op complications
- **Follow-up**: Further interventions, procedure details
- **Last Follow-up**: Follow-up duration, symptom assessment

## Technical Details

### Structured Output Format

The output format follows this JSON structure:

```json
{
  "case_results": [
    {
      "case_number": 1,
      // Fields organized by category
      "loss_of_bladder_control": true,
      "loss_of_bladder_control_confidence": {
        "value": 0.85,
        "explanation": "Mentioned clearly on page 2"
      },
      // More fields...
    }
  ],
  "truncation_info": {
    "is_truncated": false,
    "last_complete_case": 1
  }
}
```

### Gemini AI Integration

We're leveraging Gemini's structured output capabilities to enforce schema compliance:

1. The system first tries to use the structured output API with our schema
2. If that fails, it falls back to standard text generation with post-processing
3. For optimal results, use gemini-1.5-pro or gemini-2.5-flash

## Comparing Human vs. LLM Results

This integration enables direct comparison by:

1. Using identical field definitions between systems
2. Producing compatible JSON output formats
3. Allowing for field-by-field comparison of extraction accuracy
4. Tracking confidence scores for each field extracted by the LLM
5. Enabling time and quality metrics to be directly compared

## Adding/Modifying Fields

To add or modify fields:

1. Edit the column definitions through the UI (http://your-server/columns/)
2. Or modify the extraction schema JSON and re-import
3. Restart the application to update the schemas 