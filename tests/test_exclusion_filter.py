"""
Test for exclusion filter functionality.

Because sometimes you need to say "everything EXCEPT this" - like ordering
pizza with everything except anchovies. Nobody wants anchovies.

This test suite defines the expected behavior for exclusion filters using
the :! syntax, as well as combinations of inclusion and exclusion filters.
"""

import os
import pytest
from pathlib import Path

import ruamel.yaml
from sceptre_sync.param_sync import ParamSync


class TestExclusionFilter:
    """Test exclusion filter syntax and behavior."""
    
    def test_single_exclusion_filter(self):
        """Test basic exclusion filter with :! syntax."""
        sync = ParamSync()
        
        # Test data with enhanced template
        data_enhanced = {
            "template": {
                "type": "enhanced",
                "path": "templates/enhanced.yaml"
            },
            "parameters": {
                "VpcCidr": "10.0.0.0/16"
            }
        }
        
        # Test data with standard template
        data_standard = {
            "template": {
                "type": "standard",
                "path": "templates/standard.yaml"
            },
            "parameters": {
                "VpcCidr": "10.1.0.0/16"
            }
        }
        
        # Exclusion filter - exclude enhanced templates
        filter_spec = "template.path:!enhanced"
        
        # Enhanced template should NOT match (excluded)
        assert not sync.matches_filter(data_enhanced, filter_spec)
        
        # Standard template SHOULD match (not excluded)
        assert sync.matches_filter(data_standard, filter_spec)
    
    def test_multiple_exclusion_filters(self):
        """Test multiple exclusion filters with comma separation."""
        sync = ParamSync()
        
        data_tests = [
            # Multiple exclusions should use comma separation
            ({"template": {"type": "enhanced"}}, "template.type:!enhanced,template.type:!special", False),
            ({"template": {"type": "standard"}}, "template.type:!enhanced,template.type:!special", True),
            ({"template": {"type": "special"}}, "template.type:!enhanced,template.type:!special", False),
            ({"template": {"type": "basic"}}, "template.type:!enhanced,template.type:!special", True),
        ]
        
        for data, filter_spec, expected in data_tests:
            result = sync.matches_filter(data, filter_spec)
            assert result == expected, f"Filter {filter_spec} on {data} should be {expected}"
    
    def test_inclusion_and_exclusion_combined(self):
        """Test combining inclusion and exclusion in same filter."""
        sync = ParamSync()
        
        # Data variations
        data_prod_enhanced = {
            "environment": "production",
            "template": {"type": "enhanced"}
        }
        
        data_prod_standard = {
            "environment": "production",
            "template": {"type": "standard"}
        }
        
        data_dev_enhanced = {
            "environment": "development",
            "template": {"type": "enhanced"}
        }
        
        # Include production, exclude enhanced
        # Should only match production + non-enhanced
        filter_spec = "environment:production,template.type:!enhanced"
        
        assert not sync.matches_filter(data_prod_enhanced, filter_spec)  # Prod but enhanced
        assert sync.matches_filter(data_prod_standard, filter_spec)      # Prod and not enhanced
        assert not sync.matches_filter(data_dev_enhanced, filter_spec)   # Not prod
    
    def test_exclusion_with_missing_field(self):
        """Test exclusion filter when field doesn't exist."""
        sync = ParamSync()
        
        # Data without template field
        data_no_template = {
            "parameters": {
                "VpcCidr": "10.0.0.0/16"
            }
        }
        
        # Exclude enhanced - should match if field missing
        filter_spec = "template.type:!enhanced"
        assert sync.matches_filter(data_no_template, filter_spec)
    
    def test_complex_nested_exclusion(self):
        """Test exclusion with deeply nested fields."""
        sync = ParamSync()
        
        data = {
            "config": {
                "database": {
                    "engine": "mysql",
                    "version": "8.0"
                }
            }
        }
        
        # Exclude mysql databases
        assert not sync.matches_filter(data, "config.database.engine:!mysql")
        assert sync.matches_filter(data, "config.database.engine:!postgres")
    
    def test_exclusion_in_param_sync(self, temp_dir):
        """Test exclusion filter in actual sync operation."""
        source_enhanced = """
template:
  type: enhanced
  path: templates/enhanced.yaml
parameters:
  VpcCidr: 10.0.0.0/16
  Environment: production
"""
        
        source_standard = """
template:
  type: standard
  path: templates/standard.yaml
parameters:
  VpcCidr: 10.1.0.0/16
  Environment: production
"""
        
        target = """
template:
  type: enhanced
  path: templates/enhanced.yaml
parameters:
  VpcCidr: 172.16.0.0/16
  Environment: development
"""
        
        source_enhanced_file = os.path.join(temp_dir, "source_enhanced.yaml")
        source_standard_file = os.path.join(temp_dir, "source_standard.yaml")
        target_file = os.path.join(temp_dir, "target.yaml")
        
        with open(source_enhanced_file, 'w') as f:
            f.write(source_enhanced)
        with open(source_standard_file, 'w') as f:
            f.write(source_standard)
        with open(target_file, 'w') as f:
            f.write(target)
        
        sync = ParamSync()
        
        # Try to sync from enhanced source with exclusion filter
        # Should skip the file
        diff1 = sync.sync_parameters(
            source_enhanced_file, target_file,
            params_to_sync=["VpcCidr", "Environment"],
            filter_spec="template.type:!enhanced",
            dry_run=True
        )
        
        # Should return empty diff (file filtered out)
        assert diff1 == {}
        
        # Try to sync from standard source with same filter
        # Should process the file
        diff2 = sync.sync_parameters(
            source_standard_file, target_file,
            params_to_sync=["VpcCidr", "Environment"],
            filter_spec="template.type:!enhanced",
            dry_run=True
        )
        
        # Should have changes
        assert diff2 != {}
        assert 'VpcCidr' in diff2['modified']
    
    def test_exclusion_in_bulk_sync(self, temp_dir):
        """Test exclusion filter in bulk sync operations."""
        # Create directory structure
        src_dir = os.path.join(temp_dir, "src")
        tgt_dir = os.path.join(temp_dir, "tgt")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tgt_dir, exist_ok=True)
        
        # Config for testing
        config_content = """
template_patterns:
  - pattern: "**/*.yaml"
    sync_params:
      - VpcCidr
"""
        
        # Create files with different template types
        templates = [
            ("enhanced", "stack1.yaml"),
            ("standard", "stack2.yaml"),
            ("enhanced", "stack3.yaml"),
            ("basic", "stack4.yaml")
        ]
        
        for template_type, filename in templates:
            content = f"""
template:
  type: {template_type}
parameters:
  VpcCidr: 10.0.0.0/16
"""
            with open(os.path.join(src_dir, filename), 'w') as f:
                f.write(content)
            
            # Target files
            target_content = f"""
template:
  type: {template_type}
parameters:
  VpcCidr: 172.16.0.0/16
"""
            with open(os.path.join(tgt_dir, filename), 'w') as f:
                f.write(target_content)
        
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Bulk sync with exclusion filter
        from sceptre_sync.bulk_sync import BulkParamSync
        bulk_sync = BulkParamSync(config_file)
        
        summary = bulk_sync.sync_bulk(
            os.path.join(src_dir, "*.yaml"),
            os.path.join(tgt_dir, "*.yaml"),
            dry_run=False,
            interactive=False,
            yes_to_all=True,
            filter_spec="template.type:!enhanced"  # Exclude enhanced
        )
        
        # Should process 2 files (standard and basic), filter out 2 (enhanced)
        assert summary['total_files'] == 4
        assert summary['filtered_files'] == 2
        assert summary['changed_files'] == 2
        
        # Verify enhanced files weren't changed
        yaml = ruamel.yaml.YAML()
        with open(os.path.join(tgt_dir, "stack1.yaml"), 'r') as f:
            result = yaml.load(f)
        assert result['parameters']['VpcCidr'] == "172.16.0.0/16"  # Unchanged
        
        # Verify standard/basic files were changed
        with open(os.path.join(tgt_dir, "stack2.yaml"), 'r') as f:
            result = yaml.load(f)
        assert result['parameters']['VpcCidr'] == "10.0.0.0/16"  # Changed
    
    def test_filter_syntax_variations(self):
        """Test various filter syntax patterns."""
        sync = ParamSync()
        
        data = {
            "environment": "production",
            "template": {
                "type": "enhanced",
                "version": "2.0"
            }
        }
        
        # Test various syntax patterns
        test_cases = [
            # Single exclusion
            ("template.type:!enhanced", False),
            ("template.type:!standard", True),
            
            # Multiple filters (AND logic)
            ("environment:production,template.type:!enhanced", False),
            ("environment:production,template.type:!standard", True),
            
            # Field doesn't exist
            ("missing.field:!value", True),
            
            # Empty exclusion (should NOT match when field contains empty string)
            ("template.type:!", True),  # Empty value - enhanced doesn't contain empty string
        ]
        
        for filter_spec, expected in test_cases:
            result = sync.matches_filter(data, filter_spec)
            assert result == expected, f"Filter '{filter_spec}' expected {expected}, got {result}"
    
    def test_case_sensitivity_in_exclusion(self):
        """Test that exclusion filters are case-sensitive."""
        sync = ParamSync()
        
        data = {
            "template": {
                "type": "Enhanced"  # Capital E
            }
        }
        
        # Should be case-sensitive
        assert sync.matches_filter(data, "template.type:!enhanced")  # Lowercase doesn't match
        assert not sync.matches_filter(data, "template.type:!Enhanced")  # Exact match
