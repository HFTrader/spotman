#!/bin/bash
set -e  # Exit on any error

# AWS Instance Metadata Service endpoint  
AWS_METADATA_SERVER="http://169.254.169.254"

# Log all output for debugging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting test instance setup at $(date)"

# Get instance metadata
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
PRIVATE_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)
PUBLIC_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)

echo "Setting up test instance $INSTANCE_ID"
echo "Network: Private IP: $PRIVATE_IP, Public IP: $PUBLIC_IP, Region: $REGION"

# Update system
echo "Updating system packages..."
apt-get update

# Install basic tools for testing
echo "Installing development tools..."
apt-get install -y htop curl wget git vim awscli

# Create test marker with instance info
cat > /tmp/test-complete << EOF
Test instance deployed successfully at $(date)
Instance ID: $INSTANCE_ID
Private IP: $PRIVATE_IP
Public IP: $PUBLIC_IP  
Region: $REGION
EOF

# Create instance info script for easy access
cat > /home/ubuntu/instance-info.sh << 'EOF'
#!/bin/bash

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Instance Information ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Instance Type: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)"
echo "Private IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)"
echo "Public IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo 'N/A')"
echo "Region: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)"
echo "Availability Zone: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/availability-zone)"
echo "Launch Time: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/launch-time)"
EOF

chmod +x /home/ubuntu/instance-info.sh
chown ubuntu:ubuntu /home/ubuntu/instance-info.sh

echo "Test instance setup completed!"
