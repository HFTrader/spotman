# Ollama Integration with SpotMan

This document describes how `aws_ollama_manager.py` has been integrated into the SpotMan framework, providing enhanced Ollama LLM server management while maintaining the flexibility and configuration system of SpotMan.

## Integration Overview

The integration follows a **hybrid approach** that:

1. **Preserves SpotMan's generic framework** for other applications
2. **Adds Ollama-specific enhancements** without making SpotMan Ollama-aware
3. **Shares configuration files** (regions.yaml, profiles) between both systems
4. **Provides dedicated Ollama management** through specialized tools
5. **Maintains backward compatibility** with existing SpotMan usage

## New Components

### 1. Ollama Profile (`profiles/ollama-spot.yaml`)

A SpotMan profile specifically designed for Ollama LLM servers:

```yaml
# Ollama LLM Server on Spot Instance Profile
instance_type: "g5.xlarge"  # GPU instance for better LLM performance
spot_instance: true         # Cost-effective spot pricing
hibernation_enabled: true   # Preserve state during spot interruptions
root_volume_size: 100      # GB - space for models and hibernation
user_data: !include scripts/ollama-setup.sh
tags:
  ApplicationClass: "ollama"
  Service: "ollama"
```

**Key Features:**
- GPU-optimized instance types (g5.xlarge by default)
- Spot instance support with hibernation
- Large storage for LLM models
- Automatic Ollama installation and configuration
- Proper tagging for management

### 2. Ollama Setup Script (`scripts/ollama-setup.sh`)

Comprehensive setup script that:

- **System Updates**: Updates Ubuntu packages
- **Hibernation Setup**: Configures swap and hibernation support
- **Ollama Installation**: Downloads and installs Ollama
- **Service Configuration**: Configures Ollama to bind to all interfaces
- **Management Scripts**: Creates helper scripts for model management
- **Test Model**: Optionally downloads a lightweight test model

**Generated Helper Scripts:**
- `ollama-status.sh`: Check service status and system resources
- `ollama-models.sh`: Manage models (download, remove, test)
- `hibernate-ollama.sh`: Safe hibernation with Ollama preparation

### 3. Generic SSH Port Forwarding

SpotMan now supports generic port forwarding configuration in profiles. Any profile can specify port forwards that will be automatically added to SSH configuration:

```yaml
# SSH port forwarding configuration
ssh_port_forwards:
  - local_port: 11434     # Ollama API
    remote_port: 11434
    remote_host: localhost
  - local_port: 8080      # Web interface
    remote_port: 80
    remote_host: localhost
```

**How it works:**
- Port forwarding is defined in the profile YAML
- SpotMan tracks which profile was used via `Profile` tag
- SSH config generation reads the profile and adds appropriate `LocalForward` entries
- Works for any application, not just Ollama

**Supported options:**
- `local_port`: Port on your local machine
- `remote_port`: Port on the instance (defaults to local_port)
- `remote_host`: Host on the instance (defaults to localhost)

### 4. Dedicated Ollama Manager (`ollama-manager`)

A specialized management tool that provides enhanced Ollama functionality:

```bash
# Create Ollama instances
./ollama-manager create --name ollama01
./ollama-manager create --name ollama-gpu --type g5.xlarge

# Manage instances
./ollama-manager list
./ollama-manager start ollama01
./ollama-manager stop ollama01
./ollama-manager status ollama01

# Connect and test
./ollama-manager connect ollama01  # SSH with port forwarding
./ollama-manager test ollama01      # Test API connectivity
./ollama-manager logs ollama01      # View service logs

# SSH configuration
./ollama-manager update-ssh         # Update all Ollama instances
```

## Usage Examples

### Creating an Ollama Instance

Using SpotMan directly:
```bash
./spotman create --profile ollama-spot --name ollama01 --class ollama
```

Using the dedicated Ollama manager:
```bash
./ollama-manager create --name ollama01
./ollama-manager create --name ollama-gpu --type g5.2xlarge
```

### Managing Instances

Standard SpotMan commands work:
```bash
./spotman list --class ollama
./spotman hibernate start ollama01
./spotman hibernate resume ollama01
./spotman terminate ollama01
```

Enhanced Ollama commands:
```bash
./ollama-manager list
./ollama-manager connect ollama01
./ollama-manager test ollama01
```

### Working with Models

After connecting to an instance:
```bash
ssh ollama01

# Check status
./ollama-status.sh

# Manage models
./ollama-models.sh popular              # List popular models
./ollama-models.sh pull llama3.2:3b     # Download a model
./ollama-models.sh list                 # List installed models
./ollama-models.sh run llama3.2:3b      # Test a model

# Hibernate when done
./hibernate-ollama.sh
```

### API Usage

With SSH port forwarding active:
```bash
# Check API version
curl http://localhost:11434/api/version

# Generate text
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:3b", "prompt": "Hello world"}'
```

## Configuration Sharing

Both tools share the same configuration files:

### regions.yaml
```yaml
ssh_keys:
  amz-br: "~/.ssh/amz-br.pem"
  amz-us: "~/.ssh/amz-us.pem"

regions:
  us-east-1:
    ami_id: "ami-0360c520857e3138f"
    key_name: "amz-us"
    default_security_group_ids: ["sg-914dd4f5"]
  
  sa-east-1:
    ami_id: "ami-0d6d5b74032865309"
    key_name: "amz-br"
    default_security_group_ids: ["sg-1f88567a"]
```

### SSH Configuration
Both tools use the same SSH configuration system:
- Shared SSH config file: `~/.spotman/ssh_config`
- Automatic inclusion in `~/.ssh/config`
- Instance-specific entries with proper key files
- Automatic port forwarding for Ollama instances

## Benefits of Integration

### 1. **Cost Efficiency**
- Spot instances with hibernation support
- Pay only for compute time, not idle time
- Hibernate during interruptions to preserve state

### 2. **Easy Management**
- Unified configuration across regions
- Automatic SSH setup with port forwarding
- Helper scripts for common tasks

### 3. **Flexibility**
- Use SpotMan for generic management
- Use ollama-manager for specialized features
- Mix and match as needed

### 4. **State Preservation**
- Hibernation preserves running models
- Fast resume from hibernated state
- No need to reload models after resume

### 5. **Developer Experience**
- One-command instance creation
- Automatic API access via SSH tunneling
- Rich management scripts on instances

## Migration from aws_ollama_manager.py

If you were using the standalone `aws_ollama_manager.py`, here's how to migrate:

### Old Workflow:
```bash
python aws_ollama_manager.py launch -c config.yaml
python aws_ollama_manager.py start i-1234567890abcdef
python aws_ollama_manager.py stop i-1234567890abcdef
```

### New Workflow:
```bash
./ollama-manager create --name ollama01
./ollama-manager start ollama01
./ollama-manager stop ollama01
```

### Configuration Migration:
- Move AWS credentials and region settings to `regions.yaml`
- Instance configurations are now in `profiles/ollama-spot.yaml`
- SSH keys are mapped in `regions.yaml` ssh_keys section

## Advanced Usage

### Custom Instance Types
```bash
# For different workloads
./ollama-manager create --name ollama-cpu --type m5.xlarge --no-spot
./ollama-manager create --name ollama-gpu --type g5.2xlarge
./ollama-manager create --name ollama-large --type g5.4xlarge
```

### Multi-Region Deployment
```bash
# Deploy in different regions
./spotman --region us-east-1 create --profile ollama-spot --name ollama-east
./spotman --region eu-west-1 create --profile ollama-spot --name ollama-eu
./spotman --region sa-east-1 create --profile ollama-spot --name ollama-sa
```

### Hibernation Management
```bash
# Standard hibernation
./spotman hibernate start ollama01

# Resume from hibernation
./spotman hibernate resume ollama01

# Check hibernation status
./spotman hibernate status ollama01
```

## Troubleshooting

### SSH Connection Issues
1. Update SSH config: `./ollama-manager update-ssh`
2. Check instance state: `./ollama-manager status ollama01`
3. Verify security groups allow SSH (port 22)

### API Access Issues
1. Test connection: `./ollama-manager test ollama01`
2. Check if SSH port forwarding is active
3. Verify Ollama service: `ssh ollama01 './ollama-status.sh'`

### Model Download Issues
1. Check disk space: `ssh ollama01 'df -h'`
2. Check service status: `ssh ollama01 './ollama-status.sh'`
3. Manual download: `ssh ollama01 'ollama pull model-name'`

### Hibernation Issues
1. Check hibernation status: `./spotman hibernate status ollama01`
2. Verify swap space: `ssh ollama01 'free -h'`
3. Use safe hibernation: `ssh ollama01 './hibernate-ollama.sh'`

## Next Steps

The integration provides a solid foundation for LLM server management. Future enhancements could include:

1. **Model Persistence**: Separate EBS volumes for models
2. **Load Balancing**: Multiple instances with load balancer
3. **Auto-scaling**: Based on API usage metrics
4. **Monitoring**: CloudWatch integration for service health
5. **Backup**: Automated model and configuration backups