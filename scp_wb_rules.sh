#!/bin/bash

# Default target directory on remote server
TARGET_DIR="/mnt/data/etc"

# Check if required parameters are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <remote_server> <username> <password>"
    echo "Example: $0 192.168.1.100 admin password123"
    exit 1
fi

# Assign command line parameters
REMOTE_SERVER=$1
USERNAME=$2
PASSWORD=$3

# Check if wb-rules directory exists
if [ ! -d "wb-rules" ]; then
    echo "Error: wb-rules directory not found in current directory"
    exit 1
fi

# Create a temporary file to store the password
TEMP_PASS_FILE=$(mktemp)
echo "$PASSWORD" > "$TEMP_PASS_FILE"

# Function to clean up temporary files
cleanup() {
    rm -f "$TEMP_PASS_FILE"
}

# Register cleanup function to run on script exit
trap cleanup EXIT

# Use sshpass to handle password authentication for scp
if ! command -v sshpass &> /dev/null; then
    echo "Error: sshpass is not installed. Please install it first."
    echo "On Ubuntu/Debian: sudo apt-get install sshpass"
    exit 1
fi

# Perform the SCP transfer
echo "Transferring wb-rules directory to $REMOTE_SERVER..."
sshpass -f "$TEMP_PASS_FILE" scp -r -o StrictHostKeyChecking=no wb-rules "$USERNAME@$REMOTE_SERVER:$TARGET_DIR"

# Check if the transfer was successful
if [ $? -eq 0 ]; then
    echo "Transfer completed successfully!"
else
    echo "Error: Transfer failed"
    exit 1
fi 