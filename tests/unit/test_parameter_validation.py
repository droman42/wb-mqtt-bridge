import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from typing import Dict, Any

# Add parent directory to path to allow importing from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from devices.base_device import BaseDevice

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
        cmd_config = {"name": "test_command"}  # No params defined
        provided_params = {"some_param": "value"}
        
        # Method should return provided params as is
        result = self.device._resolve_and_validate_params(cmd_config, provided_params)
        self.assertEqual(result, provided_params)
        
    def test_all_parameters_provided(self):
        """Test validation when all parameters are provided."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "int_param", "type": "integer", "required": True},
                {"name": "float_param", "type": "float", "required": True},
                {"name": "string_param", "type": "string", "required": True},
                {"name": "bool_param", "type": "boolean", "required": True}
            ]
        }
        
        provided_params = {
            "int_param": "42",  # String that should be converted to int
            "float_param": 3.14,
            "string_param": "hello",
            "bool_param": "true"  # String that should be converted to bool
        }
        
        result = self.device._resolve_and_validate_params(cmd_config, provided_params)
        
        # Check type conversions
        self.assertEqual(result["int_param"], 42)
        self.assertEqual(result["float_param"], 3.14)
        self.assertEqual(result["string_param"], "hello")
        self.assertTrue(result["bool_param"])
        
    def test_missing_required_parameter(self):
        """Test validation when a required parameter is missing."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "required_param", "type": "string", "required": True}
            ]
        }
        
        provided_params = {}  # Empty params
        
        # Should raise ValueError for missing required parameter
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(cmd_config, provided_params)
            
        self.assertIn("required_param", str(context.exception))
        
    def test_default_values(self):
        """Test that default values are applied for missing optional parameters."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "optional_param", "type": "integer", "required": False, "default": 10}
            ]
        }
        
        provided_params = {}  # No parameters provided
        
        result = self.device._resolve_and_validate_params(cmd_config, provided_params)
        
        # Should apply default value
        self.assertEqual(result["optional_param"], 10)
        
    def test_range_validation(self):
        """Test range validation for numeric parameters."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "range_param", "type": "range", "required": True, "min": 0, "max": 100}
            ]
        }
        
        # Test valid value within range
        result = self.device._resolve_and_validate_params(cmd_config, {"range_param": 50})
        self.assertEqual(result["range_param"], 50)
        
        # Test value below minimum
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(cmd_config, {"range_param": -10})
        self.assertIn("below minimum", str(context.exception))
        
        # Test value above maximum
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(cmd_config, {"range_param": 200})
        self.assertIn("above maximum", str(context.exception))
        
    def test_raw_payload_conversion(self):
        """Test raw payload conversion for single-parameter commands."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "level", "type": "integer", "required": True}
            ]
        }
        
        # No parameters provided, but raw payload is
        provided_params = {}
        raw_payload = "42"
        
        result = self.device._resolve_and_validate_params(cmd_config, provided_params, raw_payload)
        
        # Should convert raw payload to parameter
        self.assertEqual(result["level"], 42)
        
    def test_raw_payload_with_multiple_params(self):
        """Test that raw payload is not used when multiple parameters are defined."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "param1", "type": "integer", "required": True},
                {"name": "param2", "type": "string", "required": True}
            ]
        }
        
        # No parameters provided
        provided_params = {}
        raw_payload = "42"
        
        # Should raise ValueError since multiple parameters are defined and can't be derived from a single payload
        with self.assertRaises(ValueError):
            self.device._resolve_and_validate_params(cmd_config, provided_params, raw_payload)
        
    def test_invalid_type_conversion(self):
        """Test validation fails with invalid type conversion."""
        cmd_config = {
            "name": "test_command",
            "params": [
                {"name": "int_param", "type": "integer", "required": True}
            ]
        }
        
        # Provide a string that can't be converted to int
        provided_params = {"int_param": "not_an_int"}
        
        with self.assertRaises(ValueError) as context:
            self.device._resolve_and_validate_params(cmd_config, provided_params)
        self.assertIn("invalid type", str(context.exception))
        

if __name__ == '__main__':
    unittest.main() 