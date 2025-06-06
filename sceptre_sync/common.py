"""
Common utilities for sceptre-sync.

Shared functionality between param_sync and bulk_sync modules.
Because DRY is not just a principle, it's a way of life.
"""

from typing import Dict


def calculate_total_changes(diff: Dict) -> int:
    """
    Calculate the total number of changes in a diff.

    Args:
        diff: Dict containing added, modified, deleted, and template changes

    Returns:
        Total count of all changes
    """
    # Check if this is a multi-key diff
    is_multi_key = any(isinstance(v, dict) and 'added' in v for k, v in diff.items() if k != 'template')
    
    if is_multi_key:
        # Multi-key format: sum changes across all keys
        total = 0
        for key, key_diff in diff.items():
            if key == 'template':
                if key_diff:
                    total += 1
            elif isinstance(key_diff, dict):
                total += len(key_diff.get('added', {}))
                total += len(key_diff.get('modified', {}))
                total += len(key_diff.get('deleted', {}))
        return total
    else:
        # Single-key format (legacy)
        total = len(diff.get('added', {}))
        total += len(diff.get('modified', {}))
        total += len(diff.get('deleted', {}))
        if diff.get('template'):
            total += 1
        return total


def format_diff_summary(diff: Dict, dry_run: bool = False) -> str:
    """
    Format a diff summary message.

    Args:
        diff: Dict containing the changes
        dry_run: Whether this is a dry run

    Returns:
        Formatted summary string
    """
    if not diff:
        return ""

    total_changes = calculate_total_changes(diff)
    if total_changes == 0:
        return ""

    action = "Would apply" if dry_run else "Applied"
    
    # Check if this is a multi-key diff
    is_multi_key = any(isinstance(v, dict) and 'added' in v for k, v in diff.items() if k != 'template')
    
    if is_multi_key:
        # Multi-key format: count changes across all keys
        additions = 0
        modifications = 0
        deletions = 0
        template_changes = 1 if diff.get('template') else 0
        
        for key, key_diff in diff.items():
            if key == 'template':
                continue
            elif isinstance(key_diff, dict):
                additions += len(key_diff.get('added', {}))
                modifications += len(key_diff.get('modified', {}))
                deletions += len(key_diff.get('deleted', {}))
        
        return (f"{action} {total_changes} changes "
                f"({additions} additions, "
                f"{modifications} modifications, "
                f"{deletions} deletions, "
                f"{template_changes} template changes)")
    else:
        # Single-key format (legacy)
        template_changes = 1 if diff.get('template') else 0
        
        return (f"{action} {total_changes} changes "
                f"({len(diff.get('added', {}))} additions, "
                f"{len(diff.get('modified', {}))} modifications, "
                f"{len(diff.get('deleted', {}))} deletions, "
                f"{template_changes} template changes)")
