#!/bin/bash
set -e  # Exit on any error

# AWS Instance Metadata Service endpoint
AWS_METADATA_SERVER="http://169.254.169.254"

# Log all output for debugging
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting web server deployment at $(date)"

# Get instance metadata for dynamic content
INSTANCE_ID=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-id)
REGION=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/region)
AZ=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/placement/availability-zone)
INSTANCE_TYPE=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/instance-type)
PRIVATE_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/local-ipv4)
PUBLIC_IP=$(curl -s $AWS_METADATA_SERVER/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")

echo "Instance info: $INSTANCE_ID ($INSTANCE_TYPE) in $AZ"
echo "Network: Private IP: $PRIVATE_IP, Public IP: $PUBLIC_IP"

# Update system packages
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# Install essential packages
echo "Installing web server and tools..."
apt-get install -y nginx htop curl wget unzip awscli jq

# Configure nginx
echo "Configuring nginx..."
systemctl start nginx
systemctl enable nginx

# Create dynamic web page
cat > /var/www/html/index.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>SpotMan Web Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .info { margin: 20px 0; }
        .label { font-weight: bold; color: #34495e; }
        .value { color: #27ae60; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="header">🚀 SpotMan Web Server</h1>
        <div class="info">
            <p><span class="label">Instance ID:</span> <span class="value">${INSTANCE_ID}</span></p>
            <p><span class="label">Instance Type:</span> <span class="value">${INSTANCE_TYPE}</span></p>
            <p><span class="label">Private IP:</span> <span class="value">${PRIVATE_IP}</span></p>
            <p><span class="label">Public IP:</span> <span class="value">${PUBLIC_IP}</span></p>
            <p><span class="label">Region:</span> <span class="value">${REGION}</span></p>
            <p><span class="label">Availability Zone:</span> <span class="value">${AZ}</span></p>
            <p><span class="label">Deployment Time:</span> <span class="value">$(date)</span></p>
        </div>
        <p class="timestamp">Deployed with SpotMan using external script</p>
    </div>
</body>
</html>
EOF

# Create a health check endpoint
cat > /var/www/html/health << EOF
{
  "status": "healthy",
  "instance_id": "${INSTANCE_ID}",
  "region": "${REGION}",
  "timestamp": "$(date -Iseconds)",
  "deployment_method": "external_script"
}
EOF

# Configure nginx for better performance
cat > /etc/nginx/sites-available/default << EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    root /var/www/html;
    index index.html index.htm;
    
    server_name _;
    
    # Health check endpoint
    location /health {
        add_header Content-Type application/json;
        return 200;
    }
    
    # Main site
    location / {
        try_files \$uri \$uri/ =404;
    }
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
EOF

# Restart nginx to apply configuration
systemctl restart nginx

# Set up log rotation
cat > /etc/logrotate.d/user-data << EOF
/var/log/user-data.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
}
EOF

# Create startup completion marker
echo "Web server deployment completed successfully at $(date)" >> /var/log/user-data.log
touch /tmp/deployment-complete

echo "SpotMan web server deployment finished successfully!"
