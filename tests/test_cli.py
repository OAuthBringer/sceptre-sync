"""
Test for cli module.

Testing the command-line interface because user experience starts at the terminal,
and a broken CLI is like a door without a handle - technically still a door,
but good luck getting through it.
"""

import pytest
from unittest.mock import Mock, patch, call
from io import StringIO
import sys

from sceptre_sync.cli import main


class TestCLI:
    """Test the CLI functionality."""

    def test_main_with_no_arguments_shows_help(self, capsys):
        """Test that main with no arguments shows help and returns 1."""
        # Call main with empty args
        exit_code = main([])
        
        # Check exit code
        assert exit_code == 1
        
        # Check that help was printed
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert "Synchronize parameters between YAML configuration files" in captured.out
        assert "sync" in captured.out
        assert "bulk" in captured.out

    @patch('sceptre_sync.cli.ParamSync')
    def test_sync_command_basic(self, mock_param_sync_class, mock_sync_result):
        """Test basic sync command execution."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        mock_param_sync.sync_parameters.return_value = {
            **mock_sync_result,
            'added': {'NewParam': 'value'}
        }
        
        # Test with dry-run (no prompt needed)
        args = ["sync", "source.yaml", "target.yaml", "--dry-run"]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        mock_param_sync_class.assert_called_once_with(None)  # No config specified
        mock_param_sync.sync_parameters.assert_called_once_with(
            "source.yaml", "target.yaml", None, None, True, False, None
        )
        mock_param_sync.print_diff.assert_called_once()

    @patch('sceptre_sync.cli.ParamSync')
    def test_sync_command_with_all_options(self, mock_param_sync_class, mock_sync_result):
        """Test sync command with all options specified."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        mock_param_sync.sync_parameters.return_value = mock_sync_result
        
        # Test with all options
        args = [
            "sync", "source.yaml", "target.yaml",
            "--config", "config.yaml",
            "--params", "Param1", "Param2",
            "--delete", "OldParam",
            "--sync-template",
            "--filter", "template.path:enhanced",
            "--yes"  # Auto-yes to avoid prompt
        ]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        mock_param_sync_class.assert_called_once_with("config.yaml")
        mock_param_sync.sync_parameters.assert_called_once_with(
            "source.yaml", "target.yaml",
            ["Param1", "Param2"],  # params
            ["OldParam"],  # delete
            False,  # not dry-run
            True,   # sync-template
            "template.path:enhanced"  # filter
        )

    @patch('sceptre_sync.cli.ParamSync')
    @patch('builtins.input', return_value='y')
    def test_sync_command_with_user_confirmation_yes(self, mock_input, mock_param_sync_class, mock_sync_result):
        """Test sync command when user confirms changes."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        mock_param_sync.sync_parameters.return_value = {
            **mock_sync_result,
            'added': {'NewParam': 'value'}
        }
        
        # Test without --yes flag (prompt expected)
        args = ["sync", "source.yaml", "target.yaml"]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        mock_input.assert_called_once_with("Apply changes? [y/N] ")
        mock_param_sync.sync_parameters.assert_called_once()
        mock_param_sync.print_diff.assert_called_once()

    @patch('sceptre_sync.cli.ParamSync')
    @patch('builtins.input', return_value='n')
    def test_sync_command_with_user_confirmation_no(self, mock_input, mock_param_sync_class):
        """Test sync command when user declines changes."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        
        # Test without --yes flag and user says no
        args = ["sync", "source.yaml", "target.yaml"]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        mock_input.assert_called_once_with("Apply changes? [y/N] ")
        # sync_parameters should NOT be called when user says no
        mock_param_sync.sync_parameters.assert_not_called()

    @patch('sceptre_sync.cli.ParamSync')
    def test_sync_command_with_changes_summary(self, mock_param_sync_class, mock_sync_result_with_changes, capsys):
        """Test that sync command prints correct summary of changes."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        mock_param_sync.sync_parameters.return_value = mock_sync_result_with_changes
        
        args = ["sync", "source.yaml", "target.yaml", "--dry-run"]
        exit_code = main(args)
        
        captured = capsys.readouterr()
        assert "Would apply 4 changes" in captured.out
        assert "1 additions" in captured.out
        assert "1 modifications" in captured.out
        assert "1 deletions" in captured.out
        assert "1 template changes" in captured.out

    @patch('sceptre_sync.cli.ParamSync')
    def test_sync_command_with_no_changes(self, mock_param_sync_class, mock_sync_result, capsys):
        """Test sync command when no changes are needed."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        mock_param_sync.sync_parameters.return_value = {
            **mock_sync_result,
            'unchanged': {'Param': 'value'}
        }
        
        args = ["sync", "source.yaml", "target.yaml", "--dry-run"]
        exit_code = main(args)
        
        captured = capsys.readouterr()
        # Should not print summary when no changes
        assert "Would apply" not in captured.out

    @patch('sceptre_sync.cli.ParamSync')
    def test_sync_command_with_filtered_file(self, mock_param_sync_class):
        """Test sync command when file is filtered out."""
        # Set up mocks
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        # Empty dict means file was filtered out
        mock_param_sync.sync_parameters.return_value = {}
        
        args = ["sync", "source.yaml", "target.yaml", "--filter", "type:vpc", "--dry-run"]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        # print_diff should not be called for filtered files
        mock_param_sync.print_diff.assert_not_called()

    @patch('sceptre_sync.cli.BulkParamSync')
    def test_bulk_command_basic(self, mock_bulk_sync_class, mock_bulk_sync_summary, capsys):
        """Test basic bulk command execution."""
        # Set up mocks
        mock_bulk_sync = Mock()
        mock_bulk_sync_class.return_value = mock_bulk_sync
        mock_bulk_sync.sync_bulk.return_value = mock_bulk_sync_summary
        
        args = [
            "bulk",
            "--source-pattern", "*/alpha/*.yaml",
            "--target-pattern", "*/dev/*.yaml",
            "--config", "config.yaml",
            "--dry-run"
        ]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        mock_bulk_sync_class.assert_called_once_with("config.yaml")
        mock_bulk_sync.sync_bulk.assert_called_once_with(
            "*/alpha/*.yaml",
            "*/dev/*.yaml",
            True,   # dry-run
            True,   # interactive (not --non-interactive)
            False,  # sync-template
            False,  # yes
            None    # filter
        )
        
        captured = capsys.readouterr()
        assert "Summary:" in captured.out
        assert "Files processed: 5" in captured.out
        assert "Files changed: 3" in captured.out
        assert "Total changes: 10" in captured.out

    @patch('sceptre_sync.cli.BulkParamSync')
    def test_bulk_command_with_all_options(self, mock_bulk_sync_class, mock_bulk_sync_summary, capsys):
        """Test bulk command with all options specified."""
        # Set up mocks
        mock_bulk_sync = Mock()
        mock_bulk_sync_class.return_value = mock_bulk_sync
        mock_bulk_sync.sync_bulk.return_value = {
            **mock_bulk_sync_summary,
            'filtered_files': 2
        }
        
        args = [
            "bulk",
            "--source-pattern", "*/alpha/**/*.yaml",
            "--target-pattern", "*/dev/**/*.yaml",
            "--config", "config.yaml",
            "--non-interactive",
            "--sync-template",
            "--filter", "template.type:vpc",
            "--yes"
        ]
        exit_code = main(args)
        
        # Verify
        assert exit_code == 0
        mock_bulk_sync.sync_bulk.assert_called_once_with(
            "*/alpha/**/*.yaml",
            "*/dev/**/*.yaml",
            False,  # not dry-run
            False,  # not interactive (--non-interactive)
            True,   # sync-template
            True,   # yes
            "template.type:vpc"  # filter
        )
        
        captured = capsys.readouterr()
        assert "Files filtered out: 2" in captured.out

    @patch('sceptre_sync.cli.BulkParamSync')
    def test_bulk_command_with_no_filtered_files(self, mock_bulk_sync_class, capsys):
        """Test bulk command output when no files are filtered."""
        # Set up mocks
        mock_bulk_sync = Mock()
        mock_bulk_sync_class.return_value = mock_bulk_sync
        mock_bulk_sync.sync_bulk.return_value = {
            'total_files': 3,
            'changed_files': 2,
            'total_changes': 5,
            'file_changes': {}
        }
        
        args = [
            "bulk",
            "-s", "*.yaml",
            "-t", "target/*.yaml",
            "-c", "config.yaml"
        ]
        exit_code = main(args)
        
        captured = capsys.readouterr()
        # Should not show filtered files line when none are filtered
        assert "Files filtered out:" not in captured.out

    def test_invalid_command_shows_help(self, capsys):
        """Test that invalid command shows help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["invalid-command"])
        
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "usage:" in captured.err
        assert "invalid choice" in captured.err

    def test_sync_command_missing_required_args(self, capsys):
        """Test sync command with missing required arguments."""
        with pytest.raises(SystemExit) as exc_info:
            main(["sync", "source.yaml"])  # Missing target
        
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "required" in captured.err.lower()

    def test_bulk_command_missing_required_args(self, capsys):
        """Test bulk command with missing required arguments."""
        with pytest.raises(SystemExit) as exc_info:
            main(["bulk", "--source-pattern", "*.yaml"])  # Missing target-pattern and config
        
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "required" in captured.err.lower()

    @patch('sceptre_sync.param_sync.ParamSync.sync_parameters')
    @patch('sceptre_sync.param_sync.ParamSync.print_diff')
    def test_cli_integration_with_param_sync(self, mock_print, mock_sync, mock_sync_result):
        """Test that CLI correctly integrates with ParamSync."""
        # This is more of an integration test but important for coverage
        mock_sync.return_value = {
            **mock_sync_result,
            'added': {'TestParam': 'value'}
        }
        
        args = ["sync", "source.yaml", "target.yaml", "--params", "TestParam", "--yes"]
        exit_code = main(args)
        
        assert exit_code == 0
        mock_sync.assert_called_once()
        mock_print.assert_called_once()

    @patch('sceptre_sync.cli.ParamSync')
    def test_short_option_flags(self, mock_param_sync_class, mock_sync_result):
        """Test that short option flags work correctly."""
        mock_param_sync = Mock()
        mock_param_sync_class.return_value = mock_param_sync
        mock_param_sync.sync_parameters.return_value = mock_sync_result
        
        # Test short flags for sync command
        args = ["sync", "s.yaml", "t.yaml", "-c", "cfg.yaml", "-p", "P1", "-D", "P2", "-d", "-T", "-f", "a:b"]
        exit_code = main(args)
        
        assert exit_code == 0
        mock_param_sync_class.assert_called_with("cfg.yaml")
        mock_param_sync.sync_parameters.assert_called_with(
            "s.yaml", "t.yaml", ["P1"], ["P2"], True, True, "a:b"
        )

    def test_end_to_end_help_command(self, capsys):
        """Integration test for help display."""
        # Test main help
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Synchronize parameters between YAML configuration files" in captured.out
        assert "sync" in captured.out
        assert "bulk" in captured.out

    def test_sync_subcommand_help(self, capsys):
        """Test sync subcommand help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["sync", "--help"])
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # The description is in the parent parser, not the subcommand help
        assert "source" in captured.out
        assert "target" in captured.out
        assert "--dry-run" in captured.out
        assert "--sync-template" in captured.out

    def test_bulk_subcommand_help(self, capsys):
        """Test bulk subcommand help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["bulk", "--help"])
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # The description is in the parent parser, not the subcommand help
        assert "--source-pattern" in captured.out
        assert "--target-pattern" in captured.out
        assert "--source-pattern" in captured.out
        assert "--non-interactive" in captured.out
