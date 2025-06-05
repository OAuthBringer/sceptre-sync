"""
Test for param_sync module.

Testing the core parameter synchronization logic because YAML manipulation
is like brain surgery with a spoon - precision matters.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestParamSync(unittest.TestCase):
    """Test the ParamSync class functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.param_sync = ParamSync()
        
        # Sample YAML content for testing
        self.source_yaml = """
template:
  path: templates/vpc.yaml
  type: cloudformation

parameters:
  VpcCidr: "10.0.0.0/16"
  PublicSubnetCidr: "10.0.1.0/24"
  PrivateSubnetCidr: "10.0.2.0/24"
  InstanceType: "t3.micro"
  Environment: "alpha"
"""
        
        self.target_yaml = """
template:
  path: templates/vpc.yaml
  type: cloudformation

parameters:
  VpcCidr: "10.1.0.0/16"
  PublicSubnetCidr: "10.1.1.0/24"
  PrivateSubnetCidr: "10.1.2.0/24"
  InstanceType: "t2.micro"
  Environment: "dev"
"""
        
        self.config_yaml = """
template_patterns:
  - pattern: "*/vpc.yaml"
    sync_params:
      - VpcCidr
      - PublicSubnetCidr
      - PrivateSubnetCidr
    delete_params:
      - DeprecatedParam
    sync_template: true
  - pattern: "*/api/*.yaml"
    sync_params:
      - CPUReservation
      - MemoryReservation
"""
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_without_config(self):
        """Test initialization without config file."""
        sync = ParamSync()
        self.assertIsInstance(sync.yaml, ruamel.yaml.YAML)
        self.assertEqual(sync.config, {})
    
    def test_init_with_config(self):
        """Test initialization with config file."""
        config_file = os.path.join(self.temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(self.config_yaml)
        
        sync = ParamSync(config_file)
        self.assertIn('template_patterns', sync.config)
        self.assertEqual(len(sync.config['template_patterns']), 2)
    
    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        sync = ParamSync()
        with self.assertRaises(SystemExit):
            sync.load_config("non_existent_file.yaml")
    
    def test_get_sync_params_with_matching_pattern(self):
        """Test getting sync parameters for matching file pattern."""
        config_file = os.path.join(self.temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(self.config_yaml)
        
        sync = ParamSync(config_file)
        params = sync.get_sync_params("config/di-alpha/vpc.yaml")
        self.assertEqual(params, ["VpcCidr", "PublicSubnetCidr", "PrivateSubnetCidr"])
    
    def test_get_sync_params_no_match(self):
        """Test getting sync parameters for non-matching file pattern."""
        config_file = os.path.join(self.temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(self.config_yaml)
        
        sync = ParamSync(config_file)
        params = sync.get_sync_params("config/di-alpha/database.yaml")
        self.assertEqual(params, [])
    
    def test_get_delete_params(self):
        """Test getting delete parameters for matching file pattern."""
        config_file = os.path.join(self.temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(self.config_yaml)
        
        sync = ParamSync(config_file)
        params = sync.get_delete_params("config/di-alpha/vpc.yaml")
        self.assertEqual(params, ["DeprecatedParam"])
    
    def test_should_sync_template(self):
        """Test checking if template should be synced."""
        config_file = os.path.join(self.temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(self.config_yaml)
        
        sync = ParamSync(config_file)
        self.assertTrue(sync.should_sync_template("config/di-alpha/vpc.yaml"))
        self.assertFalse(sync.should_sync_template("config/di-alpha/api/tasks.yaml"))
    
    def test_matches_filter_simple_field(self):
        """Test filter matching with simple field."""
        data = {
            "template": {
                "path": "templates/enhanced-vpc.yaml",
                "type": "cloudformation"
            }
        }
        
        sync = ParamSync()
        self.assertTrue(sync.matches_filter(data, "template.path:enhanced"))
        self.assertFalse(sync.matches_filter(data, "template.path:standard"))
    
    def test_matches_filter_no_filter(self):
        """Test filter matching with no filter specified."""
        data = {"any": "data"}
        sync = ParamSync()
        self.assertTrue(sync.matches_filter(data, None))
        self.assertTrue(sync.matches_filter(data, ""))
    
    def test_matches_filter_invalid_field_path(self):
        """Test filter matching with invalid field path."""
        data = {"template": {"path": "test.yaml"}}
        sync = ParamSync()
        self.assertFalse(sync.matches_filter(data, "template.missing:value"))
    
    def test_load_yaml_file(self):
        """Test loading YAML file."""
        yaml_file = os.path.join(self.temp_dir, "test.yaml")
        with open(yaml_file, 'w') as f:
            f.write(self.source_yaml)
        
        sync = ParamSync()
        data = sync.load_yaml_file(yaml_file)
        
        self.assertIn('parameters', data)
        self.assertEqual(data['parameters']['VpcCidr'], "10.0.0.0/16")
    
    def test_save_yaml_file(self):
        """Test saving YAML file."""
        yaml_file = os.path.join(self.temp_dir, "output.yaml")
        
        sync = ParamSync()
        yaml = ruamel.yaml.YAML()
        data = yaml.load(self.source_yaml)
        
        sync.save_yaml_file(yaml_file, data)
        
        # Verify file was saved and can be loaded
        self.assertTrue(os.path.exists(yaml_file))
        loaded_data = sync.load_yaml_file(yaml_file)
        self.assertEqual(loaded_data['parameters']['VpcCidr'], "10.0.0.0/16")
    
    def test_generate_diff_parameters_added(self):
        """Test diff generation for added parameters."""
        sync = ParamSync()
        source_data = {
            "parameters": {
                "Param1": "value1",
                "Param2": "value2"
            }
        }
        target_data = {
            "parameters": {
                "Param1": "value1"
            }
        }
        
        diff = sync.generate_diff(source_data, target_data, ["Param2"], [], False)
        
        self.assertIn("Param2", diff['added'])
        self.assertEqual(diff['added']['Param2'], "value2")
        self.assertEqual(len(diff['modified']), 0)
    
    def test_generate_diff_parameters_modified(self):
        """Test diff generation for modified parameters."""
        sync = ParamSync()
        source_data = {
            "parameters": {
                "Param1": "new_value"
            }
        }
        target_data = {
            "parameters": {
                "Param1": "old_value"
            }
        }
        
        diff = sync.generate_diff(source_data, target_data, ["Param1"], [], False)
        
        self.assertIn("Param1", diff['modified'])
        self.assertEqual(diff['modified']['Param1']['old'], "old_value")
        self.assertEqual(diff['modified']['Param1']['new'], "new_value")
    
    def test_generate_diff_parameters_unchanged(self):
        """Test diff generation for unchanged parameters."""
        sync = ParamSync()
        source_data = {
            "parameters": {
                "Param1": "same_value"
            }
        }
        target_data = {
            "parameters": {
                "Param1": "same_value"
            }
        }
        
        diff = sync.generate_diff(source_data, target_data, ["Param1"], [], False)
        
        self.assertIn("Param1", diff['unchanged'])
        self.assertEqual(len(diff['added']), 0)
        self.assertEqual(len(diff['modified']), 0)
    
    def test_generate_diff_parameters_deleted(self):
        """Test diff generation for deleted parameters."""
        sync = ParamSync()
        source_data = {"parameters": {}}
        target_data = {
            "parameters": {
                "DeprecatedParam": "to_be_deleted"
            }
        }
        
        diff = sync.generate_diff(source_data, target_data, [], ["DeprecatedParam"], False)
        
        self.assertIn("DeprecatedParam", diff['deleted'])
        self.assertEqual(diff['deleted']['DeprecatedParam'], "to_be_deleted")
    
    def test_generate_diff_template_sync(self):
        """Test diff generation with template sync."""
        sync = ParamSync()
        source_data = {
            "template": {"path": "new/path.yaml"},
            "parameters": {}
        }
        target_data = {
            "template": {"path": "old/path.yaml"},
            "parameters": {}
        }
        
        diff = sync.generate_diff(source_data, target_data, [], [], True)
        
        self.assertIsNotNone(diff['template'])
        self.assertEqual(diff['template']['old']['path'], "old/path.yaml")
        self.assertEqual(diff['template']['new']['path'], "new/path.yaml")
    
    def test_sync_parameters_dry_run(self):
        """Test parameter synchronization in dry run mode."""
        # Create test files
        source_file = os.path.join(self.temp_dir, "source.yaml")
        target_file = os.path.join(self.temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(self.source_yaml)
        with open(target_file, 'w') as f:
            f.write(self.target_yaml)
        
        sync = ParamSync()
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr"],
            dry_run=True
        )
        
        # Verify diff is correct
        self.assertIn("VpcCidr", diff['modified'])
        
        # Verify target file was NOT modified
        target_data = sync.load_yaml_file(target_file)
        self.assertEqual(target_data['parameters']['VpcCidr'], "10.1.0.0/16")
    
    def test_sync_parameters_actual_sync(self):
        """Test parameter synchronization with actual file modification."""
        # Create test files
        source_file = os.path.join(self.temp_dir, "source.yaml")
        target_file = os.path.join(self.temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(self.source_yaml)
        with open(target_file, 'w') as f:
            f.write(self.target_yaml)
        
        sync = ParamSync()
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr", "Environment"],
            dry_run=False
        )
        
        # Verify diff is correct
        self.assertIn("VpcCidr", diff['modified'])
        self.assertIn("Environment", diff['modified'])
        
        # Verify target file WAS modified
        target_data = sync.load_yaml_file(target_file)
        self.assertEqual(target_data['parameters']['VpcCidr'], "10.0.0.0/16")
        self.assertEqual(target_data['parameters']['Environment'], "alpha")
        # Verify unsynced parameters remain unchanged
        self.assertEqual(target_data['parameters']['InstanceType'], "t2.micro")
    
    def test_print_diff_no_changes(self):
        """Test diff printing with no changes."""
        sync = ParamSync()
        diff = {
            'added': {},
            'modified': {},
            'unchanged': {'Param1': 'value1'},
            'deleted': {},
            'template': None
        }
        
        # Capture stdout
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        sync.print_diff(diff)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("No changes to apply", output)
    
    def test_print_diff_with_changes(self):
        """Test diff printing with various changes."""
        sync = ParamSync()
        diff = {
            'added': {'NewParam': 'new_value'},
            'modified': {'ModParam': {'old': 'old_val', 'new': 'new_val'}},
            'unchanged': {},
            'deleted': {'DelParam': 'deleted_value'},
            'template': {'old': {'path': 'old.yaml'}, 'new': {'path': 'new.yaml'}}
        }
        
        # Capture stdout
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        sync.print_diff(diff)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("Parameters to add:", output)
        self.assertIn("+ NewParam: new_value", output)
        self.assertIn("Parameters to modify:", output)
        self.assertIn("~ ModParam: old_val -> new_val", output)
        self.assertIn("Parameters to delete:", output)
        self.assertIn("- DelParam: deleted_value", output)
        self.assertIn("Template to modify:", output)


if __name__ == '__main__':
    unittest.main()
