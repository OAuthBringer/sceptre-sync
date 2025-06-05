"""
Integration tests for sceptre-sync.

These tests verify end-to-end functionality without mocking internal components.
Because testing mocks is like checking your parachute works by looking at the manual.
"""

import os
import pytest

from sceptre_sync.cli import main
from sceptre_sync.param_sync import ParamSync
from sceptre_sync.bulk_sync import BulkParamSync


@pytest.mark.integration
class TestIntegration:
    """Integration tests that verify actual functionality."""
    
    def test_end_to_end_single_file_sync(self, temp_dir):
        """Test complete sync operation from CLI to file modification."""
        # Create config file
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*.yaml"
    sync_params:
      - VpcCidr
      - PublicSubnetCidr
""")
        
        # Create source file
        source_file = os.path.join(temp_dir, "source.yaml")
        with open(source_file, 'w') as f:
            f.write("""
template:
  path: templates/vpc.yaml
parameters:
  VpcCidr: "10.0.0.0/16"
  PublicSubnetCidr: "10.0.1.0/24"
  PrivateSubnetCidr: "10.0.2.0/24"
""")
        
        # Create target file
        target_file = os.path.join(temp_dir, "target.yaml")
        with open(target_file, 'w') as f:
            f.write("""
template:
  path: templates/vpc.yaml
parameters:
  VpcCidr: "192.168.0.0/16"
  PublicSubnetCidr: "192.168.1.0/24"
  PrivateSubnetCidr: "192.168.2.0/24"
""")
        
        # Run sync with --yes to avoid prompt
        args = ["sync", source_file, target_file, "--config", config_file, "--yes"]
        exit_code = main(args)
        
        assert exit_code == 0
        
        # Verify target file was modified
        with open(target_file, 'r') as f:
            content = f.read()
            assert "10.0.0.0/16" in content  # VpcCidr synced
            assert "10.0.1.0/24" in content  # PublicSubnetCidr synced
            assert "192.168.2.0/24" in content  # PrivateSubnetCidr NOT synced
    
    def test_end_to_end_bulk_sync_with_environments(self, temp_dir):
        """Test bulk sync across environment directories."""
        # Create config
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*/vpc.yaml"
    sync_params:
      - VpcCidr
  - pattern: "*/api/*.yaml"
    sync_params:
      - CPUReservation
""")
        
        # Create directory structure
        alpha_dir = os.path.join(temp_dir, "config", "di-alpha")
        alpha_api_dir = os.path.join(alpha_dir, "api")
        dev_dir = os.path.join(temp_dir, "config", "di-dev")
        dev_api_dir = os.path.join(dev_dir, "api")
        
        os.makedirs(alpha_api_dir)
        os.makedirs(dev_api_dir)
        
        # Create alpha files
        alpha_vpc = os.path.join(alpha_dir, "vpc.yaml")
        with open(alpha_vpc, 'w') as f:
            f.write("""
parameters:
  VpcCidr: "10.0.0.0/16"
  Environment: "alpha"
""")
        
        alpha_api = os.path.join(alpha_api_dir, "tasks.yaml")
        with open(alpha_api, 'w') as f:
            f.write("""
parameters:
  CPUReservation: 512
  Environment: "alpha"
""")
        
        # Create dev files with different values
        dev_vpc = os.path.join(dev_dir, "vpc.yaml")
        with open(dev_vpc, 'w') as f:
            f.write("""
parameters:
  VpcCidr: "192.168.0.0/16"
  Environment: "dev"
""")
        
        dev_api = os.path.join(dev_api_dir, "tasks.yaml")
        with open(dev_api, 'w') as f:
            f.write("""
parameters:
  CPUReservation: 256
  Environment: "dev"
""")
        
        # Run bulk sync
        args = [
            "bulk",
            "--source-pattern", os.path.join(temp_dir, "config/di-alpha/**/*.yaml"),
            "--target-pattern", os.path.join(temp_dir, "config/di-dev/**/*.yaml"),
            "--config", config_file,
            "--yes"
        ]
        exit_code = main(args)
        
        assert exit_code == 0
        
        # Verify files were synced
        with open(dev_vpc, 'r') as f:
            content = f.read()
            assert "10.0.0.0/16" in content  # VpcCidr synced from alpha
            assert 'Environment: "dev"' in content  # Environment NOT synced
        
        with open(dev_api, 'r') as f:
            content = f.read()
            assert "CPUReservation: 512" in content  # CPU synced from alpha
            assert 'Environment: "dev"' in content  # Environment NOT synced
    
    def test_filter_functionality(self, temp_dir):
        """Test that filter correctly excludes files from sync."""
        # Create config
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*.yaml"
    sync_params:
      - InstanceType
""")
        
        # Create source files
        source1 = os.path.join(temp_dir, "ec2.yaml")
        with open(source1, 'w') as f:
            f.write("""
template:
  type: ec2
parameters:
  InstanceType: "t3.large"
""")
        
        source2 = os.path.join(temp_dir, "rds.yaml")
        with open(source2, 'w') as f:
            f.write("""
template:
  type: rds
parameters:
  InstanceType: "db.t3.large"
""")
        
        # Create target files
        target1 = os.path.join(temp_dir, "target-ec2.yaml")
        with open(target1, 'w') as f:
            f.write("""
template:
  type: ec2
parameters:
  InstanceType: "t2.micro"
""")
        
        target2 = os.path.join(temp_dir, "target-rds.yaml")
        with open(target2, 'w') as f:
            f.write("""
template:
  type: rds
parameters:
  InstanceType: "db.t2.micro"
""")
        
        # Sync only EC2 files using filter
        args = [
            "sync", source1, target1,
            "--config", config_file,
            "--filter", "template.type:ec2",
            "--yes"
        ]
        exit_code = main(args)
        assert exit_code == 0
        
        # Verify EC2 file was synced
        with open(target1, 'r') as f:
            content = f.read()
            assert "t3.large" in content
        
        # Now try to sync RDS file with EC2 filter - should be skipped
        args = [
            "sync", source2, target2,
            "--config", config_file,
            "--filter", "template.type:ec2",
            "--yes"
        ]
        exit_code = main(args)
        assert exit_code == 0
        
        # Verify RDS file was NOT synced
        with open(target2, 'r') as f:
            content = f.read()
            assert "db.t2.micro" in content  # Still has original value
    
    def test_template_sync_functionality(self, temp_dir):
        """Test syncing template section."""
        # Create config
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*.yaml"
    sync_params:
      - Environment
""")
        
        # Create source with different template
        source = os.path.join(temp_dir, "source.yaml")
        with open(source, 'w') as f:
            f.write("""
template:
  path: templates/vpc-v2.yaml
  type: cloudformation
parameters:
  Environment: "prod"
""")
        
        # Create target with old template
        target = os.path.join(temp_dir, "target.yaml")
        with open(target, 'w') as f:
            f.write("""
template:
  path: templates/vpc-v1.yaml
  type: cloudformation
parameters:
  Environment: "dev"
""")
        
        # Run sync with --sync-template flag
        args = ["sync", source, target, "--config", config_file, "--sync-template", "--yes"]
        exit_code = main(args)
        assert exit_code == 0
        
        # Verify both template and parameters were synced
        with open(target, 'r') as f:
            content = f.read()
            assert "vpc-v2.yaml" in content  # Template path synced
            assert 'Environment: "prod"' in content  # Parameter synced
    
    def test_delete_parameters_functionality(self, temp_dir):
        """Test deleting parameters during sync."""
        # Create config with delete params
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*.yaml"
    sync_params:
      - NewParam
    delete_params:
      - DeprecatedParam
      - OldParam
""")
        
        # Create source
        source = os.path.join(temp_dir, "source.yaml")
        with open(source, 'w') as f:
            f.write("""
parameters:
  NewParam: "new_value"
  KeepThisParam: "keep_me"
""")
        
        # Create target with deprecated params
        target = os.path.join(temp_dir, "target.yaml")
        with open(target, 'w') as f:
            f.write("""
parameters:
  DeprecatedParam: "old_value"
  OldParam: "ancient_value"
  KeepThisParam: "keep_me"
  NewParam: "outdated_value"
""")
        
        # Run sync
        args = ["sync", source, target, "--config", config_file, "--yes"]
        exit_code = main(args)
        assert exit_code == 0
        
        # Verify parameters were deleted and synced
        param_sync = ParamSync()
        target_data = param_sync.load_yaml_file(target)
        
        assert "DeprecatedParam" not in target_data['parameters']
        assert "OldParam" not in target_data['parameters']
        assert target_data['parameters']['NewParam'] == "new_value"
        assert target_data['parameters']['KeepThisParam'] == "keep_me"
