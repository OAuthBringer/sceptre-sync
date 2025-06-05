#!/usr/bin/env python3
"""
Command Line Interface for Parameter Sync Utility

Provides a unified CLI for both single-file and bulk operations.
"""

import argparse
import sys
from typing import List, Optional

from .param_sync import ParamSync, main as param_sync_main
from .bulk_sync import BulkParamSync, main as bulk_sync_main


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for the unified CLI.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Synchronize parameters between YAML configuration files"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Single file sync command
    single_parser = subparsers.add_parser("sync", help="Sync parameters between two files")
    single_parser.add_argument("source", help="Source YAML file")
    single_parser.add_argument("target", help="Target YAML file")
    single_parser.add_argument("--config", "-c", help="Configuration file defining sync rules")
    single_parser.add_argument("--params", "-p", nargs="+", help="Specific parameters to sync")
    single_parser.add_argument("--delete", "-D", nargs="+", help="Specific parameters to delete")
    single_parser.add_argument("--dry-run", "-d", action="store_true", 
                            help="Show changes without applying them")
    single_parser.add_argument("--sync-template", "-T", action="store_true",
                            help="Sync the template section")
    single_parser.add_argument("--yes", "-y", action="store_true",
                            help="Automatically apply changes without prompting")
    single_parser.add_argument("--filter", "-f", 
                            help="Filter by field value (format: field.path:substring)")
    
    # Bulk sync command
    bulk_parser = subparsers.add_parser("bulk", help="Sync parameters across multiple files")
    bulk_parser.add_argument("--source-pattern", "-s", required=True,
                           help="Pattern for source files")
    bulk_parser.add_argument("--target-pattern", "-t", required=True,
                           help="Pattern for target files")
    bulk_parser.add_argument("--config", "-c", required=True,
                           help="Configuration file defining sync rules")
    bulk_parser.add_argument("--dry-run", "-d", action="store_true",
                           help="Show changes without applying them")
    bulk_parser.add_argument("--non-interactive", "-n", action="store_true",
                           help="Apply all changes without prompting")
    bulk_parser.add_argument("--sync-template", "-T", action="store_true",
                           help="Sync the template section")
    bulk_parser.add_argument("--yes", "-y", action="store_true",
                           help="Automatically apply all changes without prompting")
    bulk_parser.add_argument("--filter", "-f", 
                           help="Filter by field value (format: field.path:substring)")
    
    # Parse arguments
    parsed_args = parser.parse_args(args)
    
    if parsed_args.command == "sync":
        # Call single file sync
        param_sync = ParamSync(parsed_args.config)
        
        # Check if we should prompt for confirmation
        proceed = True
        if not parsed_args.dry_run and not parsed_args.yes:
            response = input("Apply changes? [y/N] ").lower()
            proceed = response in ('y', 'yes')
        
        if proceed or parsed_args.dry_run:
            diff = param_sync.sync_parameters(
                parsed_args.source, 
                parsed_args.target,
                parsed_args.params,
                parsed_args.delete,
                parsed_args.dry_run,
                parsed_args.sync_template,
                parsed_args.filter
            )
            
            # Print diff and summary only if file wasn't filtered out
            if diff:
                param_sync.print_diff(diff)
                
                # Print summary
                total_changes = len(diff['added']) + len(diff['modified']) + len(diff['deleted']) + (1 if diff['template'] else 0)
                if total_changes > 0:
                    action = "Would apply" if parsed_args.dry_run else "Applied"
                    template_changes = 1 if diff['template'] else 0
                    print(f"\n{action} {total_changes} changes ({len(diff['added'])} additions, {len(diff['modified'])} modifications, {len(diff['deleted'])} deletions, {template_changes} template changes)")
        
    elif parsed_args.command == "bulk":
        # Call bulk sync
        bulk_sync = BulkParamSync(parsed_args.config)
        summary = bulk_sync.sync_bulk(
            parsed_args.source_pattern,
            parsed_args.target_pattern,
            parsed_args.dry_run,
            not parsed_args.non_interactive,
            parsed_args.sync_template,
            parsed_args.yes,
            parsed_args.filter
        )
        
        # Print summary
        print("\nSummary:")
        print(f"  Files processed: {summary['total_files']}")
        if 'filtered_files' in summary and summary['filtered_files'] > 0:
            print(f"  Files filtered out: {summary['filtered_files']}")
        print(f"  Files changed: {summary['changed_files']}")
        print(f"  Total changes: {summary['total_changes']}")
        
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())