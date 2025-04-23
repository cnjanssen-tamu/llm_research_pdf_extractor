def prepare_continuation_prompt(original_prompt, previous_response):
    """
    Prepare a prompt for continuing processing where the previous response was truncated.
    
    Args:
        original_prompt (str): The original prompt sent to Gemini
        previous_response (str): The truncated response from the previous request
        
    Returns:
        str: A prompt that instructs Gemini to continue from where it left off
    """
    # Option 1: Simple continuation prompt with reference point
    continuation_prompt = f"""
{original_prompt}

Your previous response was truncated. Please continue from where you left off.
For context, here is the last part of your previous response:

{previous_response[-500:]}

Continue the processing, picking up from this point.
"""
    
    return continuation_prompt 