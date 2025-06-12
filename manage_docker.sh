#!/bin/bash

# Wirenboard Docker Management Script
# Manages Docker containers with GitHub artifact integration

set -euo pipefail

# Default configuration
DEFAULT_CONTAINER_NAME="wb-mqtt-bridge"
DEFAULT_IMAGE_NAME="wb-mqtt-bridge:latest"
DEFAULT_PORT="8000:8000"
DEFAULT_MEMORY="256M"
DEFAULT_CPUS="0.5"
DEFAULT_GITHUB_USER="droman42"
CONFIG_FILE="$HOME/docker_manager_config.json"
ARTIFACTS_DIR="/mnt/sdcard/artifacts"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --clean                           Perform full Docker cleanup (prune)
    --download <repo_name>            Download latest GitHub artifacts
    --install <directory>             Install downloaded artifacts to directory
    --start <container> <resource_dir> Start container with specified name and resource directory
    --info                            Show running containers with stats
    --stop <container>                Stop a running container
    --config                          Create configuration file with default values
    --help                           Show this help message

Environment Variables (optional):
    CONTAINER_NAME                   Container name (default: $DEFAULT_CONTAINER_NAME)
    IMAGE_NAME                       Docker image name (default: $DEFAULT_IMAGE_NAME)
    PORT                            Port mapping (default: $DEFAULT_PORT)
    MEMORY                          Memory limit (default: $DEFAULT_MEMORY)
    CPUS                            CPU limit (default: $DEFAULT_CPUS)
    GITHUB_USERNAME                 GitHub username
    GITHUB_PAT                      GitHub Personal Access Token

Examples:
    $0 --clean
    $0 --config
    $0 --download wb-mqtt-bridge
    $0 --install /opt/mqtt-bridge
    $0 --start wb-mqtt-bridge /opt/mqtt-bridge
    $0 --info
    $0 --stop wb-mqtt-bridge

EOF
}

# Check if required dependencies are installed
check_dependencies() {
    log "Checking dependencies..."
    
    local deps=("docker" "curl" "tar" "jq")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            error "Required dependency '$dep' is not installed"
        fi
    done
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running or not accessible"
    fi
    
    success "All dependencies are available"
}

# Create configuration file with default values
create_config() {
    local config_file="./docker_manager_config.json"
    
    log "Creating configuration file: $config_file"
    
    # Check if config file already exists
    if [[ -f "$config_file" ]]; then
        warning "Configuration file already exists at $config_file"
        echo -n "Do you want to overwrite it? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log "Configuration creation cancelled"
            return 0
        fi
    fi
    
    # Create configuration file with default values
    cat > "$config_file" << EOF
{
    "docker": {
        "container_name": "$DEFAULT_CONTAINER_NAME",
        "image_name": "$DEFAULT_IMAGE_NAME",
        "port": "$DEFAULT_PORT",
        "memory": "$DEFAULT_MEMORY",
        "cpus": "$DEFAULT_CPUS"
    },
    "github": {
        "username": "your_github_username",
        "pat": "your_personal_access_token",
        "user": "$DEFAULT_GITHUB_USER"
    },
    "paths": {
        "artifacts_dir": "$ARTIFACTS_DIR",
        "config_file": "$CONFIG_FILE"
    }
}
EOF
    
    # Set appropriate permissions
    chmod 600 "$config_file"
    
    success "Configuration file created at $config_file"
    log "Please edit the file to set your GitHub credentials:"
    log "  - Set 'github.username' to your GitHub username"
    log "  - Set 'github.pat' to your Personal Access Token"
    log "  - Modify other settings as needed"
    
    # Show the created file
    log "Current configuration:"
    cat "$config_file" | jq '.'
}

# Handle GitHub credentials
handle_credentials() {
    local username=""
    local pat=""
    local local_config="./docker_manager_config.json"
    
    # Check environment variables first
    if [[ -n "${GITHUB_USERNAME:-}" && -n "${GITHUB_PAT:-}" ]]; then
        username="$GITHUB_USERNAME"
        pat="$GITHUB_PAT"
        log "Using credentials from environment variables"
    elif [[ -f "$local_config" ]]; then
        # Check local config file first
        if jq -e '.github.username and .github.pat' "$local_config" &> /dev/null; then
            username=$(jq -r '.github.username' "$local_config")
            pat=$(jq -r '.github.pat' "$local_config")
            log "Using credentials from local config file: $local_config"
        fi
    elif [[ -f "$CONFIG_FILE" ]]; then
        # Check global config file
        if jq -e '.github.username and .github.pat' "$CONFIG_FILE" &> /dev/null; then
            username=$(jq -r '.github.username' "$CONFIG_FILE")
            pat=$(jq -r '.github.pat' "$CONFIG_FILE")
            log "Using credentials from global config file: $CONFIG_FILE"
        fi
    fi
    
    # Prompt for credentials if not found
    if [[ -z "$username" || -z "$pat" ]]; then
        log "GitHub credentials not found. Please provide them:"
        echo -n "GitHub Username: "
        read -r username
        echo -n "GitHub Personal Access Token: "
        read -rs pat
        echo
        
        # Create config file
        local config_dir
        config_dir=$(dirname "$CONFIG_FILE")
        mkdir -p "$config_dir"
        
        cat > "$CONFIG_FILE" << EOF
{
    "github": {
        "username": "$username",
        "pat": "$pat"
    }
}
EOF
        chmod 600 "$CONFIG_FILE"
        success "Credentials saved to $CONFIG_FILE"
    fi
    
    # Validate credentials
    log "Validating GitHub credentials..."
    local response
    response=$(curl -s -u "$username:$pat" "https://api.github.com/user" | jq -r '.login // empty')
    
    if [[ -z "$response" ]]; then
        error "Invalid GitHub credentials. Please check your username and token."
    fi
    
    success "GitHub credentials validated for user: $response"
    
    # Export for use in other functions
    export GITHUB_USERNAME="$username"
    export GITHUB_PAT="$pat"
}

# Docker cleanup function
docker_cleanup() {
    log "Starting Docker cleanup..."
    
    # Get initial disk usage
    local before_size
    before_size=$(docker system df --format "table {{.Size}}" | tail -n +2 | head -n 1 | awk '{print $1}')
    
    log "Cleaning up Docker system..."
    docker system prune -af
    
    log "Cleaning up Docker volumes..."
    docker volume prune -f
    
    log "Cleaning up Docker networks..."
    docker network prune -f
    
    # Get final disk usage
    local after_size
    after_size=$(docker system df --format "table {{.Size}}" | tail -n +2 | head -n 1 | awk '{print $1}')
    
    success "Docker cleanup completed"
    log "Docker system status:"
    docker system df
}

# Download GitHub artifacts
download_artifacts() {
    local repo_name="$1"
    local github_user="${DEFAULT_GITHUB_USER}"
    
    log "Downloading artifacts from ${github_user}/${repo_name}..."
    
    # Create artifacts directory
    mkdir -p "$ARTIFACTS_DIR"
    cd "$ARTIFACTS_DIR"
    
    # Get latest workflow run
    log "Fetching latest workflow run..."
    local latest_run
    latest_run=$(curl -s -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${github_user}/${repo_name}/actions/runs?status=success&per_page=1" \
        | jq -r '.workflow_runs[0].id // empty')
    
    if [[ -z "$latest_run" ]]; then
        error "No successful workflow runs found for ${github_user}/${repo_name}"
    fi
    
    log "Latest successful run ID: $latest_run"
    
    # Get artifacts for this run
    log "Fetching artifacts list..."
    local artifacts_response
    artifacts_response=$(curl -s -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${github_user}/${repo_name}/actions/runs/${latest_run}/artifacts")
    
    # Download wb-mqtt-bridge-image artifact
    log "Downloading Docker image artifact..."
    local image_artifact_id
    image_artifact_id=$(echo "$artifacts_response" | jq -r '.artifacts[] | select(.name=="wb-mqtt-bridge-image") | .id')
    
    if [[ -z "$image_artifact_id" ]]; then
        error "wb-mqtt-bridge-image artifact not found"
    fi
    
    curl -L -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${github_user}/${repo_name}/actions/artifacts/${image_artifact_id}/zip" \
        -o "wb-mqtt-bridge-image.zip"
    
    # Download wb-mqtt-bridge-config artifact
    log "Downloading config artifact..."
    local config_artifact_id
    config_artifact_id=$(echo "$artifacts_response" | jq -r '.artifacts[] | select(.name=="wb-mqtt-bridge-config") | .id')
    
    if [[ -z "$config_artifact_id" ]]; then
        error "wb-mqtt-bridge-config artifact not found"
    fi
    
    curl -L -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${github_user}/${repo_name}/actions/artifacts/${config_artifact_id}/zip" \
        -o "wb-mqtt-bridge-config.zip"
    
    # Verify downloads
    if [[ -f "wb-mqtt-bridge-image.zip" && -f "wb-mqtt-bridge-config.zip" ]]; then
        success "Artifacts downloaded successfully"
        ls -lh *.zip
    else
        error "Failed to download artifacts"
    fi
    
    cd - > /dev/null
}

# Install artifacts
install_artifacts() {
    local install_dir="$1"
    
    log "Installing artifacts to $install_dir..."
    
    # Create install directory if it doesn't exist
    if [[ ! -d "$install_dir" ]]; then
        log "Creating install directory: $install_dir"
        mkdir -p "$install_dir"
    fi
    
    # Check if artifacts exist
    if [[ ! -f "$ARTIFACTS_DIR/wb-mqtt-bridge-image.zip" || ! -f "$ARTIFACTS_DIR/wb-mqtt-bridge-config.zip" ]]; then
        error "Artifacts not found in $ARTIFACTS_DIR. Run --download first."
    fi
    
    # Extract artifacts
    log "Extracting Docker image artifact..."
    cd "$ARTIFACTS_DIR"
    unzip -o wb-mqtt-bridge-image.zip
    
    log "Extracting config artifact..."
    unzip -o wb-mqtt-bridge-config.zip
    
    # Load Docker image
    log "Loading Docker image..."
    if [[ -f "wb-mqtt-bridge.tar.gz" ]]; then
        docker load -i wb-mqtt-bridge.tar.gz
        success "Docker image loaded successfully"
    else
        error "Docker image file not found in extracted artifacts"
    fi
    
    # Extract config to install directory
    log "Extracting configuration to $install_dir..."
    if [[ -f "wb-mqtt-bridge-config.tar.gz" ]]; then
        tar -xzf wb-mqtt-bridge-config.tar.gz -C "$install_dir"
        success "Configuration extracted successfully"
    else
        error "Configuration archive not found in extracted artifacts"
    fi
    
    # Set proper permissions
    chmod -R 755 "$install_dir"
    
    # Verify installation
    log "Verifying installation..."
    if [[ -d "$install_dir/config" && -d "$install_dir/logs" && -d "$install_dir/data" ]]; then
        success "Installation completed successfully"
        log "Installed structure:"
        ls -la "$install_dir"
    else
        error "Installation verification failed"
    fi
    
    cd - > /dev/null
}

# Load configuration values from local config file if present
load_config_values() {
    local local_config="./docker_manager_config.json"
    
    if [[ -f "$local_config" ]]; then
        log "Loading configuration from local config file: $local_config"
        
        # Load Docker configuration values if not set via environment
        if [[ -z "${CONTAINER_NAME:-}" ]] && jq -e '.docker.container_name' "$local_config" &> /dev/null; then
            export CONTAINER_NAME=$(jq -r '.docker.container_name' "$local_config")
        fi
        
        if [[ -z "${IMAGE_NAME:-}" ]] && jq -e '.docker.image_name' "$local_config" &> /dev/null; then
            export IMAGE_NAME=$(jq -r '.docker.image_name' "$local_config")
        fi
        
        if [[ -z "${PORT:-}" ]] && jq -e '.docker.port' "$local_config" &> /dev/null; then
            export PORT=$(jq -r '.docker.port' "$local_config")
        fi
        
        if [[ -z "${MEMORY:-}" ]] && jq -e '.docker.memory' "$local_config" &> /dev/null; then
            export MEMORY=$(jq -r '.docker.memory' "$local_config")
        fi
        
        if [[ -z "${CPUS:-}" ]] && jq -e '.docker.cpus' "$local_config" &> /dev/null; then
            export CPUS=$(jq -r '.docker.cpus' "$local_config")
        fi
    fi
}

# Start container
start_container() {
    local container_name="$1"
    local resource_dir="$2"
    
    # Load configuration values from local config file
    load_config_values
    
    # Use environment variables or defaults
    local image_name="${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}"
    local port="${PORT:-$DEFAULT_PORT}"
    local memory="${MEMORY:-$DEFAULT_MEMORY}"
    local cpus="${CPUS:-$DEFAULT_CPUS}"
    local log_level="${LOG_LEVEL:-}"  # Allow LOG_LEVEL override
    
    log "Starting container '$container_name' with resources from '$resource_dir'..."
    
    # Verify resource directory exists
    if [[ ! -d "$resource_dir" ]]; then
        error "Resource directory '$resource_dir' does not exist"
    fi
    
    # Verify required subdirectories
    for subdir in config logs data; do
        if [[ ! -d "$resource_dir/$subdir" ]]; then
            error "Required subdirectory '$resource_dir/$subdir' not found"
        fi
    done
    
    # Stop and remove existing container if it exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        log "Stopping existing container '$container_name'..."
        docker stop "$container_name" || true
        log "Removing existing container '$container_name'..."
        docker rm "$container_name" || true
    fi
    
    # Start new container
    log "Starting new container with configuration:"
    log "  Image: $image_name"
    log "  Port: $port"
    log "  Memory: $memory"
    log "  CPUs: $cpus"
    log "  Config: $resource_dir/config:/app/config:ro"
    log "  Logs: $resource_dir/logs:/app/logs"
    log "  Data: $resource_dir/data:/app/data"
    if [[ -n "$log_level" ]]; then
        log "  Log Level Override: $log_level"
    fi
    
    # Build docker run command with optional log level
    local docker_cmd=(
        docker run -d
        --name "$container_name"
        --restart unless-stopped
        -p "$port"
        -v "$resource_dir/config:/app/config:ro"
        -v "$resource_dir/logs:/app/logs"
        -v "$resource_dir/data:/app/data"
        --memory="$memory"
        --cpus="$cpus"
    )
    
    # Add log level environment variable if specified
    if [[ -n "$log_level" ]]; then
        docker_cmd+=(-e "OVERRIDE_LOG_LEVEL=$log_level")
    fi
    
    docker_cmd+=("$image_name")
    
    # Execute the docker command
    "${docker_cmd[@]}"
    
    # Verify container started
    sleep 2
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        success "Container '$container_name' started successfully"
        
        # Show container status
        log "Container status:"
        docker ps --filter "name=$container_name" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        
        # Show recent logs
        log "Recent container logs:"
        docker logs --tail 10 "$container_name"
    else
        error "Failed to start container '$container_name'"
    fi
}

# Show container information and stats
show_container_info() {
    log "Showing Docker container information..."
    
    # Show running containers
    log "Running containers:"
    if docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | tail -n +2 | grep -q .; then
        docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        
        echo
        log "Container resource usage:"
        # Show stats for running containers (non-streaming, single snapshot)
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"
    else
        warning "No running containers found"
    fi
    
    echo
    log "All containers (including stopped):"
    docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.CreatedAt}}"
    
    echo
    log "Docker system information:"
    docker system df
}

# Stop container
stop_container() {
    local container_name="$1"
    
    log "Stopping container '$container_name'..."
    
    # Check if container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        error "Container '$container_name' does not exist"
    fi
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        warning "Container '$container_name' is not running"
        return 0
    fi
    
    # Stop the container
    if docker stop "$container_name"; then
        success "Container '$container_name' stopped successfully"
        
        # Show updated status
        log "Container status:"
        docker ps -a --filter "name=$container_name" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
    else
        error "Failed to stop container '$container_name'"
    fi
}

# Main function
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi
    
    # Check dependencies first
    check_dependencies
    
    case "$1" in
        --clean)
            docker_cleanup
            ;;
        --config)
            create_config
            ;;
        --download)
            if [[ $# -ne 2 ]]; then
                error "Usage: $0 --download <repo_name>"
            fi
            handle_credentials
            download_artifacts "$2"
            ;;
        --install)
            if [[ $# -ne 2 ]]; then
                error "Usage: $0 --install <directory>"
            fi
            install_artifacts "$2"
            ;;
        --start)
            if [[ $# -ne 3 ]]; then
                error "Usage: $0 --start <container> <resource_dir>"
            fi
            start_container "$2" "$3"
            ;;
        --info)
            show_container_info
            ;;
        --stop)
            if [[ $# -ne 2 ]]; then
                error "Usage: $0 --stop <container>"
            fi
            stop_container "$2"
            ;;
        --help)
            show_usage
            ;;
        *)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 