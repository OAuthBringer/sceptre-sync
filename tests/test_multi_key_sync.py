"""
Test for enhanced generic key/value synchronization with multi-key support.

Because syncing one key at a time is like eating M&Ms one color at a time - 
technically possible but missing the point.

This test suite defines the expected behavior for synchronizing MULTIPLE
keys in a single operation through configuration.
"""

import os
import pytest
from pathlib import Path

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestMultiKeySync:
    """Test synchronizing multiple keys in a single operation."""
    
    def test_sync_multiple_keys_from_config(self, temp_dir):
        """Test syncing multiple keys defined in config file."""
        # Config with multiple sync rules
        config_content = """
template_patterns:
  - pattern: "**/app.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcCidr
          - InstanceType
      - key: stack_tags
        sync_params:
          - Environment
          - Owner
      - key: sceptre_user_data
        sync_params:
          - database_name
          - retention_days
"""
        
        source_content = """
template: app-template.yaml
parameters:
  VpcCidr: 10.0.0.0/16
  InstanceType: t3.large
  ExtraParam: ignore-me
stack_tags:
  Environment: production
  Owner: platform-team
  Project: important
sceptre_user_data:
  database_name: prod_db
  retention_days: 30
  backup_enabled: true
"""
        
        target_content = """
template: app-template.yaml
parameters:
  VpcCidr: 10.1.0.0/16
  InstanceType: t2.micro
  LocalParam: keep-me
stack_tags:
  Environment: development
  Owner: dev-team
sceptre_user_data:
  database_name: dev_db
  retention_days: 7
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "prod/app.yaml")
        target_file = os.path.join(temp_dir, "dev/app.yaml")
        
        os.makedirs(os.path.dirname(source_file), exist_ok=True)
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        # Should sync all configured keys at once
        diff = sync.sync_parameters(
            source_file, target_file,
            dry_run=False
        )
        
        # Verify all keys were synced
        assert 'parameters' in diff
        assert 'VpcCidr' in diff['parameters']['modified']
        assert 'InstanceType' in diff['parameters']['modified']
        
        assert 'stack_tags' in diff
        assert 'Environment' in diff['stack_tags']['modified']
        assert 'Owner' in diff['stack_tags']['modified']
        
        assert 'sceptre_user_data' in diff
        assert 'database_name' in diff['sceptre_user_data']['modified']
        assert 'retention_days' in diff['sceptre_user_data']['modified']
        
        # Verify actual file changes
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # All keys should be updated
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert result['parameters']['InstanceType'] == "t3.large"
        assert result['parameters']['LocalParam'] == "keep-me"  # Unchanged
        
        assert result['stack_tags']['Environment'] == "production"
        assert result['stack_tags']['Owner'] == "platform-team"
        assert 'Project' not in result['stack_tags']  # Not in sync_params
        
        assert result['sceptre_user_data']['database_name'] == "prod_db"
        assert result['sceptre_user_data']['retention_days'] == 30
        assert 'backup_enabled' not in result['sceptre_user_data']  # Not in sync_params
    
    def test_mixed_config_with_legacy_and_multi_key(self, temp_dir):
        """Test config file that mixes old single-key and new multi-key patterns."""
        config_content = """
template_patterns:
  # New multi-key pattern
  - pattern: "**/multi/*.yaml"
    sync_rules:
      - key: parameters
        sync_params: [VpcCidr]
      - key: stack_tags
        sync_params: [Environment]
  
  # Legacy single-key pattern (backward compatibility)
  - pattern: "**/legacy/*.yaml"
    sync_params:
      - VpcCidr
      - SubnetCidr
  
  # Legacy with explicit sync_key
  - pattern: "**/tags/*.yaml"
    sync_key: stack_tags
    sync_params:
      - Environment
      - Owner
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        sync = ParamSync(config_file)
        
        # Test multi-key pattern
        rules = sync.get_sync_rules("config/multi/app.yaml")
        assert len(rules) == 2
        assert rules[0]['key'] == 'parameters'
        assert rules[0]['sync_params'] == ['VpcCidr']
        assert rules[1]['key'] == 'stack_tags'
        assert rules[1]['sync_params'] == ['Environment']
        
        # Test legacy pattern (should convert to sync_rules format)
        rules = sync.get_sync_rules("config/legacy/vpc.yaml")
        assert len(rules) == 1
        assert rules[0]['key'] == 'parameters'  # Default
        assert rules[0]['sync_params'] == ['VpcCidr', 'SubnetCidr']
        
        # Test legacy with sync_key
        rules = sync.get_sync_rules("config/tags/app.yaml")
        assert len(rules) == 1
        assert rules[0]['key'] == 'stack_tags'
        assert rules[0]['sync_params'] == ['Environment', 'Owner']
    
    def test_sync_with_delete_params_multi_key(self, temp_dir):
        """Test deletion works with multi-key sync."""
        config_content = """
template_patterns:
  - pattern: "**/cleanup.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcCidr
        delete_params:
          - OldParam
      - key: stack_tags
        sync_params:
          - Environment
        delete_params:
          - DeprecatedTag
"""
        
        source_content = """
parameters:
  VpcCidr: 10.0.0.0/16
stack_tags:
  Environment: production
"""
        
        target_content = """
parameters:
  VpcCidr: 10.1.0.0/16
  OldParam: remove-me
stack_tags:
  Environment: development
  DeprecatedTag: remove-me-too
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "cleanup.yaml")
        target_file = os.path.join(temp_dir, "cleanup.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        # Check deletions occurred
        assert 'parameters' in diff
        assert 'OldParam' in diff['parameters']['deleted']
        
        assert 'stack_tags' in diff
        assert 'DeprecatedTag' in diff['stack_tags']['deleted']
        
        # Verify file
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert 'OldParam' not in result['parameters']
        assert 'DeprecatedTag' not in result['stack_tags']
    
    def test_generate_diff_multi_key(self):
        """Test generate_diff with multiple sync rules."""
        sync = ParamSync()
        source_data = {
            "parameters": {
                "VpcCidr": "10.0.0.0/16",
                "InstanceType": "t3.large"
            },
            "stack_tags": {
                "Environment": "production",
                "Owner": "platform-team"
            }
        }
        
        target_data = {
            "parameters": {
                "VpcCidr": "10.1.0.0/16",
                "InstanceType": "t2.micro"
            },
            "stack_tags": {
                "Environment": "development"
            }
        }
        
        sync_rules = [
            {
                "key": "parameters",
                "sync_params": ["VpcCidr", "InstanceType"]
            },
            {
                "key": "stack_tags",
                "sync_params": ["Environment", "Owner"]
            }
        ]
        
        diff = sync.generate_diff_multi(
            source_data, target_data,
            sync_rules=sync_rules,
            sync_template=False
        )
        
        # Should have diffs for both keys
        assert 'parameters' in diff
        assert 'VpcCidr' in diff['parameters']['modified']
        assert 'InstanceType' in diff['parameters']['modified']
        
        assert 'stack_tags' in diff
        assert 'Environment' in diff['stack_tags']['modified']
        assert 'Owner' in diff['stack_tags']['added']
    
    def test_print_diff_multi_key(self):
        """Test diff printing with multiple keys."""
        from tests.conftest import capture_output
        
        sync = ParamSync()
        diff = {
            'parameters': {
                'added': {},
                'modified': {'VpcCidr': {'old': '10.1.0.0/16', 'new': '10.0.0.0/16'}},
                'unchanged': {},
                'deleted': {}
            },
            'stack_tags': {
                'added': {'Owner': 'platform-team'},
                'modified': {'Environment': {'old': 'dev', 'new': 'prod'}},
                'unchanged': {},
                'deleted': {}
            },
            'template': None
        }
        
        with capture_output() as (stdout, stderr):
            sync.print_diff_multi(diff)
        
        output = stdout.getvalue()
        assert "[parameters]" in output
        assert "~ VpcCidr: 10.1.0.0/16 -> 10.0.0.0/16" in output
        assert "[stack_tags]" in output
        assert "+ Owner: platform-team" in output
        assert "~ Environment: dev -> prod" in output
    
    def test_cli_multi_key_from_config(self):
        """Test CLI properly uses multi-key config."""
        from sceptre_sync.param_sync import main
        import sys
        from unittest.mock import patch, MagicMock
        
        # Mock the ParamSync class
        with patch('sceptre_sync.param_sync.ParamSync') as mock_sync_class:
            mock_instance = MagicMock()
            mock_sync_class.return_value = mock_instance
            
            # Configure the mock to return sync rules
            mock_instance.get_sync_rules.return_value = [
                {"key": "parameters", "sync_params": ["VpcCidr"]},
                {"key": "stack_tags", "sync_params": ["Environment"]}
            ]
            
            test_args = [
                "param_sync",
                "source.yaml",
                "target.yaml",
                "--config", "multi-key-config.yaml"
            ]
            
            with patch.object(sys, 'argv', test_args):
                main()
                
                # Should call sync_parameters without sync_key (using config instead)
                mock_instance.sync_parameters.assert_called_once()
                call_kwargs = mock_instance.sync_parameters.call_args.kwargs
                assert 'sync_key' not in call_kwargs or call_kwargs['sync_key'] == 'parameters'
    
    def test_nested_key_in_sync_rules(self, temp_dir):
        """Test that nested keys work in sync_rules."""
        config_content = """
template_patterns:
  - pattern: "**/nested.yaml"
    sync_rules:
      - key: config.database
        sync_params:
          - host
          - port
      - key: config.cache
        sync_params:
          - ttl
"""
        
        source_content = """
config:
  database:
    host: prod-db.example.com
    port: 5432
    password: secret
  cache:
    ttl: 3600
    size: 1024
"""
        
        target_content = """
config:
  database:
    host: dev-db.example.com
    port: 5433
  cache:
    ttl: 300
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "nested.yaml")
        target_file = os.path.join(temp_dir, "nested.target.yaml")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        # Check nested keys were synced
        assert 'config.database' in diff
        assert 'host' in diff['config.database']['modified']
        assert 'port' in diff['config.database']['modified']
        
        assert 'config.cache' in diff
        assert 'ttl' in diff['config.cache']['modified']
        
        # Verify file
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert result['config']['database']['host'] == "prod-db.example.com"
        assert result['config']['database']['port'] == 5432
        assert result['config']['cache']['ttl'] == 3600
