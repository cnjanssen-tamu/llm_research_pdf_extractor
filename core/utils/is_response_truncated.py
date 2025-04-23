import re

def is_response_truncated(text):
    """
    Check if the Gemini response appears to be truncated.
    
    Args:
        text (str): The response text from Gemini
        
    Returns:
        bool: True if the response appears truncated, False otherwise
    """
    # Check for obvious truncation indicators
    if not text:
        return False
        
    # Check if the response ends mid-sentence (no period at the end)
    if not text.rstrip().endswith(('.', '!', '?', ']', '}', '"')):
        return True
        
    # Check for incomplete JSON
    if re.search(r'```json\s*\{[\s\S]*', text) and not re.search(r'```json\s*\{[\s\S]*\}\s*```', text):
        return True
        
    # Check for unbalanced braces in the last 500 characters (focusing on the end where truncation occurs)
    text_sample = text[-500:] if len(text) > 500 else text
    open_braces = text_sample.count('{')
    close_braces = text_sample.count('}')
    
    if open_braces > close_braces:
        return True
        
    # Check for unbalanced JSON array brackets
    open_brackets = text_sample.count('[')
    close_brackets = text_sample.count(']')
    
    if open_brackets > close_brackets:
        return True
        
    # Check for incomplete code blocks
    code_block_starts = len(re.findall(r'```(?:json)?', text))
    code_block_ends = text.count('```') - code_block_starts
    
    if code_block_starts > code_block_ends:
        return True
        
    return False 