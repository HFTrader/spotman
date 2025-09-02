#!/bin/bash
set -e

# Get script directory from instance metadata or S3
SCRIPT_DIR="/tmp/spotman-scripts"
mkdir -p $SCRIPT_DIR

# Download common setup script
cat > $SCRIPT_DIR/common-setup.sh << 'COMMON_EOF'
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
COMMON_EOF

# Download web setup script
cat > $SCRIPT_DIR/web-setup.sh << 'WEB_EOF'
#!/bin/bash
# Web server specific setup

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

echo "Web server setup started at $(date)"

# Install nginx
echo "Installing nginx..."
apt-get install -y nginx
systemctl start nginx
systemctl enable nginx

# Get instance metadata
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)

# Create web page
cat > /var/www/html/index.html << HTML_EOF
<!DOCTYPE html>
<html>
<head><title>SpotMan Modular Web Server</title></head>
<body>
    <h1>🚀 SpotMan Modular Web Server</h1>
    <p>Instance: $INSTANCE_ID</p>
    <p>Region: $REGION</p>
    <p>Deployed: $(date)</p>
    <p>Architecture: Modular Scripts</p>
</body>
</html>
HTML_EOF

# Health check endpoint
echo '{"status":"healthy","instance":"'$INSTANCE_ID'","type":"modular"}' > /var/www/html/health

echo "Web server setup completed at $(date)"
WEB_EOF

# Make scripts executable
chmod +x $SCRIPT_DIR/*.sh

# Execute setup scripts in order
echo "Executing modular setup scripts..."
$SCRIPT_DIR/common-setup.sh
$SCRIPT_DIR/web-setup.sh

echo "Modular web server deployment completed at $(date)"
