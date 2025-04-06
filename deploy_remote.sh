#!/bin/bash

# Default values
DEFAULT_PORT=8080
SERVICE_NAME="mqtt-web-service"
WORKSPACE_DIR="mqtt-web-service"
VENV_DIR="venv"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
PYTHON_VERSION="3.9"

# Help message
show_help() {
    echo "MQTT Web Service Remote Deployment Script"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -h, --host           Remote host"
    echo "  -p, --port           Port for the REST API (default: 8080)"
    echo "  -u, --user           Remote user"
    echo "  -k, --key            SSH key file"
    echo "  --help               Show this help message"
    echo
    echo "Example:"
    echo "  $0 -h example.com -p 8080 -u username -k ~/.ssh/id_rsa"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            REMOTE_HOST="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -u|--user)
            REMOTE_USER="$2"
            shift 2
            ;;
        -k|--key)
            SSH_KEY="$2"
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

# Validate required arguments
if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_USER" ] || [ -z "$SSH_KEY" ]; then
    echo "Error: Remote host (-h), user (-u), and SSH key (-k) are required"
    show_help
    exit 1
fi

PORT=${PORT:-$DEFAULT_PORT}

# Create Nginx configuration
create_nginx_config() {
    cat > "$SERVICE_NAME" << EOF
server {
    listen 80;
    server_name $REMOTE_HOST;

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
User=$REMOTE_USER
WorkingDirectory=/home/$REMOTE_USER/$WORKSPACE_DIR
Environment="PATH=/home/$REMOTE_USER/$WORKSPACE_DIR/$VENV_DIR/bin"
ExecStart=/home/$REMOTE_USER/$WORKSPACE_DIR/$VENV_DIR/bin/uvicorn app.main:app --host 127.0.0.1 --port $PORT
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

echo "Starting remote deployment..."

# Create temporary deployment directory
TEMP_DIR=$(mktemp -d)
cp -r ./* "$TEMP_DIR/"

# Create configuration files
create_nginx_config
create_service_file

# Copy files to remote server
echo "Copying files to remote server..."
scp -i "$SSH_KEY" -r "$TEMP_DIR" "$REMOTE_USER@$REMOTE_HOST:$WORKSPACE_DIR"
scp -i "$SSH_KEY" "$SERVICE_NAME" "$REMOTE_USER@$REMOTE_HOST:/tmp/"
scp -i "$SSH_KEY" "$SERVICE_NAME.service" "$REMOTE_USER@$REMOTE_HOST:/tmp/"

# Execute remote setup commands
ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST" << EOF
    # Setup Python environment
    python$PYTHON_VERSION -m venv "$WORKSPACE_DIR/$VENV_DIR"
    source "$WORKSPACE_DIR/$VENV_DIR/bin/activate"
    pip install -r "$WORKSPACE_DIR/requirements.txt"
    
    # Setup Nginx (requires sudo)
    sudo mv "/tmp/$SERVICE_NAME" "$NGINX_AVAILABLE/"
    sudo ln -sf "$NGINX_AVAILABLE/$SERVICE_NAME" "$NGINX_ENABLED/"
    
    # Setup systemd service (requires sudo)
    sudo mv "/tmp/$SERVICE_NAME.service" "/etc/systemd/system/"
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start "$SERVICE_NAME"
    
    # Test and reload Nginx (requires sudo)
    sudo nginx -t && sudo systemctl reload nginx
    
    # Show service status
    sudo systemctl status "$SERVICE_NAME"
EOF

# Cleanup
rm -rf "$TEMP_DIR"
rm -f "$SERVICE_NAME" "$SERVICE_NAME.service"

echo "Remote deployment completed successfully!"
echo "Service is available at http://$REMOTE_HOST:$PORT" 