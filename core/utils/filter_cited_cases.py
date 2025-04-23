import re
import logging
from typing import List, Dict, Union, Any, Tuple

logger = logging.getLogger(__name__) # Make sure you have logging configured

def filter_cited_cases(result_data: Union[Dict, List]) -> Union[Dict, List]:
    """
    Filter out cases that appear to be from literature reviews or cited cases
    rather than primary cases presented in the document. Adds robustness
    against unexpected data structures.

    Args:
        result_data: Dictionary containing 'case_results' list or just the list of cases.

    Returns:
        The input data structure (dict or list) with cited cases filtered out.
        If input was a dict, includes 'filtering_metadata'.
    """
    cases = []
    input_was_dict = False
    original_result_data = result_data # Keep original structure reference

    # --- 1. Extract the list of cases safely ---
    if isinstance(result_data, dict):
        input_was_dict = True
        if 'case_results' in result_data and isinstance(result_data['case_results'], list):
            cases = result_data['case_results']
        else:
            logger.warning("filter_cited_cases received a dict but 'case_results' is missing or not a list.")
            # Return original data as we can't process it
            return original_result_data
    elif isinstance(result_data, list):
        cases = result_data
    else:
        logger.warning(f"filter_cited_cases received unexpected data type: {type(result_data)}")
        return original_result_data # Return original if format is wrong

    original_count = len(cases)
    if original_count == 0:
        logger.debug("filter_cited_cases: No cases to filter.")
        return original_result_data # Return original structure (empty or with other keys)

    # --- 2. Define Helper Function with Robust Checks ---
    def is_likely_cited_case(case: Dict) -> Tuple[bool, str]:
        """
        Check if a case is likely from a literature review/citation.
        Adds type checking for robustness.
        Returns (is_cited, reason).
        """
        # *** Robustness Check: Ensure case is a dictionary ***
        if not isinstance(case, dict):
            logger.warning(f"Skipping non-dictionary item found in case list: {type(case)}")
            return (False, "Item was not a dictionary") # Don't filter non-dicts, but log

        citation_score = 0
        review_score = 0
        debug_reasons = [] # Store reasons for exclusion

        # Patterns for citations (more specific)
        citation_patterns = [
            # Specific formats like Author et al., YYYY or [Ref Num]
            (r'\b[A-Z][a-z]+ et al\.?,? \d{4}\b', 2), # Strong indicator
            (r'\b[A-Z][a-z]+ and [A-Z][a-z]+,? \d{4}\b', 2), # Strong indicator
            (r'\[\d+(?:,\s*\d+)*\]', 1.5), # [1] or [1, 2]
            (r'\bRef\.?\s*\d+', 1.5), # Ref. 12
            (r'Table [IVXLCDM]+', 1), # Table I, Table IV etc. (can be primary table sometimes)
            (r'\(\s?\d{4}\s?\)', 0.5), # (YYYY) - lower score, could be year of diagnosis
        ]
        # Keywords suggesting review/summary context
        review_keywords = [
            (r'\bliterature review\b', 2),
            (r'\bpublished case[s]?\b', 1.5),
            (r'\breported by\b', 1),
            (r'\bprevious stud(y|ies)\b', 1),
            (r'\bprior case[s]?\b', 1),
            (r'\bsummar(y|ies)\b', 0.5),
            (r'\bcomparison\b', 0.5),
            (r'\bcited in\b', 1.5),
        ]

        # Process fields, focusing on text content
        for key, field_data in case.items():
            field_text = None
            # *** Robustness Check: Extract text value safely ***
            if isinstance(field_data, dict) and 'value' in field_data:
                field_text = str(field_data.get('value', ''))
            elif isinstance(field_data, str):
                 field_text = field_data # Handle direct string values if they occur
            elif isinstance(field_data, (int, float, bool)):
                 field_text = str(field_data)
            elif isinstance(field_data, list):
                 # If it's a list, join elements for searching (or check each item)
                 try:
                    field_text = " ".join(map(str, field_data))
                 except TypeError:
                     field_text = "" # Cannot convert list elements to string

            if not field_text:
                continue # Skip empty fields

            # Check for citation patterns
            for pattern, score in citation_patterns:
                if re.search(pattern, field_text, re.IGNORECASE):
                    citation_score += score
                    debug_reasons.append(f"Citation pattern '{pattern}' in field '{key}'")

            # Check for review keywords
            for keyword, score in review_keywords:
                 if re.search(keyword, field_text, re.IGNORECASE):
                     review_score += score
                     debug_reasons.append(f"Review keyword '{keyword}' in field '{key}'")

        # Check case_number specifically, higher weight if it looks like a citation
        case_number_field = case.get('case_number')
        if isinstance(case_number_field, dict) and 'value' in case_number_field:
            case_num_text = str(case_number_field['value'])
            for pattern, score in citation_patterns:
                 # Give extra weight if case number itself contains strong citation
                 if re.search(pattern, case_num_text, re.IGNORECASE) and score >= 1.5:
                    citation_score += 1.5
                    debug_reasons.append(f"Strong citation pattern '{pattern}' in 'case_number'")
            for keyword, score in review_keywords:
                 if re.search(keyword, case_num_text, re.IGNORECASE):
                     review_score += 1 # Extra weight for review keywords in case number
                     debug_reasons.append(f"Review keyword '{keyword}' in 'case_number'")


        # Determine if case is likely cited based on scores
        # Adjust thresholds as needed based on testing
        is_cited = citation_score >= 2 or review_score >= 2.5 or (citation_score >= 1 and review_score >= 1.5)

        reason_str = "; ".join(debug_reasons) if is_cited else "Not cited"
        return (is_cited, reason_str)

    # --- 3. Filter the cases ---
    filtered_cases = []
    excluded_cases_info = [] # Store info about excluded cases for logging

    for case in cases:
        is_cited, reason = is_likely_cited_case(case)
        if is_cited:
             case_num = "N/A"
             if isinstance(case, dict) and 'case_number' in case and isinstance(case.get('case_number'), dict):
                 case_num = case['case_number'].get('value', "N/A")
             excluded_cases_info.append({'case_number': case_num, 'reason': reason})
        else:
            filtered_cases.append(case)

    # --- 4. Log excluded cases ---
    excluded_count = original_count - len(filtered_cases)
    if excluded_count > 0:
        logger.info(f"filter_cited_cases: Excluded {excluded_count} potential cited/review cases out of {original_count}.")
        for info in excluded_cases_info:
            logger.debug(f"  - Excluded Case: {info['case_number']} | Reason: {info['reason']}")
    else:
        logger.debug("filter_cited_cases: No cases were filtered out as cited/review.")

    # --- 5. Handle Fallback and Prepare Return ---
    final_cases = filtered_cases
    # Decision: Don't return original if all filtered, as that's confusing.
    # If filtering seems wrong, the logic/thresholds need adjustment.
    # if not filtered_cases and cases:
    #     logger.warning("All cases were filtered out as cited. Returning original list, but filtering logic might need review.")
    #     final_cases = cases # Reverting to original list if all are filtered

    # Add metadata if the input was a dictionary
    if input_was_dict:
        # Ensure the original dict structure is preserved, update 'case_results'
        original_result_data['case_results'] = final_cases
        # Add/update filtering metadata
        original_result_data['filtering_metadata'] = {
            'original_case_count': original_count,
            'filtered_case_count': len(final_cases),
            'excluded_case_count': excluded_count,
            'filtering_applied': True
        }
        return original_result_data
    else:
        # If input was a list, return the filtered list
        return final_cases 