"""
Test for bulk_sync module.

Testing bulk operations because if you're going to make mistakes,
why not make them at scale? Like deploying to production on Friday,
but for configuration files.
"""

import pytest
from unittest.mock import Mock, patch, call, MagicMock
import os
import tempfile
import shutil
from pathlib import Path

from sceptre_sync.bulk_sync import BulkParamSync, main
import ruamel.yaml


class TestBulkParamSync:
    """Test the BulkParamSync class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "config.yaml")
        
        # Create a simple config
        with open(self.config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*/vpc.yaml"
    sync_params:
      - VpcCidr
      - PublicSubnetCidr
  - pattern: "*/api/*.yaml"
    sync_params:
      - CPUReservation
      - MemoryReservation
""")

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_with_config(self):
        """Test BulkParamSync initialization with config."""
        bulk_sync = BulkParamSync(self.config_file)
        assert bulk_sync.param_sync is not None
        assert bulk_sync.param_sync.config is not None
        assert 'template_patterns' in bulk_sync.param_sync.config

    def test_init_without_config(self):
        """Test BulkParamSync initialization without config."""
        bulk_sync = BulkParamSync()
        assert bulk_sync.param_sync is not None
        assert bulk_sync.param_sync.config == {}

    @patch('glob.glob')
    def test_find_matching_files(self, mock_glob):
        """Test finding files with glob patterns."""
        mock_glob.return_value = [
            'config/di-alpha/vpc.yaml',
            'config/di-alpha/api/tasks.yaml'
        ]
        
        # Mock ParamSync to avoid ruamel.yaml plugin issues
        with patch('sceptre_sync.bulk_sync.ParamSync'):
            bulk_sync = BulkParamSync()
            files = bulk_sync.find_matching_files('config/di-alpha/**/*.yaml')
            
            assert len(files) == 2
            assert 'config/di-alpha/vpc.yaml' in files
            mock_glob.assert_called_once_with('config/di-alpha/**/*.yaml', recursive=True)

    @patch('glob.glob')
    def test_find_matching_files_no_matches(self, mock_glob):
        """Test finding files when no matches exist."""
        mock_glob.return_value = []
        
        bulk_sync = BulkParamSync()
        files = bulk_sync.find_matching_files('config/nonexistent/*.yaml')
        
        assert files == []

    @patch('glob.glob')
    @patch('os.path.exists')
    def test_generate_file_pairs_with_environments(self, mock_exists, mock_glob):
        """Test generating file pairs between environments."""
        # Setup mocks
        mock_glob.return_value = [
            'config/di-alpha/vpc.yaml',
            'config/di-alpha/api/tasks.yaml',
            'config/di-alpha/database.yaml'
        ]
        
        # First two files exist in target, third doesn't
        mock_exists.side_effect = [True, True, False]
        
        # Mock ParamSync to avoid ruamel.yaml plugin issues
        with patch('sceptre_sync.bulk_sync.ParamSync'):
            bulk_sync = BulkParamSync()
            pairs = bulk_sync.generate_file_pairs(
                'config/di-alpha/**/*.yaml',
                'config/di-dev/**/*.yaml'
            )
            
            assert len(pairs) == 2
            assert ('config/di-alpha/vpc.yaml', 'config/di-dev/vpc.yaml') in pairs
            assert ('config/di-alpha/api/tasks.yaml', 'config/di-dev/api/tasks.yaml') in pairs

    @patch('glob.glob')
    def test_generate_file_pairs_single_files(self, mock_glob):
        """Test generating pairs when single source and target files."""
        mock_glob.side_effect = [
            ['source/file.yaml'],  # source files
            ['target/file.yaml']   # target files
        ]
        
        # Mock ParamSync to avoid ruamel.yaml plugin issues
        with patch('sceptre_sync.bulk_sync.ParamSync'):
            bulk_sync = BulkParamSync()
            pairs = bulk_sync.generate_file_pairs('source/file.yaml', 'target/file.yaml')
            
            assert len(pairs) == 1
            assert pairs[0] == ('source/file.yaml', 'target/file.yaml')

    @patch('glob.glob')
    def test_generate_file_pairs_by_filename(self, mock_glob):
        """Test matching files by filename when no environment pattern."""
        mock_glob.side_effect = [
            ['dir1/vpc.yaml', 'dir1/api.yaml'],     # source files
            ['dir2/api.yaml', 'dir2/vpc.yaml']      # target files
        ]
        
        # Mock ParamSync to avoid ruamel.yaml plugin issues
        with patch('sceptre_sync.bulk_sync.ParamSync'):
            bulk_sync = BulkParamSync()
            pairs = bulk_sync.generate_file_pairs('dir1/*.yaml', 'dir2/*.yaml')
            
            assert len(pairs) == 2
            # Should match by filename
            assert ('dir1/vpc.yaml', 'dir2/vpc.yaml') in pairs
            assert ('dir1/api.yaml', 'dir2/api.yaml') in pairs

    @patch('glob.glob')
    def test_generate_file_pairs_no_source_files(self, mock_glob):
        """Test when no source files are found."""
        mock_glob.return_value = []
        
        bulk_sync = BulkParamSync()
        with patch('builtins.print') as mock_print:
            pairs = bulk_sync.generate_file_pairs('missing/*.yaml', 'target/*.yaml')
        
        assert pairs == []
        mock_print.assert_any_call("No source files found matching pattern: missing/*.yaml")

    @patch('glob.glob')
    def test_generate_file_pairs_no_target_files(self, mock_glob):
        """Test when no target files are found (non-environment pattern)."""
        mock_glob.side_effect = [
            ['source/file.yaml'],  # source files
            []                     # no target files
        ]
        
        # Mock ParamSync to avoid ruamel.yaml plugin issues
        with patch('sceptre_sync.bulk_sync.ParamSync'):
            bulk_sync = BulkParamSync()
            with patch('builtins.print') as mock_print:
                pairs = bulk_sync.generate_file_pairs('source/*.yaml', 'target/*.yaml')
            
            assert pairs == []
            mock_print.assert_any_call("No target files found matching pattern: target/*.yaml")

    @patch.object(BulkParamSync, 'generate_file_pairs')
    def test_sync_bulk_no_file_pairs(self, mock_generate_pairs):
        """Test sync_bulk when no file pairs are found."""
        mock_generate_pairs.return_value = []
        
        bulk_sync = BulkParamSync()
        with patch('builtins.print'):  # Suppress output
            summary = bulk_sync.sync_bulk('source/*.yaml', 'target/*.yaml')
        
        assert summary['total_files'] == 0
        assert summary['changed_files'] == 0
        assert summary['total_changes'] == 0

    def test_sync_bulk_with_real_files(self):
        """Test sync_bulk with actual files."""
        # Create test directory structure
        source_dir = os.path.join(self.temp_dir, 'config', 'di-alpha')
        target_dir = os.path.join(self.temp_dir, 'config', 'di-dev')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        # Create source file
        source_file = os.path.join(source_dir, 'vpc.yaml')
        with open(source_file, 'w') as f:
            f.write("""
template:
  path: templates/vpc.yaml
parameters:
  VpcCidr: "10.0.0.0/16"
  PublicSubnetCidr: "10.0.1.0/24"
  PrivateSubnetCidr: "10.0.2.0/24"
""")
        
        # Create target file with different values
        target_file = os.path.join(target_dir, 'vpc.yaml')
        with open(target_file, 'w') as f:
            f.write("""
template:
  path: templates/vpc.yaml
parameters:
  VpcCidr: "10.1.0.0/16"
  PublicSubnetCidr: "10.1.1.0/24"
  PrivateSubnetCidr: "10.1.2.0/24"
""")
        
        # Create bulk sync with config
        bulk_sync = BulkParamSync(self.config_file)
        
        # Test dry run
        with patch('builtins.print') as mock_print:
            summary = bulk_sync.sync_bulk(
                os.path.join(self.temp_dir, 'config/di-alpha/*.yaml'),
                os.path.join(self.temp_dir, 'config/di-dev/*.yaml'),
                dry_run=True
            )
        
        assert summary['total_files'] == 1
        assert summary['changed_files'] == 0  # dry run
        assert summary['total_changes'] == 0  # dry run
        
        # Verify output
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('VpcCidr' in str(call) for call in print_calls)
        assert any('10.0.0.0/16' in str(call) for call in print_calls)

    @patch('builtins.input', return_value='y')
    def test_sync_bulk_interactive_yes(self, mock_input):
        """Test bulk sync with interactive confirmation (user says yes)."""
        # Create test files
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        source_file = os.path.join(source_dir, 'test.yaml')
        target_file = os.path.join(target_dir, 'test.yaml')
        
        with open(source_file, 'w') as f:
            f.write("parameters:\n  VpcCidr: '10.0.0.0/16'\n")
        
        with open(target_file, 'w') as f:
            f.write("parameters:\n  VpcCidr: '10.1.0.0/16'\n")
        
        # Update config to match our test file
        with open(self.config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*test.yaml"
    sync_params:
      - VpcCidr
""")
        
        bulk_sync = BulkParamSync(self.config_file)
        
        with patch('builtins.print'):  # Suppress output
            summary = bulk_sync.sync_bulk(
                os.path.join(source_dir, '*.yaml'),
                os.path.join(target_dir, '*.yaml'),
                dry_run=False,
                interactive=True
            )
        
        # Verify the file was actually changed
        with open(target_file, 'r') as f:
            content = f.read()
            assert '10.0.0.0/16' in content
        
        assert summary['total_files'] == 1
        assert summary['changed_files'] == 1
        assert summary['total_changes'] == 1
        mock_input.assert_called_once()

    @patch('builtins.input', return_value='n')
    def test_sync_bulk_interactive_no(self, mock_input):
        """Test bulk sync when user declines changes."""
        # Create test files
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        source_file = os.path.join(source_dir, 'test.yaml')
        target_file = os.path.join(target_dir, 'test.yaml')
        
        with open(source_file, 'w') as f:
            f.write("parameters:\n  VpcCidr: '10.0.0.0/16'\n")
        
        with open(target_file, 'w') as f:
            f.write("parameters:\n  VpcCidr: '10.1.0.0/16'\n")
        
        # Update config to match our test file
        with open(self.config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*test.yaml"
    sync_params:
      - VpcCidr
""")
        
        bulk_sync = BulkParamSync(self.config_file)
        
        with patch('builtins.print'):  # Suppress output
            summary = bulk_sync.sync_bulk(
                os.path.join(source_dir, '*.yaml'),
                os.path.join(target_dir, '*.yaml'),
                dry_run=False,
                interactive=True
            )
        
        # Verify the file was NOT changed
        with open(target_file, 'r') as f:
            content = f.read()
            assert '10.1.0.0/16' in content  # Still has original value
        
        assert summary['total_files'] == 1
        assert summary['changed_files'] == 0
        assert summary['total_changes'] == 0

    def test_sync_bulk_yes_to_all(self):
        """Test bulk sync with yes_to_all flag."""
        # Create multiple test files
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        # Create two pairs of files
        for i in range(2):
            source_file = os.path.join(source_dir, f'test{i}.yaml')
            target_file = os.path.join(target_dir, f'test{i}.yaml')
            
            with open(source_file, 'w') as f:
                f.write(f"parameters:\n  VpcCidr: '10.{i}.0.0/16'\n")
            
            with open(target_file, 'w') as f:
                f.write("parameters:\n  VpcCidr: '192.168.0.0/16'\n")
        
        # Update config
        with open(self.config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*test*.yaml"
    sync_params:
      - VpcCidr
""")
        
        bulk_sync = BulkParamSync(self.config_file)
        
        with patch('builtins.print'):  # Suppress output
            with patch('builtins.input') as mock_input:
                summary = bulk_sync.sync_bulk(
                    os.path.join(source_dir, '*.yaml'),
                    os.path.join(target_dir, '*.yaml'),
                    dry_run=False,
                    yes_to_all=True
                )
        
        # Should not prompt when yes_to_all is True
        mock_input.assert_not_called()
        
        # Verify both files were changed
        for i in range(2):
            target_file = os.path.join(target_dir, f'test{i}.yaml')
            with open(target_file, 'r') as f:
                content = f.read()
                assert f'10.{i}.0.0/16' in content
        
        assert summary['changed_files'] == 2
        assert summary['total_changes'] == 2

    def test_sync_bulk_with_filter(self):
        """Test bulk sync with filter specification."""
        # Create custom config with patterns matching our test files
        with open(self.config_file, 'w') as f:
            f.write("""
template_patterns:
  - pattern: "*vpc.yaml"
    sync_params:
      - VpcCidr
  - pattern: "*api.yaml"
    sync_params:
      - CPUReservation
""")
        
        # Create test files
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        # Create VPC file (should match filter)
        vpc_source = os.path.join(source_dir, 'vpc.yaml')
        vpc_target = os.path.join(target_dir, 'vpc.yaml')
        with open(vpc_source, 'w') as f:
            f.write("""
template:
  path: templates/vpc.yaml
  type: vpc
parameters:
  VpcCidr: "10.0.0.0/16"
""")
        with open(vpc_target, 'w') as f:
            f.write("""
template:
  path: templates/vpc.yaml
  type: vpc
parameters:
  VpcCidr: "10.1.0.0/16"
""")
        
        # Create API file (should NOT match filter)
        api_source = os.path.join(source_dir, 'api.yaml')
        api_target = os.path.join(target_dir, 'api.yaml')
        with open(api_source, 'w') as f:
            f.write("""
template:
  path: templates/api.yaml
  type: api
parameters:
  CPUReservation: 256
""")
        with open(api_target, 'w') as f:
            f.write("""
template:
  path: templates/api.yaml
  type: api
parameters:
  CPUReservation: 512
""")
        
        bulk_sync = BulkParamSync(self.config_file)
        
        with patch('builtins.print') as mock_print:
            summary = bulk_sync.sync_bulk(
                os.path.join(source_dir, '*.yaml'),
                os.path.join(target_dir, '*.yaml'),
                dry_run=True,
                filter_spec='template.type:vpc'
            )
        
        assert summary['total_files'] == 2
        assert summary['filtered_files'] == 1
        
        # Check that vpc file was processed
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('vpc.yaml' in str(call) and 'matches filter' in str(call) for call in print_calls)

    def test_sync_bulk_no_sync_params_defined(self):
        """Test bulk sync when no sync parameters are defined for a file."""
        # Create test file with no matching pattern
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        source_file = os.path.join(source_dir, 'unknown.yaml')
        target_file = os.path.join(target_dir, 'unknown.yaml')
        
        with open(source_file, 'w') as f:
            f.write("parameters:\n  Unknown: 'value'\n")
        with open(target_file, 'w') as f:
            f.write("parameters:\n  Unknown: 'other'\n")
        
        bulk_sync = BulkParamSync(self.config_file)
        
        with patch('builtins.print') as mock_print:
            summary = bulk_sync.sync_bulk(
                os.path.join(source_dir, '*.yaml'),
                os.path.join(target_dir, '*.yaml')
            )
        
        assert summary['total_files'] == 1
        assert summary['changed_files'] == 0
        
        # Verify skip message
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('No sync parameters defined' in str(call) for call in print_calls)


class TestBulkSyncMain:
    """Test the main function for bulk sync CLI."""

    def test_main_with_all_arguments(self):
        """Test main function with all arguments."""
        with patch('sceptre_sync.bulk_sync.BulkParamSync') as mock_bulk_class:
            mock_bulk = Mock()
            mock_bulk_class.return_value = mock_bulk
            mock_bulk.sync_bulk.return_value = {
                'total_files': 5,
                'changed_files': 3,
                'total_changes': 10,
                'filtered_files': 1,
                'file_changes': {}
            }
            
            with patch('sys.argv', [
                'bulk_sync.py',
                '--source-pattern', '*/alpha/*.yaml',
                '--target-pattern', '*/dev/*.yaml',
                '--config', 'config.yaml',
                '--dry-run',
                '--non-interactive',
                '--sync-template',
                '--yes',
                '--filter', 'type:vpc'
            ]):
                exit_code = main()
            
            assert exit_code == 0
            mock_bulk_class.assert_called_once_with('config.yaml')
            mock_bulk.sync_bulk.assert_called_once_with(
                '*/alpha/*.yaml',
                '*/dev/*.yaml',
                True,   # dry-run
                False,  # interactive (--non-interactive)
                True,   # sync-template
                True,   # yes
                'type:vpc'  # filter
            )

    def test_main_with_minimum_arguments(self):
        """Test main function with minimum required arguments."""
        with patch('sceptre_sync.bulk_sync.BulkParamSync') as mock_bulk_class:
            mock_bulk = Mock()
            mock_bulk_class.return_value = mock_bulk
            mock_bulk.sync_bulk.return_value = {
                'total_files': 1,
                'changed_files': 0,
                'total_changes': 0,
                'file_changes': {}
            }
            
            with patch('sys.argv', [
                'bulk_sync.py',
                '-s', 'source.yaml',
                '-t', 'target.yaml',
                '-c', 'config.yaml'
            ]):
                exit_code = main()
            
            assert exit_code == 0
            mock_bulk.sync_bulk.assert_called_once_with(
                'source.yaml',
                'target.yaml',
                False,  # not dry-run
                True,   # interactive (default)
                False,  # not sync-template
                False,  # not yes
                None    # no filter
            )

    def test_main_missing_required_args(self):
        """Test main function with missing required arguments."""
        with patch('sys.argv', ['bulk_sync.py', '--source-pattern', 'source/*.yaml']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 2

    @pytest.mark.integration
    def test_main_help(self, capsys):
        """Test main function help display."""
        with patch('sys.argv', ['bulk_sync.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "Bulk synchronize parameters" in captured.out
            assert "--source-pattern" in captured.out
            assert "--target-pattern" in captured.out
