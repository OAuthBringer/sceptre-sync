"""
Shared pytest fixtures and configuration for sceptre-sync tests.

Because repeating yourself in tests is like using the same password everywhere -
technically works, but you're setting yourself up for pain.
"""

import pytest
import tempfile
import shutil
import os
import sys
from io import StringIO
from contextlib import contextmanager
from unittest.mock import Mock


@pytest.fixture
def temp_dir():
    """Create a temporary directory that's automatically cleaned up."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def capture_output():
    """Context manager to capture stdout and stderr."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = StringIO()
    stderr_capture = StringIO()
    
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        yield stdout_capture, stderr_capture
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# Common YAML content for tests
SAMPLE_YAML_CONTENT = {
    'vpc_source': """
template:
  path: templates/vpc.yaml
  type: cloudformation

parameters:
  VpcCidr: "10.0.0.0/16"
  PublicSubnetCidr: "10.0.1.0/24"
  PrivateSubnetCidr: "10.0.2.0/24"
  InstanceType: "t3.micro"
  Environment: "alpha"
""",
    
    'vpc_target': """
template:
  path: templates/vpc.yaml
  type: cloudformation

parameters:
  VpcCidr: "10.1.0.0/16"
  PublicSubnetCidr: "10.1.1.0/24"
  PrivateSubnetCidr: "10.1.2.0/24"
  InstanceType: "t2.micro"
  Environment: "dev"
""",
    
    'config_with_delete': """
template_patterns:
  - pattern: "*/vpc.yaml"
    sync_params:
      - VpcCidr
      - PublicSubnetCidr
      - PrivateSubnetCidr
    delete_params:
      - DeprecatedParam
    sync_template: true
  - pattern: "*/api/*.yaml"
    sync_params:
      - CPUReservation
      - MemoryReservation
"""
}


@pytest.fixture
def yaml_content():
    """Provide common YAML content for tests."""
    return SAMPLE_YAML_CONTENT


@pytest.fixture
def config_file(temp_dir):
    """Create a basic config file for testing."""
    config_path = os.path.join(temp_dir, "config.yaml")
    with open(config_path, 'w') as f:
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
  - pattern: "*test.yaml"
    sync_params:
      - VpcCidr
  - pattern: "*test*.yaml"
    sync_params:
      - VpcCidr
""")
    return config_path


@pytest.fixture
def simple_config_file(temp_dir):
    """Create a simple config file with just test patterns."""
    config_path = os.path.join(temp_dir, "simple_config.yaml")
    with open(config_path, 'w') as f:
        f.write("""
template_patterns:
  - pattern: "*vpc.yaml"
    sync_params:
      - VpcCidr
  - pattern: "*api.yaml"
    sync_params:
      - CPUReservation
""")
    return config_path


@pytest.fixture
def source_target_files(temp_dir):
    """Create a pair of source and target YAML files."""
    source_dir = os.path.join(temp_dir, 'source')
    target_dir = os.path.join(temp_dir, 'target')
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)
    
    source_file = os.path.join(source_dir, 'test.yaml')
    target_file = os.path.join(target_dir, 'test.yaml')
    
    with open(source_file, 'w') as f:
        f.write("parameters:\n  VpcCidr: '10.0.0.0/16'\n")
    
    with open(target_file, 'w') as f:
        f.write("parameters:\n  VpcCidr: '10.1.0.0/16'\n")
    
    return source_file, target_file


@pytest.fixture
def environment_files(temp_dir):
    """Create directory structure for environment-based file pairing tests."""
    alpha_dir = os.path.join(temp_dir, 'config', 'di-alpha')
    alpha_api_dir = os.path.join(alpha_dir, 'api')
    dev_dir = os.path.join(temp_dir, 'config', 'di-dev')
    dev_api_dir = os.path.join(dev_dir, 'api')
    
    os.makedirs(alpha_api_dir, exist_ok=True)
    os.makedirs(dev_api_dir, exist_ok=True)
    
    # Create source files
    alpha_vpc = os.path.join(alpha_dir, 'vpc.yaml')
    alpha_api = os.path.join(alpha_api_dir, 'tasks.yaml')
    alpha_db = os.path.join(alpha_dir, 'database.yaml')
    
    # Create target files (only vpc and api exist)
    dev_vpc = os.path.join(dev_dir, 'vpc.yaml')
    dev_api = os.path.join(dev_api_dir, 'tasks.yaml')
    
    # Write test content
    for f in [alpha_vpc, alpha_api, alpha_db]:
        with open(f, 'w') as file:
            file.write(f"test: {os.path.basename(f)}")
    
    for f in [dev_vpc, dev_api]:
        with open(f, 'w') as file:
            file.write(f"test: {os.path.basename(f)}")
    
    return {
        'alpha_dir': alpha_dir,
        'dev_dir': dev_dir,
        'alpha_vpc': alpha_vpc,
        'alpha_api': alpha_api,
        'alpha_db': alpha_db,
        'dev_vpc': dev_vpc,
        'dev_api': dev_api
    }


@pytest.fixture
def sync_result_factory():
    """Factory for creating sync result dictionaries."""
    def _create_result(added=None, modified=None, deleted=None, unchanged=None, template=None):
        return {
            'added': added or {},
            'modified': modified or {},
            'deleted': deleted or {},
            'unchanged': unchanged or {},
            'template': template
        }
    return _create_result


@pytest.fixture
def mock_sync_result(sync_result_factory):
    """Standard mock result for sync operations."""
    return sync_result_factory()


@pytest.fixture
def mock_sync_result_with_changes(sync_result_factory):
    """Mock result with various changes for testing."""
    return sync_result_factory(
        added={'NewParam': 'value'},
        modified={'ModParam': {'old': 'old_val', 'new': 'new_val'}},
        deleted={'DelParam': 'deleted_value'},
        template={'old': {'path': 'old.yaml'}, 'new': {'path': 'new.yaml'}}
    )


@pytest.fixture
def mock_bulk_sync_summary():
    """Standard mock summary for bulk sync operations."""
    return {
        'total_files': 5,
        'changed_files': 3,
        'total_changes': 10,
        'filtered_files': 0,
        'file_changes': {}
    }


# Register custom markers to avoid warnings
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
