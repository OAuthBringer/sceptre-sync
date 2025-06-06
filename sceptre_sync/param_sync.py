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
import sys
from typing import Dict, List, Optional, Tuple

import ruamel.yaml
from ruamel.yaml.comments import CommentedMap

from .common import format_diff_summary


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

    def get_sync_key(self, file_path: str) -> str:
        """
        Get the sync key for a file based on configuration patterns.

        Args:
            file_path: Path to the file to match against patterns

        Returns:
            The sync key to use (defaults to 'parameters')
        """
        if not self.config or 'template_patterns' not in self.config:
            return 'parameters'

        for pattern_config in self.config['template_patterns']:
            pattern = pattern_config.get('pattern')
            if pattern and fnmatch.fnmatch(file_path, pattern):
                return pattern_config.get('sync_key', 'parameters')

        return 'parameters'

    def get_sync_rules(self, file_path: str) -> List[Dict]:
        """
        Get sync rules for a file based on configuration patterns.
        
        Converts legacy format to new sync_rules format for compatibility.
        
        Args:
            file_path: Path to the file to match against patterns
            
        Returns:
            List of sync rule dictionaries with 'key' and 'sync_params'
        """
        if not self.config or 'template_patterns' not in self.config:
            return []
        
        for pattern_config in self.config['template_patterns']:
            pattern = pattern_config.get('pattern')
            if pattern and fnmatch.fnmatch(file_path, pattern):
                # Check for new sync_rules format
                if 'sync_rules' in pattern_config:
                    return pattern_config['sync_rules']
                
                # Convert legacy format to sync_rules
                if 'sync_params' in pattern_config:
                    sync_key = pattern_config.get('sync_key', 'parameters')
                    return [{
                        'key': sync_key,
                        'sync_params': pattern_config['sync_params'],
                        'delete_params': pattern_config.get('delete_params', [])
                    }]
        
        return []

    def matches_filter(self, data: Dict, filter_spec: str) -> bool:
        """
        Check if the data matches the specified filter.

        Filter spec format: 
        - Inclusion: "field_path:substring" - checks if field contains substring
        - Exclusion: "field_path:!substring" - checks if field does NOT contain substring
        - Multiple filters: "field1:value1,field2:!value2" - ALL must match (AND logic)
        
        Examples:
        - "template.path:enhanced" - include files with 'enhanced' in template path
        - "template.path:!enhanced" - exclude files with 'enhanced' in template path
        - "environment:prod,template.type:!test" - prod environment but not test templates

        Args:
            data: The YAML data to check
            filter_spec: The filter specification string

        Returns:
            True if the data matches the filter, False otherwise
        """
        if not filter_spec:
            return True  # No filter means match everything
            
        # Split multiple filters by comma (AND logic)
        filters = filter_spec.split(',')
        
        for single_filter in filters:
            single_filter = single_filter.strip()
            if ':' not in single_filter:
                continue  # Skip invalid filters
                
            field_path, value_spec = single_filter.split(':', 1)
            
            # Check if this is an exclusion filter
            is_exclusion = value_spec.startswith('!')
            if is_exclusion:
                value_spec = value_spec[1:]  # Remove the ! prefix
            
            # Navigate through the nested structure
            field_parts = field_path.split('.')
            current = data
            field_exists = True
            
            for part in field_parts:
                if not isinstance(current, dict) or part not in current:
                    field_exists = False
                    break
                current = current[part]
            
            # Apply filter logic
            if is_exclusion:
                # Exclusion filter
                if field_exists and isinstance(current, str):
                    # Field exists - check it doesn't contain the value
                    # Special case: empty exclusion value means exclude empty strings only
                    if not value_spec:
                        # Exclude only if the field is empty
                        if current == '':
                            print(f"Exclusion filter failed: field is empty")
                            return False
                    elif value_spec in current:
                        print(f"Exclusion filter failed: '{value_spec}' found in '{current}'")
                        return False
                # Field doesn't exist or doesn't contain value - passes exclusion
            else:
                # Inclusion filter
                if not field_exists:
                    print(f"Field path '{field_path}' not found in data")
                    return False
                if not isinstance(current, str) or value_spec not in current:
                    print(f"Filter no match: '{value_spec}' not found in '{current}'")
                    return False
                print(f"Filter match: '{value_spec}' found in '{current}'")
        
        return True  # All filters passed

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

    def _compare_templates(self, source_template: Dict, target_template: Dict) -> Optional[Dict]:
        """
        Compare source and target templates to determine if they differ.

        This method extracts the template comparison logic to reduce nesting
        in the generate_diff method.

        Args:
            source_template: Template from source YAML
            target_template: Template from target YAML

        Returns:
            Dict with 'old' and 'new' keys if templates differ, None if identical
        """
        # Compare template path
        if 'path' in source_template and 'path' in target_template:
            if source_template['path'] != target_template['path']:
                return {
                    'old': target_template,
                    'new': source_template
                }
        # Compare template type
        elif 'type' in source_template and 'type' in target_template:
            if source_template['type'] != target_template['type']:
                return {
                    'old': target_template,
                    'new': source_template
                }
        # Compare entire template if structure differs
        elif str(source_template) != str(target_template):
            return {
                'old': target_template,
                'new': source_template
            }

        return None

    def _get_nested_value(self, data: Dict, key_path: str) -> Optional[Dict]:
        """
        Get a nested value from data using dot notation.

        Args:
            data: The data dictionary
            key_path: Path to the value (e.g., "stack_tags.nested")

        Returns:
            The value at the specified path, or None if not found
        """
        parts = key_path.split('.')
        current = data
        
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        # Return the final part if it exists
        if isinstance(current, dict) and parts[-1] in current:
            return current[parts[-1]]
        return None

    def _set_nested_value(self, data: Dict, key_path: str, value: Dict) -> None:
        """
        Set a nested value in data using dot notation.

        Args:
            data: The data dictionary to modify
            key_path: Path to set (e.g., "stack_tags.nested")
            value: The value to set
        """
        parts = key_path.split('.')
        current = data
        
        # Create nested structure if needed
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the final value
        current[parts[-1]] = value

    def _diff_parameters(self, source_params: Dict, target_params: Dict,
                         params_to_sync: List[str]) -> Tuple[Dict, Dict, Dict]:
        """
        Compare source and target parameters to categorize changes.

        This method extracts the parameter diffing logic to reduce complexity
        in the generate_diff method.

        Args:
            source_params: Parameters from source YAML
            target_params: Parameters from target YAML
            params_to_sync: List of parameter names to compare

        Returns:
            Tuple of (added, modified, unchanged) dictionaries
        """
        added = {}
        modified = {}
        unchanged = {}

        for param in params_to_sync:
            if param in source_params:
                source_value = source_params[param]

                if param not in target_params:
                    added[param] = source_value
                elif str(source_params[param]) != str(target_params[param]):
                    modified[param] = {
                        'old': target_params[param],
                        'new': source_value
                    }
                else:
                    unchanged[param] = source_value

        return added, modified, unchanged

    def generate_diff(self, source_data: Dict, target_data: Dict,
                      params_to_sync: List[str], params_to_delete: List[str],
                      sync_template: bool = False, sync_key: str = 'parameters') -> Dict:
        """
        Generate a diff of changes that would be applied.

        Args:
            source_data: Source YAML data
            target_data: Target YAML data
            params_to_sync: List of parameters to synchronize
            params_to_delete: List of parameters to delete
            sync_template: Whether to sync the template section
            sync_key: The key to synchronize (defaults to 'parameters')

        Returns:
            Dict containing added, modified, unchanged, and deleted parameters
        """
        # Handle None/empty YAML files
        if source_data is None:
            source_data = {}
        if target_data is None:
            target_data = {}
            
        # Get data from source and target using the sync_key
        if '.' in sync_key:
            source_params = self._get_nested_value(source_data, sync_key) or {}
            target_params = self._get_nested_value(target_data, sync_key) or {}
        else:
            source_params = source_data.get(sync_key, {})
            target_params = target_data.get(sync_key, {})

        # Use helper method to diff parameters
        added, modified, unchanged = self._diff_parameters(
            source_params, target_params, params_to_sync
        )

        # Check parameters to delete
        deleted = {}
        for param in params_to_delete:
            if param in target_params:
                deleted[param] = target_params[param]

        # Check template if requested
        template_diff = None
        if sync_template and 'template' in source_data and 'template' in target_data:
            template_diff = self._compare_templates(
                source_data['template'],
                target_data['template']
            )

        return {
            'added': added,
            'modified': modified,
            'unchanged': unchanged,
            'deleted': deleted,
            'template': template_diff
        }

    def generate_diff_multi(self, source_data: Dict, target_data: Dict,
                           sync_rules: List[Dict], sync_template: bool = False) -> Dict:
        """
        Generate diff for multiple keys based on sync rules.
        
        Args:
            source_data: Source YAML data
            target_data: Target YAML data
            sync_rules: List of sync rule dictionaries
            sync_template: Whether to sync the template section
            
        Returns:
            Dict with diffs organized by key
        """
        # Handle None/empty YAML files
        if source_data is None:
            source_data = {}
        if target_data is None:
            target_data = {}
            
        multi_diff = {}
        
        # Process each sync rule
        for rule in sync_rules:
            key = rule['key']
            sync_params = rule.get('sync_params', [])
            delete_params = rule.get('delete_params', [])
            static_values = rule.get('static_values', {})
            
            # Get source and target data for this key
            if '.' in key:
                source_key_data = self._get_nested_value(source_data, key) or {}
                target_key_data = self._get_nested_value(target_data, key) or {}
            else:
                source_key_data = source_data.get(key, {})
                target_key_data = target_data.get(key, {})
            
            # Start with source values for sync_params
            effective_source = {}
            for param in sync_params:
                if param in source_key_data:
                    effective_source[param] = source_key_data[param]
            
            # Override/add static values
            # Static values take precedence over source values
            for param, value in static_values.items():
                effective_source[param] = value
            
            # Now generate diff using effective source
            added = {}
            modified = {}
            unchanged = {}
            deleted = {}
            
            # Check all params that should be synced (from source + static)
            all_params = set(sync_params) | set(static_values.keys())
            for param in all_params:
                if param in effective_source:
                    source_value = effective_source[param]
                    if param not in target_key_data:
                        added[param] = source_value
                    elif str(source_value) != str(target_key_data[param]):
                        modified[param] = {
                            'old': target_key_data[param],
                            'new': source_value
                        }
                    else:
                        unchanged[param] = source_value
            
            # Check parameters to delete
            for param in delete_params:
                if param in target_key_data:
                    deleted[param] = target_key_data[param]
            
            # Store the diff under the key name
            multi_diff[key] = {
                'added': added,
                'modified': modified,
                'unchanged': unchanged,
                'deleted': deleted
            }
        
        # Handle template if requested
        if sync_template:
            multi_diff['template'] = self._compare_templates(
                source_data.get('template', {}),
                target_data.get('template', {})
            ) if 'template' in source_data and 'template' in target_data else None
        else:
            multi_diff['template'] = None
            
        return multi_diff

    def sync_parameters(self, source_file: str, target_file: str,
                        params_to_sync: Optional[List[str]] = None,
                        params_to_delete: Optional[List[str]] = None,
                        dry_run: bool = False,
                        sync_template: Optional[bool] = None,
                        filter_spec: Optional[str] = None,
                        sync_key: str = 'parameters') -> Dict:
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
            sync_key: The key to synchronize (defaults to 'parameters')

        Returns:
            Dict containing the diff of changes
        """
        # Load source and target files
        source_data = self.load_yaml_file(source_file)
        target_data = self.load_yaml_file(target_file)
        
        # Check if target file has only comments (loaded as None)
        # If so, we need to preserve the original content when writing
        target_was_comments_only = target_data is None
        if target_was_comments_only:
            # Read the original file content to preserve comments
            with open(target_file, 'r') as f:
                original_target_content = f.read()

        # Apply filter if specified
        if filter_spec:
            if not self.matches_filter(source_data, filter_spec):
                print(f"Source file {source_file} does not match filter {filter_spec}, skipping.")
                return {}
            else:
                print(f"Source file {source_file} matches filter {filter_spec}, processing.")

        # Check if we have sync rules (multi-key) or need to use single-key logic
        sync_rules = self.get_sync_rules(source_file)
        
        if sync_rules:
            # Multi-key sync using sync_rules
            # Determine if template should be synced
            if sync_template is None:
                sync_template = self.should_sync_template(source_file)
            
            # Generate multi-key diff
            diff = self.generate_diff_multi(
                source_data, target_data, sync_rules, sync_template
            )
        else:
            # Legacy single-key sync
            # Determine parameters to sync if not provided
            if params_to_sync is None:
                params_to_sync = self.get_sync_params(source_file)
                if not params_to_sync:
                    print(f"No sync parameters defined for {source_file}", file=sys.stderr)
                    return {
                        'added': {}, 'modified': {}, 'unchanged': {},
                        'deleted': {}, 'template': None
                    }

            # Determine parameters to delete if not provided
            if params_to_delete is None:
                params_to_delete = self.get_delete_params(source_file)

            # Determine if template should be synced if not provided
            if sync_template is None:
                sync_template = self.should_sync_template(source_file)

            # Generate single-key diff
            diff = self.generate_diff(
                source_data, target_data, params_to_sync,
                params_to_delete, sync_template, sync_key
            )

        # Apply changes if not dry run
        if not dry_run:
            # Initialize target_data if it was None/empty
            if target_data is None:
                target_data = {}
                
            if sync_rules:
                # Multi-key apply
                for key_name, key_diff in diff.items():
                    if key_name == 'template':
                        # Handle template separately
                        if key_diff:
                            target_data['template'] = source_data['template']
                        continue
                    
                    # Get source values for this key
                    if '.' in key_name:
                        source_values = self._get_nested_value(source_data, key_name) or {}
                    else:
                        source_values = source_data.get(key_name, {})
                    
                    # Apply additions and modifications
                    added_and_modified = list(key_diff['added'].keys()) + list(key_diff['modified'].keys())
                    
                    # Need to rebuild effective source for apply
                    # Find the sync rule for this key to get static values
                    rule = next((r for r in sync_rules if r['key'] == key_name), None)
                    if rule:
                        static_values = rule.get('static_values', {})
                        # Build effective source with static values
                        effective_source = {}
                        for param in added_and_modified:
                            if param in static_values:
                                effective_source[param] = static_values[param]
                            elif param in source_values:
                                effective_source[param] = source_values[param]
                        
                        # Apply from effective source
                        for param in added_and_modified:
                            if param in effective_source:
                                param_value = effective_source[param]
                                if '.' in key_name:
                                    # Get or create the nested structure
                                    parts = key_name.split('.')
                                    current = target_data
                                    for part in parts[:-1]:
                                        if part not in current:
                                            current[part] = {}
                                        current = current[part]
                                    if parts[-1] not in current:
                                        current[parts[-1]] = {}
                                    current[parts[-1]][param] = param_value
                                else:
                                    if key_name not in target_data:
                                        target_data[key_name] = {}
                                    target_data[key_name][param] = param_value
                    else:
                        # Fallback to old behavior if no rule found
                        for param in added_and_modified:
                            if '.' in key_name:
                                # Get or create the nested structure
                                parts = key_name.split('.')
                                current = target_data
                                for part in parts[:-1]:
                                    if part not in current:
                                        current[part] = {}
                                    current = current[part]
                                if parts[-1] not in current:
                                    current[parts[-1]] = {}
                                current[parts[-1]][param] = source_values.get(param)
                            else:
                                if key_name not in target_data:
                                    target_data[key_name] = {}
                                target_data[key_name][param] = source_values.get(param)
                    
                    # Apply deletions
                    for param in key_diff['deleted'].keys():
                        if '.' in key_name:
                            target_values = self._get_nested_value(target_data, key_name)
                            if target_values and param in target_values:
                                del target_values[param]
                        else:
                            if key_name in target_data and param in target_data[key_name]:
                                del target_data[key_name][param]
            else:
                # Single-key apply (legacy)
                # Get source values
                if '.' in sync_key:
                    source_values = self._get_nested_value(source_data, sync_key) or {}
                else:
                    source_values = source_data.get(sync_key, {})

                # Apply parameter additions and modifications
                added_and_modified = list(diff['added'].keys()) + list(diff['modified'].keys())
                for param in added_and_modified:
                    # Create the sync_key structure if it doesn't exist
                    if '.' in sync_key:
                        # Get or create the nested structure
                        parts = sync_key.split('.')
                        current = target_data
                        for part in parts[:-1]:
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                        if parts[-1] not in current:
                            current[parts[-1]] = {}
                        current[parts[-1]][param] = source_values[param]
                    else:
                        if sync_key not in target_data:
                            target_data[sync_key] = {}
                        target_data[sync_key][param] = source_values[param]

                # Apply parameter deletions
                for param in diff['deleted'].keys():
                    if '.' in sync_key:
                        target_values = self._get_nested_value(target_data, sync_key)
                        if target_values and param in target_values:
                            del target_values[param]
                    else:
                        if sync_key in target_data and param in target_data[sync_key]:
                            del target_data[sync_key][param]

                # Apply template change if needed
                if diff['template']:
                    target_data['template'] = source_data['template']

            # Save the updated target file
            if target_was_comments_only and target_data:
                # Special handling for files that were comments-only
                # We need to append the new data while preserving comments
                with open(target_file, 'w') as f:
                    # Write original comments
                    f.write(original_target_content.rstrip())
                    if original_target_content and not original_target_content.endswith('\n'):
                        f.write('\n')
                    # Append the new data
                    from io import StringIO
                    stream = StringIO()
                    self.yaml.dump(target_data, stream)
                    f.write(stream.getvalue())
            else:
                # Normal save for files that had data structure
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

        # Check if this is a multi-key diff
        is_multi_key = any(isinstance(v, dict) and 'added' in v for k, v in diff.items() if k != 'template')
        
        if is_multi_key:
            self.print_diff_multi(diff)
            return

        changes_exist = (
            diff['added'] or diff['modified'] or
            diff['deleted'] or diff['template']
        )
        if not changes_exist:
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
    
    def print_diff_multi(self, diff: Dict) -> None:
        """
        Print a human-readable diff for multi-key changes.
        
        Args:
            diff: Dict containing diffs organized by key
        """
        # Check if any changes exist
        has_changes = False
        for key, key_diff in diff.items():
            if key == 'template':
                if key_diff:
                    has_changes = True
            elif isinstance(key_diff, dict) and (
                key_diff.get('added') or key_diff.get('modified') or key_diff.get('deleted')
            ):
                has_changes = True
                break
        
        if not has_changes:
            print("No changes to apply.")
            return
            
        print("\nChanges to apply:")
        
        # Process each key
        for key, key_diff in sorted(diff.items()):
            if key == 'template':
                if key_diff:
                    print("\n  Template to modify:")
                    print(f"    ~ {key_diff['old']} -> {key_diff['new']}")
                continue
            
            if not isinstance(key_diff, dict):
                continue
                
            changes_in_key = (
                key_diff.get('added') or key_diff.get('modified') or key_diff.get('deleted')
            )
            
            if changes_in_key:
                print(f"\n  [{key}]")
                
                if key_diff.get('added'):
                    for param, value in key_diff['added'].items():
                        print(f"    + {param}: {value}")
                
                if key_diff.get('modified'):
                    for param, values in key_diff['modified'].items():
                        print(f"    ~ {param}: {values['old']} -> {values['new']}")
                
                if key_diff.get('deleted'):
                    for param, value in key_diff['deleted'].items():
                        print(f"    - {param}: {value}")
                
                if key_diff.get('unchanged'):
                    print(f"    ({len(key_diff['unchanged'])} unchanged)")


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
    parser.add_argument("--sync-key", "-k",
                        help="Key to synchronize (default: parameters)")

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
        args.filter,
        sync_key=args.sync_key if args.sync_key else 'parameters'
    )

    # Print diff
    param_sync.print_diff(diff)

    # Print summary
    if diff:  # Only print summary if file wasn't filtered out
        summary = format_diff_summary(diff, args.dry_run)
        if summary:
            print(f"\n{summary}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
