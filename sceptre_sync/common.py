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
    template_changes = 1 if diff.get('template') else 0

    return (f"{action} {total_changes} changes "
            f"({len(diff.get('added', {}))} additions, "
            f"{len(diff.get('modified', {}))} modifications, "
            f"{len(diff.get('deleted', {}))} deletions, "
            f"{template_changes} template changes)")
