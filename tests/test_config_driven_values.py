"""
Test for configuration-driven value addition/replacement.

Because sometimes you need to inject values that don't exist in any source file,
like setting Environment=production across all configs or adding standard tags.

This test suite defines the expected behavior for adding or replacing values
directly through configuration, without requiring them to exist in source files.
"""

import os
import pytest
from pathlib import Path

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestConfigDrivenValues:
    """Test adding/replacing values directly from configuration."""
    
    def test_add_static_values_from_config(self, temp_dir):
        """Test adding static values defined in config, not from source."""
        # Config that adds values directly
        config_content = """
template_patterns:
  - pattern: "**/app.yaml"
    sync_rules:
      - key: parameters
        static_values:
          Environment: production
          Region: us-east-1
      - key: stack_tags
        static_values:
          ManagedBy: sceptre
          CostCenter: engineering
          Owner: platform-team
"""
        
        # Source has NO parameters or stack_tags
        source_content = """
template: app-template.yaml
"""
        
        # Target has some existing values
        target_content = """
template: app-template.yaml
parameters:
  VpcCidr: 10.0.0.0/16
stack_tags:
  Project: my-app
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "app.yaml")
        target_file = os.path.join(temp_dir, "target/app.yaml")
        
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        # Should add static values
        assert 'parameters' in diff
        assert 'Environment' in diff['parameters']['added']
        assert 'Region' in diff['parameters']['added']
        
        assert 'stack_tags' in diff
        assert 'ManagedBy' in diff['stack_tags']['added']
        assert 'CostCenter' in diff['stack_tags']['added']
        assert 'Owner' in diff['stack_tags']['added']
        
        # Verify file
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Static values added
        assert result['parameters']['Environment'] == "production"
        assert result['parameters']['Region'] == "us-east-1"
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"  # Original kept
        
        assert result['stack_tags']['ManagedBy'] == "sceptre"
        assert result['stack_tags']['CostCenter'] == "engineering"
        assert result['stack_tags']['Owner'] == "platform-team"
        assert result['stack_tags']['Project'] == "my-app"  # Original kept
    
    def test_replace_values_from_config(self, temp_dir):
        """Test replacing existing values with config-defined values."""
        config_content = """
template_patterns:
  - pattern: "**/override.yaml"
    sync_rules:
      - key: parameters
        static_values:
          Environment: production  # Always override to production
          LogLevel: INFO          # Force standard log level
        sync_params:
          - VpcCidr              # Also sync this from source
"""
        
        source_content = """
parameters:
  VpcCidr: 10.0.0.0/16
  Environment: development  # This should be ignored
"""
        
        target_content = """
parameters:
  VpcCidr: 10.1.0.0/16
  Environment: staging     # Should be replaced with production
  LogLevel: DEBUG         # Should be replaced with INFO
  KeepMe: unchanged
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "override.yaml")
        target_file = os.path.join(temp_dir, "override.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        # Check modifications
        assert 'parameters' in diff
        assert 'Environment' in diff['parameters']['modified']
        assert diff['parameters']['modified']['Environment']['new'] == "production"
        assert 'LogLevel' in diff['parameters']['modified']
        assert 'VpcCidr' in diff['parameters']['modified']
        
        # Verify file
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Static values override everything
        assert result['parameters']['Environment'] == "production"
        assert result['parameters']['LogLevel'] == "INFO"
        # Source value synced
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        # Untouched value remains
        assert result['parameters']['KeepMe'] == "unchanged"
    
    def test_environment_variable_in_static_values(self, temp_dir):
        """Test that environment variables in static values work (future feature).
        
        This test is skipped because template variable resolution is not implemented.
        It's questionable whether this feature is even needed - if you know the value
        is 'production', just put 'production' in the static value.
        
        The only valid use case would be environment variable substitution like:
        Environment: "{{ $ENV_NAME }}" or external lookups, not internal variables.
        """
        pytest.skip("Template variable resolution not implemented - questionable if needed")
        
        config_content = """
template_patterns:
  - pattern: "**/env.yaml"
    sync_rules:
      - key: parameters
        static_values:
          Environment: "{{ $ENVIRONMENT }}"
          Region: "{{ $AWS_REGION }}"
"""
        
        # This test is more of a reminder that IF we implement templating,
        # it should be for external values, not internal variable references
    
    def test_combined_static_and_sync_values(self, temp_dir):
        """Test combining static values with synced values."""
        config_content = """
template_patterns:
  - pattern: "**/combined.yaml"
    sync_rules:
      - key: parameters
        static_values:
          Environment: production
          ManagedBy: terraform
        sync_params:
          - VpcCidr
          - InstanceType
        delete_params:
          - OldParam
"""
        
        source_content = """
parameters:
  VpcCidr: 10.0.0.0/16
  InstanceType: t3.large
  Environment: development  # Should be overridden by static value
  IgnoreMe: not-synced
"""
        
        target_content = """
parameters:
  VpcCidr: 10.1.0.0/16
  InstanceType: t2.micro
  Environment: staging
  OldParam: delete-me
  LocalParam: keep-me
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "combined.yaml")
        target_file = os.path.join(temp_dir, "combined.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        # Verify combined behavior
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Static values applied
        assert result['parameters']['Environment'] == "production"
        assert result['parameters']['ManagedBy'] == "terraform"
        # Synced from source
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert result['parameters']['InstanceType'] == "t3.large"
        # Deleted
        assert 'OldParam' not in result['parameters']
        # Kept local
        assert result['parameters']['LocalParam'] == "keep-me"
    
    def test_nested_static_values(self, temp_dir):
        """Test adding static values to nested keys."""
        config_content = """
template_patterns:
  - pattern: "**/nested.yaml"
    sync_rules:
      - key: config.monitoring
        static_values:
          enabled: true
          retention_days: 30
          alert_email: ops@example.com
      - key: config.backup
        static_values:
          enabled: true
          frequency: daily
"""
        
        source_content = """
config:
  app:
    name: my-app
"""
        
        target_content = """
config:
  app:
    name: my-app
  monitoring:
    enabled: false
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "nested.yaml")
        target_file = os.path.join(temp_dir, "nested.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Nested static values applied
        assert result['config']['monitoring']['enabled'] is True
        assert result['config']['monitoring']['retention_days'] == 30
        assert result['config']['monitoring']['alert_email'] == "ops@example.com"
        assert result['config']['backup']['enabled'] is True
        assert result['config']['backup']['frequency'] == "daily"
    
    def test_static_values_only_no_source_needed(self, temp_dir):
        """Test that static values work even without sync_params."""
        config_content = """
template_patterns:
  - pattern: "**/static-only.yaml"
    sync_rules:
      - key: metadata
        static_values:
          version: "1.0.0"
          managed_by: sceptre
          last_updated: "2023-12-01"
"""
        
        # Source file doesn't even have the key
        source_content = """
template: basic.yaml
"""
        
        target_content = """
template: basic.yaml
parameters:
  SomeParam: value
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "static-only.yaml")
        target_file = os.path.join(temp_dir, "static-only.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Static values added without any source values
        assert result['metadata']['version'] == "1.0.0"
        assert result['metadata']['managed_by'] == "sceptre"
        assert result['metadata']['last_updated'] == "2023-12-01"
        # Original content preserved
        assert result['parameters']['SomeParam'] == "value"
    
    def test_static_values_with_complex_types(self, temp_dir):
        """Test static values with lists and nested structures."""
        config_content = """
template_patterns:
  - pattern: "**/complex.yaml"
    sync_rules:
      - key: parameters
        static_values:
          SecurityGroups:
            - sg-12345
            - sg-67890
          Tags:
            Environment: production
            Team: platform
            Compliance:
              - sox
              - pci
"""
        
        source_content = """
template: complex.yaml
"""
        
        target_content = """
template: complex.yaml
"""
        
        config_file = os.path.join(temp_dir, "config.yaml")
        source_file = os.path.join(temp_dir, "complex.yaml")
        target_file = os.path.join(temp_dir, "complex.yaml.target")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        with open(source_file, 'w') as f:
            f.write(source_content)
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        sync = ParamSync(config_file)
        diff = sync.sync_parameters(source_file, target_file, dry_run=False)
        
        yaml = ruamel.yaml.YAML()
        with open(target_file, 'r') as f:
            result = yaml.load(f)
        
        # Complex static values applied
        assert result['parameters']['SecurityGroups'] == ['sg-12345', 'sg-67890']
        assert result['parameters']['Tags']['Environment'] == "production"
        assert result['parameters']['Tags']['Team'] == "platform"
        assert result['parameters']['Tags']['Compliance'] == ['sox', 'pci']
