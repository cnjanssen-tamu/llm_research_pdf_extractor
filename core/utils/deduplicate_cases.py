from typing import List, Dict

def calculate_case_similarity(case1: dict, case2: dict) -> float:
    """
    Calculate similarity between two cases based on their content.
    
    Args:
        case1: First case dictionary
        case2: Second case dictionary
        
    Returns:
        float: Similarity score between 0.0 and 1.0
    """
    # Simple implementation - count matching field values
    if not case1 or not case2:
        return 0.0
    
    # Get all keys in both cases
    all_keys = set(case1.keys()) | set(case2.keys())
    if not all_keys:
        return 0.0
    
    # Count matching values
    matches = 0
    total = 0
    
    for key in all_keys:
        # Skip case_number which is expected to be different
        if key == 'case_number':
            continue
            
        # Skip non-comparable keys
        if key not in case1 or key not in case2:
            continue
            
        total += 1
        
        # Compare values - handle different data types and structures
        val1 = case1[key]
        val2 = case2[key]
        
        # Handle nested dictionaries with confidence values
        if isinstance(val1, dict) and isinstance(val2, dict):
            # If both have "value" keys, compare those
            if "value" in val1 and "value" in val2:
                if str(val1["value"]).lower() == str(val2["value"]).lower():
                    matches += 1
        else:
            # Handle direct comparison
            if str(val1).lower() == str(val2).lower():
                matches += 1
    
    # Calculate similarity score
    return matches / total if total > 0 else 0.0

def deduplicate_cases(cases: List[dict], similarity_threshold: float = 0.8) -> List[dict]:
    """
    Remove duplicate cases from a list based on similarity threshold.
    
    Args:
        cases: List of case dictionaries
        similarity_threshold: Threshold to consider cases as duplicates (0.0 to 1.0)
        
    Returns:
        List[dict]: Deduplicated list of cases
    """
    if not cases:
        return []
        
    # Filter out empty cases first
    valid_cases = [case for case in cases if case and len(case) > 1]
    
    # If 0 or 1 cases, no deduplication needed
    if len(valid_cases) <= 1:
        return valid_cases
        
    # Find duplicates
    unique_cases = []
    
    for case in valid_cases:
        # Check if this case is similar to any already in unique_cases
        is_duplicate = False
        for existing in unique_cases:
            similarity = calculate_case_similarity(case, existing)
            if similarity >= similarity_threshold:
                is_duplicate = True
                break
                
        if not is_duplicate:
            unique_cases.append(case)
    
    return unique_cases 