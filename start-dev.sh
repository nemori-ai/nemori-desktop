#!/bin/bash

# Nemori Development Start Script
# This script starts both backend and frontend for development

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Nemori Development Environment..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is required but not found."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

# Start backend
echo "Starting Python backend..."
cd "$SCRIPT_DIR/backend"
python3 main.py &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 3

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "Error: Backend failed to start."
    exit 1
fi

echo "Backend started (PID: $BACKEND_PID)"

# Start frontend
echo "Starting Electron frontend..."
cd "$SCRIPT_DIR/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  Nemori Development Environment"
echo "========================================"
echo "  Backend:  http://127.0.0.1:21978"
echo "  API Docs: http://127.0.0.1:21978/docs"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
