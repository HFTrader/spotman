#!/bin/bash
set -e

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

# Comprehensive logging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Simple spot instance deployment started at $(date)"

# Get instance metadata
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)

echo "Instance: $INSTANCE_ID in region: $REGION"

# System updates
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install development tools
echo "Installing development tools..."
apt-get install -y \
  htop iotop \
  curl wget \
  git vim nano \
  awscli \
  build-essential \
  python3-pip \
  nodejs npm

# Configure git (basic setup)
git config --system init.defaultBranch main

# Create development directories
mkdir -p /home/ubuntu/{projects,scripts,logs}
chown ubuntu:ubuntu /home/ubuntu/{projects,scripts,logs}

# Create environment info script
cat > /home/ubuntu/info.sh << 'EOF'
#!/bin/bash

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Simple Spot Instance Info ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Region: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)"
echo "Instance Type: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)"
echo "Deployment: $(cat /tmp/deployment-time 2>/dev/null || echo 'Unknown')"
echo "Uptime: $(uptime)"
EOF
chmod +x /home/ubuntu/info.sh
chown ubuntu:ubuntu /home/ubuntu/info.sh

# Mark deployment completion
echo "$(date)" > /tmp/deployment-time
touch /tmp/simple-spot-complete

echo "Simple spot instance setup completed successfully at $(date)"
