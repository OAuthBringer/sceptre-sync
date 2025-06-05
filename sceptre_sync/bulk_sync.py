#!/usr/bin/env python3
"""
Bulk Parameter Sync Utility

Extension of the parameter sync utility to handle bulk operations
across multiple files and directories.
"""

import argparse
import fnmatch
import os
import sys
import re
import glob
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .param_sync import ParamSync


class BulkParamSync:
    """Class for handling bulk parameter synchronization operations."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the BulkParamSync utility.

        Args:
            config_file: Path to the configuration file defining sync rules
        """
        self.param_sync = ParamSync(config_file)
    
    def find_matching_files(self, pattern: str) -> List[str]:
        """
        Find all files matching the given pattern using glob.

        Args:
            pattern: Glob pattern to match files

        Returns:
            List of file paths matching the pattern
        """
        # Use glob directly which is more efficient and safer
        return glob.glob(pattern, recursive=True)
    
    def generate_file_pairs(self, source_pattern: str, target_pattern: str) -> List[Tuple[str, str]]:
        """
        Generate pairs of source and target files based on patterns.
        
        This version maps files between environment directories by replacing
        the environment name in the path.

        Args:
            source_pattern: Pattern for source files
            target_pattern: Pattern for target files

        Returns:
            List of (source_file, target_file) tuples
        """
        # Extract environment names from patterns
        source_env_match = re.search(r'/(di-[^/]+)/', source_pattern)
        target_env_match = re.search(r'/(di-[^/]+)/', target_pattern)
        
        # Find all source files
        source_files = self.find_matching_files(source_pattern)
        
        if not source_files:
            print(f"No source files found matching pattern: {source_pattern}")
            return []
            
        print(f"Found {len(source_files)} source files")
        
        # Generate file pairs
        file_pairs = []
        
        # If we have environment patterns, use them for mapping
        if source_env_match and target_env_match:
            source_env = source_env_match.group(1)
            target_env = target_env_match.group(1)
            
            print(f"Source environment: {source_env}")
            print(f"Target environment: {target_env}")
            
            for source_file in source_files:
                # Create target file path by replacing environment name
                target_file = source_file.replace(f"/{source_env}/", f"/{target_env}/")
                
                # Check if target file exists
                if os.path.exists(target_file):
                    file_pairs.append((source_file, target_file))
                else:
                    print(f"Target file not found: {target_file}")
        else:
            # For non-environment patterns, try direct mapping
            target_files = self.find_matching_files(target_pattern)
            
            if not target_files:
                print(f"No target files found matching pattern: {target_pattern}")
                return []
                
            print(f"Found {len(target_files)} target files")
            
            # If we have exactly one source and one target, pair them
            if len(source_files) == 1 and len(target_files) == 1:
                file_pairs.append((source_files[0], target_files[0]))
            else:
                # Try to match by filename
                for source_file in source_files:
                    source_filename = os.path.basename(source_file)
                    for target_file in target_files:
                        target_filename = os.path.basename(target_file)
                        if source_filename == target_filename:
                            file_pairs.append((source_file, target_file))
                            break
        
        return file_pairs
    
    def sync_bulk(self, source_pattern: str, target_pattern: str, 
                 dry_run: bool = False, interactive: bool = True,
                 sync_template: bool = False, yes_to_all: bool = False,
                 filter_spec: Optional[str] = None) -> Dict:
        """
        Synchronize parameters across multiple file pairs.

        Args:
            source_pattern: Pattern for source files
            target_pattern: Pattern for target files
            dry_run: If True, only show changes without applying them
            interactive: If True, prompt for confirmation before each file pair
            sync_template: Whether to sync the template section
            yes_to_all: If True, automatically apply all changes without prompting
            filter_spec: Filter specification to apply (field_path:substring)

        Returns:
            Dict containing summary of changes
        """
        print(f"Source pattern: {source_pattern}")
        print(f"Target pattern: {target_pattern}")
        print(f"Sync template: {sync_template}")
        print(f"Auto-apply changes: {yes_to_all}")
        if filter_spec:
            print(f"Filter: {filter_spec}")
        
        file_pairs = self.generate_file_pairs(source_pattern, target_pattern)
        
        if not file_pairs:
            print("No matching file pairs found.")
            return {'total_files': 0, 'changed_files': 0, 'total_changes': 0}
        
        print(f"Found {len(file_pairs)} file pairs to process.")
        
        summary = {
            'total_files': len(file_pairs),
            'changed_files': 0,
            'total_changes': 0,
            'file_changes': {},
            'filtered_files': 0
        }
        
        for source_file, target_file in file_pairs:
            print(f"\nProcessing: {source_file} -> {target_file}")
            
            # Determine parameters to sync based on source file
            params_to_sync = self.param_sync.get_sync_params(source_file)
            
            if not params_to_sync:
                print(f"No sync parameters defined for {source_file}, skipping.")
                continue
            
            # Determine parameters to delete based on source file
            params_to_delete = self.param_sync.get_delete_params(source_file)
            
            # Determine if template should be synced
            should_sync_template = sync_template or self.param_sync.should_sync_template(source_file)
            
            # Generate diff
            diff = self.param_sync.sync_parameters(
                source_file, target_file, params_to_sync, params_to_delete,
                dry_run=True, sync_template=should_sync_template,
                filter_spec=filter_spec
            )
            
            # Check if file was filtered out
            if not diff and filter_spec:
                summary['filtered_files'] += 1
                continue
                
            # Print diff
            self.param_sync.print_diff(diff)
            
            total_changes = len(diff['added']) + len(diff['modified']) + len(diff['deleted']) + (1 if diff['template'] else 0)
            
            if total_changes == 0:
                print("No changes needed.")
                continue
            
            # Determine whether to apply changes
            proceed = True
            
            # If not in yes_to_all mode and interactive mode is on, prompt for confirmation
            if not yes_to_all and interactive and not dry_run:
                response = input("\nApply these changes? [y/N] ").lower()
                proceed = response in ('y', 'yes')
            
            # Apply changes if confirmed or yes_to_all
            if proceed and not dry_run:
                self.param_sync.sync_parameters(
                    source_file, target_file, params_to_sync, params_to_delete,
                    dry_run=False, sync_template=should_sync_template,
                    filter_spec=filter_spec
                )
                print("Changes applied.")
                summary['changed_files'] += 1
                summary['total_changes'] += total_changes
                summary['file_changes'][target_file] = total_changes
            
        return summary


def main():
    """Main entry point for the bulk sync command line interface."""
    parser = argparse.ArgumentParser(
        description="Bulk synchronize parameters between YAML configuration files"
    )
    parser.add_argument("--source-pattern", "-s", required=True,
                        help="Pattern for source files")
    parser.add_argument("--target-pattern", "-t", required=True,
                        help="Pattern for target files")
    parser.add_argument("--config", "-c", required=True,
                        help="Configuration file defining sync rules")
    parser.add_argument("--dry-run", "-d", action="store_true",
                        help="Show changes without applying them")
    parser.add_argument("--non-interactive", "-n", action="store_true",
                        help="Apply all changes without prompting")
    parser.add_argument("--sync-template", "-T", action="store_true",
                        help="Sync the template section")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Automatically apply all changes without prompting")
    parser.add_argument("--filter", "-f", 
                        help="Filter by field value (format: field.path:substring)")
    
    args = parser.parse_args()
    
    # Initialize BulkParamSync
    bulk_sync = BulkParamSync(args.config)
    
    # Perform bulk sync operation
    summary = bulk_sync.sync_bulk(
        args.source_pattern,
        args.target_pattern,
        args.dry_run,
        not args.non_interactive,
        args.sync_template,
        args.yes,
        args.filter
    )
    
    # Print summary
    print("\nSummary:")
    print(f"  Files processed: {summary['total_files']}")
    if 'filtered_files' in summary and summary['filtered_files'] > 0:
        print(f"  Files filtered out: {summary['filtered_files']}")
    print(f"  Files changed: {summary['changed_files']}")
    print(f"  Total changes: {summary['total_changes']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())