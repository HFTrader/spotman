#!/bin/bash
set -e  # Exit on any error

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

# Comprehensive logging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Ollama LLM server setup started at $(date)"

# Get instance information
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
INSTANCE_TYPE=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)
PRIVATE_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)
PUBLIC_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)

echo "Setting up Ollama on instance $INSTANCE_ID ($INSTANCE_TYPE)"
echo "Private IP: $PRIVATE_IP, Public IP: $PUBLIC_IP, Region: $REGION"

# System updates
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install prerequisite packages
echo "Installing prerequisite packages..."
apt-get install -y curl wget htop iotop jq pm-utils

# Install AWS CLI v2
echo "Installing AWS CLI v2..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
apt-get install -y unzip
unzip awscliv2.zip
./aws/install
rm -rf awscliv2.zip aws/

# Configure swap for hibernation (hibernation requires swap >= RAM)
echo "Configuring swap space for hibernation..."

# Get RAM size to determine swap size
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
SWAP_GB=$((RAM_GB + 2))  # Add 2GB buffer

echo "RAM: ${RAM_GB}GB, Creating ${SWAP_GB}GB swap file for hibernation"

# Create swap file if it doesn't exist
if [ ! -f /swapfile ]; then
    fallocate -l ${SWAP_GB}G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap file created and activated"
else
    echo "Swap file already exists"
fi

# Update initramfs for hibernation support
echo "Updating initramfs for hibernation support..."
update-initramfs -u

# Install Ollama
echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

# Configure Ollama service to bind to all interfaces
echo "Configuring Ollama service..."
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

# Enable and start Ollama service
systemctl daemon-reload
systemctl enable ollama
systemctl start ollama

# Wait for Ollama to be ready
echo "Waiting for Ollama service to be ready..."
sleep 10

# Test Ollama installation
echo "Testing Ollama installation..."
ollama --version
systemctl status ollama --no-pager

# Create Ollama management scripts
echo "Creating Ollama management scripts..."

# Ollama status script
cat > /home/ubuntu/ollama-status.sh << 'EOF'
#!/bin/bash

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Ollama Server Status ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Instance Type: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)"
echo "Private IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)"
echo "Public IP: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo 'N/A')"
echo ""

echo "Ollama Service Status:"
systemctl status ollama --no-pager
echo ""

echo "Ollama Version:"
ollama --version
echo ""

echo "Available Models:"
ollama list
echo ""

echo "Resource Usage:"
echo "Memory:"
free -h
echo ""
echo "Disk:"
df -h /
echo ""

echo "Network Connectivity Test:"
echo "Ollama API test: $(curl -s http://localhost:11434/api/version | jq -r '.version' || echo 'Failed')"
EOF

# Model management script
cat > /home/ubuntu/ollama-models.sh << 'EOF'
#!/bin/bash

echo "=== Ollama Model Management ==="
echo ""

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <command> [model_name]"
    echo ""
    echo "Commands:"
    echo "  list              - List installed models"
    echo "  pull <model>      - Download a model"
    echo "  remove <model>    - Remove a model"
    echo "  run <model>       - Run/test a model"
    echo "  popular           - Show popular models to download"
    echo ""
    echo "Popular models:"
    echo "  llama3.2:3b      - Latest Llama model (3B parameters)"
    echo "  mistral:7b       - Mistral 7B model"
    echo "  codellama:7b     - Code-focused Llama model"
    echo "  phi3:mini        - Small efficient model"
    echo ""
    exit 1
fi

case "$1" in
    "list")
        echo "Installed models:"
        ollama list
        ;;
    "pull")
        if [ -z "$2" ]; then
            echo "Error: Please specify a model name"
            exit 1
        fi
        echo "Downloading model: $2"
        ollama pull "$2"
        ;;
    "remove")
        if [ -z "$2" ]; then
            echo "Error: Please specify a model name"
            exit 1
        fi
        echo "Removing model: $2"
        ollama rm "$2"
        ;;
    "run")
        if [ -z "$2" ]; then
            echo "Error: Please specify a model name"
            exit 1
        fi
        echo "Testing model: $2"
        echo "Type a message and press Enter (type 'exit' to quit):"
        ollama run "$2"
        ;;
    "popular")
        echo "Popular Ollama models:"
        echo ""
        echo "Small models (good for testing):"
        echo "  phi3:mini        - 3.8GB - Microsoft Phi-3 Mini"
        echo "  gemma2:2b        - 1.6GB - Google Gemma 2B"
        echo ""
        echo "Medium models (balanced performance):"
        echo "  llama3.2:3b      - 2.0GB - Meta Llama 3.2 3B"
        echo "  mistral:7b       - 4.1GB - Mistral 7B"
        echo "  codellama:7b     - 3.8GB - Code Llama 7B"
        echo ""
        echo "Large models (best performance, more resources needed):"
        echo "  llama3.1:8b      - 4.7GB - Meta Llama 3.1 8B"
        echo "  mistral:8x7b     - 26GB  - Mistral 8x7B MoE"
        echo ""
        echo "To download: ./ollama-models.sh pull <model_name>"
        ;;
    *)
        echo "Unknown command: $1"
        exit 1
        ;;
esac
EOF

# Hibernation script with Ollama-specific preparation
cat > /home/ubuntu/hibernate-ollama.sh << 'EOF'
#!/bin/bash
# Script to safely hibernate the Ollama instance

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "=== Ollama Instance Hibernation ==="
echo "Instance ID: $(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)"
echo "Current time: $(date)"
echo ""

echo "Checking Ollama service..."
if systemctl is-active --quiet ollama; then
    echo "✓ Ollama service is running"
    echo "  Models available: $(ollama list | grep -c '^' || echo '0')"
else
    echo "⚠ Ollama service is not running"
fi

# Check hibernation readiness
SWAP_TOTAL=$(free -g | awk '/^Swap:/{print $2}')
RAM_TOTAL=$(free -g | awk '/^Mem:/{print $2}')

echo ""
echo "Hibernation readiness check:"
echo "RAM: ${RAM_TOTAL}GB, Swap: ${SWAP_TOTAL}GB"

if [ "$SWAP_TOTAL" -lt "$RAM_TOTAL" ]; then
    echo "❌ WARNING: Insufficient swap space for hibernation"
    echo "   This may cause hibernation to fail"
else
    echo "✓ Swap space is adequate for hibernation"
fi

echo ""
echo "Preparing for hibernation..."

# Sync filesystem
sync

echo "Initiating hibernation..."
echo "Note: Use 'spotman hibernate resume <instance>' to resume"

# Hibernate the system
sudo systemctl hibernate
EOF

# Make scripts executable and set ownership
chmod +x /home/ubuntu/ollama-*.sh /home/ubuntu/hibernate-ollama.sh
chown ubuntu:ubuntu /home/ubuntu/ollama-*.sh /home/ubuntu/hibernate-ollama.sh

# Create Ollama info file
cat > /home/ubuntu/ollama-info.txt << EOF
=== Ollama LLM Server Information ===

Setup completed: $(date)
Instance ID: $INSTANCE_ID
Instance Type: $INSTANCE_TYPE
Private IP: $PRIVATE_IP
Public IP: $PUBLIC_IP
Region: $REGION
RAM: ${RAM_GB}GB
Swap: ${SWAP_GB}GB

Ollama Configuration:
- Service: ollama (systemd)
- Port: 11434 (bound to all interfaces)
- API Endpoint: http://localhost:11434
- Models Directory: /usr/share/ollama/.ollama/models

Available Scripts:
- ./ollama-status.sh: Check Ollama service status
- ./ollama-models.sh: Manage models (download/remove/test)
- ./hibernate-ollama.sh: Hibernate with Ollama preparation

Quick Start:
1. Download a model: ./ollama-models.sh pull llama3.2:3b
2. Test the model: ./ollama-models.sh run llama3.2:3b
3. Check status: ./ollama-status.sh

API Usage:
curl http://localhost:11434/api/version
curl -X POST http://localhost:11434/api/generate \\
  -H "Content-Type: application/json" \\
  -d '{"model": "llama3.2:3b", "prompt": "Hello world"}'

Port Forwarding (SSH):
Your SSH config should include: LocalForward 11434 localhost:11434
Access from local machine: http://localhost:11434

Hibernation:
- Use ./hibernate-ollama.sh to hibernate safely
- Resume with: spotman hibernate resume <instance-name>
- Hibernation preserves running models and state

Spot Instance Notes:
- This is a spot instance - may be interrupted
- Use hibernation to preserve state during interruptions
- Monitor spot instance status in AWS console
EOF
chown ubuntu:ubuntu /home/ubuntu/ollama-info.txt

# Download a lightweight model for testing (optional)
echo "Downloading a lightweight test model..."
su - ubuntu -c "ollama pull phi3:mini" || echo "Model download failed - can be done manually later"

# Setup completion
echo "$(date)" > /tmp/ollama-setup-complete
echo "Ollama LLM server setup completed successfully at $(date)"
echo ""
echo "=== Next Steps ==="
echo "1. SSH to the instance: ssh ollama-<instance-name>"
echo "2. Check status: ./ollama-status.sh"  
echo "3. Download models: ./ollama-models.sh pull llama3.2:3b"
echo "4. Read info: cat ollama-info.txt"
echo ""
echo "API available at: http://localhost:11434 (via SSH port forwarding)"