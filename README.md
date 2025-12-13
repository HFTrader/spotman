# SpotMan - Advanced AWS Instance Manager

**SpotMan** is a powerful, CLI-based AWS instance manager that simplifies deploying and managing EC2 instances across multiple regions. It supports both spot and on-demand instances, hibernation, and uses YAML profiles for configuration.

## Quick Start

Create an instance from a YAML profile:
```bash
./spotman create --profile web-server --alias web01 --class web
```

Create an instance with auto-generated name:
```bash
./spotman create --profile algorithmica-c7i --class algorithmica
# Creates: algorithmica-c7i-20251211-143052
```

Check spot prices and capacity across regions:
```bash
./spotman price --profile algorithmica-c7i
```

List all instances across configured regions:
```bash
./spotman list
```

## Features

- **Multi-Region Support**: Automatically searches all configured regions when managing instances
- **Spot Instance Management**: Cost-optimized spot instances with automatic request cancellation on terminate
- **Spot Capacity Scores**: View availability scores (1-10) when checking spot prices
- **Hibernation Support**: Full hibernation capability for both on-demand and spot instances
- **Auto-Generated Names**: Instance names default to `profile-YYYYMMDD-HHMMSS` if not specified
- **Duplicate Prevention**: Blocks creation of instances with duplicate names
- **SSH Port Forwarding**: Configure port forwarding in profiles for any application
- **Native YAML Includes**: Modular profiles using `!include` directives for external scripts
- **Application Classes**: Tag instances with application classes for organization
- **SSH Config Management**: Automatically update ~/.ssh/config with instance IP addresses

## Installation

### Quick Setup

```bash
pip install -r requirements.txt
chmod +x spotman
```

### AWS Configuration

Configure AWS credentials using one of:
- AWS CLI: `aws configure`
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- IAM roles (if running on EC2)

## Commands

### Create Instance

```bash
# With explicit name
./spotman create --profile web-server --alias web01 --class web

# With auto-generated name
./spotman create --profile web-server --class web

# In specific availability zone
./spotman create --profile algorithmica-c7i --az us-east-1b --class algorithmica

# In specific region
./spotman --region us-west-2 create --profile web-server --class web
```

### List Instances

```bash
# List all spotman-managed instances across all configured regions
./spotman list

# List by application class
./spotman list --class web

# List by state
./spotman list --state running

# List ALL instances (including non-spotman)
./spotman list --all
```

### Check Spot Prices and Capacity

```bash
# Check prices for a profile's instance type
./spotman price --profile algorithmica-c7i

# Check specific instance type
./spotman price --instance-type c7i.4xlarge

# Check in specific region
./spotman --region us-west-2 price --instance-type c7i.4xlarge
```

Output includes capacity scores:
```
Current Spot Prices:
======================================================================

📦 c7i.4xlarge
   us-east-2c: $0.2512/hr [capacity: 3/10 +]
   us-east-2a: $0.2646/hr [capacity: 3/10 +]
   us-east-2b: $0.2792/hr [capacity: 3/10 +]

📊 Capacity Score Legend: 10=high likelihood, 1=low likelihood
   +++ (8-10): Excellent | ++ (5-7): Good | + (3-4): Fair | - (1-2): Poor
```

### Instance Control

All commands automatically find instances across configured regions:

```bash
# Start instance
./spotman start web01

# Stop instance
./spotman stop web01

# Terminate instance (also cancels spot request if applicable)
./spotman terminate web01

# Hibernate instance
./spotman hibernate web01

# Resume hibernated instance
./spotman resume web01

# Check spot instance status
./spotman status web01
```

### SSH Config Management

```bash
# Update SSH config for all instances in a class
./spotman update-ssh --class web

# Update SSH config for specific instance
./spotman update-ssh --instance web01
```

## Profile Configuration

### Basic Profile

```yaml
# profiles/web-server.yaml
instance_type: "t3.micro"
os_type: "ubuntu"
update_os: true
spot_instance: false

root_volume_size: 20
root_volume_type: "gp3"

tags:
  ApplicationClass: "web-server"
  Environment: "development"
```

### Spot Instance with Hibernation

```yaml
# profiles/spot-hibernation.yaml
instance_type: "c7i.4xlarge"
spot_instance: true
hibernation_enabled: true

# Hibernation requires:
# - Encrypted root volume
# - Volume size >= RAM + OS space
root_volume_size: 80
root_volume_type: "gp3"
root_volume_encrypted: true

os_type: "ubuntu"
update_os: true

tags:
  ApplicationClass: "compute"
  Environment: "development"
```

**Important for Hibernation:**
- `root_volume_encrypted: true` is required
- `root_volume_size` must be >= RAM size + space for OS/data
- No `spot_price` means AWS uses on-demand price as max (better availability)

### SSH Port Forwarding

```yaml
# profiles/dev-server.yaml
instance_type: "t3.medium"
spot_instance: false

ssh_port_forwards:
  - local_port: 3000
    remote_port: 3000
  - local_port: 8080
    remote_port: 8080
  - local_port: 5432
    remote_port: 5432

tags:
  ApplicationClass: "development"
```

### User Data Scripts

```yaml
# Use !include for external scripts
user_data: !include scripts/setup.sh
```

### AMI Configuration

SpotMan can automatically find the latest AMI for supported operating systems, or you can specify an exact AMI.

**Supported OS types:**

| os_type | Description | Default AMI Pattern |
|---------|-------------|---------------------|
| `ubuntu` | Ubuntu 22.04 LTS (Jammy) | `ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*` |
| `amazon-linux` | Amazon Linux 2 | `amzn2-ami-hvm-*-x86_64-gp2` |
| `centos` | CentOS 7 | `CentOS Linux 7 x86_64 HVM EBS *` |

**Auto-select latest AMI (recommended):**
```yaml
# Uses the latest Ubuntu 22.04 AMI
os_type: "ubuntu"
```

**Custom AMI pattern:**
```yaml
# Use a different Ubuntu version
os_type: "ubuntu"
ami_name: "ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"
```

**Specific AMI ID:**
```yaml
# Use an exact AMI (skips auto-detection)
ami_id: "ami-0123456789abcdef0"
```

## Region Configuration

Configure regions in `regions.yaml`:

```yaml
regions:
  us-east-1:
    key_name: "my-key-useast1"
  us-east-2:
    key_name: "my-key-useast2"
  us-west-2:
    key_name: "my-key-uswest2"

ssh_keys:
  my-key-useast1: "~/.ssh/my-key-useast1.pem"
  my-key-useast2: "~/.ssh/my-key-useast2.pem"
  my-key-uswest2: "~/.ssh/my-key-uswest2.pem"
```

SpotMan automatically:
- Searches all configured regions when looking for instances by name
- Queries all regions when listing instances
- Infers region from availability zone (e.g., `--az us-east-1a` uses `us-east-1`)

## Spot Instance Best Practices

### Capacity Issues

If you get "InsufficientInstanceCapacity" errors:

1. **Don't specify an AZ** - Let AWS pick one with capacity
2. **Check capacity scores** - Use `./spotman price` to see availability
3. **Try different regions** - Some regions have more capacity
4. **Use on-demand** - Set `spot_instance: false` for guaranteed capacity

### Hibernation vs Termination

For spot instances:
- `hibernation_enabled: true` makes spot requests **persistent**
- On capacity reclaim, instance hibernates instead of terminating
- When capacity returns, instance automatically resumes

Without hibernation:
- Spot requests are **one-time**
- On capacity reclaim, instance is terminated

### Spot Request Cleanup

When you terminate a spot instance, SpotMan automatically cancels the spot request. This prevents persistent spot requests from spawning new unmanaged instances.

## AWS Permissions Required

```
ec2:DescribeInstances
ec2:DescribeSpotPriceHistory
ec2:GetSpotPlacementScores
ec2:RunInstances
ec2:StartInstances
ec2:StopInstances
ec2:TerminateInstances
ec2:CreateTags
ec2:DescribeSpotInstanceRequests
ec2:CancelSpotInstanceRequests
ec2:DescribeAvailabilityZones
ec2:DescribeVpcs
ec2:DescribeSubnets
ec2:DescribeImages
```

## File Structure

```
spotman/
├── spotman              # Main CLI
├── spotman_core.py      # Core library
├── profiles/            # Instance profiles
│   ├── algorithmica-c7i.yaml
│   ├── algorithmica-c7a.yaml
│   ├── web-server.yaml
│   └── ...
├── scripts/             # Setup scripts for !include
├── regions.yaml         # Region configuration
└── config.yaml          # SpotMan configuration
```

## Troubleshooting

### Instance not found

SpotMan searches the current region first, then all configured regions. If an instance isn't found:
- Check `./spotman list` to see all instances
- Ensure the instance wasn't terminated
- Use instance ID instead of name if there are duplicates

### Spot capacity unavailable

```bash
# Check current capacity scores
./spotman price --instance-type c7i.4xlarge

# Try without specifying AZ
./spotman create --profile myprofile --class myclass

# Or use on-demand
# Set spot_instance: false in profile
```

### Orphaned spot instances

If you see instances not managed by SpotMan after termination, they were spawned by persistent spot requests. SpotMan now cancels spot requests on terminate to prevent this.
