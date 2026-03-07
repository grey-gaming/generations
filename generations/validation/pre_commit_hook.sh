#!/bin/bash

COMMIT_MSG_FILE="$1"
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

if ! echo "$COMMIT_MSG" | grep -qE 'Block-[0-9]+'; then
    echo "ERROR: Commit message must contain a 'Block-N' tag (e.g., Block-1, Block-2)"
    echo "Commit message: $COMMIT_MSG"
    exit 1
fi

exit 0
