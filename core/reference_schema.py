"""
Schema for reference extraction structured output.
This defines the JSON schema for Gemini's structured output format when extracting references.
"""

def generate_reference_schema():
    """
    Generate a JSON schema for reference extraction.
    
    Returns:
        dict: A JSON schema defining the structure for reference extraction output.
    """
    schema = {
        "type": "object",
        "properties": {
            "references": {
                "type": "array",
                "description": "Array of references extracted from the document.",
                "items": {
                    "type": "object",
                    "properties": {
                        "citation_text": {
                            "type": "string",
                            "description": "The full citation text as extracted from the document."
                        },
                        "source_type": {
                            "type": "string",
                            "description": "Type of reference (journal, book, website, report, conference, thesis, news, other, unknown).",
                            "enum": ["journal", "book", "website", "report", "conference", "thesis", "news", "other", "unknown"]
                        },
                        "authors": {
                            "type": "string",
                            "description": "Authors of the reference. Can be a string with comma-separated authors.",
                            "nullable": True
                        },
                        "title": {
                            "type": "string",
                            "description": "The title of the article, chapter, book, or webpage.",
                            "nullable": True
                        },
                        "source_name": {
                            "type": "string",
                            "description": "Name of journal, book, website, conference proceedings, etc.",
                            "nullable": True
                        },
                        "publication_year": {
                            "type": "integer",
                            "description": "Year of publication.",
                            "nullable": True
                        },
                        "volume": {
                            "type": "string",
                            "description": "Journal or book volume number.",
                            "nullable": True
                        },
                        "issue": {
                            "type": "string",
                            "description": "Journal issue number.",
                            "nullable": True
                        },
                        "pages": {
                            "type": "string",
                            "description": "Page range (e.g., '123-145') or article number.",
                            "nullable": True
                        },
                        "doi_or_url": {
                            "type": "string",
                            "description": "Digital Object Identifier or a direct URL. Prioritize DOI if available.",
                            "nullable": True
                        },
                        "confidence": {
                            "type": "integer",
                            "description": "Confidence score (0-100) for the extracted fields.",
                            "nullable": True
                        }
                    },
                    "required": ["citation_text", "source_type"]
                }
            }
        },
        "required": ["references"]
    }
    
    return schema 