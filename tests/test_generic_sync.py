"""
Test for generic key/value synchronization functionality.

Because hardcoding 'parameters' is like wearing the same underwear every day - 
it works, but there are better options.

This test suite defines the expected behavior for synchronizing ANY top-level
key in YAML files, not just 'parameters'. It follows TDD principles by being
written BEFORE the implementation exists.
"""

import os
import pytest
from pathlib import Path

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestGenericKeyValueSync:
    """Test generic key/value synchronization beyond just parameters."""
    
    def test_sync_stack_tags(self, temp_dir):
        """Test synchronizing stack_tags instead of parameters."""
        # Create source with stack_tags
        source_content = """
template: some-template.yaml
stack_tags:
  Environment: production
  Owner: platform-team
  CostCenter: engineering
parameters:
  VpcCidr: 10.0.0.0/16
"""
        
        # Create target with different stack_tags
        target_content = """
template: some-template.yaml
stack_tags:
  Environment: development
  Owner: dev-team
parameters:
  VpcCidr: 10.1.0.0/16
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # This should sync stack_tags instead of parameters
        diff = sync.sync_parameters(
            source_file, target_file,
            sync_key="stack_tags",  # NEW PARAMETER!
            params_to_sync=["Environment", "Owner", "CostCenter"],
            dry_run=False
        )
        
        # Verify stack_tags were synced
        assert "Environment" in diff['modified']
        assert "Owner" in diff['modified']
        assert "CostCenter" in diff['added']
        
        # Verify actual file changes
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert result['stack_tags']['Environment'] == "production"
        assert result['stack_tags']['Owner'] == "platform-team"
        assert result['stack_tags']['CostCenter'] == "engineering"
        # Parameters should remain unchanged
        assert result['parameters']['VpcCidr'] == "10.1.0.0/16"
    
    def test_sync_sceptre_user_data(self, temp_dir):
        """Test synchronizing sceptre_user_data section."""
        source_content = """
template: some-template.yaml
sceptre_user_data:
  database_name: prod_db
  retention_days: 30
  enable_backups: true
parameters:
  InstanceType: t3.large
"""
        
        target_content = """
template: some-template.yaml
sceptre_user_data:
  database_name: dev_db
  retention_days: 7
parameters:
  InstanceType: t2.micro
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        diff = sync.sync_parameters(
            source_file, target_file,
            sync_key="sceptre_user_data",
            params_to_sync=["database_name", "retention_days", "enable_backups"],
            dry_run=False
        )
        
        # Verify changes
        assert "database_name" in diff['modified']
        assert "retention_days" in diff['modified']
        assert "enable_backups" in diff['added']
        
        # Verify file was updated correctly
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert result['sceptre_user_data']['database_name'] == "prod_db"
        assert result['sceptre_user_data']['retention_days'] == 30
        assert result['sceptre_user_data']['enable_backups'] is True
        # Parameters unchanged
        assert result['parameters']['InstanceType'] == "t2.micro"
    
    def test_parent_child_key_syntax(self, temp_dir):
        """Test using parent.child syntax to specify sync key."""
        source_content = """
template: some-template.yaml
stack_tags:
  nested:
    Environment: production
    Region: us-east-1
parameters:
  VpcCidr: 10.0.0.0/16
"""
        
        target_content = """
template: some-template.yaml
stack_tags:
  nested:
    Environment: development
parameters:
  VpcCidr: 10.1.0.0/16
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # Use dot notation for nested keys
        diff = sync.sync_parameters(
            source_file, target_file,
            sync_key="stack_tags.nested",
            params_to_sync=["Environment", "Region"],
            dry_run=False
        )
        
        # Verify nested values were synced
        assert "Environment" in diff['modified']
        assert "Region" in diff['added']
        
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert result['stack_tags']['nested']['Environment'] == "production"
        assert result['stack_tags']['nested']['Region'] == "us-east-1"
    
    def test_config_file_with_sync_key(self, temp_dir):
        """Test config file that specifies sync_key for patterns."""
        config_content = """
template_patterns:
  - pattern: "**/stack_tags/*.yaml"
    sync_key: stack_tags
    sync_params:
      - Environment
      - Owner
      - CostCenter
  - pattern: "**/sceptre_user_data/*.yaml"
    sync_key: sceptre_user_data
    sync_params:
      - database_name
      - retention_days
  - pattern: "**/vpc.yaml"
    # No sync_key means default to 'parameters'
    sync_params:
      - VpcCidr
      - SubnetCidr
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        sync = ParamSync(config_file)
        
        # Test getting sync key for different patterns
        assert sync.get_sync_key("config/prod/stack_tags/app.yaml") == "stack_tags"
        assert sync.get_sync_key("config/prod/sceptre_user_data/db.yaml") == "sceptre_user_data"
        assert sync.get_sync_key("config/prod/vpc.yaml") == "parameters"  # default
        assert sync.get_sync_key("config/prod/unknown.yaml") == "parameters"  # default
    
    def test_backward_compatibility_default_parameters(self, temp_dir):
        """Test that omitting sync_key defaults to 'parameters' for backward compatibility."""
        source_content = """
template: some-template.yaml
parameters:
  VpcCidr: 10.0.0.0/16
  Environment: production
stack_tags:
  Owner: platform-team
"""
        
        target_content = """
template: some-template.yaml
parameters:
  VpcCidr: 10.1.0.0/16
  Environment: development
stack_tags:
  Owner: dev-team
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # Don't specify sync_key - should default to parameters
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr", "Environment"],
            dry_run=False
        )
        
        # Verify only parameters were synced
        assert "VpcCidr" in diff['modified']
        assert "Environment" in diff['modified']
        
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Parameters synced
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert result['parameters']['Environment'] == "production"
        # Stack tags unchanged
        assert result['stack_tags']['Owner'] == "dev-team"
    
    def test_sync_nonexistent_key_creates_it(self, temp_dir):
        """Test that syncing to a non-existent key creates it."""
        source_content = """
template: some-template.yaml
stack_tags:
  Environment: production
  Owner: platform-team
"""
        
        # Target doesn't have stack_tags at all
        target_content = """
template: some-template.yaml
parameters:
  VpcCidr: 10.1.0.0/16
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        diff = sync.sync_parameters(
            source_file, target_file,
            sync_key="stack_tags",
            params_to_sync=["Environment", "Owner"],
            dry_run=False
        )
        
        # All should be added since key didn't exist
        assert "Environment" in diff['added']
        assert "Owner" in diff['added']
        
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # stack_tags should be created
        assert 'stack_tags' in result
        assert result['stack_tags']['Environment'] == "production"
        assert result['stack_tags']['Owner'] == "platform-team"
        # Parameters unchanged
        assert result['parameters']['VpcCidr'] == "10.1.0.0/16"
    
    def test_generate_diff_with_custom_key(self):
        """Test generate_diff method with custom sync key."""
        sync = ParamSync()
        source_data = {
            "stack_tags": {
                "Environment": "production",
                "Owner": "platform-team"
            },
            "parameters": {
                "VpcCidr": "10.0.0.0/16"
            }
        }
        
        target_data = {
            "stack_tags": {
                "Environment": "development"
            },
            "parameters": {
                "VpcCidr": "10.1.0.0/16"
            }
        }
        
        # Generate diff for stack_tags instead of parameters
        diff = sync.generate_diff(
            source_data, target_data,
            params_to_sync=["Environment", "Owner"],
            params_to_delete=[],
            sync_template=False,
            sync_key="stack_tags"  # NEW PARAMETER!
        )
        
        assert "Environment" in diff['modified']
        assert diff['modified']['Environment']['old'] == "development"
        assert diff['modified']['Environment']['new'] == "production"
        assert "Owner" in diff['added']
        assert diff['added']['Owner'] == "platform-team"
    
    def test_cli_with_sync_key_argument(self):
        """Test that CLI accepts --sync-key argument."""
        # This tests the expected CLI interface
        # We'll need to update the argparse configuration
        from sceptre_sync.param_sync import main
        import sys
        from unittest.mock import patch
        
        test_args = [
            "param_sync",
            "source.yaml",
            "target.yaml",
            "--sync-key", "stack_tags",
            "--params", "Environment", "Owner",
            "--dry-run"
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('sceptre_sync.param_sync.ParamSync') as mock_sync:
                # This should not raise an error about unrecognized arguments
                main()
                
                # Verify sync_parameters was called with sync_key
                mock_sync.return_value.sync_parameters.assert_called_once()
                call_args = mock_sync.return_value.sync_parameters.call_args
                assert call_args.kwargs.get('sync_key') == 'stack_tags'
    
    def test_filter_with_custom_sync_key(self, temp_dir):
        """Test that filters work with custom sync keys."""
        source_content = """
template:
  path: templates/enhanced-vpc.yaml
stack_tags:
  Environment: production
  Feature: enhanced
parameters:
  VpcCidr: 10.0.0.0/16
"""
        
        target_content = """
template:
  path: templates/standard-vpc.yaml
stack_tags:
  Environment: development
parameters:
  VpcCidr: 10.1.0.0/16
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        
        # Filter by stack_tags.Feature
        diff = sync.sync_parameters(
            source_file, target_file,
            sync_key="stack_tags",
            params_to_sync=["Environment", "Feature"],
            filter_spec="stack_tags.Feature:enhanced",
            dry_run=True
        )
        
        # Should process since filter matches
        assert "Environment" in diff['modified']
        assert "Feature" in diff['added']
        
        # Try with non-matching filter
        diff2 = sync.sync_parameters(
            source_file, target_file,
            sync_key="stack_tags",
            params_to_sync=["Environment", "Feature"],
            filter_spec="stack_tags.Feature:standard",
            dry_run=True
        )
        
        # Should skip processing
        assert diff2 == {}
