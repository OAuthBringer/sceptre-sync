#!/usr/bin/env python3
"""
Parameter Sync Utility

A tool for synchronizing configuration parameters between YAML files,
particularly designed for Sceptre configuration files.

This utility allows selective copying of parameters from a source file to a target file
based on configuration rules, preserving formatting and comments.
"""

import argparse
import fnmatch
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import ruamel.yaml
from ruamel.yaml.comments import CommentedMap


class ParamSync:
    """Main class for parameter synchronization operations."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the ParamSync utility.

        Args:
            config_file: Path to the configuration file defining sync rules
        """
        self.yaml = ruamel.yaml.YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        
        self.config = {}
        if config_file:
            self.load_config(config_file)

    def load_config(self, config_file: str) -> Dict:
        """
        Load the configuration file that defines sync rules.

        Args:
            config_file: Path to the configuration file

        Returns:
            Dict containing the parsed configuration
        """
        try:
            with open(config_file, 'r') as f:
                self.config = self.yaml.load(f)
            return self.config
        except Exception as e:
            print(f"Error loading config file: {e}", file=sys.stderr)
            sys.exit(1)

    def get_sync_params(self, file_path: str) -> List[str]:
        """
        Get the list of parameters to sync based on file path patterns.

        Args:
            file_path: Path to the file to match against patterns

        Returns:
            List of parameter names to synchronize
        """
        if not self.config or 'template_patterns' not in self.config:
            return []

        sync_params = []
        for pattern_config in self.config['template_patterns']:
            pattern = pattern_config.get('pattern')
            if pattern and fnmatch.fnmatch(file_path, pattern):
                sync_params.extend(pattern_config.get('sync_params', []))
        
        return sync_params

    def get_delete_params(self, file_path: str) -> List[str]:
        """
        Get the list of parameters to delete based on file path patterns.

        Args:
            file_path: Path to the file to match against patterns

        Returns:
            List of parameter names to delete
        """
        if not self.config or 'template_patterns' not in self.config:
            return []

        delete_params = []
        for pattern_config in self.config['template_patterns']:
            pattern = pattern_config.get('pattern')
            if pattern and fnmatch.fnmatch(file_path, pattern):
                if 'delete_params' in pattern_config:
                    delete_params.extend(pattern_config.get('delete_params', []))
        
        return delete_params

    def should_sync_template(self, file_path: str) -> bool:
        """
        Determine if the template should be synchronized for this file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the template should be synchronized, False otherwise
        """
        if not self.config or 'template_patterns' not in self.config:
            return False

        for pattern_config in self.config['template_patterns']:
            pattern = pattern_config.get('pattern')
            if pattern and fnmatch.fnmatch(file_path, pattern):
                return pattern_config.get('sync_template', False)
        
        return False

    def matches_filter(self, data: Dict, filter_spec: str) -> bool:
        """
        Check if the data matches the specified filter.
        
        Filter spec format: "field_path:substring"
        Example: "template.path:enhanced" - checks if data['template']['path'] contains "enhanced"
        
        Args:
            data: The YAML data to check
            filter_spec: The filter specification string
            
        Returns:
            True if the data matches the filter, False otherwise
        """
        if not filter_spec or ':' not in filter_spec:
            return True  # No filter or invalid filter means match everything
            
        field_path, substring = filter_spec.split(':', 1)
        field_parts = field_path.split('.')
        
        # Navigate through the nested structure
        current = data
        for part in field_parts:
            if not isinstance(current, dict) or part not in current:
                print(f"Field path '{part}' not found in data")
                return False
            current = current[part]
        
        # Check if the field value contains the substring
        if isinstance(current, str) and substring in current:
            print(f"Filter match: '{substring}' found in '{current}'")
            return True
        
        print(f"Filter no match: '{substring}' not found in '{current}'")
        return False

    def load_yaml_file(self, file_path: str) -> CommentedMap:
        """
        Load a YAML file while preserving comments and formatting.

        Args:
            file_path: Path to the YAML file

        Returns:
            CommentedMap containing the parsed YAML
        """
        try:
            with open(file_path, 'r') as f:
                return self.yaml.load(f)
        except Exception as e:
            print(f"Error loading YAML file {file_path}: {e}", file=sys.stderr)
            sys.exit(1)

    def save_yaml_file(self, file_path: str, data: CommentedMap) -> None:
        """
        Save a YAML file while preserving comments and formatting.

        Args:
            file_path: Path to save the YAML file
            data: CommentedMap containing the YAML data to save
        """
        try:
            with open(file_path, 'w') as f:
                self.yaml.dump(data, f)
        except Exception as e:
            print(f"Error saving YAML file {file_path}: {e}", file=sys.stderr)
            sys.exit(1)

    def generate_diff(self, source_data: Dict, target_data: Dict, params_to_sync: List[str], 
                     params_to_delete: List[str], sync_template: bool = False) -> Dict:
        """
        Generate a diff of changes that would be applied.

        Args:
            source_data: Source YAML data
            target_data: Target YAML data
            params_to_sync: List of parameters to synchronize
            params_to_delete: List of parameters to delete
            sync_template: Whether to sync the template section

        Returns:
            Dict containing added, modified, unchanged, and deleted parameters
        """
        diff = {
            'added': {},
            'modified': {},
            'unchanged': {},
            'deleted': {},
            'template': None
        }

        # Check if parameters are nested
        source_params = source_data.get('parameters', {})
        target_params = target_data.get('parameters', {})
        
        # Check parameters to sync
        for param in params_to_sync:
            if param in source_params:
                source_value = source_params[param]
                
                if param not in target_params:
                    diff['added'][param] = source_value
                elif str(source_params[param]) != str(target_params[param]):
                    diff['modified'][param] = {
                        'old': target_params[param],
                        'new': source_value
                    }
                else:
                    diff['unchanged'][param] = source_value
        
        # Check parameters to delete
        for param in params_to_delete:
            if param in target_params:
                diff['deleted'][param] = target_params[param]
        
        # Check template if requested
        if sync_template and 'template' in source_data and 'template' in target_data:
            # Deep comparison of template sections
            source_template = source_data['template']
            target_template = target_data['template']
            
            # Compare template path
            if 'path' in source_template and 'path' in target_template:
                if source_template['path'] != target_template['path']:
                    diff['template'] = {
                        'old': target_template,
                        'new': source_template
                    }
            # Compare template type
            elif 'type' in source_template and 'type' in target_template:
                if source_template['type'] != target_template['type']:
                    diff['template'] = {
                        'old': target_template,
                        'new': source_template
                    }
            # Compare entire template if structure differs
            elif str(source_template) != str(target_template):
                diff['template'] = {
                    'old': target_template,
                    'new': source_template
                }
        
        return diff

    def sync_parameters(self, source_file: str, target_file: str, 
                        params_to_sync: Optional[List[str]] = None,
                        params_to_delete: Optional[List[str]] = None,
                        dry_run: bool = False,
                        sync_template: Optional[bool] = None,
                        filter_spec: Optional[str] = None) -> Dict:
        """
        Synchronize parameters from source file to target file.

        Args:
            source_file: Path to the source YAML file
            target_file: Path to the target YAML file
            params_to_sync: List of parameters to synchronize (if None, determined from config)
            params_to_delete: List of parameters to delete (if None, determined from config)
            dry_run: If True, only show changes without applying them
            sync_template: Whether to sync the template section (if None, determined from config)
            filter_spec: Filter specification to apply (field_path:substring)

        Returns:
            Dict containing the diff of changes
        """
        # Load source and target files
        source_data = self.load_yaml_file(source_file)
        target_data = self.load_yaml_file(target_file)
        
        # Apply filter if specified
        if filter_spec:
            if not self.matches_filter(source_data, filter_spec):
                print(f"Source file {source_file} does not match filter {filter_spec}, skipping.")
                return {}
            else:
                print(f"Source file {source_file} matches filter {filter_spec}, processing.")
        
        # Determine parameters to sync if not provided
        if params_to_sync is None:
            params_to_sync = self.get_sync_params(source_file)
            if not params_to_sync:
                print(f"No sync parameters defined for {source_file}", file=sys.stderr)
                return {'added': {}, 'modified': {}, 'unchanged': {}, 'deleted': {}, 'template': None}
        
        # Determine parameters to delete if not provided
        if params_to_delete is None:
            params_to_delete = self.get_delete_params(source_file)
        
        # Determine if template should be synced if not provided
        if sync_template is None:
            sync_template = self.should_sync_template(source_file)
        
        # Generate diff
        diff = self.generate_diff(source_data, target_data, params_to_sync, params_to_delete, sync_template)
        
        # Apply changes if not dry run
        if not dry_run:
            # Apply parameter additions and modifications
            for param in list(diff['added'].keys()) + list(diff['modified'].keys()):
                if 'parameters' not in target_data:
                    target_data['parameters'] = {}
                target_data['parameters'][param] = source_data['parameters'][param]
            
            # Apply parameter deletions
            for param in diff['deleted'].keys():
                if 'parameters' in target_data and param in target_data['parameters']:
                    del target_data['parameters'][param]
            
            # Apply template change if needed
            if diff['template']:
                target_data['template'] = source_data['template']
            
            # Save the updated target file
            self.save_yaml_file(target_file, target_data)
        
        return diff

    def print_diff(self, diff: Dict) -> None:
        """
        Print a human-readable diff of changes.

        Args:
            diff: Dict containing added, modified, unchanged, and deleted parameters
        """
        if not diff:
            # Empty diff means file was filtered out
            return
            
        if not diff['added'] and not diff['modified'] and not diff['deleted'] and not diff['template']:
            print("No changes to apply.")
            return
        
        print("\nChanges to apply:")
        
        if diff['added']:
            print("\n  Parameters to add:")
            for param, value in diff['added'].items():
                print(f"    + {param}: {value}")
        
        if diff['modified']:
            print("\n  Parameters to modify:")
            for param, values in diff['modified'].items():
                print(f"    ~ {param}: {values['old']} -> {values['new']}")
        
        if diff['deleted']:
            print("\n  Parameters to delete:")
            for param, value in diff['deleted'].items():
                print(f"    - {param}: {value}")
        
        if diff['template']:
            print("\n  Template to modify:")
            print(f"    ~ {diff['template']['old']} -> {diff['template']['new']}")
        
        if diff['unchanged']:
            print(f"\n  {len(diff['unchanged'])} parameters already in sync.")


def main():
    """Main entry point for the command line interface."""
    parser = argparse.ArgumentParser(
        description="Synchronize parameters between YAML configuration files"
    )
    parser.add_argument("source", help="Source YAML file")
    parser.add_argument("target", help="Target YAML file")
    parser.add_argument("--config", "-c", help="Configuration file defining sync rules")
    parser.add_argument("--params", "-p", nargs="+", help="Specific parameters to sync")
    parser.add_argument("--delete", "-D", nargs="+", help="Specific parameters to delete")
    parser.add_argument("--dry-run", "-d", action="store_true", 
                        help="Show changes without applying them")
    parser.add_argument("--sync-template", "-T", action="store_true",
                        help="Sync the template section")
    parser.add_argument("--filter", "-f", 
                        help="Filter by field value (format: field.path:substring)")
    
    args = parser.parse_args()
    
    # Initialize ParamSync
    param_sync = ParamSync(args.config)
    
    # Perform sync operation
    diff = param_sync.sync_parameters(
        args.source, 
        args.target,
        args.params,
        args.delete,
        args.dry_run,
        args.sync_template,
        args.filter
    )
    
    # Print diff
    param_sync.print_diff(diff)
    
    # Print summary
    if diff:  # Only print summary if file wasn't filtered out
        total_changes = len(diff['added']) + len(diff['modified']) + len(diff['deleted']) + (1 if diff['template'] else 0)
        if total_changes > 0:
            action = "Would apply" if args.dry_run else "Applied"
            template_changes = 1 if diff['template'] else 0
            print(f"\n{action} {total_changes} changes ({len(diff['added'])} additions, {len(diff['modified'])} modifications, {len(diff['deleted'])} deletions, {template_changes} template changes)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())