#!/bin/bash

# Help message
show_help() {
    echo "MQTT Web Service Docker Deployment Script"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -b, --build       Rebuild containers"
    echo "  -d, --down        Stop and remove containers"
    echo "  -r, --restart     Restart containers"
    echo "  --deps            Clone/update required local dependencies"
    echo "  --help            Show this help message"
}

# Parse command line arguments
CLONE_DEPS=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--build)
            BUILD=true
            shift
            ;;
        -d|--down)
            DOWN=true
            shift
            ;;
        -r|--restart)
            RESTART=true
            shift
            ;;
        --deps)
            CLONE_DEPS=true
            shift
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

# Clone or update required dependencies
if [ "$CLONE_DEPS" = true ]; then
    echo "Checking for required dependencies..."
    
    # Define the parent directory (one level up)
    PARENT_DIR="$(dirname $(pwd))"
    
    # Check for pymotivaxmc2
    if [ ! -d "$PARENT_DIR/pymotivaxmc2" ]; then
        echo "Cloning pymotivaxmc2..."
        git -C "$PARENT_DIR" clone https://github.com/droman42/pymotivaxmc2.git
    else
        echo "Updating pymotivaxmc2..."
        git -C "$PARENT_DIR/pymotivaxmc2" pull
    fi
    
    # Check for asyncwebostv
    if [ ! -d "$PARENT_DIR/asyncwebostv" ]; then
        echo "Cloning asyncwebostv..."
        git -C "$PARENT_DIR" clone https://github.com/droman42/asyncwebostv.git
    else
        echo "Updating asyncwebostv..."
        git -C "$PARENT_DIR/asyncwebostv" pull
    fi
    
    echo "Dependencies updated."
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating default .env file..."
    cp .env.example .env || echo "No .env.example found, please create .env manually."
fi

# Create necessary directories
mkdir -p logs config/devices nginx/conf.d

# Check if nginx config exists
if [ ! -f nginx/conf.d/default.conf ]; then
    echo "Creating default nginx configuration..."
    cat > nginx/conf.d/default.conf << 'EOL'
server {
    listen 80;  # This is the internal port (remains 80)
    server_name localhost;

    # The service will be available externally on port 8081 (or NGINX_PORT from .env)
    location / {
        proxy_pass http://wb-mqtt-bridge:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOL
fi

# Stop and remove containers if requested
if [ "$DOWN" = true ]; then
    echo "Stopping and removing containers..."
    docker-compose down
    exit 0
fi

# Build and start containers
if [ "$BUILD" = true ]; then
    echo "Building and starting containers..."
    docker-compose up -d --build
elif [ "$RESTART" = true ]; then
    echo "Restarting containers..."
    docker-compose restart
else
    echo "Starting containers..."
    docker-compose up -d
fi

# Check container status
echo "Checking container status..."
docker-compose ps 