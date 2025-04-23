from django.test import TestCase
from core.utils import validate_case_structure
from core.models import ColumnDefinition

class ValidateCaseStructureTests(TestCase):
    def setUp(self):
        # Create test columns
        self.required_column = ColumnDefinition.objects.create(
            name='required_field',
            description='Required Field',
            optional=False
        )
        self.optional_column = ColumnDefinition.objects.create(
            name='optional_field',
            description='Optional Field',
            optional=True
        )

    def test_valid_case_structure(self):
        """Test validation with valid case structure"""
        case = {
            'required_field': {
                'value': 'test value',
                'confidence': 5
            },
            'optional_field': {
                'value': 'optional value',
                'confidence': 3
            }
        }
        self.assertTrue(validate_case_structure(case))

    def test_valid_case_missing_optional(self):
        """Test validation with missing optional field"""
        case = {
            'required_field': {
                'value': 'test value',
                'confidence': 5
            }
        }
        self.assertTrue(validate_case_structure(case))

    def test_invalid_missing_required(self):
        """Test validation with missing required field"""
        case = {
            'optional_field': {
                'value': 'optional value',
                'confidence': 3
            }
        }
        self.assertFalse(validate_case_structure(case))

    def test_invalid_not_dict(self):
        """Test validation with non-dict input"""
        case = ['not', 'a', 'dict']
        self.assertFalse(validate_case_structure(case))

    def test_invalid_field_structure(self):
        """Test validation with invalid field structure"""
        # Missing 'value' key
        case = {
            'required_field': {
                'confidence': 5
            }
        }
        self.assertFalse(validate_case_structure(case))

        # Missing 'confidence' key
        case = {
            'required_field': {
                'value': 'test value'
            }
        }
        self.assertFalse(validate_case_structure(case))

        # Field value not a dict
        case = {
            'required_field': 'not a dict'
        }
        self.assertFalse(validate_case_structure(case))

    def test_invalid_confidence_value(self):
        """Test validation with invalid confidence values"""
        # Confidence too low
        case = {
            'required_field': {
                'value': 'test value',
                'confidence': 0
            }
        }
        self.assertFalse(validate_case_structure(case))

        # Confidence too high
        case = {
            'required_field': {
                'value': 'test value',
                'confidence': 6
            }
        }
        self.assertFalse(validate_case_structure(case))

        # Non-numeric confidence
        case = {
            'required_field': {
                'value': 'test value',
                'confidence': 'high'
            }
        }
        self.assertFalse(validate_case_structure(case))

    def test_empty_case(self):
        """Test validation with empty case"""
        case = {}
        self.assertFalse(validate_case_structure(case))

    def test_none_case(self):
        """Test validation with None input"""
        case = None
        self.assertFalse(validate_case_structure(case))

    def test_extra_fields(self):
        """Test validation with extra unknown fields"""
        case = {
            'required_field': {
                'value': 'test value',
                'confidence': 5
            },
            'unknown_field': {
                'value': 'extra value',
                'confidence': 3
            }
        }
        # Should still be valid as all required fields are present
        self.assertTrue(validate_case_structure(case)) 