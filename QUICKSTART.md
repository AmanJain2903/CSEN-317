# Quick Start Guide - P2P Mode

Get the P2P Distributed Chat System running in 5 minutes.

## Peer-to-Peer Setup

Each peer is a complete node that participates in the distributed system.

```bash
# 1. Install dependencies
pip install -r requirements.txt
mkdir -p data/logs

# 2. Start three peers (in separate terminals)
# Terminal 1 - Peer 1 (bootstrap)
python -m src.peer_tui --id 1 --host 127.0.0.1 --port 6001

# Terminal 2 - Peer 2 (joins via peer 1)
python -m src.peer_tui --id 2 --host 127.0.0.1 --port 6002 --seed 1:127.0.0.1:6001

# Terminal 3 - Peer 3 (joins via peer 1)
python -m src.peer_tui --id 3 --host 127.0.0.1 --port 6003 --seed 1:127.0.0.1:6001

# 3. Type messages directly in any peer terminal!
peer_1> Hello from peer 1!
peer_2> Message from peer 2!
peer_3> Peer 3 says hi!

# 4. Test leader failure
# Kill peer with highest ID (leader)
# Ctrl+C in Terminal 3
# Watch remaining peers elect new leader
# Continue sending messages from peer 1 or 2

# 5. Commands within peer
/status   # Show peer status, role, leader
/quit     # Exit gracefully
```

## Using Quick Start Script

```bash
# Automated startup script
./run_p2p.sh
```

## Using Makefile

```bash
# Run tests
make test

# Clean logs
make clean
```

## What to Expect

- Each peer has a prompt: `peer_1>`, `peer_2>`, etc.
- Type messages directly (no separate client needed)
- All peers see messages with sequence numbers
- Check `/status` to see role (LEADER/FOLLOWER)
- Peer 3 typically becomes leader (highest ID)

## Test Scenarios

### Test 1: Basic Messaging
```bash
# Terminal 1
python -m src.peer_tui --id 1 --host 127.0.0.1 --port 6001
peer_1> First message

# Terminal 2  
python -m src.peer_tui --id 2 --host 127.0.0.1 --port 6002 --seed 1:127.0.0.1:6001
peer_2> Second message

# Both peers show messages in same order
```

### Test 2: Leader Failure (P2P)
```bash
# Start 3 peers (peer 3 becomes leader)
# Send messages from all peers
# Ctrl+C on peer 3 terminal
# Watch peer 2 become leader
# Continue messaging from peers 1 and 2
```

### Test 3: Scalability (P2P)
```bash
# Run automated test
python ScaleTestP2P.py

# Or manual with many peers
# Start 10 peers connecting to peer 1
for i in {2..10}; do
  python -m src.peer_tui --id $i --host 127.0.0.1 --port 600$i --seed 1:127.0.0.1:6001 &
done
```

## Troubleshooting

**Peers won't connect?**
- Ensure first peer (bootstrap) is running before starting others
- Use `127.0.0.1` for local testing
- Check ports aren't already in use: `lsof -i :6001`

**No leader elected?**
- Check logs for election messages
- Verify peer IDs are unique
- Ensure network connectivity between peers

**Port in use?**
- Change ports: `--port 6011`, `--port 6012`, etc.
- Or kill existing process: `kill -9 <PID>`

**Need help?**
- Check full `README.md` for detailed docs
- View `P2P_README.md` for P2P-specific info
- Run tests: `pytest tests/ -v`
- Logs are very informative!

## Next Steps

- Read `P2P_README.md` for P2P architecture details
- Read `README.md` for client-server mode
- Try killing/restarting peers
- Run the test suite: `pytest tests/ -v`
- Test with more peers (10, 20, 50...)
- Explore the code in `src/`

Enjoy exploring distributed systems!

