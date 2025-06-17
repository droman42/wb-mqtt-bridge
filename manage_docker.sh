#!/bin/bash

# Wirenboard Multi-Container Docker Management Script
# Manages Docker containers with GitHub artifact integration and multi-container orchestration

set -euo pipefail

# Runtime Container Definitions (structured data)
declare -A CONTAINERS=()
declare -A DEPENDENCIES=()
declare -A CONTAINER_TYPES=()
declare -A CONTAINER_REPOS=()
declare -A CONTAINER_PORTS=()
declare -A CONTAINER_MEMORY=()
declare -A CONTAINER_CPUS=()
declare -A CONTAINER_RESOURCE_DIRS=()

# Configuration
DOCKER_NETWORK="wb-network"
ARTIFACTS_DIR="/mnt/sdcard/artifacts"
CONFIG_FILE="$HOME/docker_manager_config.json"
DEFAULT_LOG_LEVEL="DEBUG"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
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

info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Show usage information
show_usage() {
    cat << EOF
Wirenboard Multi-Container Docker Management

Usage: $0 <command> [arguments]

Commands:
    deploy <container|all|ui|backend>    Deploy container(s) from GitHub artifacts
    redeploy <container|all|ui|backend>  Full redeploy: stop, clean, download, install, start
    start <container|all>                Start container(s)
    stop <container|all>                 Stop container(s)  
    restart <container|all>              Restart container(s)
    status [container]                   Show container status and stats
    logs <container> [lines]             Show container logs
    cleanup                              Docker system cleanup
    network                              Manage Docker network
    config                               Create/edit configuration file

Configuration:
    Local config:  ./docker_manager_config.json  (takes precedence)
    Global config: $CONFIG_FILE
    If no config files exist, built-in defaults are used

Container Management:
    all                                  All defined containers
    ui                                   All UI containers
    backend                              All backend containers
    <container_name>                     Specific container

Available Containers:
$(printf "    %-20s %s\n" "Name" "Type:Repository")
$(for container in "${!CONTAINERS[@]}"; do
    local type="${CONTAINER_TYPES[$container]}"
    local repo="${CONTAINER_REPOS[$container]}"
    printf "    %-20s %s:%s\n" "$container" "$type" "$repo"
done)

Examples:
    $0 deploy all                        Deploy entire stack
    $0 deploy wb-mqtt-ui                 Deploy UI container
    $0 deploy backend                    Deploy all backend containers
    $0 redeploy wb-mqtt-bridge          Full redeploy with cleanup
    $0 start wb-mqtt-bridge             Start specific container
    $0 stop all                          Stop all containers
    $0 status                            Show all container status
    $0 logs wb-mqtt-ui 50               Show last 50 log lines
    $0 cleanup                           Clean Docker system

EOF
}

# Load configuration from files
load_configuration() {
    local local_config="./docker_manager_config.json"
    local global_config="$CONFIG_FILE"
    local config_loaded=false
    
    # Check for local config file first
    if [[ -f "$local_config" ]]; then
        log "Loading configuration from local file: $local_config"
        load_containers_from_config "$local_config"
        config_loaded=true
    elif [[ -f "$global_config" ]]; then
        log "Loading configuration from global file: $global_config"
        load_containers_from_config "$global_config"
        config_loaded=true
    fi
    
    # Fall back to defaults if no config found
    if [[ "$config_loaded" == "false" ]]; then
        log "No configuration file found, using built-in defaults"
        load_default_containers
    fi
    
    # Validate loaded configuration
    validate_container_configuration
}

# Load containers from JSON configuration file
load_containers_from_config() {
    local config_file="$1"
    
    # Clear existing containers
    CONTAINERS=()
    DEPENDENCIES=()
    CONTAINER_TYPES=()
    CONTAINER_REPOS=()
    CONTAINER_PORTS=()
    CONTAINER_MEMORY=()
    CONTAINER_CPUS=()
    CONTAINER_RESOURCE_DIRS=()
    
    # Check if config file has containers section
    if ! jq -e '.containers' "$config_file" &> /dev/null; then
        warning "No containers section found in $config_file, using defaults"
        load_default_containers
        return
    fi
    
    # Load containers
    while IFS= read -r container_name; do
        local type repo port memory cpu resource_dir
        
        type=$(jq -r ".containers[\"$container_name\"].type" "$config_file")
        repo=$(jq -r ".containers[\"$container_name\"].repo" "$config_file")
        port=$(jq -r ".containers[\"$container_name\"].port" "$config_file")
        memory=$(jq -r ".containers[\"$container_name\"].memory" "$config_file")
        cpu=$(jq -r ".containers[\"$container_name\"].cpu" "$config_file")
        
        # Store in structured arrays
        CONTAINERS["$container_name"]="1"  # Just mark as existing
        CONTAINER_TYPES["$container_name"]="$type"
        CONTAINER_REPOS["$container_name"]="$repo"
        CONTAINER_PORTS["$container_name"]="$port"
        CONTAINER_MEMORY["$container_name"]="$memory"
        CONTAINER_CPUS["$container_name"]="$cpu"
        
        # Add resource_dir for backend containers if specified
        if [[ "$type" == "backend" ]]; then
            resource_dir=$(jq -r ".containers[\"$container_name\"].resource_dir // \"\"" "$config_file")
            if [[ -n "$resource_dir" && "$resource_dir" != "null" ]]; then
                CONTAINER_RESOURCE_DIRS["$container_name"]="$resource_dir"
            fi
        fi
        
    done < <(jq -r '.containers | keys[]' "$config_file")
    
    # Load dependencies if they exist in config
    if jq -e '.dependencies' "$config_file" &> /dev/null; then
        while IFS= read -r container_name; do
            local deps
            deps=$(jq -r ".dependencies[\"$container_name\"]" "$config_file")
            if [[ "$deps" != "null" ]]; then
                DEPENDENCIES["$container_name"]="$deps"
            fi
        done < <(jq -r '.dependencies | keys[]' "$config_file" 2>/dev/null || true)
    fi
    
    success "Loaded ${#CONTAINERS[@]} containers from configuration"
}

# Load default container configuration
load_default_containers() {
    # Clear existing containers
    CONTAINERS=()
    DEPENDENCIES=()
    CONTAINER_TYPES=()
    CONTAINER_REPOS=()
    CONTAINER_PORTS=()
    CONTAINER_MEMORY=()
    CONTAINER_CPUS=()
    CONTAINER_RESOURCE_DIRS=()
    
    # Define default containers
    CONTAINERS["wb-mqtt-bridge"]="1"
    CONTAINER_TYPES["wb-mqtt-bridge"]="backend"
    CONTAINER_REPOS["wb-mqtt-bridge"]="droman42/wb-mqtt-bridge"
    CONTAINER_PORTS["wb-mqtt-bridge"]="8000:8000"
    CONTAINER_MEMORY["wb-mqtt-bridge"]="256M"
    CONTAINER_CPUS["wb-mqtt-bridge"]="0.5"
    CONTAINER_RESOURCE_DIRS["wb-mqtt-bridge"]="/opt/wb-bridge"
    
    CONTAINERS["wb-mqtt-ui"]="1"
    CONTAINER_TYPES["wb-mqtt-ui"]="ui"
    CONTAINER_REPOS["wb-mqtt-ui"]="droman42/wb-mqtt-ui"
    CONTAINER_PORTS["wb-mqtt-ui"]="3000:3000"
    CONTAINER_MEMORY["wb-mqtt-ui"]="128M"
    CONTAINER_CPUS["wb-mqtt-ui"]="0.3"
    
    CONTAINERS["wb-http-api"]="1"
    CONTAINER_TYPES["wb-http-api"]="backend"
    CONTAINER_REPOS["wb-http-api"]="droman42/wb-http-api"
    CONTAINER_PORTS["wb-http-api"]="8080:8080"
    CONTAINER_MEMORY["wb-http-api"]="512M"
    CONTAINER_CPUS["wb-http-api"]="1.0"
    CONTAINER_RESOURCE_DIRS["wb-http-api"]="/opt/wb-api"
    
    # Define default dependencies
    DEPENDENCIES["wb-mqtt-ui"]="wb-mqtt-bridge"
    DEPENDENCIES["wb-http-api"]="wb-mqtt-bridge"
    
    log "Loaded ${#CONTAINERS[@]} default containers"
}

# Validate container configuration
validate_container_configuration() {
    if [[ ${#CONTAINERS[@]} -eq 0 ]]; then
        error "No containers defined in configuration"
    fi
    
    # Validate each container configuration
    for container in "${!CONTAINERS[@]}"; do
        # Check required fields exist
        if [[ -z "${CONTAINER_TYPES[$container]:-}" ]]; then
            error "Missing type for container '$container'"
        fi
        
        if [[ -z "${CONTAINER_REPOS[$container]:-}" ]]; then
            error "Missing repo for container '$container'"
        fi
        
        if [[ -z "${CONTAINER_PORTS[$container]:-}" ]]; then
            error "Missing port for container '$container'"
        fi
        
        if [[ -z "${CONTAINER_MEMORY[$container]:-}" ]]; then
            error "Missing memory for container '$container'"
        fi
        
        if [[ -z "${CONTAINER_CPUS[$container]:-}" ]]; then
            error "Missing cpu for container '$container'"
        fi
        
        # Validate container type
        local type="${CONTAINER_TYPES[$container]}"
        if [[ "$type" != "backend" && "$type" != "ui" ]]; then
            error "Invalid container type '$type' for container '$container' (must be 'backend' or 'ui')"
        fi
        
        # Validate backend containers have resource_dir
        if [[ "$type" == "backend" && -z "${CONTAINER_RESOURCE_DIRS[$container]:-}" ]]; then
            error "Backend container '$container' missing resource_dir"
        fi
    done
    
    success "Container configuration validated"
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    local deps=("docker" "curl" "tar" "jq")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            error "Required dependency '$dep' is not installed"
        fi
    done
    
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running or not accessible"
    fi
    
    success "All dependencies available"
}

# Get container configuration
get_container_config() {
    local container_name="$1"
    local field="$2"
    
    if [[ -z "${CONTAINERS[$container_name]:-}" ]]; then
        error "Unknown container: $container_name"
    fi
    
    case "$field" in
        "type") echo "${CONTAINER_TYPES[$container_name]}" ;;
        "repo") echo "${CONTAINER_REPOS[$container_name]}" ;;
        "port") echo "${CONTAINER_PORTS[$container_name]}" ;;
        "memory") echo "${CONTAINER_MEMORY[$container_name]}" ;;
        "cpu") echo "${CONTAINER_CPUS[$container_name]}" ;;
        "resource_dir") echo "${CONTAINER_RESOURCE_DIRS[$container_name]:-}" ;;
        "image") echo "$container_name:latest" ;;
        *) error "Unknown config field: $field" ;;
    esac
}

# Get containers by type
get_containers_by_type() {
    local target_type="$1"
    local containers=()
    
    for container in "${!CONTAINERS[@]}"; do
        local type=$(get_container_config "$container" "type")
        if [[ "$type" == "$target_type" ]]; then
            containers+=("$container")
        fi
    done
    
    printf '%s\n' "${containers[@]}"
}

# Resolve container list from argument
resolve_containers() {
    local target="$1"
    
    case "$target" in
        "all")
            printf '%s\n' "${!CONTAINERS[@]}"
            ;;
        "ui")
            get_containers_by_type "ui"
            ;;
        "backend")
            get_containers_by_type "backend"
            ;;
        *)
            if [[ -n "${CONTAINERS[$target]:-}" ]]; then
                echo "$target"
            else
                error "Unknown container or group: $target"
            fi
            ;;
    esac
}

# Ensure Docker network exists
ensure_docker_network() {
    if ! docker network ls --format '{{.Name}}' | grep -q "^${DOCKER_NETWORK}$"; then
        log "Creating Docker network: $DOCKER_NETWORK"
        docker network create "$DOCKER_NETWORK"
        success "Docker network '$DOCKER_NETWORK' created"
    else
        log "Docker network '$DOCKER_NETWORK' already exists"
    fi
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
        if jq -e '.github.username and .github.pat' "$local_config" &> /dev/null; then
            username=$(jq -r '.github.username' "$local_config")
            pat=$(jq -r '.github.pat' "$local_config")
            log "Using credentials from local config: $local_config"
        fi
    elif [[ -f "$CONFIG_FILE" ]]; then
        if jq -e '.github.username and .github.pat' "$CONFIG_FILE" &> /dev/null; then
            username=$(jq -r '.github.username' "$CONFIG_FILE")
            pat=$(jq -r '.github.pat' "$CONFIG_FILE")
            log "Using credentials from global config: $CONFIG_FILE"
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
        
        # Save credentials to global config
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
        error "Invalid GitHub credentials"
    fi
    
    success "GitHub credentials validated for user: $response"
    
    export GITHUB_USERNAME="$username"
    export GITHUB_PAT="$pat"
}

# Download GitHub artifacts for a container
download_artifacts() {
    local container_name="$1"
    local repo=$(get_container_config "$container_name" "repo")
    local type=$(get_container_config "$container_name" "type")
    
    log "Downloading artifacts for $container_name from $repo..."
    
    mkdir -p "$ARTIFACTS_DIR"
    cd "$ARTIFACTS_DIR"
    
    # Get latest successful workflow run
    log "Fetching latest workflow run for $repo..."
    local latest_run
    latest_run=$(curl -s -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${repo}/actions/runs?status=success&per_page=1" \
        | jq -r '.workflow_runs[0].id // empty')
    
    if [[ -z "$latest_run" ]]; then
        error "No successful workflow runs found for $repo"
    fi
    
    log "Latest successful run ID: $latest_run"
    
    # Get artifacts for this run
    local artifacts_response
    artifacts_response=$(curl -s -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${repo}/actions/runs/${latest_run}/artifacts")
    
    # Download Docker image artifact
    log "Downloading Docker image artifact..."
    local image_artifact_id
    image_artifact_id=$(echo "$artifacts_response" | jq -r ".artifacts[] | select(.name==\"${container_name}-image\") | .id")
    
    if [[ -z "$image_artifact_id" ]]; then
        error "${container_name}-image artifact not found"
    fi
    
    curl -L -u "$GITHUB_USERNAME:$GITHUB_PAT" \
        "https://api.github.com/repos/${repo}/actions/artifacts/${image_artifact_id}/zip" \
        -o "${container_name}-image.zip"
    
    # Download config artifact for backend containers
    if [[ "$type" == "backend" ]]; then
        log "Downloading config artifact..."
        local config_artifact_id
        config_artifact_id=$(echo "$artifacts_response" | jq -r ".artifacts[] | select(.name==\"${container_name}-config\") | .id")
        
        if [[ -z "$config_artifact_id" ]]; then
            error "${container_name}-config artifact not found"
        fi
        
        curl -L -u "$GITHUB_USERNAME:$GITHUB_PAT" \
            "https://api.github.com/repos/${repo}/actions/artifacts/${config_artifact_id}/zip" \
            -o "${container_name}-config.zip"
    fi
    
    success "Artifacts downloaded for $container_name"
    cd - > /dev/null
}

# Install artifacts for backend container
install_backend_artifacts() {
    local container_name="$1"
    local resource_dir=$(get_container_config "$container_name" "resource_dir")
    
    log "Installing backend artifacts for $container_name to $resource_dir..."
    
    # Create resource directory
    if [[ ! -d "$resource_dir" ]]; then
        log "Creating resource directory: $resource_dir"
        mkdir -p "$resource_dir"
    fi
    
    cd "$ARTIFACTS_DIR"
    
    # Extract and load Docker image
    if [[ -f "${container_name}-image.zip" ]]; then
        unzip -o "${container_name}-image.zip"
        if [[ -f "${container_name}.tar.gz" ]]; then
            log "Loading Docker image..."
            docker load -i "${container_name}.tar.gz"
            success "Docker image loaded"
        fi
    fi
    
    # Extract config
    if [[ -f "${container_name}-config.zip" ]]; then
        unzip -o "${container_name}-config.zip"
        if [[ -f "${container_name}-config.tar.gz" ]]; then
            log "Extracting configuration..."
            tar -xzf "${container_name}-config.tar.gz" -C "$resource_dir"
            chmod -R 755 "$resource_dir"
            success "Configuration extracted"
        fi
    fi
    
    cd - > /dev/null
}

# Install artifacts for UI container
install_ui_artifacts() {
    local container_name="$1"
    
    log "Installing UI artifacts for $container_name..."
    
    cd "$ARTIFACTS_DIR"
    
    # Extract and load Docker image
    if [[ -f "${container_name}-image.zip" ]]; then
        unzip -o "${container_name}-image.zip"
        if [[ -f "${container_name}.tar.gz" ]]; then
            log "Loading Docker image..."
            docker load -i "${container_name}.tar.gz"
            success "Docker image loaded"
        fi
    else
        error "Image artifact not found for $container_name"
    fi
    
    cd - > /dev/null
}

# Deploy a container
deploy_container() {
    local container_name="$1"
    local type=$(get_container_config "$container_name" "type")
    
    log "Deploying $type container: $container_name"
    
    # Handle credentials
    handle_credentials
    
    # Download artifacts
    download_artifacts "$container_name"
    
    # Install artifacts based on type
    case "$type" in
        "backend")
            install_backend_artifacts "$container_name"
            ;;
        "ui")
            install_ui_artifacts "$container_name"
            ;;
        *)
            error "Unknown container type: $type"
            ;;
    esac
    
    # Start the container
    start_container "$container_name"
    
    success "Container $container_name deployed successfully"
}

# Full redeploy container (like original --redeploy)
redeploy_container() {
    local container_name="$1"
    local type=$(get_container_config "$container_name" "type")
    
    log "Starting full redeploy of $type container: $container_name"
    
    # Step 1: Stop container (if running)
    log "Step 1/4: Stopping container '$container_name'..."
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        stop_container "$container_name"
    else
        log "Container '$container_name' is not running, skipping stop step"
    fi
    
    # Step 2: Docker cleanup
    log "Step 2/4: Performing Docker cleanup..."
    docker_cleanup
    
    # Step 3: Deploy container (download, install, start)
    log "Step 3/4: Deploying container '$container_name'..."
    deploy_container "$container_name"
    
    # Step 4: Verification
    log "Step 4/4: Verifying redeploy..."
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        success "Full redeploy of '$container_name' completed successfully!"
        local port=$(get_container_config "$container_name" "port")
        info "Container accessible at: http://localhost:${port%:*}"
    else
        error "Redeploy verification failed - container is not running"
    fi
}

# Start a container
start_container() {
    local container_name="$1"
    local type=$(get_container_config "$container_name" "type")
    local port=$(get_container_config "$container_name" "port")
    local memory=$(get_container_config "$container_name" "memory")
    local cpu=$(get_container_config "$container_name" "cpu")
    local image=$(get_container_config "$container_name" "image")
    
    log "Starting $type container: $container_name"
    
    # Ensure network exists
    ensure_docker_network
    
    # Stop and remove existing container
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        log "Stopping existing container..."
        docker stop "$container_name" 2>/dev/null || true
        docker rm "$container_name" 2>/dev/null || true
    fi
    
    # Build docker run command
    local docker_cmd=(
        docker run -d
        --name "$container_name"
        --restart unless-stopped
        --network "$DOCKER_NETWORK"
        -p "$port"
        --memory="$memory"
        --cpus="$cpu"
        -e "TZ=$(cat /etc/timezone 2>/dev/null || echo 'UTC')"
    )
    
    # Add type-specific volumes and environment
    case "$type" in
        "backend")
            local resource_dir=$(get_container_config "$container_name" "resource_dir")
            docker_cmd+=(
                -v "$resource_dir/config:/app/config:ro"
                -v "$resource_dir/logs:/app/logs"
                -v "$resource_dir/data:/app/data"
                -v "/etc/localtime:/etc/localtime:ro"
                -v "/etc/timezone:/etc/timezone:ro"
            )
            if [[ -n "${LOG_LEVEL:-$DEFAULT_LOG_LEVEL}" ]]; then
                docker_cmd+=(-e "OVERRIDE_LOG_LEVEL=${LOG_LEVEL:-$DEFAULT_LOG_LEVEL}")
            fi
            ;;
        "ui")
            # UI containers typically don't need persistent volumes
            docker_cmd+=(-v "/etc/localtime:/etc/localtime:ro")
            ;;
    esac
    
    docker_cmd+=("$image")
    
    # Start container
    log "Starting with: ${docker_cmd[*]}"
    "${docker_cmd[@]}"
    
    # Verify container started
    sleep 2
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        success "Container '$container_name' started successfully"
        info "Access at: http://localhost:${port%:*}"
    else
        error "Failed to start container '$container_name'"
    fi
}

# Stop a container
stop_container() {
    local container_name="$1"
    
    log "Stopping container: $container_name"
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        warning "Container '$container_name' is not running"
        return 0
    fi
    
    if docker stop "$container_name"; then
        success "Container '$container_name' stopped"
    else
        error "Failed to stop container '$container_name'"
    fi
}

# Restart a container  
restart_container() {
    local container_name="$1"
    
    log "Restarting container: $container_name"
    stop_container "$container_name"
    start_container "$container_name"
}

# Show container status
show_status() {
    local target="${1:-all}"
    
    log "Container Status Report"
    echo
    
    # Resolve containers to show
    local containers
    mapfile -t containers < <(resolve_containers "$target")
    
    if [[ ${#containers[@]} -eq 0 ]]; then
        warning "No containers found for target: $target"
        return
    fi
    
    # Show running containers
    info "Running Containers:"
    local running_found=false
    for container in "${containers[@]}"; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            running_found=true
            local port=$(get_container_config "$container" "port")
            local type=$(get_container_config "$container" "type")
            printf "  %-20s %-10s http://localhost:%s\n" "$container" "($type)" "${port%:*}"
        fi
    done
    
    if [[ "$running_found" == "false" ]]; then
        echo "  No containers running"
    fi
    
    echo
    info "Container Details:"
    docker ps -a --filter "$(printf "name=%s " "${containers[@]}")" \
        --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.CreatedAt}}" 2>/dev/null || true
    
    echo
    info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
        $(printf "%s " "${containers[@]}") 2>/dev/null || echo "  No running containers"
    
    echo
    info "Network Status:"
    if docker network ls --format '{{.Name}}' | grep -q "^${DOCKER_NETWORK}$"; then
        echo "  Network '$DOCKER_NETWORK': ✓ Active"
        docker network inspect "$DOCKER_NETWORK" --format "  Connected containers: {{len .Containers}}" 2>/dev/null || true
    else
        echo "  Network '$DOCKER_NETWORK': ✗ Not found"
    fi
}

# Show container logs
show_logs() {
    local container_name="$1"
    local lines="${2:-100}"
    
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        error "Container '$container_name' does not exist"
    fi
    
    log "Showing last $lines lines for container: $container_name"
    docker logs --tail "$lines" --timestamps "$container_name"
}

# Docker cleanup
docker_cleanup() {
    log "Performing Docker cleanup..."
    
    log "Cleaning up Docker system..."
    docker system prune -af
    
    log "Cleaning up Docker volumes..."
    docker volume prune -f
    
    log "Cleaning up Docker networks..."
    docker network prune -f
    
    success "Docker cleanup completed"
    
    log "Docker system status:"
    docker system df
}

# Manage Docker network
manage_network() {
    log "Docker Network Management"
    
    if docker network ls --format '{{.Name}}' | grep -q "^${DOCKER_NETWORK}$"; then
        info "Network '$DOCKER_NETWORK' exists"
        docker network inspect "$DOCKER_NETWORK" --format "{{json .}}" | jq .
    else
        log "Creating network '$DOCKER_NETWORK'..."
        ensure_docker_network
    fi
}

# Create configuration file
create_config() {
    local config_file="./docker_manager_config.json"
    
    log "Creating configuration file: $config_file"
    
    if [[ -f "$config_file" ]]; then
        warning "Configuration file already exists"
        echo -n "Overwrite? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log "Configuration creation cancelled"
            return 0
        fi
    fi
    
         cat > "$config_file" << EOF
{
    "github": {
        "username": "your_github_username",
        "pat": "your_personal_access_token"
    },
    "docker": {
        "network": "$DOCKER_NETWORK",
        "artifacts_dir": "$ARTIFACTS_DIR"
    },
    "containers": {
$(for container in "${!CONTAINERS[@]}"; do
    local type="${CONTAINER_TYPES[$container]}"
    local repo="${CONTAINER_REPOS[$container]}"
    local port="${CONTAINER_PORTS[$container]}"
    local memory="${CONTAINER_MEMORY[$container]}"
    local cpu="${CONTAINER_CPUS[$container]}"
    echo "        \"$container\": {"
    echo "            \"type\": \"$type\","
    echo "            \"repo\": \"$repo\","
    echo "            \"port\": \"$port\","
    echo "            \"memory\": \"$memory\","
    echo "            \"cpu\": \"$cpu\""
    if [[ "$type" == "backend" ]]; then
        local resource_dir="${CONTAINER_RESOURCE_DIRS[$container]:-}"
        if [[ -n "$resource_dir" ]]; then
            echo "            ,\"resource_dir\": \"$resource_dir\""
        fi
    fi
    echo "        },"
done | sed '$ s/,$//')
    },
    "dependencies": {
$(for container in "${!DEPENDENCIES[@]}"; do
    echo "        \"$container\": \"${DEPENDENCIES[$container]}\","
done | sed '$ s/,$//')
    }
}
EOF
    
    chmod 600 "$config_file"
    success "Configuration created: $config_file"
    
    if [[ -f "$config_file" ]]; then
        log "Current configuration:"
        cat "$config_file" | jq '.'
    fi
}

# Resolve dependencies and deploy in order
deploy_with_dependencies() {
    local containers=("$@")
    local deployed=()
    local to_deploy=("${containers[@]}")
    
    log "Resolving deployment order for containers: ${containers[*]}"
    
    while [[ ${#to_deploy[@]} -gt 0 ]]; do
        local progress=false
        local remaining=()
        
        for container in "${to_deploy[@]}"; do
            local deps="${DEPENDENCIES[$container]:-}"
            local can_deploy=true
            
            # Check if all dependencies are deployed
            for dep in $deps; do
                if [[ ! " ${deployed[*]} " =~ " $dep " ]]; then
                    can_deploy=false
                    break
                fi
            done
            
            if [[ "$can_deploy" == "true" ]]; then
                log "Deploying $container (dependencies satisfied)"
                deploy_container "$container"
                deployed+=("$container")
                progress=true
            else
                remaining+=("$container")
            fi
        done
        
        to_deploy=("${remaining[@]}")
        
        if [[ "$progress" == "false" && ${#to_deploy[@]} -gt 0 ]]; then
            error "Circular dependency or missing containers: ${to_deploy[*]}"
        fi
    done
    
    success "All containers deployed in dependency order"
}

# Resolve dependencies and redeploy in order
redeploy_with_dependencies() {
    local containers=("$@")
    local deployed=()
    local to_deploy=("${containers[@]}")
    
    log "Resolving redeploy order for containers: ${containers[*]}"
    
    while [[ ${#to_deploy[@]} -gt 0 ]]; do
        local progress=false
        local remaining=()
        
        for container in "${to_deploy[@]}"; do
            local deps="${DEPENDENCIES[$container]:-}"
            local can_deploy=true
            
            # Check if all dependencies are deployed
            for dep in $deps; do
                if [[ ! " ${deployed[*]} " =~ " $dep " ]]; then
                    can_deploy=false
                    break
                fi
            done
            
            if [[ "$can_deploy" == "true" ]]; then
                log "Redeploying $container (dependencies satisfied)"
                redeploy_container "$container"
                deployed+=("$container")
                progress=true
            else
                remaining+=("$container")
            fi
        done
        
        to_deploy=("${remaining[@]}")
        
        if [[ "$progress" == "false" && ${#to_deploy[@]} -gt 0 ]]; then
            error "Circular dependency or missing containers: ${to_deploy[*]}"
        fi
    done
    
    success "All containers redeployed in dependency order"
}

# Main function
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi
    
    # Check dependencies
    check_dependencies
    
    # Load configuration
    load_configuration
    
    local command="$1"
    shift
    
    case "$command" in
        "deploy")
            local target="${1:-}"
            if [[ -z "$target" ]]; then
                error "Usage: $0 deploy <container|all|ui|backend>"
            fi
            
            local containers
            mapfile -t containers < <(resolve_containers "$target")
            
            if [[ ${#containers[@]} -eq 1 ]]; then
                deploy_container "${containers[0]}"
            else
                deploy_with_dependencies "${containers[@]}"
            fi
            ;;
        "redeploy")
            local target="${1:-}"
            if [[ -z "$target" ]]; then
                error "Usage: $0 redeploy <container|all|ui|backend>"
            fi
            
            local containers
            mapfile -t containers < <(resolve_containers "$target")
            
            if [[ ${#containers[@]} -eq 1 ]]; then
                redeploy_container "${containers[0]}"
            else
                redeploy_with_dependencies "${containers[@]}"
            fi
            ;;
        "start")
            local target="${1:-}"
            if [[ -z "$target" ]]; then
                error "Usage: $0 start <container|all>"
            fi
            
            local containers
            mapfile -t containers < <(resolve_containers "$target")
            
            for container in "${containers[@]}"; do
                start_container "$container"
            done
            ;;
        "stop")
            local target="${1:-}"
            if [[ -z "$target" ]]; then
                error "Usage: $0 stop <container|all>"
            fi
            
            local containers
            mapfile -t containers < <(resolve_containers "$target")
            
            for container in "${containers[@]}"; do
                stop_container "$container"
            done
            ;;
        "restart")
            local target="${1:-}"
            if [[ -z "$target" ]]; then
                error "Usage: $0 restart <container|all>"
            fi
            
            local containers
            mapfile -t containers < <(resolve_containers "$target")
            
            for container in "${containers[@]}"; do
                restart_container "$container"
            done
            ;;
        "status")
            local target="${1:-all}"
            show_status "$target"
            ;;
        "logs")
            local container="${1:-}"
            local lines="${2:-100}"
            if [[ -z "$container" ]]; then
                error "Usage: $0 logs <container> [lines]"
            fi
            show_logs "$container" "$lines"
            ;;
        "cleanup")
            docker_cleanup
            ;;
        "network")
            manage_network
            ;;
        "config")
            create_config
            ;;
        *)
            error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 