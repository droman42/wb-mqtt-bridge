#!/bin/bash

# Deploy the WB-MSW v3 IR ROM tools (ir_common / ir_backup / ir_restore / ir_verify) to a Wiren
# Board controller. These are standalone operational tools -- NOT wb-rules engine scripts -- so
# they get their own deploy path, separate from scp_wb_rules.sh.
#
# Target is /tmp/ir-tools (ephemeral: wiped on reboot, re-deploy each session).
#
# Usage: scp_ir_tools.sh <remote_server> <username> <password> [push|pull]
#   push (default): copy the tools + any local ir_backup_*.csv to /tmp/ir-tools on the controller
#   pull          : copy ir_backup_*.csv FROM /tmp/ir-tools back into wb-rules/ (version-control
#                   the safety-net backups a backup run just produced)
# Example:
#   ./scp_ir_tools.sh 192.168.110.250 root password          # deploy tools
#   ./scp_ir_tools.sh 192.168.110.250 root password pull     # retrieve the produced CSVs

TARGET_DIR="/tmp/ir-tools"
TOOLS="ir.py ir_common.py ir_backup.py ir_restore.py ir_verify.py"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <remote_server> <username> <password> [push|pull]"
    echo "Example: $0 192.168.110.250 root password"
    exit 1
fi

REMOTE_SERVER=$1
USERNAME=$2
PASSWORD=$3
MODE=${4:-push}

if [ "$MODE" != "push" ] && [ "$MODE" != "pull" ]; then
    echo "Error: mode must be 'push' or 'pull' (got '$MODE')"
    exit 1
fi

# This script lives in wb-rules/; operate on the files alongside it regardless of the caller's CWD.
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

if ! command -v sshpass &> /dev/null; then
    echo "Error: sshpass is not installed. Please install it first."
    echo "On Ubuntu/Debian: sudo apt-get install sshpass"
    exit 1
fi

# Store the password in a temp file so it never appears in the process list / shell history.
TEMP_PASS_FILE=$(mktemp)
echo "$PASSWORD" > "$TEMP_PASS_FILE"
cleanup() { rm -f "$TEMP_PASS_FILE"; }
trap cleanup EXIT

SSH="sshpass -f $TEMP_PASS_FILE ssh -o StrictHostKeyChecking=no"
SCP="sshpass -f $TEMP_PASS_FILE scp -o StrictHostKeyChecking=no"

if [ "$MODE" = "pull" ]; then
    echo "Pulling ir_backup_*.csv from $REMOTE_SERVER:$TARGET_DIR ..."
    if $SCP "$USERNAME@$REMOTE_SERVER:$TARGET_DIR/ir_backup_*.csv" .; then
        echo "Pull completed successfully!"
    else
        echo "Error: pull failed (no CSVs there yet?)"
        exit 1
    fi
    exit 0
fi

# push
echo "Deploying IR tools to $REMOTE_SERVER:$TARGET_DIR ..."
$SSH "$USERNAME@$REMOTE_SERVER" "mkdir -p $TARGET_DIR" || { echo "Error: could not create $TARGET_DIR"; exit 1; }

# Tools (must exist). CSVs are optional -- only present after a local backup/pull.
CSVS=$(ls ir_backup_*.csv 2>/dev/null)
if $SCP $TOOLS $CSVS "$USERNAME@$REMOTE_SERVER:$TARGET_DIR/"; then
    echo "Deploy completed successfully -> $TARGET_DIR"
    echo "Run on the controller, e.g.:"
    echo "  sudo python3 $TARGET_DIR/ir.py backup wb-msw-v3_207 --port /dev/ttyRS485-2"
    echo "  sudo python3 $TARGET_DIR/ir.py verify ir_backup_wb-msw-v3_207.csv --only-rom 65-70"
else
    echo "Error: deploy failed"
    exit 1
fi
