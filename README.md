# Sceptre Sync Utility

A powerful utility for synchronizing configuration values between YAML files, originally designed for Sceptre but now supports any YAML configuration structure.

## Features

- **Multi-Key Synchronization**: Sync multiple configuration sections in a single operation
- **Generic Key Support**: Sync any top-level or nested key in YAML files (not just `parameters`)
- **Backward Compatible**: Defaults to `parameters` for existing configurations
- **Nested Key Support**: Use dot notation to sync nested structures (e.g., `stack_tags.environment`)
- **Pattern-Based Configuration**: Define different sync rules for different file patterns
- **Format Preservation**: Maintains YAML formatting, comments, and structure
- **Bulk Operations**: Sync across multiple files with pattern matching
- **Interactive Mode**: Confirm changes before applying
- **Dry Run Mode**: Preview changes without modifying files
- **Filter Support**: Process only files matching specific criteria

## Installation

```bash
# Clone the repository
git clone <repository-url>

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

## Usage

### Basic Parameter Sync (Original Behavior)

Synchronize parameters between two files:

```bash
python -m sceptre_sync.param_sync source.yaml target.yaml --params VpcCidr SubnetCidr
```

### Generic Key Sync (New Feature)

Synchronize any key in your YAML files:

```bash
# Sync stack_tags instead of parameters
python -m sceptre_sync.param_sync source.yaml target.yaml --sync-key stack_tags --params Environment Owner

# Sync sceptre_user_data
python -m sceptre_sync.param_sync source.yaml target.yaml --sync-key sceptre_user_data --params database_name retention_days

# Sync nested keys using dot notation
python -m sceptre_sync.param_sync source.yaml target.yaml --sync-key stack_tags.nested --params Environment Region
```

### Command Line Options

- `--config`, `-c`: Configuration file defining sync rules
- `--params`, `-p`: Specific parameters/values to sync
- `--delete`, `-D`: Parameters to delete from target
- `--dry-run`, `-d`: Show changes without applying them
- `--sync-template`, `-T`: Also sync the template section
- `--filter`, `-f`: Filter files by field value (e.g., `template.path:enhanced`)
- `--sync-key`, `-k`: Key to synchronize (default: `parameters`)

### Bulk Operations

Synchronize across multiple files:

```bash
# Sync parameters (default behavior)
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/prod/**/*.yaml" \
  --target-pattern "config/dev/**/*.yaml" \
  --config sync-config.yaml

# Sync stack_tags across environments
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/prod/**/*.yaml" \
  --target-pattern "config/dev/**/*.yaml" \
  --config sync-config.yaml \
  --sync-key stack_tags
```

## Configuration File

Create a YAML configuration file to define sync rules:

### Basic Configuration (Parameters Only)

```yaml
template_patterns:
  - pattern: "**/vpc.yaml"
    sync_params:
      - VpcCidr
      - PublicSubnetCidr
      - PrivateSubnetCidr
    delete_params:
      - DeprecatedParam
    sync_template: true
```

### Advanced Configuration (Multi-Key Sync)

```yaml
template_patterns:
  # Sync multiple keys in a single operation (NEW!)
  - pattern: "**/app/*.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcCidr
          - InstanceType
      - key: stack_tags
        sync_params:
          - Environment
          - Owner
          - CostCenter
      - key: sceptre_user_data
        sync_params:
          - database_name
          - retention_days
  
  # Single-key configuration (backward compatible)
  - pattern: "**/vpc.yaml"
    sync_key: parameters  # Optional, defaults to 'parameters'
    sync_params:
      - VpcCidr
      - SubnetCidr
  
  # Legacy format still works
  - pattern: "**/legacy/*.yaml"
    sync_params:  # No sync_key means 'parameters'
      - Environment
      - Region
```

## Examples

### Example 1: Multi-Key Sync (NEW!)

With the new multi-key support, you can synchronize multiple configuration sections in a single operation:

```bash
# Using config file with sync_rules
python -m sceptre_sync.param_sync prod/app.yaml dev/app.yaml --config multi-sync.yaml
```

This will sync parameters, stack_tags, and sceptre_user_data all at once based on your configuration.

### Example 2: Sync Stack Tags Only

Source file (`prod/app.yaml`):
```yaml
template: app-template.yaml
stack_tags:
  Environment: production
  Owner: platform-team
  CostCenter: engineering
parameters:
  InstanceType: t3.large
```

Target file (`dev/app.yaml`):
```yaml
template: app-template.yaml
stack_tags:
  Environment: development
  Owner: dev-team
parameters:
  InstanceType: t2.micro
```

Command:
```bash
python -m sceptre_sync.param_sync prod/app.yaml dev/app.yaml \
  --sync-key stack_tags \
  --params Environment Owner CostCenter
```

Result in `dev/app.yaml`:
```yaml
template: app-template.yaml
stack_tags:
  Environment: production      # Changed from 'development'
  Owner: platform-team         # Changed from 'dev-team'
  CostCenter: engineering      # Added
parameters:
  InstanceType: t2.micro       # Unchanged
```

### Multi-Key Sync Output

When using `sync_rules` to sync multiple keys, the output clearly shows changes for each key:

```
Changes to apply:

  [parameters]
    ~ VpcCidr: 10.1.0.0/16 -> 10.0.0.0/16
    ~ InstanceType: t2.micro -> t3.large
    
  [stack_tags]
    + CostCenter: engineering
    ~ Environment: development -> production
    ~ Owner: dev-team -> platform-team
    
  [sceptre_user_data]
    ~ database_name: dev_db -> prod_db
    ~ retention_days: 7 -> 30
```

### Example 3: Sync Nested Configuration

```bash
# Sync nested configuration values
python -m sceptre_sync.param_sync source.yaml target.yaml \
  --sync-key config.database.settings \
  --params connection_pool max_retries
```

### Example 4: Filter-Based Sync

```bash
# Only sync files that use enhanced templates
python -m sceptre_sync.param_sync source.yaml target.yaml \
  --filter "template.path:enhanced" \
  --sync-key stack_tags \
  --params Environment
```

### Example 5: Backward Compatible Usage

```bash
# Original behavior - syncs 'parameters' by default
python -m sceptre_sync.param_sync source.yaml target.yaml \
  --params VpcCidr InstanceType

# Explicitly specify parameters (same result)
python -m sceptre_sync.param_sync source.yaml target.yaml \
  --sync-key parameters \
  --params VpcCidr InstanceType
```

## Use Cases

1. **Environment Promotion**: Sync production settings to development environments
2. **Tag Management**: Ensure consistent tagging across stacks
3. **Configuration Drift**: Detect and fix configuration differences
4. **Sceptre User Data**: Sync custom Jinja2 variables between stacks
5. **Multi-Region Deployments**: Maintain consistent configurations across regions

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sceptre_sync --cov-report=term-missing

# Run specific test file
pytest tests/test_generic_sync.py -v
```

## Requirements

- Python 3.8+
- ruamel.yaml (preserves YAML formatting)
- jsonschema (configuration validation)
- pytest (for testing)
