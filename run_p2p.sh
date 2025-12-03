#!/bin/bash

# Start 3 peers in P2P mode for local testing

echo "Starting P2P Distributed Chat System"
echo "===================================="
echo ""
echo "Starting 3 peers..."
echo "Press Ctrl+C to stop all peers"
echo ""

# Create log directory
mkdir -p data/p2p_logs

# Start peers in background
python -m src.peer_tui --id 1 --host 127.0.0.1 --port 6001 &
PID1=$!
sleep 1

python -m src.peer_tui --id 2 --host 127.0.0.1 --port 6002 --seed 1:127.0.0.1:6001 &
PID2=$!
sleep 1

python -m src.peer_tui --id 3 --host 127.0.0.1 --port 6003 --seed 1:127.0.0.1:6001 &
PID3=$!

echo "Peers started:"
echo "  Peer 1: PID $PID1"
echo "  Peer 2: PID $PID2"
echo "  Peer 3: PID $PID3"
echo ""
echo "Press Ctrl+C to stop all"

# Wait and cleanup on Ctrl+C
trap "echo 'Stopping peers...'; kill $PID1 $PID2 $PID3 2>/dev/null; exit" INT

wait
