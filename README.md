# SpotMan - Advanced AWS Instance Manager

**SpotMan** is a powerful, CLI-based AWS instance manager that simplifies deploying and managing EC2 instances across multiple regions. It supports both spot and on-demand instances, hibernation, and uses YAML profiles for configuration.

## 🚀 New: Ollama Integration

SpotMan now includes integrated support for Ollama LLM servers! Deploy and manage GPU-accelerated language models with ease:

```bash
# Create an Ollama instance with automatic setup
./ollama-manager create --name ollama01

# Connect with automatic SSH port forwarding
./ollama-manager connect ollama01

# Access Ollama API at http://localhost:11434
```

See [OLLAMA_INTEGRATION.md](OLLAMA_INTEGRATION.md) for complete documentation.

## Quick Start

Create an instance from a YAML profile:
```bash
./spotman create --profile web-server --name web01 --class web
```

Create a hibernation-enabled spot instance:
```bash
./spotman create --profile spot-hibernation --name spot01 --class development
```

Create an Ollama LLM server:
```bash
./spotman create --profile ollama-spot --name ollama01 --class ollama
```

## Features

- **🤖 Ollama LLM Integration**: Dedicated profiles and management for Ollama language model servers
- **🔌 Generic SSH Port Forwarding**: Configure port forwarding in profiles for any application
- **Native YAML Includes**: Modular profiles using `!include` directives for external scripts
- **Hibernation Support**: Full hibernation capability for both on-demand and spot instances
- **Spot Instance Integration**: Cost-optimized spot instances with hibernation support
- **Instance Creation**: Create instances from YAML profiles with automatic OS updates
- **Application Classes**: Tag instances with application classes for organization
- **Instance Listing**: List all instances with filtering by application class and state
- **SSH Config Management**: Automatically update ~/.ssh/config with instance IP addresses
- **Instance Control**: Stop, terminate, hibernate, and resume instances
- **Region-Agnostic Profiles**: External region configuration for true portability
- **Modern AWS APIs**: Uses InstanceMarketOptions for advanced spot instance features
- **AWS CLI-style Interface**: Command-line interface similar to AWS CLI

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure AWS credentials (one of the following):
   - AWS CLI: `aws configure`
   - Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - IAM roles (if running on EC2)
   - AWS credentials file

3. Make the script executable:
```bash
chmod +x spotman
```

## Usage

### Create an Instance

Create an instance from a YAML profile:
```bash
./spotman create --profile web-server --name web01 --class web
```

Create a hibernation-enabled spot instance:
```bash
./spotman create --profile spot-hibernation --name spot01 --class development
```

Create an on-demand hibernation instance:
```bash
./spotman create --profile hibernation-ondemand --name prod01 --class production
```

### List Instances

List all instances:
```bash
./spotman list
```

List instances by application class:
```bash
./spotman list --class web
```

List instances by state:
```bash
./spotman list --state running
```

List instances in JSON format:
```bash
./spotman list --json
```

### Stop an Instance

```bash
./spotman stop i-1234567890abcdef0
```

### Terminate an Instance

```bash
./spotman terminate i-1234567890abcdef0
```

### Update SSH Config

Update SSH config for all instances in an application class:
```bash
./spotman update-ssh --class web
```

Update SSH config for a specific instance:
```bash
./spotman update-ssh --instance-id i-1234567890abcdef0
```

Specify custom SSH config path:
```bash
./spotman update-ssh --class web --config-path /path/to/ssh/config
```

### Manage Default Region

Show current default region:
```bash
./spotman region show
```

Set default region for future operations:
```bash
./spotman region set us-west-2
```

List available regions from configuration:
```bash
./spotman region list
```

### Hibernation Management

Hibernate an instance for cost savings:
```bash
./spotman hibernate start i-1234567890abcdef0
```

Resume a hibernated instance:
```bash
./spotman hibernate resume i-1234567890abcdef0
```

List hibernated instances:
```bash
./spotman list --hibernated
```

Check hibernation capability:
```bash
./spotman hibernate status i-1234567890abcdef0
```

## YAML Profile Format

Instance profiles use native YAML includes for modular configuration. External scripts are included using the `!include` directive.

### Modern Profile Format with Native Includes

```yaml
# profiles/web-server.yaml - Application profile with native includes
instance_type: "t3.micro"
os_type: "ubuntu"
update_os: true

# Include external script using native YAML
user_data: !include scripts/webserver-setup.sh

# Optional hibernation support
hibernation_enabled: false
spot_instance: false

# Storage configuration
root_volume_size: 20
root_volume_type: "gp3"

tags:
  ApplicationClass: "web-server"
  Environment: "development"
  ManagedBy: "spotman"
```

### Hibernation Profile Examples

#### Spot Instance with Hibernation
```yaml
# profiles/spot-hibernation.yaml
instance_type: "m5.large"  # Hibernation-compatible family
spot_instance: true
hibernation_enabled: true
os_type: "ubuntu"
update_os: true

# Include hibernation setup script
user_data: !include scripts/hibernation-setup.sh

root_volume_size: 20
root_volume_type: "gp3"

tags:
  ApplicationClass: "hibernation"
  Environment: "development"
  InstanceType: "spot"
  HibernationEnabled: "true"
```

#### On-Demand with Hibernation
```yaml
# profiles/hibernation-ondemand.yaml
instance_type: "m5.large"
spot_instance: false
hibernation_enabled: true
os_type: "ubuntu"
update_os: true

user_data: !include scripts/hibernation-setup.sh

tags:
  ApplicationClass: "hibernation"
  Environment: "production"
  InstanceType: "on-demand"
  HibernationEnabled: "true"
```

### SSH Port Forwarding Configuration

SpotMan supports automatic SSH port forwarding configuration in profiles. Define port forwards in your profile and they'll be automatically added to SSH config:

```yaml
# profiles/dev-server.yaml
instance_type: "t3.medium"
spot_instance: false

# SSH port forwarding configuration
ssh_port_forwards:
  - local_port: 3000      # React dev server
    remote_port: 3000
    remote_host: localhost
  - local_port: 8080      # Backend API
    remote_port: 8080
    remote_host: localhost
  - local_port: 5432      # PostgreSQL
    remote_port: 5432
    remote_host: localhost

user_data: !include scripts/dev-setup.sh

tags:
  ApplicationClass: "development"
  Purpose: "multi-service-dev"
```

**Port Forward Options:**
- `local_port`: Port on your local machine (required)
- `remote_port`: Port on the instance (defaults to local_port)
- `remote_host`: Host on the instance (defaults to localhost)

**Generated SSH Config:**
```ssh
Host dev-server-01
    HostName 1.2.3.4
    User ubuntu
    IdentityFile ~/.ssh/key.pem
    StrictHostKeyChecking no
    LocalForward 3000 localhost:3000
    LocalForward 8080 localhost:8080
    LocalForward 5432 localhost:5432
```

## Profile Options

### External Region Configuration (regions.yaml)

#### Regions Section
Region-specific configurations:
- `ami_id`: **Optional** - Override the default AMI for this region
- `key_name`: **Required** - EC2 key pair name for this region
- `default_security_group_ids`: Default security group IDs for this region
- `default_subnet_id`: Default subnet ID for this region

#### Defaults Section
Global defaults applied when not specified in profiles or regions:
- `instance_type`: EC2 instance type (default: t3.micro)
- `os_type`: Operating system type for update commands
- `update_os`: Whether to update the OS (default: true)
- `ami_id`: **Optional** - Default AMI ID used unless overridden by region

### Application Profile Options

#### Required/Common Fields
- `instance_type`: EC2 instance type
- `os_type`: Operating system type  
- `update_os`: Whether to update the OS
- `user_data`: Shell script to run on first boot (supports `!include` directive)
- `tags`: Dictionary of tags to apply

#### Modern Features
- **Native YAML Includes**: Use `!include scripts/filename.sh` for external scripts
- **Hibernation Support**: `hibernation_enabled: true` for hibernation capability
- **Spot Integration**: `spot_instance: true` for cost-optimized spot instances
- **Enhanced Storage**: Configure `root_volume_size` and `root_volume_type`

#### Cost Optimization Fields
- `spot_instance`: Enable spot instance pricing (default: false)
- `hibernation_enabled`: Enable hibernation for cost savings (default: false)

#### Storage Configuration
- `root_volume_size`: Root volume size in GB (default: 8)
- `root_volume_type`: EBS volume type - gp2, gp3, io1, io2 (default: gp3)

#### Optional Override Fields
These override the region defaults when specified:
- `security_group_ids`: Security group IDs (overrides region default)
- `subnet_id`: Subnet ID (overrides region default)
- `security_groups`: Security group names (for default VPC)

### Legacy Format Fields
For backward compatibility, the old single-region format is still supported:
- `ami_id`: The AMI ID to launch
- `instance_type`: EC2 instance type
- `key_name`: EC2 key pair name  
- `security_groups`: Security group names
- `security_group_ids`: Security group IDs
- `subnet_id`: Subnet ID
- `os_type`: Operating system type
- `update_os`: Whether to update the OS
- `user_data`: Shell script to run on first boot
- `tags`: Dictionary of tags

## Region-Agnostic Configuration

SpotMan now supports truly region-agnostic profiles using external region configuration:

### External Region Configuration

Region-specific settings (AMI IDs, key pairs, network settings) are stored in a separate `regions.yaml` file:

```yaml
# regions.yaml - External region configuration
regions:
  us-east-1:
    # ami_id: "ami-override123"  # Optional: override default AMI
    key_name: "my-keypair-useast1"
    default_security_group_ids:
      - "sg-0123456789abcdef0"
    default_subnet_id: "subnet-0123456789abcdef0"
  
  us-west-2:
    ami_id: "ami-0d1cd67c26f5fca19"  # Region-specific AMI
    key_name: "my-keypair-uswest2"
    default_security_group_ids:
      - "sg-fedcba9876543210"
    default_subnet_id: "subnet-fedcba9876543210"

defaults:
  instance_type: "t3.micro"
  os_type: "ubuntu"
  update_os: true
  ami_id: "ami-0c55b159cbfafe1d0"  # Default AMI used unless overridden
```

### Profile Format (Region-Agnostic)

Application profiles contain only application-specific configuration:

```yaml
# profiles/web-server.yaml - Application profile with native includes
instance_type: "t3.micro"
os_type: "ubuntu"
update_os: true

# Include external script using native YAML !include
user_data: !include scripts/webserver-setup.sh

# Optional hibernation and cost optimization
hibernation_enabled: false
spot_instance: false

tags:
  ApplicationClass: "web-server"
  Environment: "development"
  ManagedBy: "spotman"
```

### Benefits
- **Complete Separation**: Application logic separated from infrastructure
- **Easy Maintenance**: Update region settings in one place
- **Consistent Deployment**: Same application profiles work everywhere
- **Override Capability**: Profiles can override region defaults when needed
- **Legacy Support**: Old single-region profiles still work
- **Smart Defaults**: Remembers last used region for convenience

### Setup Process
1. **Configure regions.yaml**: Set up AMI IDs, key pairs, and network defaults for each region
2. **Create application profiles**: Focus only on application-specific configuration
3. **Set default region**: `./spotman region set us-west-2` (optional)
4. **Deploy anywhere**: Same profile works across all configured regions

```bash
# Set your preferred default region
./spotman region set eu-west-1

# Now commands use eu-west-1 by default (unless --region is specified)
./spotman create --profile web-server --name web01-eu

# Override for specific deployment
./spotman --region us-east-1 create --profile web-server --name web01-east
```

### Region Selection Priority

SpotMan selects regions in the following order of priority:

1. **Command line `--region` flag** (highest priority)
2. **Last used region** (saved in `~/.spotman/config.yaml`)
3. **AWS session default** (from AWS CLI config or environment)

```bash
# Set default for convenience
./spotman region set eu-west-1

# Uses eu-west-1 (last used)
./spotman create --profile web-server --name web01

# Override to us-west-2 for this command only
./spotman --region us-west-2 create --profile web-server --name web02
```

### AMI Selection Priority

SpotMan selects AMI IDs in the following order of priority:

1. **Region-specific AMI** (in `regions.{region}.ami_id`)
2. **Default AMI** (in `defaults.ami_id`)
3. **Error** if neither is specified

```yaml
# Example: us-east-1 uses default AMI, us-west-2 uses region-specific AMI
defaults:
  ami_id: "ami-default123"  # Used by us-east-1

regions:
  us-east-1:
    key_name: "key-east"    # Uses default AMI
  
  us-west-2:
    ami_id: "ami-west456"   # Overrides default AMI
    key_name: "key-west"
```

4. Monitor spot prices and instance interruptions

## Spot Instances and Hibernation

### Hibernation Requirements

For hibernation to work, instances must meet these requirements:

1. **Compatible Instance Types**: M3, M4, M5, M5a, R3, R4, R5, R5a, C3, C4, C5, C5a families
2. **Encrypted Root Volume**: Required for hibernation (automatically enabled by SpotMan)
3. **Instance RAM**: Must be less than 150 GB
4. **Swap Space**: Should be configured >= RAM size for proper hibernation

### Hibernation Benefits

- **Cost Savings**: Pay only for EBS storage while hibernated
- **Fast Resume**: Instances resume with all processes and memory intact
- **Spot Integration**: Combine with spot instances for maximum savings
- **Development Workflow**: Hibernate dev instances overnight, resume in the morning

### Example Workflow

```bash
# Create a hibernation-enabled spot instance
./spotman create --profile spot-hibernation --name dev-work --class development

# Work during the day...

# Hibernate overnight to save costs
./spotman hibernate start dev-work

# Resume next morning
./spotman hibernate resume dev-work
```

### Cost Optimization Tips

1. Use spot instances for non-critical workloads (60-90% savings)
2. Enable hibernation for development instances
3. Use larger storage for hibernation swap space
4. Monitor spot prices and instance interruptions

## Application Classes

Instances are organized using the `ApplicationClass` tag. This allows you to:
- Group related instances together
- Filter instances by their purpose
- Manage SSH configurations by application class
- Apply bulk operations to instance groups

## AWS Permissions

The script requires the following AWS permissions:
- `ec2:DescribeInstances`
- `ec2:RunInstances`
- `ec2:StopInstances`
- `ec2:TerminateInstances`
- `ec2:CreateTags`

## Examples

### Web Server Setup
```bash
# Create multiple web servers using modern profile syntax
./spotman create --profile web-server --name web01 --class web
./spotman create --profile web-server --name web02 --class web

# List all web servers
./spotman list --class web

# Update SSH config for all web servers
./spotman update-ssh --class web
```

### Hibernation Workflow
```bash
# Create hibernation-enabled instances
./spotman create --profile spot-hibernation --name dev-work --class development
./spotman create --profile hibernation-ondemand --name prod-work --class production

# Hibernate during off-hours for cost savings
./spotman hibernate start dev-work

# Resume when needed
./spotman hibernate resume dev-work

# List hibernated instances
./spotman list --hibernated
```

### Database Setup
```bash
# Create a database server
./spotman create --profile database --name db01 --class database

# Check database server status
./spotman list --class database --state running
```

## Configuration Files

The `profiles/` directory contains modern YAML profiles with native includes:
- `web-server.yaml`: Web server configuration with !include directives
- `database.yaml`: Database server configuration
- `spot-hibernation.yaml`: Cost-optimized spot instance with hibernation
- `hibernation-ondemand.yaml`: Reliable hibernation for production workloads
- `test.yaml`: Minimal test configuration

The `scripts/` directory contains modular setup scripts:
- `hibernation-setup.sh`: Comprehensive hibernation configuration
- `webserver-setup.sh`: Complete web server setup with Nginx
- `test-setup.sh`: Basic test environment setup

Copy and modify these profiles for your specific needs.

## Troubleshooting

### AWS Credentials
If you get credential errors, ensure your AWS credentials are configured:
```bash
aws configure list
```

### Permissions
If you get permission errors, check that your AWS user/role has the required EC2 permissions.

### SSH Config
The SSH config update assumes:
- Default user is `ubuntu` (modify the script for other users)
- SSH key file is at `~/.ssh/your-key.pem` (update the script for your key path)

## Customization

The script can be easily customized for your specific needs:
- Modify the SSH config template in the `update_ssh_config` method
- Add additional OS types in the `_get_os_update_script` method
- Extend the YAML profile format with additional fields
- Add new commands to the argument parser
