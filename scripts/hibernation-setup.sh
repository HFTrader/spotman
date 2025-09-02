#!/bin/bash
set -e  # Exit on any error

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

# Comprehensive logging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Hibernation-capable instance setup started at $(date)"

# Get instance information
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
INSTANCE_TYPE=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)
PRIVATE_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)
PUBLIC_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)

echo "Setting up hibernation on instance $INSTANCE_ID ($INSTANCE_TYPE)"
echo "Private IP: $PRIVATE_IP, Public IP: $PUBLIC_IP, Region: $REGION"

# System updates
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install hibernation support packages
echo "Installing hibernation support packages..."
apt-get install -y pm-utils uswsusp hibernate

# Configure swap for hibernation (hibernation requires swap >= RAM)
echo "Configuring swap space for hibernation..."

# Get RAM size to determine swap size
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
SWAP_GB=$((RAM_GB + 2))  # Add 2GB buffer

echo "RAM: ${RAM_GB}GB, Creating ${SWAP_GB}GB swap file"

# Create swap file
fallocate -l ${SWAP_GB}G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Configure hibernation
echo "Configuring hibernation settings..."

# Update initramfs for hibernation support
update-initramfs -u

# Install monitoring and development tools
echo "Installing additional tools..."
apt-get install -y htop iotop awscli curl wget jq

# Create hibernation management scripts
echo "Creating hibernation scripts..."

# Hibernation preparation script
cat > /home/ubuntu/hibernate.sh << 'EOF'
#!/bin/bash
# Script to safely hibernate the instance

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Hibernation Preparation ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Private IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)"
echo "Public IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo 'N/A')"
echo "Current time: $(date)"
echo "Uptime: $(uptime -p)"
echo ""

echo "Checking hibernation readiness..."

# Check swap space
SWAP_TOTAL=$(free -g | awk '/^Swap:/{print $2}')
RAM_TOTAL=$(free -g | awk '/^Mem:/{print $2}')

echo "RAM: ${RAM_TOTAL}GB, Swap: ${SWAP_TOTAL}GB"

if [ "$SWAP_TOTAL" -lt "$RAM_TOTAL" ]; then
  echo "WARNING: Swap space ($SWAP_TOTAL GB) is less than RAM ($RAM_TOTAL GB)"
  echo "Hibernation may not work properly!"
else
  echo "Swap space is adequate for hibernation"
fi

echo ""
echo "Preparing for hibernation..."

# Sync filesystem
sync

echo "Initiating hibernation..."
echo "Note: Use AWS console to resume the instance"

# Hibernate the system
sudo systemctl hibernate
EOF

# System status script
cat > /home/ubuntu/hibernate-status.sh << 'EOF'
#!/bin/bash

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Hibernation Status ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Instance Type: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)"
echo "Private IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)"
echo "Public IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo 'N/A')"
echo "Region: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)"
echo ""
echo "Memory Status:"
free -h
echo ""
echo "Swap Status:"
swapon --show
echo ""
echo "Hibernation Support:"
if [ -f /sys/power/state ]; then
  echo "Available power states: $(cat /sys/power/state)"
fi
if [ -f /sys/power/disk ]; then
  echo "Hibernation methods: $(cat /sys/power/disk)"
fi
EOF

# Make scripts executable and set ownership
chmod +x /home/ubuntu/hibernate*.sh
chown ubuntu:ubuntu /home/ubuntu/hibernate*.sh

# Create hibernation info file
cat > /home/ubuntu/hibernation-info.txt << EOF
=== Hibernation Setup Information ===

Setup completed: $(date)
Instance ID: $INSTANCE_ID
Instance Type: $INSTANCE_TYPE
Private IP: $PRIVATE_IP
Public IP: $PUBLIC_IP
Region: $REGION
RAM: ${RAM_GB}GB
Swap: ${SWAP_GB}GB

Available Scripts:
- ./hibernate.sh: Safely hibernate the instance
- ./hibernate-status.sh: Check hibernation readiness

Manual Hibernation:
sudo systemctl hibernate

Resume Instance:
Use AWS console or CLI to start the stopped instance

Notes:
- Hibernation saves instance state to disk
- Instance stops and can be resumed later
- Faster startup than cold boot
- Preserves memory contents and running processes
EOF
chown ubuntu:ubuntu /home/ubuntu/hibernation-info.txt

# Setup completion
echo "$(date)" > /tmp/hibernation-setup-complete
echo "Hibernation setup completed successfully at $(date)"
echo "Run './hibernate-status.sh' to check hibernation readiness"
