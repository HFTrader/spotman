# SpotMan Scripts Directory

This directory contains all the external scripts used by SpotMan profiles, implementing a modular architecture with **native YAML `!include` support** for better maintainability and reusability.

## Script Overview

| Script File | Used By Profile | Purpose |
|-------------|----------------|---------|
| `hibernation-setup.sh` | `spot-hibernation.yaml`, `hibernation-ondemand.yaml` | Comprehensive hibernation configuration with swap management |
| `webserver-setup.sh` | `web-server.yaml` | Complete web server setup with Nginx |
| `test-setup.sh` | `test.yaml` | Basic development tools for testing instances |

## Key Features

### ✅ **Native YAML Includes**
- Uses standard YAML `!include` directive (no custom syntax)
- Proper YAML parsing and validation
- Better IDE support and syntax highlighting
- Standards-compliant YAML processing

### ✅ **Hibernation Scripts**
- Full hibernation capability for both spot and on-demand instances
- Automatic swap configuration (RAM + buffer)
- Hibernation package installation and management
- Enhanced error handling and logging

### ✅ **Modular Architecture**
- Scripts are version controlled separately
- Easier to debug and test individual components
- Clear separation of concerns
- Reusable across multiple profiles

## Usage Pattern

In profile YAML files:
```yaml
# Include external script
user_data: !include scripts/script-name.sh

# Can also use absolute paths
user_data: !include /path/to/external/script.sh
```

## Script Requirements

All scripts should:
1. Start with proper shebang (`#!/bin/bash`)
2. Use `set -e` for error handling
3. Include comprehensive logging
4. Set proper file permissions when creating files
5. Use meaningful variable names and comments

## Directory Structure

```
scripts/
├── README.md                 # This file
├── test-setup.sh            # Test instance setup
├── webserver-setup.sh       # Web server deployment
├── modular-web-setup.sh     # Modular architecture demo
├── hibernation-setup.sh     # Hibernation configuration
├── simple-spot-setup.sh     # Spot development environment
├── spot-simple-setup.sh     # Basic spot instance
└── [future scripts...]      # Additional scripts as needed
```

## Adding New Scripts

1. Create the script file in this directory
2. Make it executable: `chmod +x scripts/new-script.sh`
3. Reference it in profiles: `user_data: !include scripts/new-script.sh`
4. Test with SpotMan: `./spotman create --profile profile-name --name test`

## Migration Notes

All SpotMan profiles have been migrated from embedded user_data to external scripts using the native YAML `!include` directive. This provides:

- Better code organization
- Easier script maintenance
- Version control for individual scripts
- Improved testing capabilities
- Cleaner profile definitions
