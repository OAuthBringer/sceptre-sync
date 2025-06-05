"""
Test for config_schema module.

Testing schema validation because invalid configs are like typos in production -
they only hurt when customers find them.
"""

import unittest
import jsonschema
from sceptre_sync.config_schema import validate_config, CONFIG_SCHEMA


class TestConfigSchema(unittest.TestCase):
    """Test configuration schema validation."""
    
    def test_valid_config_passes_validation(self):
        """Test that a valid configuration passes validation."""
        valid_config = {
            "template_patterns": [
                {
                    "pattern": "*/api/tasks/*.yaml",
                    "sync_params": ["CPUReservation", "MemoryReservation"]
                }
            ]
        }
        # Should not raise an exception
        self.assertTrue(validate_config(valid_config))
    
    def test_missing_template_patterns_fails(self):
        """Test that missing template_patterns fails validation."""
        invalid_config = {}
        with self.assertRaises(jsonschema.ValidationError) as context:
            validate_config(invalid_config)
        self.assertIn("'template_patterns' is a required property", str(context.exception))
    
    def test_empty_template_patterns_is_valid(self):
        """Test that empty template_patterns array is valid."""
        config = {"template_patterns": []}
        self.assertTrue(validate_config(config))
    
    def test_missing_pattern_in_template_pattern_fails(self):
        """Test that missing pattern field fails validation."""
        invalid_config = {
            "template_patterns": [
                {
                    "sync_params": ["CPUReservation"]
                }
            ]
        }
        with self.assertRaises(jsonschema.ValidationError) as context:
            validate_config(invalid_config)
        self.assertIn("'pattern' is a required property", str(context.exception))
    
    def test_missing_sync_params_fails(self):
        """Test that missing sync_params fails validation."""
        invalid_config = {
            "template_patterns": [
                {
                    "pattern": "*.yaml"
                }
            ]
        }
        with self.assertRaises(jsonschema.ValidationError) as context:
            validate_config(invalid_config)
        self.assertIn("'sync_params' is a required property", str(context.exception))
    
    def test_invalid_sync_params_type_fails(self):
        """Test that non-array sync_params fails validation."""
        invalid_config = {
            "template_patterns": [
                {
                    "pattern": "*.yaml",
                    "sync_params": "not-an-array"
                }
            ]
        }
        with self.assertRaises(jsonschema.ValidationError) as context:
            validate_config(invalid_config)
        self.assertIn("'not-an-array' is not of type 'array'", str(context.exception))
    
    def test_non_string_sync_param_fails(self):
        """Test that non-string items in sync_params fail validation."""
        invalid_config = {
            "template_patterns": [
                {
                    "pattern": "*.yaml",
                    "sync_params": ["ValidParam", 123, "AnotherValidParam"]
                }
            ]
        }
        with self.assertRaises(jsonschema.ValidationError) as context:
            validate_config(invalid_config)
        self.assertIn("123 is not of type 'string'", str(context.exception))
    
    def test_additional_properties_allowed(self):
        """Test that additional properties in template patterns are allowed."""
        config = {
            "template_patterns": [
                {
                    "pattern": "*.yaml",
                    "sync_params": ["Param1"],
                    "description": "This is allowed",
                    "custom_field": "Also allowed"
                }
            ],
            "extra_top_level": "This is also fine"
        }
        self.assertTrue(validate_config(config))
    
    def test_schema_constants(self):
        """Test that the schema constants are properly defined."""
        self.assertIsInstance(CONFIG_SCHEMA, dict)
        self.assertIn("type", CONFIG_SCHEMA)
        self.assertEqual(CONFIG_SCHEMA["type"], "object")
        self.assertIn("required", CONFIG_SCHEMA)
        self.assertIn("template_patterns", CONFIG_SCHEMA["required"])


if __name__ == '__main__':
    unittest.main()
