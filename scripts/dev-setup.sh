#!/bin/bash
# Development environment setup
echo "Development environment setup started at $(date)"

# Install development tools
echo "Installing development tools..."
apt-get install -y \
    git vim nano \
    build-essential \
    python3-pip \
    nodejs npm \
    docker.io

# Configure git
git config --system init.defaultBranch main

# Add user to docker group
usermod -aG docker ubuntu

# Install common Python packages
pip3 install boto3 requests

# Create development workspace
mkdir -p /home/ubuntu/{projects,workspace,bin}
chown ubuntu:ubuntu /home/ubuntu/{projects,workspace,bin}

# Add development aliases
cat >> /home/ubuntu/.bashrc << 'EOF'

# Development aliases
alias ll='ls -la'
alias la='ls -A'
alias ..='cd ..'
alias ...='cd ../..'
alias gs='git status'
alias gp='git pull'
alias gc='git commit'
alias gd='git diff'
EOF

echo "Development environment setup completed at $(date)"
