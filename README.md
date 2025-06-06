# Sceptre Sync Utility

A powerful YAML configuration synchronization tool that enables bulk updates across multiple files while preserving formatting and comments. Originally designed for AWS Sceptre but works with any YAML configuration files.

## 🚀 Key Features

- **Bulk Operations**: Sync hundreds of files with a single command using glob patterns
- **Multi-Key Synchronization**: Update multiple configuration sections simultaneously
- **Static Value Injection**: Define standard values in configuration that override source files
- **Flexible Key Support**: Sync any YAML key, not just `parameters`
- **Nested Key Support**: Access nested structures with dot notation (e.g., `config.database.host`)
- **Pattern-Based Rules**: Different sync rules for different file patterns
- **Format Preservation**: Maintains YAML formatting, comments, and structure
- **Optional Parameters**: Works with YAML files that don't have all keys
- **Backward Compatible**: Existing configurations continue to work

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd sceptre-sync

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## Quick Start

### Basic Bulk Sync (Most Common Use Case)

Synchronize parameters from development to production:

```bash
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/dev/**/*.yaml" \
  --target-pattern "config/prod/**/*.yaml" \
  --config sync-config.yaml \
  --yes  # Auto-approve all changes
```

### Example Configuration File

```yaml
# sync-config.yaml
template_patterns:
  # Modern multi-key configuration with static values
  - pattern: "**/app-*.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcCidr
          - InstanceType
        static_values:
          Environment: production  # Always set to production
          ManagedBy: sceptre      # Inject standard management tag
      
      - key: stack_tags
        sync_params:
          - Application
        static_values:
          CostCenter: engineering
          Owner: platform-team
          Compliance: sox
  
  # Simple configuration for VPC stacks
  - pattern: "**/vpc.yaml"
    sync_params:  # Legacy format - still works!
      - VpcCidr
      - PublicSubnetCidr
      - PrivateSubnetCidr
```

## Real-World Usage Examples

### 1. Standardize Environment Across All Stacks

Force all stacks to use production values regardless of source:

```yaml
# standardize-prod.yaml
template_patterns:
  - pattern: "**/*.yaml"
    sync_rules:
      - key: parameters
        static_values:
          Environment: production
          Region: us-east-1
          LogLevel: INFO
      
      - key: stack_tags
        static_values:
          Environment: production
          ManagedBy: terraform
          LastUpdated: "2024-01-01"
```

```bash
# Apply to all stacks in prod environment
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/dev/stub.yaml" \  # Source doesn't matter for static values
  --target-pattern "config/prod/**/*.yaml" \
  --config standardize-prod.yaml \
  --yes
```

### 2. Promote Changes from Dev to Prod

Selectively sync configuration while preserving environment-specific values:

```yaml
# promote-to-prod.yaml
template_patterns:
  - pattern: "**/app-*.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - InstanceType      # Sync these from dev
          - MinSize
          - MaxSize
        static_values:
          Environment: production  # But force prod environment
      
      - key: sceptre_user_data
        sync_params:
          - app_version
          - feature_flags
```

```bash
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/dev/apps/*.yaml" \
  --target-pattern "config/prod/apps/*.yaml" \
  --config promote-to-prod.yaml \
  --dry-run  # Preview changes first
```

### 3. Add Compliance Tags to All Resources

Inject required compliance tags without modifying existing tags:

```yaml
# compliance-tags.yaml
template_patterns:
  - pattern: "**/*.yaml"
    sync_rules:
      - key: stack_tags
        static_values:
          Compliance: sox-pci
          DataClassification: internal
          BackupRequired: "true"
          CostCenter: "{{ cost_center }}"  # Can use variables if needed
```

```bash
# Add compliance tags to all stacks
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/prod/stub.yaml" \
  --target-pattern "config/prod/**/*.yaml" \
  --config compliance-tags.yaml \
  --yes
```

### 4. Environment-Specific VPC Configuration

Sync network configuration between environments with different CIDR blocks:

```yaml
# network-sync.yaml
template_patterns:
  - pattern: "**/vpc.yaml"
    sync_params:
      - VpcCidr
      - PublicSubnetCidr
      - PrivateSubnetCidr
      - EnableNatGateway
      - EnableVpnGateway
    
  - pattern: "**/app-*.yaml"
    sync_rules:
      - key: parameters
        sync_params:
          - VpcId::output     # Reference Sceptre outputs
          - SubnetIds::output
```

### 5. Multi-Region Deployment Standardization

Ensure consistent configuration across regions:

```bash
# Sync from us-east-1 to all other regions
for region in us-west-2 eu-west-1 ap-southeast-1; do
  python -m sceptre_sync.bulk_sync \
    --source-pattern "config/prod/us-east-1/**/*.yaml" \
    --target-pattern "config/prod/${region}/**/*.yaml" \
    --config regional-sync.yaml \
    --yes
done
```

### 6. Selective Sync with Filters

Only sync stacks that match specific criteria:

```bash
# Only sync stacks using enhanced templates
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/dev/**/*.yaml" \
  --target-pattern "config/prod/**/*.yaml" \
  --config sync-config.yaml \
  --filter "template.path:enhanced" \
  --yes
```

## Advanced Configuration Options

### Multi-Key Sync Rules

```yaml
template_patterns:
  - pattern: "**/database-*.yaml"
    sync_rules:
      # Sync parameters with some static overrides
      - key: parameters
        sync_params:
          - DBInstanceClass
          - AllocatedStorage
        static_values:
          MultiAZ: "true"           # Force Multi-AZ in production
          BackupRetentionPeriod: 30 # Standard retention
        delete_params:
          - DeprecatedParameter
      
      # Nested key configuration
      - key: sceptre_user_data.database
        sync_params:
          - connection_string
        static_values:
          ssl_required: "true"
      
      # Complex nested structures
      - key: config.monitoring
        static_values:
          enabled: true
          retention_days: 90
          alerts:
            - type: cpu
              threshold: 80
            - type: memory
              threshold: 90
```

### Static Values with Complex Types

```yaml
template_patterns:
  - pattern: "**/app-*.yaml"
    sync_rules:
      - key: parameters
        static_values:
          # Lists
          SecurityGroups:
            - sg-app-default
            - sg-app-web
          
          # Nested dictionaries
          Tags:
            Environment: production
            Team: platform
            Compliance:
              - sox
              - pci
          
          # Multi-line strings
          UserData: |
            #!/bin/bash
            echo "Standardized startup script"
            /opt/app/start.sh
```

### Environment Mapping

Bulk sync automatically maps between environment directories:

```bash
# Automatically maps files between environments
# dev/vpc.yaml -> prod/vpc.yaml
# dev/app/web.yaml -> prod/app/web.yaml
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/di-development/**/*.yaml" \
  --target-pattern "config/di-production/**/*.yaml" \
  --config sync-config.yaml \
  --yes
```

## Command Line Reference

### Bulk Sync (Primary Interface)

```bash
python -m sceptre_sync.bulk_sync [OPTIONS]

Options:
  --source-pattern, -s   Glob pattern for source files (required)
  --target-pattern, -t   Glob pattern for target files (required)
  --config, -c          Configuration file path (required)
  --dry-run, -d         Preview changes without applying
  --yes, -y             Auto-approve all changes
  --non-interactive, -n  Run without prompts (same as --yes)
  --sync-template, -T    Also sync template sections
  --filter, -f          Filter by field value (e.g., template.path:enhanced)
```

### Single File Sync

```bash
python -m sceptre_sync.param_sync SOURCE TARGET [OPTIONS]

Options:
  --config, -c          Configuration file path
  --params, -p          Specific parameters to sync
  --delete, -D          Parameters to delete
  --dry-run, -d         Preview changes without applying
  --sync-template, -T    Also sync template section
  --filter, -f          Filter by field value
  --sync-key, -k        Key to sync (default: parameters)
```

## Common Patterns

### CI/CD Pipeline Integration

```bash
#!/bin/bash
# promote-to-prod.sh

set -e

# Dry run first
echo "Previewing changes..."
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/staging/**/*.yaml" \
  --target-pattern "config/prod/**/*.yaml" \
  --config promote-config.yaml \
  --dry-run

# Apply if approved
read -p "Apply changes? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  python -m sceptre_sync.bulk_sync \
    --source-pattern "config/staging/**/*.yaml" \
    --target-pattern "config/prod/**/*.yaml" \
    --config promote-config.yaml \
    --yes
fi
```

### Drift Detection

```bash
# Check if prod has drifted from staging
python -m sceptre_sync.bulk_sync \
  --source-pattern "config/staging/**/*.yaml" \
  --target-pattern "config/prod/**/*.yaml" \
  --config drift-check.yaml \
  --dry-run > drift-report.txt

if [ -s drift-report.txt ]; then
  echo "Configuration drift detected!"
  cat drift-report.txt
fi
```

## Tips and Best Practices

1. **Always dry-run first**: Use `--dry-run` to preview changes before applying
2. **Use static_values for standards**: Enforce organizational standards across all stacks
3. **Version control your sync configs**: Track sync configurations in git
4. **Be specific with patterns**: Use precise glob patterns to avoid unintended matches
5. **Test on non-production first**: Validate sync rules in dev/staging environments
6. **Use filters for selective updates**: Process subsets of files when needed
7. **Combine sync_params and static_values**: Sync some values, override others

## Troubleshooting

### No files found

```bash
# Debug file patterns
ls config/dev/**/*.yaml  # Check source pattern
ls config/prod/**/*.yaml # Check target pattern
```

### Changes not applying

- Check if sync rules match your file patterns
- Verify key names are correct (use `sync_key` or `sync_rules`)
- Ensure static_values syntax is correct

### Pattern matching issues

```bash
# Test pattern matching
python -c "import glob; print(glob.glob('config/**/*.yaml', recursive=True))"
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sceptre_sync --cov-report=term-missing

# Run specific test file
pytest tests/test_bulk_sync.py -v
```

## Requirements

- Python 3.8+
- ruamel.yaml (preserves YAML formatting)
- See requirements.txt for full list
