"""
Tests for common utility functions.

Because shared code needs tests too - like testing the foundation 
before building the house.
"""

import pytest
from sceptre_sync.common import format_diff_summary, calculate_total_changes


class TestCommon:
    """Test common utility functions."""
    
    def test_calculate_total_changes_empty_diff(self):
        """Test calculating total changes for empty diff."""
        diff = {
            'added': {},
            'modified': {},
            'deleted': {},
            'template': None
        }
        assert calculate_total_changes(diff) == 0
    
    def test_calculate_total_changes_with_all_types(self):
        """Test calculating total changes with all change types."""
        diff = {
            'added': {'param1': 'val1', 'param2': 'val2'},
            'modified': {'param3': {'old': 'old', 'new': 'new'}},
            'deleted': {'param4': 'val4'},
            'template': {'old': 'old_template', 'new': 'new_template'}
        }
        assert calculate_total_changes(diff) == 5
    
    def test_calculate_total_changes_template_only(self):
        """Test calculating total changes with template change only."""
        diff = {
            'added': {},
            'modified': {},
            'deleted': {},
            'template': {'old': 'old', 'new': 'new'}
        }
        assert calculate_total_changes(diff) == 1
    
    def test_format_diff_summary_dry_run(self):
        """Test formatting diff summary for dry run mode."""
        diff = {
            'added': {'p1': 'v1'},
            'modified': {'p2': {'old': 'o', 'new': 'n'}},
            'deleted': {},
            'template': None
        }
        result = format_diff_summary(diff, dry_run=True)
        assert "Would apply 2 changes" in result
        assert "1 additions" in result
        assert "1 modifications" in result
        assert "0 deletions" in result
        assert "0 template changes" in result
    
    def test_format_diff_summary_applied(self):
        """Test formatting diff summary for applied changes."""
        diff = {
            'added': {},
            'modified': {},
            'deleted': {'p1': 'v1', 'p2': 'v2'},
            'template': {'old': 'o', 'new': 'n'}
        }
        result = format_diff_summary(diff, dry_run=False)
        assert "Applied 3 changes" in result
        assert "0 additions" in result
        assert "0 modifications" in result
        assert "2 deletions" in result
        assert "1 template changes" in result
