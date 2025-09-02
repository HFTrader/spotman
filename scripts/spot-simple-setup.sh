#!/bin/bash
set -e

# Basic logging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Basic spot instance initialization at $(date)"

# Essential system updates
echo "Performing system updates..."
apt-get update && apt-get upgrade -y

# Install core utilities
echo "Installing core utilities..."
apt-get install -y htop curl wget awscli jq

# Create basic environment
echo "Setting up environment..."

# Add useful aliases for ubuntu user
cat >> /home/ubuntu/.bashrc << 'EOF'

# SpotMan aliases
alias ll='ls -la'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias h='history'
alias df='df -h'
alias du='du -h'
alias free='free -h'
EOF

# Create simple system info command
cat > /usr/local/bin/sysinfo << 'EOF'
#!/bin/bash

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== System Information ==="
echo "Hostname: $(hostname)"
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id 2>/dev/null || echo 'N/A')"
echo "Instance Type: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type 2>/dev/null || echo 'N/A')"
echo "Region: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region 2>/dev/null || echo 'N/A')"
echo "Uptime: $(uptime -p)"
echo "Load: $(cat /proc/loadavg | cut -d' ' -f1-3)"
echo "Memory: $(free -h | grep Mem | awk '{print $3"/"$2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3"/"$2" ("$5" used)"}')"
EOF
chmod +x /usr/local/bin/sysinfo

# Setup completion marker
echo "$(date)" > /tmp/setup-completed
echo "Basic spot instance setup completed at $(date)"
