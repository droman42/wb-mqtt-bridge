import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from typing import Dict, Any, List

# Add parent directory to path to allow importing from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from devices.base_device import BaseDevice
from app.schemas import CommandParameterDefinition

class TestParameterValidation(unittest.TestCase):
    """Test suite for parameter validation functionality."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock device for testing
        self.device = MagicMock(spec=BaseDevice)
        # Use the actual implementation for the method under test
        self.device._resolve_and_validate_params = BaseDevice._resolve_and_validate_params.__get__(self.device, BaseDevice)
        
    def test_no_parameters_defined(self):
        """Test behavior when no parameters are defined in the command."""
        params = []  # No params defined
        provided_params = {"some_param": "value"}
        
        # Method should return provided params as is
        result = self.device._resolve_and_validate_params(params, provided_params)
        self.assertEqual(result, provided_params)
        
    def test_all_parameters_provided(self):
        """Test validation when all parameters are provided."""
        params = [
            CommandParameterDefinition(name="int_param", type="integer", required=True),
            CommandParameterDefinition(name="float_param", type="float", required=True),
            CommandParameterDefinition(name="string_param", type="string", required=True),
            CommandParameterDefinition(name="bool_param", type="boolean", required=True)
        ]
        
        provided_params = {
            "int_param": "42",  # String that should be converted to int
            "float_param": 3.14,
            "string_param": "hello",
            "bool_param": "true"  # String that should be converted to bool
        }
        
        result = self.device._resolve_and_validate_params(params, provided_params)
        
        # Check type conversions
        self.assertEqual(result["int_param"], 42)
        self.assertEqual(result["float_param"], 3.14)
        self.assertEqual(result["string_param"], "hello")
        self.assertTrue(result["bool_param"])
        
    def test_missing_required_parameter(self):
        """Test validation when a required parameter is missing."""
        params = [
            CommandParameterDefinition(name="required_param", type="string", required=True)
        ]
        
        provided_params = {}  # Empty params
        
        # Should raise ValueError for missing required parameter
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(params, provided_params)
            
        self.assertIn("required_param", str(context.exception))
        
    def test_default_values(self):
        """Test that default values are applied for missing optional parameters."""
        params = [
            CommandParameterDefinition(name="optional_param", type="integer", required=False, default=10)
        ]
        
        provided_params = {}  # No parameters provided
        
        result = self.device._resolve_and_validate_params(params, provided_params)
        
        # Should apply default value
        self.assertEqual(result["optional_param"], 10)
        
    def test_range_validation(self):
        """Test range validation for numeric parameters."""
        params = [
            CommandParameterDefinition(name="range_param", type="range", required=True, min=0, max=100)
        ]
        
        # Test valid value within range
        result = self.device._resolve_and_validate_params(params, {"range_param": 50})
        self.assertEqual(result["range_param"], 50)
        
        # Test value below minimum
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(params, {"range_param": -10})
        self.assertIn("below minimum", str(context.exception))
        
        # Test value above maximum
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(params, {"range_param": 200})
        self.assertIn("above maximum", str(context.exception))
        
    def test_autoconversion_for_single_parameter(self):
        """Test automatic conversion for a single parameter command with string input."""
        params = [
            CommandParameterDefinition(name="level", type="integer", required=True)
        ]
        
        # Provide a string that can be automatically converted to the parameter type
        provided_params = {"level": "42"}
        
        result = self.device._resolve_and_validate_params(params, provided_params)
        
        # Should convert the string to integer
        self.assertEqual(result["level"], 42)
        
    def test_invalid_type_conversion(self):
        """Test validation fails with invalid type conversion."""
        params = [
            CommandParameterDefinition(name="int_param", type="integer", required=True)
        ]
        
        # Provide a string that can't be converted to int
        provided_params = {"int_param": "not_an_int"}
        
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(params, provided_params)
        self.assertIn("invalid type", str(context.exception))
        

if __name__ == '__main__':
    unittest.main() 