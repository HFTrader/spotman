# SpotMan External Region Configuration Architecture

## Overview

SpotMan now uses **external region configuration** to achieve true region-agnostic application profiles.

## File Structure

```
aws/
├── spotman                 # Main script
├── regions.yaml           # Region-specific infrastructure configuration
├── profiles/              # Application-specific profiles
│   ├── web-server.yaml    # Web server application profile
│   ├── database.yaml      # Database application profile
│   └── test.yaml         # Test application profile
└── ...
```

## Configuration Separation

### regions.yaml (Infrastructure Layer)
Contains region-specific infrastructure settings:
- AMI IDs for each region
- Key pair names for each region  
- Default security groups and subnets
- Global infrastructure defaults

### profiles/*.yaml (Application Layer)
Contains application-specific configuration:
- Instance types and sizes
- Application software installation
- Application-specific tags
- User data scripts
- Optional infrastructure overrides

## Benefits

1. **True Separation of Concerns**
   - Infrastructure settings separate from application logic
   - One place to manage all region-specific settings
   - Application profiles focus only on the application

2. **Easy Maintenance**
   - Update AMI IDs in one file for all applications
   - Change key pairs globally without touching application profiles
   - Consistent network settings across applications

3. **Flexibility**
   - Application profiles can override region defaults when needed
   - Support for both new external config and legacy single-file profiles
   - Same application profile works across all configured regions

4. **Scalability**
   - Add new regions without modifying application profiles
   - Create new applications without duplicating infrastructure config
   - Easy to standardize infrastructure settings across teams

## Usage Examples

```bash
# Edit regions.yaml to add your security groups and subnets
# Then use the same profile across regions:

./spotman --region us-east-1 create --profile web-server --name web01-east
./spotman --region eu-west-1 create --profile web-server --name web01-eu
```

## Migration Path

- **Legacy profiles continue to work** - no breaking changes
- **New profiles use external configuration** - regions.yaml + simplified profiles
- **Gradual migration** - convert profiles one at a time as needed

This architecture provides the perfect balance of simplicity, maintainability, and flexibility for multi-region AWS deployments.
