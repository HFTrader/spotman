#!/bin/bash
# Common setup script for all instances
set -e

# Logging setup
exec > >(tee /var/log/user-data.log) 2>&1
echo "Common setup started at $(date)"

# System updates
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install essential tools
echo "Installing common tools..."
apt-get install -y htop curl wget awscli jq

# Create common directories
mkdir -p /home/ubuntu/{scripts,logs}
chown ubuntu:ubuntu /home/ubuntu/{scripts,logs}

echo "Common setup completed at $(date)"
