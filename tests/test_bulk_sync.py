"""
Test for bulk sync functionality with all new features.

Because testing one file at a time is like eating soup with a fork -
technically possible but missing the entire point.
"""

import os
import pytest
from pathlib import Path
import tempfile

import ruamel.yaml
from sceptre_sync.bulk_sync import BulkParamSync


class TestBulkSync:
    """Test bulk synchronization with multi-key support and static values."""
    
    def test_bulk_sync_with_multi_key_rules(self, temp_dir):
        """Test bulk sync using multi-key sync rules."""
        # Create directory structure
        dev_dir = os.path.join(temp_dir, "configs/dev")
        prod_dir = os.path.join(temp_dir, "configs/prod")
        os.makedirs(dev_dir, exist_ok=True)
        os.makedirs(prod_dir, exist_ok=True)
        
        # Config with multi-key rules
        config_content = """
template_patterns:
  - pattern: "**/app-*.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcCidr
          - InstanceType
      - key: stack_tags
        sync_params:
          - Application
          - Owner
"""
        
        # Create multiple dev files
        for i in range(1, 4):
            dev_content = f"""
template: app-{i}.yaml
parameters:
  VpcCidr: 10.{i}.0.0/16
  InstanceType: t3.large
  DevOnlyParam: ignore-me
stack_tags:
  Application: app-{i}
  Owner: platform-team
  Environment: development
"""
            
            prod_content = f"""
template: app-{i}.yaml
parameters:
  VpcCidr: 172.{i}.0.0/16
  InstanceType: t2.micro
  ProdOnlyParam: keep-me
stack_tags:
  Application: old-app-{i}
  Owner: ops-team
  Environment: production
"""
            
            with open(os.path.join(dev_dir, f"app-{i}.yaml"), 'w') as f:
                f.write(dev_content)
            with open(os.path.join(prod_dir, f"app-{i}.yaml"), 'w') as f:
                f.write(prod_content)
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Run bulk sync
        bulk_sync = BulkParamSync(config_file)
        summary = bulk_sync.sync_bulk(
            os.path.join(dev_dir, "app-*.yaml"),
            os.path.join(prod_dir, "app-*.yaml"),
            dry_run=False,
            interactive=False,
            yes_to_all=True
        )
        
        # Verify summary
        assert summary['total_files'] == 3
        assert summary['changed_files'] == 3
        assert summary['total_changes'] > 0
        
        # Verify each file was updated correctly
        yaml = ruamel.yaml.YAML()
        for i in range(1, 4):
            with open(os.path.join(prod_dir, f"app-{i}.yaml"), 'r') as f:
                result = yaml.load(f)
            
            # Parameters synced from dev
            assert result['parameters']['VpcCidr'] == f"10.{i}.0.0/16"
            assert result['parameters']['InstanceType'] == "t3.large"
            # Prod-only params preserved
            assert result['parameters']['ProdOnlyParam'] == "keep-me"
            # Dev-only params not copied
            assert 'DevOnlyParam' not in result['parameters']
            
            # Stack tags synced
            assert result['stack_tags']['Application'] == f"app-{i}"
            assert result['stack_tags']['Owner'] == "platform-team"
            # Environment not in sync list, so unchanged
            assert result['stack_tags']['Environment'] == "production"
    
    def test_bulk_sync_with_static_values(self, temp_dir):
        """Test bulk sync with static values injection."""
        # Create directory structure
        src_dir = os.path.join(temp_dir, "source")
        tgt_dir = os.path.join(temp_dir, "target")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tgt_dir, exist_ok=True)
        
        # Config with static values
        config_content = """
template_patterns:
  - pattern: "**/svc-*.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - ServiceName
        static_values:
          Environment: production
          ManagedBy: sceptre
          Region: us-east-1
      - key: metadata
        static_values:
          version: "1.0.0"
          last_updated: "2023-12-01"
"""
        
        # Create source files with minimal content
        for svc in ['api', 'web', 'worker']:
            src_content = f"""
template: service.yaml
parameters:
  ServiceName: {svc}-service
"""
            
            tgt_content = f"""
template: service.yaml
parameters:
  ServiceName: old-{svc}
  Environment: staging
  LocalParam: keep-me
"""
            
            with open(os.path.join(src_dir, f"svc-{svc}.yaml"), 'w') as f:
                f.write(src_content)
            with open(os.path.join(tgt_dir, f"svc-{svc}.yaml"), 'w') as f:
                f.write(tgt_content)
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Run bulk sync
        bulk_sync = BulkParamSync(config_file)
        summary = bulk_sync.sync_bulk(
            os.path.join(src_dir, "svc-*.yaml"),
            os.path.join(tgt_dir, "svc-*.yaml"),
            dry_run=False,
            interactive=False,
            yes_to_all=True
        )
        
        # Verify all files processed
        assert summary['total_files'] == 3
        assert summary['changed_files'] == 3
        
        # Verify static values were injected
        yaml = ruamel.yaml.YAML()
        for svc in ['api', 'web', 'worker']:
            with open(os.path.join(tgt_dir, f"svc-{svc}.yaml"), 'r') as f:
                result = yaml.load(f)
            
            # Synced from source
            assert result['parameters']['ServiceName'] == f"{svc}-service"
            # Static values injected/overridden
            assert result['parameters']['Environment'] == "production"
            assert result['parameters']['ManagedBy'] == "sceptre"
            assert result['parameters']['Region'] == "us-east-1"
            # Local params preserved
            assert result['parameters']['LocalParam'] == "keep-me"
            
            # Metadata added (didn't exist before)
            assert result['metadata']['version'] == "1.0.0"
            assert result['metadata']['last_updated'] == "2023-12-01"
    
    def test_bulk_sync_backward_compatibility(self, temp_dir):
        """Test bulk sync still works with old-style configs."""
        # Create directories
        dev_dir = os.path.join(temp_dir, "dev")
        prod_dir = os.path.join(temp_dir, "prod")
        os.makedirs(dev_dir, exist_ok=True)
        os.makedirs(prod_dir, exist_ok=True)
        
        # Old-style config
        config_content = """
template_patterns:
  - pattern: "**/legacy.yaml"
    sync_params:
      - VpcCidr
      - SubnetCidr
    delete_params:
      - OldParam
"""
        
        # Create files
        dev_content = """
template: vpc.yaml
parameters:
  VpcCidr: 10.0.0.0/16
  SubnetCidr: 10.0.1.0/24
  DevParam: ignore
"""
        
        prod_content = """
template: vpc.yaml
parameters:
  VpcCidr: 172.16.0.0/16
  SubnetCidr: 172.16.1.0/24
  OldParam: delete-me
  ProdParam: keep
"""
        
        with open(os.path.join(dev_dir, "legacy.yaml"), 'w') as f:
            f.write(dev_content)
        with open(os.path.join(prod_dir, "legacy.yaml"), 'w') as f:
            f.write(prod_content)
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Run bulk sync
        bulk_sync = BulkParamSync(config_file)
        summary = bulk_sync.sync_bulk(
            os.path.join(dev_dir, "legacy.yaml"),
            os.path.join(prod_dir, "legacy.yaml"),
            dry_run=False,
            interactive=False,
            yes_to_all=True
        )
        
        # Verify it worked
        assert summary['total_files'] == 1
        assert summary['changed_files'] == 1
        
        yaml = ruamel.yaml.YAML()
        with open(os.path.join(prod_dir, "legacy.yaml"), 'r') as f:
            result = yaml.load(f)
        
        # Old-style sync worked
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"
        assert result['parameters']['SubnetCidr'] == "10.0.1.0/24"
        assert 'OldParam' not in result['parameters']
        assert result['parameters']['ProdParam'] == "keep"
    
    def test_bulk_sync_with_filter(self, temp_dir):
        """Test bulk sync with filter spec."""
        # Create directories
        src_dir = os.path.join(temp_dir, "src")
        tgt_dir = os.path.join(temp_dir, "tgt")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tgt_dir, exist_ok=True)
        
        config_content = """
template_patterns:
  - pattern: "**/*.yaml"
    sync_params:
      - VpcCidr
"""
        
        # Create files with different templates
        for i, template_type in enumerate(['standard', 'enhanced', 'basic']):
            src_content = f"""
template:
  type: {template_type}
  path: templates/{template_type}.yaml
parameters:
  VpcCidr: 10.{i}.0.0/16
"""
            
            tgt_content = f"""
template:
  type: {template_type}
  path: templates/{template_type}.yaml
parameters:
  VpcCidr: 172.{i}.0.0/16
"""
            
            with open(os.path.join(src_dir, f"stack-{i}.yaml"), 'w') as f:
                f.write(src_content)
            with open(os.path.join(tgt_dir, f"stack-{i}.yaml"), 'w') as f:
                f.write(tgt_content)
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Run bulk sync with filter - only process 'enhanced' templates
        bulk_sync = BulkParamSync(config_file)
        summary = bulk_sync.sync_bulk(
            os.path.join(src_dir, "*.yaml"),
            os.path.join(tgt_dir, "*.yaml"),
            dry_run=False,
            interactive=False,
            yes_to_all=True,
            filter_spec="template.path:enhanced"
        )
        
        # Only 1 file should match the filter
        assert summary['total_files'] == 3
        assert summary['filtered_files'] == 2
        assert summary['changed_files'] == 1
        
        yaml = ruamel.yaml.YAML()
        # Check enhanced was updated
        with open(os.path.join(tgt_dir, "stack-1.yaml"), 'r') as f:
            result = yaml.load(f)
        assert result['parameters']['VpcCidr'] == "10.1.0.0/16"
        
        # Check others were not updated
        with open(os.path.join(tgt_dir, "stack-0.yaml"), 'r') as f:
            result = yaml.load(f)
        assert result['parameters']['VpcCidr'] == "172.0.0.0/16"  # Unchanged
    
    def test_bulk_sync_environment_mapping(self, temp_dir):
        """Test the special environment directory mapping feature."""
        # Create Sceptre-style environment directories
        dev_dir = os.path.join(temp_dir, "config/di-development")
        prod_dir = os.path.join(temp_dir, "config/di-production")
        os.makedirs(dev_dir, exist_ok=True)
        os.makedirs(prod_dir, exist_ok=True)
        
        config_content = """
template_patterns:
  - pattern: "**/*.yaml"
    sync_rules:
      - key: parameters
        sync_params: [InstanceType]
        static_values:
          Environment: production
"""
        
        # Create matching files in dev
        for stack in ['vpc', 'app', 'db']:
            content = f"""
parameters:
  InstanceType: t3.large
  StackName: {stack}
"""
            with open(os.path.join(dev_dir, f"{stack}.yaml"), 'w') as f:
                f.write(content)
            
            # Only create vpc and app in prod (db will be skipped)
            if stack != 'db':
                prod_content = f"""
parameters:
  InstanceType: t2.micro
  StackName: {stack}
  Environment: staging
"""
                with open(os.path.join(prod_dir, f"{stack}.yaml"), 'w') as f:
                    f.write(prod_content)
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Run bulk sync with environment pattern
        bulk_sync = BulkParamSync(config_file)
        summary = bulk_sync.sync_bulk(
            os.path.join(temp_dir, "config/di-development/*.yaml"),
            os.path.join(temp_dir, "config/di-production/*.yaml"),
            dry_run=False,
            interactive=False,
            yes_to_all=True
        )
        
        # Should find 2 pairs (vpc and app, not db)
        assert summary['total_files'] == 2
        assert summary['changed_files'] == 2
        
        yaml = ruamel.yaml.YAML()
        for stack in ['vpc', 'app']:
            with open(os.path.join(prod_dir, f"{stack}.yaml"), 'r') as f:
                result = yaml.load(f)
            assert result['parameters']['InstanceType'] == "t3.large"
            assert result['parameters']['Environment'] == "production"  # Static override
            assert result['parameters']['StackName'] == stack  # Preserved
