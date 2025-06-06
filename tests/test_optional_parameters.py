"""
Test for optional parameters support.

Because not every YAML file needs a parameters section - sometimes they're just
templates, or only have stack_tags, or are minimalist by nature.

This test suite defines the expected behavior for handling YAML files without
a parameters section, following TDD principles.
"""

import os
import pytest
from pathlib import Path

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestOptionalParameters:
    """Test handling of YAML files without parameters section."""
    
    def test_sync_file_without_parameters_section(self, temp_dir):
        """Test syncing when source has parameters but target doesn't."""
        # Source has parameters
        source_content = """
template: some-template.yaml
parameters:
  VpcCidr: 10.0.0.0/16
  Environment: production
stack_tags:
  Owner: platform-team
"""
        
        # Target has no parameters section at all
        target_content = """
template: some-template.yaml
stack_tags:
  Owner: dev-team
  Project: test
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # This should NOT fail even though target has no parameters
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr", "Environment"],
            dry_run=False
        )
        
        # Should create parameters section in target
        assert "VpcCidr" in diff['added']
        assert "Environment" in diff['added']
        
        # Verify file was updated
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert 'parameters' in result
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert result['parameters']['Environment'] == "production"
        # Other sections unchanged
        assert result['stack_tags']['Owner'] == "dev-team"
    
    def test_sync_when_neither_file_has_parameters(self, temp_dir):
        """Test syncing when neither file has parameters section."""
        source_content = """
template: some-template.yaml
stack_tags:
  Environment: production
"""
        
        target_content = """
template: some-template.yaml
stack_tags:
  Environment: development
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # Should handle gracefully - no parameters to sync
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr"],
            dry_run=True
        )
        
        # No changes since neither has the requested parameter
        assert len(diff['added']) == 0
        assert len(diff['modified']) == 0
        assert len(diff['deleted']) == 0
    
    def test_delete_params_when_target_has_no_parameters(self, temp_dir):
        """Test delete operation when target has no parameters section."""
        source_content = """
template: some-template.yaml
sceptre_user_data:
  database: prod-db
"""
        
        target_content = """
template: some-template.yaml
sceptre_user_data:
  database: dev-db
"""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # Should not fail when trying to delete from non-existent section
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_delete=["OldParam"],
            dry_run=True
        )
        
        # No deletions since section doesn't exist
        assert len(diff['deleted']) == 0
    
    def test_multi_key_sync_with_missing_sections(self, temp_dir):
        """Test multi-key sync when some sections are missing."""
        config_content = """
template_patterns:
  - pattern: "**/mixed.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcCidr
      - key: stack_tags
        sync_params:
          - Environment
      - key: sceptre_user_data
        sync_params:
          - database_name
"""
        
        # Source has all sections
        source_content = """
template: mixed-template.yaml
parameters:
  VpcCidr: 10.0.0.0/16
stack_tags:
  Environment: production
sceptre_user_data:
  database_name: prod_db
"""
        
        # Target missing parameters and sceptre_user_data
        target_content = """
template: mixed-template.yaml
stack_tags:
  Environment: development
  Owner: dev-team
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "mixed.yaml")
        target_file = os.path.join(temp_dir, "mixed.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        # Should handle missing sections gracefully
        assert 'parameters' in diff
        assert 'VpcCidr' in diff['parameters']['added']
        
        assert 'stack_tags' in diff
        assert 'Environment' in diff['stack_tags']['modified']
        
        assert 'sceptre_user_data' in diff
        assert 'database_name' in diff['sceptre_user_data']['added']
        
        # Verify file has all sections now
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert 'parameters' in result
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert 'sceptre_user_data' in result
        assert result['sceptre_user_data']['database_name'] == "prod_db"
    
    def test_generate_diff_handles_missing_keys(self):
        """Test generate_diff when sync_key doesn't exist in data."""
        sync = ParamSync()
        
        # Source has the key
        source_data = {
            "parameters": {
                "VpcCidr": "10.0.0.0/16"
            }
        }
        
        # Target missing the key entirely
        target_data = {
            "template": "some-template.yaml"
        }
        
        diff = sync.generate_diff(
            source_data, target_data,
            params_to_sync=["VpcCidr"],
            params_to_delete=[],
            sync_template=False,
            sync_key="parameters"
        )
        
        # Should treat as all parameters being added
        assert "VpcCidr" in diff['added']
        assert diff['added']['VpcCidr'] == "10.0.0.0/16"
    
    def test_sync_nonexistent_nested_key(self, temp_dir):
        """Test syncing a nested key that doesn't exist in target."""
        source_content = """
config:
  database:
    host: prod-db.example.com
    port: 5432
  cache:
    ttl: 3600
"""
        
        # Target missing entire config.database section
        target_content = """
config:
  cache:
    ttl: 300
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
            sync_key="config.database",
            params_to_sync=["host", "port"],
            dry_run=False
        )
        
        # Should add the missing nested structure
        assert "host" in diff['added']
        assert "port" in diff['added']
        
        # Verify nested structure was created
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert 'config' in result
        assert 'database' in result['config']
        assert result['config']['database']['host'] == "prod-db.example.com"
        assert result['config']['database']['port'] == 5432
        # Original cache settings preserved
        assert result['config']['cache']['ttl'] == 300
    
    def test_empty_yaml_files(self, temp_dir):
        """Test handling completely empty YAML files."""
        source_content = """
parameters:
  VpcCidr: 10.0.0.0/16
"""
        
        # Completely empty file
        target_content = ""
        
        source_file = os.path.join(temp_dir, "source.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync()
        # Should handle empty file gracefully
        diff = sync.sync_parameters(
            source_file, target_file,
            params_to_sync=["VpcCidr"],
            dry_run=False
        )
        
        assert "VpcCidr" in diff['added']
        
        # Verify file now has content
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        assert result is not None
        assert 'parameters' in result
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
    
    def test_yaml_with_only_comments(self, temp_dir):
        """Test YAML files that only contain comments."""
        source_content = """
# Production configuration
parameters:
  Environment: production
"""
        
        target_content = """
# Development configuration
# This file intentionally has no parameters yet
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
            params_to_sync=["Environment"],
            dry_run=False
        )
        
        assert "Environment" in diff['added']
        
        # Verify comments are preserved
        with open(target_file, 'r') as f:
            content = f.read()
        
        assert "# Development configuration" in content
        assert "# This file intentionally has no parameters yet" in content
        assert "Environment: production" in content
