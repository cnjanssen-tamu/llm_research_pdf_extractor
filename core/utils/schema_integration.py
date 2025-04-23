"""
Utility module for integrating column definitions with LLM prompting.
This helps generate structured output instructions for the LLM.
"""

import json
from core.models import ColumnDefinition
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

def generate_schema_instructions():
    """
    Generate structured output schema instructions for the LLM based on all current column definitions.
    
    Returns:
        str: Formatted schema instructions for LLM
    """
    columns = ColumnDefinition.objects.filter(active=True).order_by('category', 'display_order', 'name')
    
    if not columns:
        return "Extract data into a structured format with patient demographics, symptoms, and diagnostic details."
    
    # Generate schema instructions
    instructions = "Extract the following fields for each patient case:\n\n"
    
    # Group by category
    categories = {}
    for col in columns:
        if col.category not in categories:
            categories[col.category] = []
        categories[col.category].append(col)
    
    # Generate instructions for each category
    for category, cols in categories.items():
        category_display = category.replace('_', ' ').title()
        instructions += f"## {category_display}\n"
        
        for col in cols:
            instructions += f"- {col.name}: {col.description}"
            if col.data_type == 'enum' and col.enum_values:
                instructions += f" (Valid values: {', '.join(col.enum_values)})"
            instructions += "\n"
        
        instructions += "\n"
    
    # Close the schema structure
    instructions += "Please ensure all extracted data is accurately derived from the document."
    
    return instructions

def generate_gemini_schema():
    """
    Generate a structured schema specifically formatted for Gemini's structured output.
    This follows Gemini's JSON Schema format for defining structured outputs.
    
    Returns:
        dict: A JSON schema definition for Gemini
    """
    columns = ColumnDefinition.objects.filter(active=True).order_by('category', 'display_order', 'name')
    
    if not columns:
        # Return a minimal default schema if no columns are defined
        return {
            "type": "object",
            "properties": {
                "case_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "case_number": {"type": "integer"},
                            "patient_demographics": {"type": "string"},
                            "clinical_findings": {"type": "string"},
                            "diagnosis": {"type": "string"},
                            "treatment": {"type": "string"}
                        },
                        "required": ["case_number"]
                    }
                }
            },
            "required": ["case_results"]
        }
    
    # Group columns by category
    categories = {}
    for col in columns:
        if col.category not in categories:
            categories[col.category] = []
        categories[col.category].append(col)
    
    # Map our field types to JSON schema types
    type_mapping = {
        'string': 'string',
        'text': 'string',
        'integer': 'integer',
        'float': 'number',
        'boolean': 'boolean',
        'date': 'string',
        'enum': 'string'
    }
    
    # Create properties for each column
    properties = {
        "case_number": {"type": "integer", "description": "Sequential number for this case within the document"}
    }
    
    for category, cols in categories.items():
        for col in cols:
            schema_type = type_mapping.get(col.data_type, 'string')
            
            prop = {
                "type": schema_type,
                "description": col.description or f"The {col.name.replace('_', ' ')}"
            }
            
            # Handle enum type
            if col.data_type == 'enum' and col.enum_values:
                prop["enum"] = col.enum_values
            
            properties[col.name] = prop
    
    # Build the complete schema
    schema = {
        "type": "object",
        "properties": {
            "case_results": {
                "type": "array",
                "description": "List of extracted patient cases",
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": ["case_number"]
                }
            }
        },
        "required": ["case_results"]
    }
    
    return schema

def map_django_type_to_gemini_type(django_type):
    """
    Map our data types to Gemini schema types.
    
    Args:
        django_type (str): The Django field type
        
    Returns:
        str: The corresponding Gemini schema type
    """
    mapping = {
        'string': 'string',
        'text': 'string',
        'integer': 'integer',
        'float': 'number',
        'boolean': 'boolean',
        'date': 'string',
        'enum': 'string'
    }
    return mapping.get(django_type, 'string')

def get_field_example(column):
    """
    Generate an example value for a field based on its data type.
    
    Args:
        column (ColumnDefinition): The column definition
        
    Returns:
        str: Example value representation
    """
    if column.data_type == 'string':
        return '"Example text value"'
    elif column.data_type == 'integer':
        return '42'
    elif column.data_type == 'float':
        return '3.14'
    elif column.data_type == 'date':
        return '"2023-04-15"'
    elif column.data_type == 'boolean':
        return 'true'
    elif column.data_type == 'enum':
        if column.enum_values and len(column.enum_values) > 0:
            return f'"{column.enum_values[0]}"'
        return '"Option1"'
    else:
        return '"Value"'


def get_category_display_name(category_code):
    """
    Get the display name for a category code.
    
    Args:
        category_code (str): The category code
        
    Returns:
        str: The display name
    """
    category_map = {
        'demographics': 'Demographics Information',
        'clinical': 'Clinical Information',
        'pathology': 'Pathology Information',
        'treatment': 'Treatment Information',
        'outcome': 'Outcome Information',
        'presentation': 'Presentation Information',
        'symptoms': 'Signs and Symptoms',
        'imaging': 'Imaging Information',
        'workup': 'Workup Information',
        'intervention': 'Intervention Details',
        'postop': 'Immediate Post-op Outcomes',
        'followup': 'Follow-up Information',
        'lastfollowup': 'Last Follow-up Information',
    }
    
    return category_map.get(category_code, category_code.title()) 