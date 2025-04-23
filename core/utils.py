from .models import ColumnDefinition, JobColumnMapping  # Add this import at the top
import json
from json import JSONDecodeError
import logging
import re
from collections import defaultdict
import random
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional, Union
import pandas as pd
import os
import uuid
import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)

class StreamJSONParser:
    """Efficient streaming JSON parser for medical case data."""
    
    def __init__(self):
        self.buffer = ""
        self.stack = []
        self.cases = []
        self.current_case = {}
        self.in_string = False
        self.escape_char = False
        self.seen_cases = set()  # Track seen cases
        
    def feed(self, chunk):
        """Process a new chunk of JSON data."""
        self.buffer += chunk
        try:
            while self.buffer:
                obj = self._parse_next_object()
                if obj:
                    if 'case_results' in obj:
                        # Process each case for deduplication
                        for case in obj['case_results']:
                            if self._is_valid_case(case):
                                case_hash = self._get_case_hash(case)
                                if case_hash not in self.seen_cases:
                                    self.cases.append(case)
                                    self.seen_cases.add(case_hash)
                    elif isinstance(obj, dict) and all(k in obj for k in ['value', 'confidence']):
                        # Single case field
                        self.current_case[obj['name']] = obj
                else:
                    break
        except Exception as e:
            logger.error(f"Error parsing chunk: {str(e)}")
            logger.debug(f"Buffer content: {repr(self.buffer[:200])}")
    
    def _parse_next_object(self):
        """Parse the next complete JSON object from the buffer."""
        start_idx = self.buffer.find('{')
        if start_idx < 0:
            return None
            
        brace_count = 0
        in_string = False
        escape_char = False
        
        for i, char in enumerate(self.buffer[start_idx:], start=start_idx):
            if escape_char:
                escape_char = False
                continue
                
            if char == '\\':
                escape_char = True
                continue
                
            if char == '"' and not escape_char:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            obj = json.loads(self.buffer[start_idx:i+1])
                            self.buffer = self.buffer[i+1:]
                            return obj
                        except JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON object: {str(e)}")
                            return None
        
        return None
    
    def _is_valid_case(self, case):
        """Check if a case has enough valid data to be included."""
        if not isinstance(case, dict):
            return False
            
        # Count fields with non-empty values and good confidence
        valid_fields = 0
        total_confidence = 0
        field_count = 0
        
        for field, data in case.items():
            if isinstance(data, dict) and 'value' in data and 'confidence' in data:
                field_count += 1
                if data['value'] and data['confidence'] >= 50:  # Adjust threshold as needed
                    valid_fields += 1
                    total_confidence += data['confidence']
        
        # Require at least 25% of fields to be valid with non-zero values
        # and average confidence above 60
        return (field_count > 0 and 
                valid_fields >= field_count * 0.25 and 
                (total_confidence / field_count if field_count > 0 else 0) >= 60)
    
    def _get_case_hash(self, case):
        """Generate a unique hash for a case based on its key fields."""
        # Use key fields that should be unique for each case
        key_fields = ['0', '1', '2', '3', '4']  # Article name, DOI, author, year, case number
        hash_parts = []
        
        for field in key_fields:
            if field in case and isinstance(case[field], dict):
                value = case[field].get('value', '')
                if value:
                    hash_parts.append(str(value))
        
        # If we don't have enough identifying information, use all non-empty fields
        if len(hash_parts) < 2:
            for field, data in case.items():
                if isinstance(data, dict) and data.get('value'):
                    hash_parts.append(f"{field}:{data['value']}")
        
        return hash(','.join(hash_parts))
    
    def get_cases(self):
        """Return all complete cases parsed so far."""
        return self.cases
    
    def clear(self):
        """Reset the parser state."""
        self.buffer = ""
        self.stack = []
        self.cases = []
        self.current_case = {}
        self.seen_cases = set()

class CaseValidator:
    """Validates and filters medical case data."""
    
    def __init__(self):
        # Required fields that should have non-empty values
        self.required_fields = {
            '0': 'Article Name',
            '1': 'DOI',
            '2': 'Author',
            '3': 'Year',
            '4': 'Case Number'
        }
        
        # Fields that should be consistent within a document
        self.document_consistent_fields = ['0', '1', '2', '3']  # Article, DOI, Author, Year
        
    def validate_cases(self, cases, document_id=None):
        """Validate and filter a list of cases."""
        if not cases:
            return []
            
        # Get document-level values for consistency check
        doc_values = self._get_document_values(cases) if document_id else None
        
        valid_cases = []
        for case in cases:
            if self._is_valid_case(case, doc_values):
                valid_cases.append(case)
                
        return valid_cases
    
    def _is_valid_case(self, case, doc_values=None):
        """Check if a single case is valid."""
        if not isinstance(case, dict):
            return False
            
        # Check required fields
        missing_required = False
        for field_id in self.required_fields:
            if field_id not in case or not isinstance(case[field_id], dict):
                missing_required = True
                break
            field_data = case[field_id]
            if not field_data.get('value') or field_data.get('confidence', 0) < 50:
                missing_required = True
                break
                
        if missing_required:
            return False
            
        # Check document consistency if doc_values provided
        if doc_values:
            for field_id in self.document_consistent_fields:
                if field_id in case and field_id in doc_values:
                    case_value = case[field_id].get('value', '').strip().lower()
                    doc_value = doc_values[field_id].strip().lower()
                    if case_value and doc_value and case_value != doc_value:
                        return False
        
        # Check overall confidence
        total_confidence = 0
        field_count = 0
        valid_fields = 0
        
        for field_id, field_data in case.items():
            if isinstance(field_data, dict) and 'value' in field_data and 'confidence' in field_data:
                field_count += 1
                confidence = field_data['confidence']
                total_confidence += confidence
                if field_data['value'] and confidence >= 50:
                    valid_fields += 1
        
        # Require at least 25% valid fields and average confidence above 60
        if field_count == 0:
            return False
            
        avg_confidence = total_confidence / field_count
        valid_ratio = valid_fields / field_count
        
        return valid_ratio >= 0.25 and avg_confidence >= 60
    
    def _get_document_values(self, cases):
        """Extract consistent document-level values from cases."""
        doc_values = {}
        
        # Get most common non-empty value for each document-consistent field
        for field_id in self.document_consistent_fields:
            values = {}
            for case in cases:
                if field_id in case and isinstance(case[field_id], dict):
                    value = case[field_id].get('value', '').strip()
                    confidence = case[field_id].get('confidence', 0)
                    if value and confidence >= 80:  # Only use high-confidence values
                        values[value] = values.get(value, 0) + 1
            
            if values:
                # Get most common value
                most_common = max(values.items(), key=lambda x: x[1])[0]
                doc_values[field_id] = most_common
        
        return doc_values

def validate_case_structure(case: dict) -> bool:
    """Validates that a case has the correct structure."""
    if not isinstance(case, dict):
        return False
    
    # Check for basic required fields
    required_fields = ['case_number']
    for field in required_fields:
        if field not in case:
            return False
        if not isinstance(case[field], dict):
            return False
        if 'value' not in case[field]:
            return False
    
    return True

def calculate_case_similarity(case1: dict, case2: dict) -> float:
    """Calculate similarity between two cases based on matching fields."""
    if not isinstance(case1, dict) or not isinstance(case2, dict):
        return 0.0
    
    all_fields = set(case1.keys()) | set(case2.keys())
    matching_fields = 0
    total_fields = 0
    
    for field in all_fields:
        # Skip case_number field
        if field == 'case_number':
            continue
        
        # Skip fields that don't exist in both cases
        if field not in case1 or field not in case2:
            total_fields += 1
            continue
        
        # Both have the field, compare the values
        try:
            # Handle the case where field values are dictionaries with 'value' keys
            if (isinstance(case1[field], dict) and 'value' in case1[field] and
                isinstance(case2[field], dict) and 'value' in case2[field]):
                if case1[field]['value'] == case2[field]['value']:
                    matching_fields += 1
            # Handle the case where field values are direct values
            elif case1[field] == case2[field]:
                matching_fields += 1
        except (TypeError, KeyError):
            # Skip fields that can't be compared
            pass
        
        total_fields += 1
    
    if total_fields == 0:
        return 0.0
    
    return matching_fields / total_fields

def deduplicate_cases(cases: List[dict], similarity_threshold: float = 0.8) -> List[dict]:
    """Remove duplicate cases based on a similarity threshold."""
    if not cases:
        return []
    
    unique_cases = [cases[0]]
    
    for case in cases[1:]:
        is_duplicate = False
        for unique_case in unique_cases:
            similarity = calculate_case_similarity(case, unique_case)
            if similarity > similarity_threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_cases.append(case)
    
    return unique_cases

def generate_varied_values(base_value: Union[float, int, str], count: int, field_type: str) -> List[str]:
    """Generate varied values around a base value based on field type."""
    if field_type == 'age':
        # For age, create a normal distribution around the base value
        try:
            base_float = float(base_value)
            std_dev = max(3.0, base_float * 0.1)  # Standard deviation of ~10% of mean or at least 3
            values = np.random.normal(base_float, std_dev, count)
            values = [max(0, round(val, 1)) for val in values]  # Ensure no negative ages
            return [str(val) for val in values]
        except (ValueError, TypeError):
            # If base_value can't be converted to float, fall back to basic variation
            return [f"{base_value} (Patient {i+1})" for i in range(count)]
    
    elif field_type == 'date':
        # For dates, vary within a reasonable range (e.g., ±30 days)
        try:
            import datetime
            if isinstance(base_value, str) and len(base_value) >= 8:
                # Try to parse various date formats
                date_formats = [
                    '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
                    '%b %d, %Y', '%d %b %Y', '%B %d, %Y', '%d %B %Y'
                ]
                
                base_date = None
                for fmt in date_formats:
                    try:
                        base_date = datetime.datetime.strptime(base_value, fmt)
                        break
                    except ValueError:
                        continue
                
                if base_date:
                    # Generate dates within ±30 days
                    days_range = 60  # ±30 days
                    values = []
                    for _ in range(count):
                        day_offset = random.randint(-30, 30)
                        new_date = base_date + datetime.timedelta(days=day_offset)
                        values.append(new_date.strftime('%Y-%m-%d'))
                    return values
            
            # If we can't parse the date, fall back to the default
            return [f"{base_value} (Patient {i+1})" for i in range(count)]
        except (ImportError, ValueError, TypeError):
            return [f"{base_value} (Patient {i+1})" for i in range(count)]
    
    elif field_type == 'numeric':
        # For general numeric values, create a reasonable variation
        try:
            base_float = float(base_value)
            variance = max(1.0, base_float * 0.15)  # 15% variance or at least 1
            values = [base_float + random.uniform(-variance, variance) for _ in range(count)]
            return [str(round(val, 2)) for val in values]
        except (ValueError, TypeError):
            return [f"{base_value} (Patient {i+1})" for i in range(count)]
    
    # Default for text and other types
    return [f"{base_value} (Patient {i+1})" for i in range(count)]

def extract_distribution_info(value: str) -> List[Tuple[str, int]]:
    """
    Extract distribution information from a string like "GTR (4 cases), STR (8 cases)"
    Returns a list of (value, count) tuples
    """
    # Pattern to match value (count) patterns
    pattern = r'([^(,]+)\s*\((\d+)(?:\s*cases|\s*patients|\s*people)?\)'
    matches = re.finditer(pattern, value)
    
    distribution = []
    for match in matches:
        val = match.group(1).strip()
        count = int(match.group(2))
        distribution.append((val, count))
    
    return distribution

def extract_gender_distribution(value: str) -> Tuple[int, int]:
    """
    Extract gender distribution information from text.
    Returns a tuple of (male_count, female_count)
    """
    # Pattern for male/female distribution
    male_pattern = r'(\d+)\s*(?:male|males|m|men|man)'
    female_pattern = r'(\d+)\s*(?:female|females|f|women|woman)'
    
    male_matches = re.finditer(male_pattern, value.lower())
    female_matches = re.finditer(female_pattern, value.lower())
    
    male_count = 0
    for match in male_matches:
        male_count += int(match.group(1))
    
    female_count = 0
    for match in female_matches:
        female_count += int(match.group(1))
    
    return (male_count, female_count)

def parse_age_information(value: str) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
    """
    Parse age information from text.
    Returns (mean_age, age_range) where age_range is (min_age, max_age)
    """
    # Pattern for mean/median age
    mean_pattern = r'(?:mean|median|average|avg)(?:\s*age)?\s*(?:of|was|is)?\s*(\d+\.?\d*)'
    # Pattern for age range
    range_pattern = r'(?:age\s*range|ages|range)\s*(?:of|was|is|:)?\s*(\d+\.?\d*)\s*(?:to|-|–)\s*(\d+\.?\d*)'
    
    mean_age = None
    age_range = None
    
    # Check for mean/median
    mean_match = re.search(mean_pattern, value.lower())
    if mean_match:
        mean_age = float(mean_match.group(1))
    
    # Check for range
    range_match = re.search(range_pattern, value.lower())
    if range_match:
        min_age = float(range_match.group(1))
        max_age = float(range_match.group(2))
        age_range = (min_age, max_age)
    
    return (mean_age, age_range)

def disaggregate_summary_cases(cases: List[dict]) -> List[dict]:
    """
    Transform summary cases into individual patient cases.
    This is used when the model returns a summary instead of individual patients despite instructions.
    """
    if not cases or len(cases) == 0:
        return []
    
    # If we already have multiple cases with patient numbers, they're probably already disaggregated
    if len(cases) > 1 and all('case_number' in case and 'Patient' in case['case_number'].get('value', '') for case in cases):
        return cases
    
    # Check if this case has characteristics of a summary (indicators like "N males, M females")
    disaggregated_cases = []
    
    for case in cases:
        logging.info(f"Checking case for disaggregation: {case['case_number'].get('value', 'Unknown')}")
        
        # Skip if not a valid case structure
        if not validate_case_structure(case):
            logging.warning(f"Skipping invalid case structure")
            disaggregated_cases.append(case)
            continue
        
        # Look for indicators of a summary case
        indicators = {
            'has_gender_counts': False,
            'has_distributions': False,
            'explicit_patient_count': 0,
            'gender_counts': (0, 0)
        }
        
        # Check if this case explicitly mentions the number of patients
        patient_count = 0
        patient_count_pattern = r'(\d+)\s*(?:patients|cases|individuals|people)'
        
        # First look for patient count in the case_number field
        case_number_value = case.get('case_number', {}).get('value', '')
        patient_count_match = re.search(patient_count_pattern, case_number_value)
        if patient_count_match:
            patient_count = int(patient_count_match.group(1))
            indicators['explicit_patient_count'] = patient_count
        
        # Check fields for various summarization indicators
        for field_key, field_data in case.items():
            if not isinstance(field_data, dict) or 'value' not in field_data:
                continue
            
            value = str(field_data.get('value', ''))
            
            # Check for gender distribution
            if field_key == 'gender' or 'gender' in field_key or 'sex' in field_key:
                if ',' in value or ('male' in value.lower() and re.search(r'\d+', value)):
                    male_count, female_count = extract_gender_distribution(value)
                    if male_count > 0 or female_count > 0:
                        indicators['has_gender_counts'] = True
                        indicators['gender_counts'] = (male_count, female_count)
                        
                        # Update patient count if we found gender counts
                        if male_count + female_count > patient_count:
                            patient_count = male_count + female_count
                            indicators['explicit_patient_count'] = patient_count
            
            # Look for distribution patterns (X in N cases)
            if re.search(r'\d+\s*cases|\d+\s*patients', value):
                distribution = extract_distribution_info(value)
                if distribution:
                    indicators['has_distributions'] = True
                    
                    # Update patient count from distribution if applicable
                    total_in_distribution = sum(count for _, count in distribution)
                    if total_in_distribution > patient_count:
                        patient_count = total_in_distribution
                        indicators['explicit_patient_count'] = patient_count
        
        # If we've detected summarization indicators, disaggregate
        if indicators['has_gender_counts'] or indicators['has_distributions'] or indicators['explicit_patient_count'] > 1:
            # Determine how many cases to create
            num_cases = indicators['explicit_patient_count']
            if num_cases < 2:  # If we couldn't determine a count, default to at least 2
                num_cases = max(2, indicators['gender_counts'][0] + indicators['gender_counts'][1])
            
            logging.info(f"Disaggregating summary case into {num_cases} individual cases")
            
            # Create individual cases
            new_cases = []
            for i in range(num_cases):
                new_case = {}
                
                # Set case number
                new_case['case_number'] = {
                    'value': f"Patient {i+1}",
                    'confidence': 100
                }
                
                # Disaggregate other fields
                for field_key, field_data in case.items():
                    if field_key == 'case_number':
                        continue
                    
                    if not isinstance(field_data, dict) or 'value' not in field_data:
                        continue
                    
                    value = field_data.get('value', '')
                    confidence = field_data.get('confidence', 50)
                    
                    # Handle gender field specifically
                    if field_key == 'gender' or 'gender' in field_key or 'sex' in field_key:
                        male_count, female_count = indicators['gender_counts']
                        
                        if male_count > 0 or female_count > 0:
                            # Distribute gender based on counts
                            if i < male_count:
                                new_case[field_key] = {'value': 'M', 'confidence': 90}
                            else:
                                new_case[field_key] = {'value': 'F', 'confidence': 90}
                        else:
                            # No gender counts found, keep original or alternate
                            new_case[field_key] = {'value': value, 'confidence': confidence}
                    
                    # Handle age field with realistic distribution
                    elif field_key == 'age' or 'age' in field_key:
                        mean_age, age_range = parse_age_information(str(value))
                        
                        if age_range:
                            min_age, max_age = age_range
                            # Uniform distribution within the range
                            new_age = min_age + ((max_age - min_age) * (i / max(1, num_cases - 1)))
                            new_case[field_key] = {'value': str(round(new_age, 1)), 'confidence': 70}
                        elif mean_age:
                            # Normal distribution around the mean
                            std_dev = max(3.0, mean_age * 0.1)  # ~10% of mean or at least 3
                            # Use a deterministic approach to get varied but consistent values
                            new_age = mean_age + ((i % 5) - 2) * (std_dev / 2)
                            new_case[field_key] = {'value': str(round(new_age, 1)), 'confidence': 60}
                        else:
                            # No age information to distribute
                            new_case[field_key] = {'value': value, 'confidence': confidence}
                    
                    # Handle fields with distribution patterns (e.g., "GTR in 4 cases, STR in 8 cases")
                    elif isinstance(value, str) and re.search(r'\d+\s*cases|\d+\s*patients', value):
                        distribution = extract_distribution_info(value)
                        
                        if distribution:
                            # Calculate cumulative counts for assignment
                            cumulative = 0
                            assigned = False
                            
                            for val, count in distribution:
                                if i < cumulative + count and not assigned:
                                    new_case[field_key] = {'value': val, 'confidence': 75}
                                    assigned = True
                                cumulative += count
                            
                            # If not assigned by distribution, keep original
                            if not assigned:
                                new_case[field_key] = {'value': value, 'confidence': confidence}
                        else:
                            # No distribution pattern found
                            new_case[field_key] = {'value': value, 'confidence': confidence}
                    
                    # For other fields, either keep as is or generate variations
                    else:
                        # For numeric values, try to generate variations
                        if isinstance(value, (int, float)) or (isinstance(value, str) and re.match(r'^\d+(\.\d+)?$', value)):
                            try:
                                varied_values = generate_varied_values(
                                    value, 
                                    num_cases,
                                    'numeric' if not any(term in field_key.lower() for term in ['date', 'day', 'time']) else 'date'
                                )
                                new_case[field_key] = {
                                    'value': varied_values[i % len(varied_values)],
                                    'confidence': max(30, confidence - 20)  # Lower confidence for derived values
                                }
                            except:
                                # If variation generation fails, keep original
                                new_case[field_key] = {'value': value, 'confidence': confidence}
                        else:
                            # Non-numeric fields without specific handling, keep as is
                            new_case[field_key] = {'value': value, 'confidence': confidence}
                
                new_cases.append(new_case)
            
            # Add the disaggregated cases
            disaggregated_cases.extend(new_cases)
            
        else:
            # This doesn't look like a summary case, keep it as is
            disaggregated_cases.append(case)
    
    # Deduplicate and return
    return deduplicate_cases(disaggregated_cases)

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

def filter_cited_cases(result_data):
    """
    Filter out cases that appear to be from literature reviews or cited cases
    rather than primary cases presented in the document.
    
    Args:
        result_data (dict): The extracted JSON data with case_results
        
    Returns:
        dict: Filtered JSON data with cited cases removed
    """
    # Handle different input formats
    cases = []
    original_type = type(result_data)
    
    if not result_data:
        return result_data
        
    # Handle different ways the function might be called
    if isinstance(result_data, dict):
        if 'case_results' in result_data:
            cases = result_data['case_results']
        else:
            # Just a single case or unknown structure
            return result_data
    elif isinstance(result_data, list):
        # Sometimes called directly with the case_results list instead of the outer dict
        cases = result_data
        # Create a wrapper dict for consistent return structure
        result_data = {'case_results': cases} 
    else:
        # Unrecognized format
        return result_data
    
    original_count = len(cases) if isinstance(cases, list) else 0
    if not cases or not isinstance(cases, list):
        return result_data if isinstance(result_data, dict) else {'case_results': []}
    
    filtered_cases = []
    excluded_cases = []
    
    # Citation patterns to detect in case numbers or descriptions
    citation_patterns = [
        r'table [ivxIVX]+ -',          # "Table I -", "Table IV -", etc.
        r'\[\s*[A-Za-z]+\s*,?\s*\d{4}\s*\]',  # "[Author, 2024]", "[Smith et al., 2020]"
        r'\[\s*ref\.?\s*\d+\s*\]',      # "[Ref 12]", "[ref. 5]"
        r'literature review',           # "Literature Review Patient"
        r'previous.*?case',             # "Previous Case 3"
        r'published.*?case',            # "Published Case 2"
        r'reported by',                 # "Case reported by Smith"
        r'reference.*?case',            # "Reference Case 5"
        r'cited.*?case',                # "Cited Case 4"
        r'prior.*?case',                # "Prior Case 1"
        r'author.*? et al',             # "Author et al" 
        r'\([12]\d{3}\)',               # "(2020)", year citations
        r'et al\.',                     # "et al."
        r'review of.*?literature'       # "Review of Literature Case"
    ]
    
    for case in cases:
        # Guard against non-dictionary cases
        if not isinstance(case, dict):
            # Skip non-dict cases and log warning
            logger.warning(f"Skipping non-dict case: {type(case)}")
            continue
            
        should_exclude = False
        
        # Check case_number field - with type safety
        case_number_field = case.get('case_number')
        if isinstance(case_number_field, dict) and 'value' in case_number_field:
            case_num_value = str(case_number_field['value']).lower()
            
            # Check for citation patterns in the case number
            for pattern in citation_patterns:
                if re.search(pattern, case_num_value, re.IGNORECASE):
                    should_exclude = True
                    excluded_cases.append(case)
                    break
        
        # Check description or summary fields if they exist - with type safety
        for field_name in ['description', 'summary', 'title', 'comment', 'note']:
            if field_name not in case:
                continue
                
            field_data = case[field_name]
            # ADD DEFENSIVE TYPE CHECKING - Skip if not a dict
            if not isinstance(field_data, dict):
                continue
                
            if 'value' in field_data:
                field_value = str(field_data['value']).lower()
                
                # Check for citation patterns in the field
                for pattern in citation_patterns:
                    if re.search(pattern, field_value, re.IGNORECASE):
                        should_exclude = True
                        if case not in excluded_cases:
                            excluded_cases.append(case)
                        break
        
        # Check for other indicators of cited cases - with type safety for all fields
        for key, value in case.items():
            # ADD DEFENSIVE TYPE CHECKING
            if not isinstance(value, dict):
                continue
                
            if 'value' in value:
                field_value = str(value['value']).lower()
                
                # Look for citation indicators that might be in any field
                if re.search(r'reported by', field_value, re.IGNORECASE) and \
                   re.search(r'et al\.', field_value, re.IGNORECASE):
                    should_exclude = True
                    if case not in excluded_cases:
                        excluded_cases.append(case)
                    break
                
                # Look for year citations that indicate literature review
                if re.search(r'\(\d{4}\)', field_value) and \
                   re.search(r'reported|published|described', field_value, re.IGNORECASE):
                    should_exclude = True
                    if case not in excluded_cases:
                        excluded_cases.append(case)
                    break
        
        # Include the case if it passed all filters
        if not should_exclude:
            filtered_cases.append(case)
    
    # Update the result with filtered cases
    if isinstance(result_data, dict) and 'case_results' in result_data:
        result_data['case_results'] = filtered_cases
    elif original_type == list:
        # Return a list if that's what was passed in
        return filtered_cases
    
    # Add metadata about filtering
    filtered_count = len(filtered_cases)
    excluded_count = original_count - filtered_count
    
    if excluded_count > 0 and isinstance(result_data, dict):
        # Add filtering metadata
        result_data['filtering_metadata'] = {
            'original_case_count': original_count,
            'filtered_case_count': filtered_count,
            'excluded_case_count': excluded_count,
            'filtering_applied': True
        }
        
        # Log information about excluded cases for debugging
        if logger.isEnabledFor(logging.DEBUG):
            # Only log detailed info at debug level to avoid cluttering logs
            excluded_case_numbers = []
            for case in excluded_cases:
                if isinstance(case, dict) and 'case_number' in case:
                    case_number = case['case_number']
                    # Add type safety check
                    if isinstance(case_number, dict) and 'value' in case_number:
                        excluded_case_numbers.append(str(case_number['value']))
            
            logger.debug(f"Filtered out {excluded_count} cited cases: {', '.join(excluded_case_numbers)}")
    
    return result_data

def generate_gemini_json_schema(job):
    """
    Generates an OpenAPI schema dictionary for Gemini based on a job's columns.
    
    Args:
        job: A ProcessingJob instance
        
    Returns:
        dict: An OpenAPI schema for Gemini's structured output
    """
    # Fetch columns associated with the job
    mappings = JobColumnMapping.objects.filter(job=job).order_by('order').select_related('column')
    columns = [mapping.column for mapping in mappings]
    
    if not columns:
        # Fallback to a minimal schema if no columns are defined
        logger.warning(f"Job {job.id} has no columns defined for schema generation.")
        return {
            'type': 'object',
            'properties': {
                'extracted_text': {'type': 'string', 'description': 'Full text extracted from the document.'}
            },
            'required': ['extracted_text']
        }
    
    # Define the schema for a single extracted field (value + confidence)
    field_schema_props = {
        "value": {
            "type": "string",  # Default to string, will be adjusted based on data_type
            "description": "The extracted value for the field."
        },
        "confidence": {
            "type": "integer",
            "description": "Confidence score (0-100) for the extraction.",
            "minimum": 0,
            "maximum": 100
        }
    }
    
    # Define properties for a single case based on columns
    case_properties = {}
    required_case_fields = []
    
    for col in columns:
        # Map Django model types to JSON schema types
        json_type = 'string'  # Default
        if col.data_type == 'integer':
            json_type = 'integer'
        elif col.data_type == 'float':
            json_type = 'number'
        elif col.data_type == 'boolean':
            json_type = 'boolean'
        elif col.data_type == 'date':
            json_type = 'string'  # Dates are represented as strings in JSON
        
        # Create the field schema
        col_field_schema = {
            "type": "object",
            "description": col.description or f"Data for {col.name}",
            "properties": {
                "value": {
                    "type": json_type,
                    "description": "The extracted value."
                },
                "confidence": field_schema_props["confidence"]
            },
            "required": ["value", "confidence"]
        }
        
        # Add enum constraint if applicable
        if col.data_type == 'enum' and col.enum_values:
            col_field_schema['properties']['value']['enum'] = col.enum_values
        
        # Add to case properties
        case_properties[col.name] = col_field_schema
        
        # Decide which fields are required within a case
        if col.name == 'case_number' or not col.optional:
            required_case_fields.append(col.name)
    
    # Define the schema for a single case object
    single_case_schema = {
        "type": "object",
        "properties": case_properties,
        "required": required_case_fields
    }
    
    # Define the overall top-level schema (list of cases)
    output_schema = {
        "type": "object",
        "properties": {
            "case_results": {
                "type": "array",
                "description": "An array of extracted patient case objects.",
                "items": single_case_schema
            }
        },
        "required": ["case_results"]
    }
    
    return output_schema