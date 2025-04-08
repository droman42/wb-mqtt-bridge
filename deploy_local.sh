#!/bin/bash

# Default values
DEFAULT_PORT=8080
SERVICE_NAME="wb-mqtt-bridge"
WORKSPACE_DIR="$HOME/$SERVICE_NAME"
VENV_DIR="$WORKSPACE_DIR/venv"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
PYTHON_VERSION="3.9"

# Help message
show_help() {
    echo "MQTT Web Service Local Deployment Script"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -p, --port           Port for the REST API (default: 8080)"
    echo "  --help               Show this help message"
    echo
    echo "Example:"
    echo "  $0 -p 8080"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

PORT=${PORT:-$DEFAULT_PORT}

# Create Nginx configuration
create_nginx_config() {
    local config_file="$SERVICE_NAME"
    
    cat > "$config_file" << EOF
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
}

# Create systemd service file
create_service_file() {
    cat > "$SERVICE_NAME.service" << EOF
[Unit]
Description=MQTT Web Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$WORKSPACE_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/uvicorn app.main:app --host 127.0.0.1 --port $PORT
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

echo "Starting local deployment..."

# Create workspace directory
mkdir -p "$WORKSPACE_DIR"

# Copy project files
cp -r ./* "$WORKSPACE_DIR/"

# Setup Python virtual environment
python$PYTHON_VERSION -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -r "$WORKSPACE_DIR/requirements.txt"

# Create and enable Nginx configuration
create_nginx_config
mv "$SERVICE_NAME" "$NGINX_AVAILABLE/"
ln -sf "$NGINX_AVAILABLE/$SERVICE_NAME" "$NGINX_ENABLED/"

# Create and enable systemd service
create_service_file
mv "$SERVICE_NAME.service" "/etc/systemd/system/"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Test Nginx configuration and reload
nginx -t && systemctl reload nginx

echo "Local deployment completed successfully!"
echo "Service is available at http://localhost:$PORT"

# Show service status
systemctl status "$SERVICE_NAME" 