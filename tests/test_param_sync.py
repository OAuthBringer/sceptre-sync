"""
Test for param_sync module.

Testing the core parameter synchronization logic because YAML manipulation
is like brain surgery with a spoon - precision matters.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestParamSync:
    """Test the ParamSync class functionality."""
    
    def test_init_without_config(self):
        """Test initialization without config file."""
        sync = ParamSync()
        assert isinstance(sync.yaml, ruamel.yaml.YAML)
        assert sync.config == {}
    
    def test_init_with_config(self, temp_dir, yaml_content):
        """Test initialization with config file."""
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(yaml_content['config_with_delete'])
        
        sync = ParamSync(config_file)
        assert 'template_patterns' in sync.config
        assert len(sync.config['template_patterns']) == 2
    
    def test_load_config_file_not_found(self, temp_dir):
        """Test loading non-existent config file."""
        # This test verifies the actual error handling, not just SystemExit
        sync = ParamSync()
        non_existent_file = os.path.join(temp_dir, "definitely_does_not_exist.yaml")
        
        # Use the capture_output context manager from conftest
        from tests.conftest import capture_output
        
        with capture_output() as (stdout, stderr):
            with pytest.raises(SystemExit) as cm:
                sync.load_config(non_existent_file)
            # Verify it exits with code 1
            assert cm.value.code == 1
        
        # Verify error message was printed
        error_output = stderr.getvalue()
        assert "Error loading config file" in error_output
    
    def test_get_sync_params_with_matching_pattern(self, temp_dir, yaml_content):
        """Test getting sync parameters for matching file pattern."""
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(yaml_content['config_with_delete'])
        
        sync = ParamSync(config_file)
        params = sync.get_sync_params("config/di-alpha/vpc.yaml")
        assert params == ["VpcCidr", "PublicSubnetCidr", "PrivateSubnetCidr"]
    
    def test_get_sync_params_no_match(self, temp_dir, yaml_content):
        """Test getting sync parameters for non-matching file pattern."""
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(yaml_content['config_with_delete'])
        
        sync = ParamSync(config_file)
        params = sync.get_sync_params("config/di-alpha/database.yaml")
        assert params == []
    
    def test_get_delete_params(self, temp_dir, yaml_content):
        """Test getting delete parameters for matching file pattern."""
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(yaml_content['config_with_delete'])
        
        sync = ParamSync(config_file)
        params = sync.get_delete_params("config/di-alpha/vpc.yaml")
        assert params == ["DeprecatedParam"]
    
    def test_should_sync_template(self, temp_dir, yaml_content):
        """Test checking if template should be synced."""
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(yaml_content['config_with_delete'])
        
        sync = ParamSync(config_file)
        assert sync.should_sync_template("config/di-alpha/vpc.yaml") is True
        assert sync.should_sync_template("config/di-alpha/api/tasks.yaml") is False
    
    def test_matches_filter_simple_field(self):
        """Test filter matching with simple field."""
        data = {
            "template": {
                "path": "templates/enhanced-vpc.yaml",
                "type": "cloudformation"
            }
        }
        
        sync = ParamSync()
        assert sync.matches_filter(data, "template.path:enhanced") is True
        assert sync.matches_filter(data, "template.path:standard") is False
    
    def test_matches_filter_no_filter(self):
        """Test filter matching with no filter specified."""
        data = {"any": "data"}
        sync = ParamSync()
        assert sync.matches_filter(data, None) is True
        assert sync.matches_filter(data, "") is True
    
    def test_matches_filter_invalid_field_path(self):
        """Test filter matching with invalid field path."""
        data = {"template": {"path": "test.yaml"}}
        sync = ParamSync()
        assert sync.matches_filter(data, "template.missing:value") is False
    
    def test_load_yaml_file(self, temp_dir, yaml_content):
        """Test loading YAML file."""
        yaml_file = os.path.join(temp_dir, "test.yaml")
        with open(yaml_file, 'w') as f:
            f.write(yaml_content['vpc_source'])
        
        sync = ParamSync()
        data = sync.load_yaml_file(yaml_file)
        
        assert 'parameters' in data
        assert data['parameters']['VpcCidr'] == "10.0.0.0/16"
    
    def test_save_yaml_file(self, temp_dir, yaml_content):
        """Test saving YAML file."""
        yaml_file = os.path.join(temp_dir, "output.yaml")
        
        sync = ParamSync()
        yaml = ruamel.yaml.YAML()
        data = yaml.load(yaml_content['vpc_source'])
        
        sync.save_yaml_file(yaml_file, data)
        
        # Verify file was saved and can be loaded
        assert os.path.exists(yaml_file)
        loaded_data = sync.load_yaml_file(yaml_file)
        assert loaded_data['parameters']['VpcCidr'] == "10.0.0.0/16"
    
    def test_generate_diff_parameters_added(self, sync_result_factory):
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
        
        assert "Param2" in diff['added']
        assert diff['added']['Param2'] == "value2"
        assert len(diff['modified']) == 0
    
    def test_generate_diff_parameters_modified(self, sync_result_factory):
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
        
        assert "Param1" in diff['modified']
        assert diff['modified']['Param1']['old'] == "old_value"
        assert diff['modified']['Param1']['new'] == "new_value"
    
    def test_generate_diff_parameters_unchanged(self, sync_result_factory):
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
        
        assert "Param1" in diff['unchanged']
        assert len(diff['added']) == 0
        assert len(diff['modified']) == 0
    
    def test_generate_diff_parameters_deleted(self, sync_result_factory):
        """Test diff generation for deleted parameters."""
        sync = ParamSync()
        source_data = {"parameters": {}}
        target_data = {
            "parameters": {
                "DeprecatedParam": "to_be_deleted"
            }
        }
        
        diff = sync.generate_diff(source_data, target_data, [], ["DeprecatedParam"], False)
        
        assert "DeprecatedParam" in diff['deleted']
        assert diff['deleted']['DeprecatedParam'] == "to_be_deleted"
    
    def test_generate_diff_template_sync(self, sync_result_factory):
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
        
        assert diff['template'] is not None
        assert diff['template']['old']['path'] == "old/path.yaml"
        assert diff['template']['new']['path'] == "new/path.yaml"
    
    def test_sync_parameters_dry_run(self, temp_dir, yaml_content):
        """Test parameter synchronization in dry run mode."""
        # Create test files
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(yaml_content['vpc_source'])
        with open(target_file, 'w') as f:
            f.write(yaml_content['vpc_target'])
        
        sync = ParamSync()
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr"],
            dry_run=True
        )
        
        # Verify diff is correct
        assert "VpcCidr" in diff['modified']
        
        # Verify target file was NOT modified
        target_data = sync.load_yaml_file(target_file)
        assert target_data['parameters']['VpcCidr'] == "10.1.0.0/16"
    
    def test_sync_parameters_actual_sync(self, temp_dir, yaml_content):
        """Test parameter synchronization with actual file modification."""
        # Create test files
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(yaml_content['vpc_source'])
        with open(target_file, 'w') as f:
            f.write(yaml_content['vpc_target'])
        
        sync = ParamSync()
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr", "Environment"],
            dry_run=False
        )
        
        # Verify diff is correct
        assert "VpcCidr" in diff['modified']
        assert "Environment" in diff['modified']
        
        # Verify target file WAS modified
        target_data = sync.load_yaml_file(target_file)
        assert target_data['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert target_data['parameters']['Environment'] == "alpha"
        # Verify unsynced parameters remain unchanged
        assert target_data['parameters']['InstanceType'] == "t2.micro"
    
    def test_print_diff_no_changes(self):
        """Test diff printing with no changes."""
        from tests.conftest import capture_output
        
        sync = ParamSync()
        diff = {
            'added': {},
            'modified': {},
            'unchanged': {'Param1': 'value1'},
            'deleted': {},
            'template': None
        }
        
        with capture_output() as (stdout, stderr):
            sync.print_diff(diff)
        
        output = stdout.getvalue()
        assert "No changes to apply" in output
    
    def test_print_diff_with_changes(self):
        """Test diff printing with various changes."""
        from tests.conftest import capture_output
        
        sync = ParamSync()
        diff = {
            'added': {'NewParam': 'new_value'},
            'modified': {'ModParam': {'old': 'old_val', 'new': 'new_val'}},
            'unchanged': {},
            'deleted': {'DelParam': 'deleted_value'},
            'template': {'old': {'path': 'old.yaml'}, 'new': {'path': 'new.yaml'}}
        }
        
        with capture_output() as (stdout, stderr):
            sync.print_diff(diff)
        
        output = stdout.getvalue()
        assert "Parameters to add:" in output
        assert "+ NewParam: new_value" in output
        assert "Parameters to modify:" in output
        assert "~ ModParam: old_val -> new_val" in output
        assert "Parameters to delete:" in output
        assert "- DelParam: deleted_value" in output
        assert "Template to modify:" in output
