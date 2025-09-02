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
cat > /var/www/html/index.html << EOF
<!DOCTYPE html>
<html>
<head><title>SpotMan Web Server</title></head>
<body>
    <h1>🚀 SpotMan Web Server</h1>
    <p>Instance: $INSTANCE_ID</p>
    <p>Region: $REGION</p>
    <p>Deployed: $(date)</p>
</body>
</html>
EOF

# Health check endpoint
echo '{"status":"healthy","instance":"'$INSTANCE_ID'"}' > /var/www/html/health

echo "Web server setup completed at $(date)"
