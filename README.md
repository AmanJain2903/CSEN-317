# Distributed Chat System - Peer-to-Peer

A fully decentralized peer-to-peer distributed chat application demonstrating key distributed systems concepts including total order broadcast, leader election, and failure detection.

## Features

- Fully Peer-to-Peer Architecture: Each peer is both client and node - completely decentralized
- Total Order Broadcast: Messages are delivered in the same order across all peers using sequence numbers assigned by a leader
- Leader Election: Bully algorithm for automatic leader election based on peer priority
- Failure Detection: Heartbeat-based monitoring with automatic failover
- Persistence: Append-only log files for crash recovery
- Catch-up Protocol: Peers can request missing messages when rejoining

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data/logs
```

## Running the System

### Start Peer-to-Peer Cluster

Start three peers in separate terminals:

```bash
# Terminal 1 - First peer (bootstrap)
python -m src.peer_tui --id 1 --host 127.0.0.1 --port 6001

# Terminal 2 - Second peer
python -m src.peer_tui --id 2 --host 127.0.0.1 --port 6002 --seed 1:127.0.0.1:6001

# Terminal 3 - Third peer
python -m src.peer_tui --id 3 --host 127.0.0.1 --port 6003 --seed 1:127.0.0.1:6001
```

### Using Quick Start Script

```bash
./run_p2p.sh
```

### Commands

Once a peer is running, you can use these commands:

- Type messages directly in the terminal
- `/status` - Show peer status, role, and leader
- `/quit` - Exit gracefully

### Example Usage

```bash
# Type messages directly in any peer terminal
peer_1> Hello from peer 1!
peer_2> Hi from peer 2!
peer_3> Peer 3 says hi!

# All peers will see messages in the same order with sequence numbers
```

## Testing

```bash
# Run all tests
make test

# Or use pytest directly
pytest tests/ -v

# Run specific test file
pytest tests/test_ordering.py -v
```

## Configuration

Peers are configured via command-line arguments:

```bash
python -m src.peer_tui \
  --id 1 \                    # Unique peer ID (higher = higher priority)
  --host 127.0.0.1 \          # Listen address
  --port 6001 \               # Listen port
  --seed 2:127.0.0.1:6002     # Bootstrap peer(s) (optional)
```

## Troubleshooting

**Peers won't connect?**
- Ensure first peer (bootstrap) is running before starting others
- Use `127.0.0.1` for local testing
- Check ports aren't already in use: `lsof -i :6001`

**Port in use?**
- Change ports: `--port 6011`, `--port 6012`, etc.
- Or kill existing process: `kill -9 <PID>`

**No leader elected?**
- Check logs for election messages
- Verify peer IDs are unique
- Ensure network connectivity between peers

## Project Structure

**Core Distributed System:**
- `common.py`: Data structures, message schemas, enums
- `transport.py`: Async TCP communication layer
- `membership.py`: Cluster membership management
- `failure.py`: Heartbeat-based failure detection
- `election.py`: Bully algorithm implementation
- `ordering.py`: Sequence number assignment and ordered delivery
- `storage.py`: Persistent message logs

**P2P Interface:**
- `peer.py`: ChatPeer class combining user interface + distributed node
- `peer_tui.py`: Terminal UI for peer-to-peer chat

## License

This project is for educational purposes as part of CSEN 317 - Distributed Systems course.
