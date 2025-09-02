#!/bin/bash
set -e

# Custom Development Environment Setup Script
# This script demonstrates how you can create custom setup scripts
# in your user config directory (~/.spotman/scripts/)

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

# Comprehensive logging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Custom development environment setup started at $(date)"

# Get instance metadata
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)

echo "Instance: $INSTANCE_ID in region: $REGION"

# System updates
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install your preferred development tools
echo "Installing custom development tools..."
apt-get install -y \
  htop iotop \
  curl wget \
  git vim nano \
  awscli \
  build-essential \
  python3-pip python3-venv \
  nodejs npm \
  docker.io \
  postgresql-client \
  redis-tools \
  jq tree

# Install additional Python packages
echo "Installing Python development packages..."
pip3 install --upgrade pip
pip3 install \
  boto3 \
  requests \
  flask \
  django \
  pandas \
  numpy \
  jupyter

# Configure git with your preferences
git config --system init.defaultBranch main
git config --system user.name "SpotMan User"
git config --system user.email "user@spotman.local"

# Create development directories
mkdir -p /home/ubuntu/{projects,scripts,logs,workspace}
chown ubuntu:ubuntu /home/ubuntu/{projects,scripts,logs,workspace}

# Setup Python virtual environment
su - ubuntu -c "python3 -m venv ~/venv"
su - ubuntu -c "echo 'source ~/venv/bin/activate' >> ~/.bashrc"

# Create custom info script
cat > /home/ubuntu/dev-info.sh << 'EOF'
#!/bin/bash

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Custom Development Environment Info ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Region: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)"
echo "Instance Type: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)"
echo "Deployment: $(cat /tmp/deployment-time 2>/dev/null || echo 'Unknown')"
echo "Uptime: $(uptime)"
echo ""
echo "Available tools:"
echo "  - Python 3 with virtual environment"
echo "  - Node.js and npm"
echo "  - Docker"
echo "  - PostgreSQL and Redis clients"
echo "  - Development tools (git, vim, etc.)"
echo ""
echo "Directories:"
echo "  ~/projects - Your project workspace"
echo "  ~/scripts - Custom scripts"
echo "  ~/workspace - Additional workspace"
echo "  ~/venv - Python virtual environment"
EOF
chmod +x /home/ubuntu/dev-info.sh
chown ubuntu:ubuntu /home/ubuntu/dev-info.sh

# Mark deployment completion
echo "$(date)" > /tmp/deployment-time
touch /tmp/custom-dev-complete

echo "Custom development environment setup completed successfully at $(date)"
echo ""
echo "Next steps:"
echo "1. Run: source ~/venv/bin/activate"
echo "2. Run: ./dev-info.sh"
echo "3. Start developing in ~/projects/"
