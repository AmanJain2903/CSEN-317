#!/bin/bash
# Script to run all three nodes locally for testing

set -e

echo "Starting Distributed Chat System..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Create data directory
mkdir -p data/logs

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping all nodes..."
    kill $NODE1_PID $NODE2_PID $NODE3_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

# Start nodes
echo "Starting Node 1..."
python -m src.node --config configs/node1_local.yml &
NODE1_PID=$!

sleep 1

echo "Starting Node 2..."
python -m src.node --config configs/node2_local.yml &
NODE2_PID=$!

sleep 1

echo "Starting Node 3..."
python -m src.node --config configs/node3_local.yml &
NODE3_PID=$!

echo ""
echo "All nodes started!"
echo "  Node 1: PID $NODE1_PID (port 5001)"
echo "  Node 2: PID $NODE2_PID (port 5002)"
echo "  Node 3: PID $NODE3_PID (port 5003)"
echo ""
echo "Connect a client with:"
echo "  python -m src.client_tui --host 127.0.0.1 --port 5001"
echo ""
echo "Press Ctrl+C to stop all nodes"
echo ""

# Wait for all nodes
wait

