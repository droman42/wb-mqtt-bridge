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
    echo "  --help           Show this help message"
}

# Parse command line arguments
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

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating default .env file..."
    cp .env.example .env
fi

# Create necessary directories
mkdir -p logs config/devices nginx/conf.d

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