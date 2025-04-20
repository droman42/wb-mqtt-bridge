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
    echo "  --save [path]     After building, save images to tar files for transfer to Wirenboard"
    echo "  --transfer [ip]   Transfer saved images to Wirenboard at specified IP address"
    echo "  --help            Show this help message"
    echo
    echo "This script supports ARMv7 architecture for Wirenboard 7."
    echo "If building on a non-ARM machine, Docker Buildx will be used for cross-platform builds."
    echo
    echo "Examples:"
    echo "  $0 -b --save                      # Build and save images to current directory"
    echo "  $0 --save ./images                # Save images to ./images directory"
    echo "  $0 --transfer 192.168.1.100       # Transfer previously saved images to Wirenboard"
    echo "  $0 -b --save --transfer 192.168.1.100  # Build, save, and transfer in one step"
}

# Parse command line arguments
CLONE_DEPS=false
SAVE_IMAGES=false
TRANSFER_IMAGES=false
SAVE_PATH="."
WB_IP=""

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
        --save)
            SAVE_IMAGES=true
            if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                SAVE_PATH="$2"
                shift
            fi
            shift
            ;;
        --transfer)
            TRANSFER_IMAGES=true
            if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                WB_IP="$2"
                shift
            else
                echo "Error: --transfer requires an IP address"
                exit 1
            fi
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

# Detect host architecture
HOST_ARCHITECTURE=$(uname -m)
echo "Detected host architecture: $HOST_ARCHITECTURE"

# Set target architecture for Wirenboard 7
TARGET_ARCHITECTURE="armv7l"
echo "Target architecture: $TARGET_ARCHITECTURE (Wirenboard 7 - Debian Bullseye)"

# Set environment variables based on architecture
export ARCH=arm32v7

# Determine if cross-compilation is needed
CROSS_COMPILE=false
if [[ "$HOST_ARCHITECTURE" != "$TARGET_ARCHITECTURE" ]]; then
    echo "Cross-compilation required (building $TARGET_ARCHITECTURE on $HOST_ARCHITECTURE)"
    CROSS_COMPILE=true
    
    # Check if Docker Buildx is available
    if ! docker buildx version > /dev/null 2>&1; then
        echo "Error: Docker Buildx is required for cross-platform builds but not available"
        echo "Please install Docker Buildx: https://docs.docker.com/buildx/working-with-buildx/"
        exit 1
    fi
    
    # Setup ARM emulation support
    echo "Setting up ARM architecture emulation..."
    docker run --privileged --rm tonistiigi/binfmt --install arm
    
    # Create and configure buildx builder for ARM
    echo "Creating and configuring buildx builder for ARM architecture..."
    docker buildx create --name arm_builder --use
    docker buildx inspect --bootstrap
    
    echo "ARM build environment is ready"
fi

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

# Save Docker images as tar files for transfer to Wirenboard
save_images() {
    local save_dir="$1"
    echo "Saving Docker images to $save_dir for transfer to Wirenboard 7..."
    
    mkdir -p "$save_dir"
    
    echo "Saving wb-mqtt-bridge image..."
    docker save wb-mqtt-bridge:latest | gzip > "$save_dir/wb-mqtt-bridge.tar.gz"
    
    echo "Saving arm32v7/nginx image..."
    docker save arm32v7/nginx:1.22-bullseye | gzip > "$save_dir/nginx-arm32v7.tar.gz"
    
    echo "Saving docker-compose.yml and related files..."
    tar -czf "$save_dir/wb-mqtt-bridge-config.tar.gz" docker-compose.yml nginx/conf.d .env
    
    echo "Images and configuration saved to:"
    echo "  $save_dir/wb-mqtt-bridge.tar.gz"
    echo "  $save_dir/nginx-arm32v7.tar.gz"
    echo "  $save_dir/wb-mqtt-bridge-config.tar.gz"
    echo
    echo "Transfer these files to your Wirenboard 7 device and run:"
    echo "  docker load -i wb-mqtt-bridge.tar.gz"
    echo "  docker load -i nginx-arm32v7.tar.gz"
    echo "  tar -xzf wb-mqtt-bridge-config.tar.gz"
    echo "  docker-compose up -d"
}

# Transfer images to Wirenboard device
transfer_images() {
    local wb_ip="$1"
    local save_dir="$2"
    
    if [ ! -f "$save_dir/wb-mqtt-bridge.tar.gz" ] || [ ! -f "$save_dir/nginx-arm32v7.tar.gz" ]; then
        echo "Error: Docker image files not found in $save_dir"
        echo "Run '$0 --save $save_dir' first to create the image files"
        exit 1
    fi
    
    echo "Transferring Docker images to Wirenboard 7 at $wb_ip..."
    
    # Create remote directory
    ssh root@$wb_ip "mkdir -p /root/wb-mqtt-bridge"
    
    # Transfer files
    echo "Transferring images and configuration (this may take a while)..."
    scp "$save_dir/wb-mqtt-bridge.tar.gz" "$save_dir/nginx-arm32v7.tar.gz" "$save_dir/wb-mqtt-bridge-config.tar.gz" root@$wb_ip:/root/wb-mqtt-bridge/
    
    echo "Setting up on Wirenboard..."
    ssh root@$wb_ip "cd /root/wb-mqtt-bridge && \
        tar -xzf wb-mqtt-bridge-config.tar.gz && \
        docker load -i wb-mqtt-bridge.tar.gz && \
        docker load -i nginx-arm32v7.tar.gz && \
        docker-compose up -d"
    
    echo "Deployment to Wirenboard 7 complete."
    echo "Check status with: ssh root@$wb_ip 'cd /root/wb-mqtt-bridge && docker-compose ps'"
}

# Stop and remove containers if requested
if [ "$DOWN" = true ]; then
    echo "Stopping and removing containers..."
    docker-compose down
    exit 0
fi

# Build and start containers
if [ "$BUILD" = true ]; then
    if [ "$CROSS_COMPILE" = true ]; then
        echo "Building with Docker Buildx for ARM architecture (Wirenboard 7)..."
        
        # Use buildx for cross-platform build of both services
        echo "Building wb-mqtt-bridge image..."
        docker buildx build \
            --platform linux/arm/v7 \
            --build-arg ARCH=arm32v7 \
            --tag wb-mqtt-bridge:latest \
            --load \
            .
        
        # Only start containers locally if not saving for transfer
        if [ "$SAVE_IMAGES" = false ] && [ "$TRANSFER_IMAGES" = false ]; then
            echo "Starting containers with docker-compose..."
            docker-compose up -d
        fi
    else
        echo "Building directly for native ARM architecture..."
        docker-compose up -d --build
    fi
elif [ "$RESTART" = true ]; then
    echo "Restarting containers..."
    docker-compose restart
elif [ "$SAVE_IMAGES" = false ] && [ "$TRANSFER_IMAGES" = false ]; then
    echo "Starting containers..."
    docker-compose up -d
fi

# Save images if requested
if [ "$SAVE_IMAGES" = true ]; then
    save_images "$SAVE_PATH"
fi

# Transfer images if requested
if [ "$TRANSFER_IMAGES" = true ]; then
    if [ -z "$WB_IP" ]; then
        echo "Error: No IP address specified for transfer"
        exit 1
    fi
    transfer_images "$WB_IP" "$SAVE_PATH"
fi

# Check container status if we're running locally
if [ "$SAVE_IMAGES" = false ] && [ "$TRANSFER_IMAGES" = false ]; then
    echo "Checking container status..."
    docker-compose ps
fi 