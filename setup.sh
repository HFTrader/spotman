#!/bin/bash
# Setup script for AWS Instance Manager

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

# Make the script executable
chmod +x spotman

# Create symlink for easier access (optional)
if [ -w /usr/local/bin ]; then
    ln -sf "$(pwd)/spotman" /usr/local/bin/spotman
    echo "Created symlink: spotman -> $(pwd)/spotman"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Quick start:"
echo "1. Configure AWS credentials: aws configure"
echo "2. Edit a profile file in the profiles/ directory"
echo "3. Create an instance: ./spotman create --profile web-server --name test01 --class test"
echo "4. List instances: ./spotman list"
echo ""
echo "See README.md for full documentation."
