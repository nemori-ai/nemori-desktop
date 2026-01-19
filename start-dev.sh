#!/bin/bash

# Nemori Development Start Script
# The Electron app manages its own backend, so we only need to start the frontend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Nemori Development Environment..."

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is required but not found."
    exit 1
fi

# Start frontend (Electron will automatically start the backend)
echo "Starting Electron frontend..."
cd "$SCRIPT_DIR/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo ""
echo "========================================"
echo "  Nemori Development Environment"
echo "========================================"
echo "  Backend is managed by Electron"
echo "========================================"
echo ""

npm run dev
