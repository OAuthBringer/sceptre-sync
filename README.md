# Parameter Sync Utility

A utility for synchronizing configuration parameters between YAML files, particularly designed for Sceptre configuration files.

## Features

- Synchronize specific parameters between YAML files
- Preserve formatting and comments in YAML files
- Pattern-based configuration to define which parameters to sync
- Support for both single file operations and bulk operations
- Interactive mode for confirming changes
- Dry run mode to preview changes without applying them

## Installation

```bash
# Clone the repository
git clone <repository-url>

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

## Usage

### Single File Sync

Synchronize parameters between two files:

```bash
python -m param_sync.cli sync source_file.yaml target_file.yaml --config config.yaml
```

Options:
- `--config`, `-c`: Configuration file defining sync rules
- `--params`, `-p`: Specific parameters to sync (overrides config)
- `--dry-run`, `-d`: Show changes without applying them

### Bulk Sync

Synchronize parameters across multiple files:

```bash
python -m param_sync.cli bulk --source-pattern "*/di-alpha/**/*.yaml" --target-pattern "*/di-dev/**/*.yaml" --config config.yaml
```

Options:
- `--source-pattern`, `-s`: Pattern for source files
- `--target-pattern`, `-t`: Pattern for target files
- `--config`, `-c`: Configuration file defining sync rules
- `--dry-run`, `-d`: Show changes without applying them
- `--non-interactive`, `-n`: Apply all changes without prompting

## Configuration

Create a YAML configuration file to define which parameters to sync for different file patterns:

```yaml
template_patterns:
  - pattern: "*/api/tasks/*.yaml"
    sync_params:
      - CPUReservation
      - MemoryReservation
      - ScaleOutCooldownPeriod
      - CpuScalingTargetValue

  - pattern: "*/core/vpc.yaml"
    sync_params:
      - CidrBlock
      - PublicSubnetCidrBlocks
      - PrivateSubnetCidrBlocks
```

## Examples

### Sync specific parameters between two files

```bash
python -m param_sync.cli sync config/di-alpha/api/tasks/service.yaml config/di-dev/api/tasks/service.yaml --params CPUReservation MemoryReservation
```

### Preview changes without applying them

```bash
python -m param_sync.cli sync config/di-alpha/api/tasks/service.yaml config/di-dev/api/tasks/service.yaml --config config.yaml --dry-run
```

### Bulk sync from alpha to dev environment

```bash
python -m param_sync.cli bulk --source-pattern "config/di-alpha/api/tasks/*.yaml" --target-pattern "config/di-dev/api/tasks/*.yaml" --config config.yaml
```

## Requirements

- Python 3.6+
- ruamel.yaml
- jsonschema