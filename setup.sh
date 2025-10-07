#!/bin/bash
# Setup script for SpotMan - AWS Instance Manager

echo "Setting up SpotMan..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed. Please install pip3 first."
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Warning: AWS CLI is not installed. You may want to install it for easier credential management."
    echo "Install with: pip3 install awscli"
else
    echo "AWS CLI found."
fi

# Make the scripts executable
echo "Setting up executable permissions..."
chmod +x spotman
chmod +x ollama-manager

# Verify core module is present
if [ ! -f "spotman_core.py" ]; then
    echo "Error: spotman_core.py not found. This is required for SpotMan to function."
    exit 1
fi

echo "Core module found: spotman_core.py"

# Create symlinks for easier access (optional)
if [ -w /usr/local/bin ]; then
    ln -sf "$(pwd)/spotman" /usr/local/bin/spotman
    ln -sf "$(pwd)/ollama-manager" /usr/local/bin/ollama-manager
    echo "Created symlinks:"
    echo "  spotman -> $(pwd)/spotman"
    echo "  ollama-manager -> $(pwd)/ollama-manager"
fi

# Verify installation
echo ""
echo "Verifying installation..."

# Test spotman
if ./spotman --help > /dev/null 2>&1; then
    echo "✅ spotman: Working correctly"
else
    echo "❌ spotman: Failed to run"
fi

# Test ollama-manager
if ./ollama-manager --help > /dev/null 2>&1; then
    echo "✅ ollama-manager: Working correctly"
else
    echo "❌ ollama-manager: Failed to run"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Available tools:"
echo "  ./spotman        - Main AWS instance manager"
echo "  ./ollama-manager - Specialized Ollama LLM server manager"
echo ""
echo "Quick start:"
echo "1. Configure AWS credentials: aws configure"
echo "2. Edit a profile file in the profiles/ directory"
echo "3. Create an instance: ./spotman create --profile test --name test01 --class test"
echo "4. List instances: ./spotman list"
echo "5. Create Ollama instance: ./ollama-manager create --name ollama01"
echo ""
echo "See README.md for full documentation."
