import re
import json

def extract_json_from_text(text):
    """
    Extract JSON object from text response, with enhanced error handling and cleaning.
    
    Args:
        text (str): Text potentially containing JSON
        
    Returns:
        dict or None: Extracted JSON as a dictionary, or None if extraction fails
    """
    if not text:
        return None
    
    # First attempt - find standard JSON markers
    try:
        # Look for JSON within the text using common patterns
        json_pattern = r'({[\s\S]*})'
        match = re.search(json_pattern, text)
        
        if match:
            json_text = match.group(1)
            # Clean common issues before parsing
            json_text = _clean_json_response(json_text)
            return json.loads(json_text)
    except Exception:
        pass  # Continue with other methods
    
    # Second attempt - try to extract JSON with more aggressive cleaning
    try:
        # First clean the text to handle common issues
        cleaned_text = _clean_json_response(text)
        
        # Try loading as is first (might be clean JSON already)
        try:
            return json.loads(cleaned_text)
        except:
            pass
        
        # Try to identify JSON blocks with more sophisticated pattern
        json_pattern = r'({[\s\S]*?})(?:\s*$|\s*```)'
        json_matches = re.findall(json_pattern, cleaned_text)
        
        # Try each potential JSON match
        for potential_json in json_matches:
            try:
                if len(potential_json) > 50:  # Avoid tiny fragments
                    result = json.loads(potential_json)
                    if isinstance(result, dict) and len(result) > 0:
                        return result
            except:
                continue
    except Exception:
        pass
    
    # Last resort - very aggressive JSON extraction
    try:
        # Try to find the largest block that looks like JSON
        # Look for opening braces and attempt to find balanced closing braces
        if '{' in text:
            start_idx = text.find('{')
            # Find closing brace, accounting for nested structures
            depth = 0
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        # We found a balanced JSON-like structure
                        json_candidate = text[start_idx:i+1]
                        try:
                            cleaned = _clean_json_response(json_candidate)
                            return json.loads(cleaned)
                        except:
                            pass
    except Exception:
        pass
    
    # If all extraction methods fail, return None
    return None

def _clean_json_response(text):
    """
    Clean JSON response text to handle common issues.
    
    Args:
        text (str): Text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return text
    
    # Convert to string if not already
    if not isinstance(text, str):
        text = str(text)
    
    # Replace common markdown code block markers
    text = re.sub(r'```json', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove trailing commas before closing brackets (common JSON error)
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    
    # Remove code comments that might be in the JSON
    text = re.sub(r'//.*?[\n\r]', '\n', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    
    # Remove "// ... other" and similar truncation markers
    text = re.sub(r'//\s*\.{3}\s*\w*', '', text)
    text = re.sub(r'//\.{3}', '', text)
    
    # Replace special quotes with standard quotes
    text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    
    # Handle cases where JSON might be incomplete at the end
    if text.count('{') > text.count('}'):
        missing = text.count('{') - text.count('}')
        text += '}' * missing
    
    # Handle cases where JSON might have unescaped quotes in string values
    # This is more complex and might require more sophisticated handling in specific cases
    
    return text.strip() 