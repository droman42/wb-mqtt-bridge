#!/bin/bash

# Default values
DEFAULT_PORT=8080
DEFAULT_HOST="localhost"
PYTHON_VERSION="3.9"
SERVICE_NAME="mqtt-web-service"
WORKSPACE_DIR="$HOME/$SERVICE_NAME"
VENV_DIR="$WORKSPACE_DIR/venv"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"

# Help message
show_help() {
    echo "MQTT Web Service Deployment Script"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -e, --environment     Deployment environment (local|remote)"
    echo "  -h, --host           Remote host (for remote deployment)"
    echo "  -p, --port           Port for the REST API (default: 8080)"
    echo "  -u, --user           Remote user (for remote deployment)"
    echo "  -k, --key            SSH key file (for remote deployment)"
    echo "  --help               Show this help message"
    echo
    echo "Example:"
    echo "  Local deployment:  $0 -e local -p 8080"
    echo "  Remote deployment: $0 -e remote -h example.com -p 8080 -u username -k ~/.ssh/id_rsa"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
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
if [ -z "$ENVIRONMENT" ]; then
    echo "Error: Environment (-e) is required"
    show_help
    exit 1
fi

if [ "$ENVIRONMENT" != "local" ] && [ "$ENVIRONMENT" != "remote" ]; then
    echo "Error: Environment must be either 'local' or 'remote'"
    exit 1
fi

if [ "$ENVIRONMENT" = "remote" ]; then
    if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_USER" ] || [ -z "$SSH_KEY" ]; then
        echo "Error: Remote deployment requires host (-h), user (-u), and SSH key (-k)"
        exit 1
    fi
fi

PORT=${PORT:-$DEFAULT_PORT}

# Create Nginx configuration
create_nginx_config() {
    local config_file="$SERVICE_NAME"
    
    cat > "$config_file" << EOF
server {
    listen 80;
    server_name ${1:-localhost};

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

# Local deployment function
deploy_local() {
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
    sudo mv "$SERVICE_NAME" "$NGINX_AVAILABLE/"
    sudo ln -sf "$NGINX_AVAILABLE/$SERVICE_NAME" "$NGINX_ENABLED/"
    
    # Create and enable systemd service
    create_service_file
    sudo mv "$SERVICE_NAME.service" "/etc/systemd/system/"
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start "$SERVICE_NAME"
    
    # Test Nginx configuration and reload
    sudo nginx -t && sudo systemctl reload nginx
    
    echo "Local deployment completed successfully!"
    echo "Service is available at http://localhost:$PORT"
}

# Remote deployment function
deploy_remote() {
    echo "Starting remote deployment..."
    
    # Create temporary deployment directory
    TEMP_DIR=$(mktemp -d)
    cp -r ./* "$TEMP_DIR/"
    
    # Create Nginx and systemd configurations
    create_nginx_config "$REMOTE_HOST"
    create_service_file
    
    # Copy files to remote server
    echo "Copying files to remote server..."
    scp -i "$SSH_KEY" -r "$TEMP_DIR" "$REMOTE_USER@$REMOTE_HOST:$WORKSPACE_DIR"
    scp -i "$SSH_KEY" "$SERVICE_NAME" "$REMOTE_USER@$REMOTE_HOST:/tmp/"
    scp -i "$SSH_KEY" "$SERVICE_NAME.service" "$REMOTE_USER@$REMOTE_HOST:/tmp/"
    
    # Execute remote setup commands
    ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST" << EOF
        # Setup Python environment
        python$PYTHON_VERSION -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        pip install -r "$WORKSPACE_DIR/requirements.txt"
        
        # Setup Nginx
        sudo mv "/tmp/$SERVICE_NAME" "$NGINX_AVAILABLE/"
        sudo ln -sf "$NGINX_AVAILABLE/$SERVICE_NAME" "$NGINX_ENABLED/"
        
        # Setup systemd service
        sudo mv "/tmp/$SERVICE_NAME.service" "/etc/systemd/system/"
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME"
        
        # Reload Nginx
        sudo nginx -t && sudo systemctl reload nginx
EOF
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    rm -f "$SERVICE_NAME" "$SERVICE_NAME.service"
    
    echo "Remote deployment completed successfully!"
    echo "Service is available at http://$REMOTE_HOST:$PORT"
}

# Main deployment logic
if [ "$ENVIRONMENT" = "local" ]; then
    deploy_local
else
    deploy_remote
fi 