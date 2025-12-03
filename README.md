# Distributed Chat System - Peer-to-Peer

A fully decentralized peer-to-peer distributed chat application demonstrating key distributed systems concepts including total order broadcast, leader election, and failure detection.

## Project Overview

This project implements a **fully peer-to-peer distributed chat system** where all peers are equal participants - each peer is both a user interface and a complete distributed system node. Peers form a cluster, maintain total message ordering through a sequencer-based approach, handle leader failures through the Bully algorithm, and provide eventual consistency across all nodes.

### Key Features

- **Fully Peer-to-Peer Architecture**: Each peer is both client and node - completely decentralized
- **Total Order Broadcast**: Messages are delivered in the same order across all peers using sequence numbers assigned by a leader
- **Leader Election**: Bully algorithm for automatic leader election based on peer priority with election cancellation
- **Failure Detection**: Heartbeat-based monitoring with automatic failover
- **Persistence**: Append-only log files for crash recovery
- **Catch-up Protocol**: Peers can request missing messages when rejoining
- **Exactly-once Delivery**: Idempotent message handling using (seq_no, term) tuples
- **Seamless Failover**: Leader PeerInfo propagation ensures immediate connectivity after elections
- **Split-brain Prevention**: Election cancellation when higher-priority coordinator appears

### Algorithms Used

1. **Total Order via Sequencer**: Leader assigns monotonically increasing sequence numbers
2. **Bully Algorithm**: Higher priority nodes (higher node_id) become leaders
3. **Heartbeat-based Failure Detection**: Followers detect leader failures through missed heartbeats

## Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Peer 1    │◄───────►│   Peer 2    │◄───────►│   Peer 3    │
│  (Follower) │         │  (Follower) │         │   (Leader)  │
│  User + Node│         │  User + Node│         │  User + Node│
└─────────────┘         └─────────────┘         └─────────────┘
       │                       │                       │
       │                       │                       │
       └───────────────────────┴───────────────────────┘
           All peers communicate via TCP (P2P)
```

### Message Flow

1. **User types message** → Local peer
2. **Follower peer forwards** → Leader peer
3. **Leader assigns seq_no** → Broadcasts SEQ_CHAT to all peers
4. **All peers deliver in order** → Based on sequence number
5. **Persist to log** → Append-only file storage

### Components

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

## Quick Start

### Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd CSEN317-Distributed-Systems

# Create virtual environment (Python 3.10+ required)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data/logs
```

### Start Peer-to-Peer Cluster

```bash
# Terminal 1 - First peer (bootstrap)
python -m src.peer_tui --id 1 --host 127.0.0.1 --port 6001

# Terminal 2 - Second peer
python -m src.peer_tui --id 2 --host 127.0.0.1 --port 6002 --seed 1:127.0.0.1:6001

# Terminal 3 - Third peer
python -m src.peer_tui --id 3 --host 127.0.0.1 --port 6003 --seed 1:127.0.0.1:6001

# Type messages directly in any terminal:
peer_1> Hello from peer 1!
peer_2> Hi from peer 2!

# Commands:
/status   # Show peer status
/quit     # Exit
```

You should see:
- Peers discovering each other
- Election process (Peer 3 becomes leader)
- Heartbeats being sent/received
- Messages appearing on all peers with sequence numbers

### Quick Start Script

Use the provided script for automated startup:

```bash
./run_p2p.sh
```

See `P2P_README.md` for detailed documentation.

#### 1. Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd CSEN317-Distributed-Systems

# Create virtual environment (Python 3.10+ required)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

## Running Tests

```bash
# Run all tests (recommended)
make test

# Or use pytest directly
pytest tests/ -v

# Run specific test file
pytest tests/test_ordering.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Test Coverage

**17/17 tests passing (100% pass rate)**

- `test_ordering.py` (4 tests): Sequence number assignment, buffering, delivery order
- `test_election.py` (5 tests): Bully algorithm, coordinator announcement, election cancellation
- `test_failure.py` (4 tests): Heartbeat recording, timeout detection, role changes
- `test_integration_local.py` (4 tests): End-to-end scenarios with storage and recovery

## P2P Testing

### Basic P2P Messaging

```bash
# Terminal 1 - Bootstrap peer
python -m src.peer_tui --id 1 --port 6001

# Terminal 2 - Second peer
python -m src.peer_tui --id 2 --port 6002 --seed 1:127.0.0.1:6001

# Terminal 3 - Third peer
python -m src.peer_tui --id 3 --port 6003 --seed 1:127.0.0.1:6001

# Type in any terminal:
peer_1> Test message
/status  # Check role and leader
```

### P2P Leader Failure Test

```bash
# 1. Start 3 peers (peer 3 becomes leader)
# 2. Send messages from peer 1 or 2
# 3. Kill peer 3 (Ctrl+C or /quit)
# 4. Peer 2 should become leader
# 5. Continue sending messages - ordering maintained
```

### P2P Scalability Test

```bash
# Automated test with N peers
python ScaleTestP2P.py

# This will:
# - Start multiple peers automatically
# - Send concurrent messages
# - Verify total ordering
# - Test leader election with failures
```

### P2P Reconnection Test

```bash
# 1. Start 3 peers
# 2. Send messages: "msg1", "msg2", "msg3"
# 3. Kill peer 2 (Ctrl+C)
# 4. Send more messages: "msg4", "msg5"
# 5. Restart peer 2: python -m src.peer_tui --id 2 --port 6002 --seed 1:127.0.0.1:6001
# 6. Peer 2 catches up and receives all messages in order
```

### Quick P2P Test Script

Use the provided script for fast startup:

```bash
# Edit run_p2p.sh to set number of peers
./run_p2p.sh
```

## Peer Configuration

Peers are configured via command-line arguments (no YAML files needed):

```bash
python -m src.peer_tui \
  --id 1 \                    # Unique peer ID (higher = higher priority)
  --host 127.0.0.1 \          # Listen address
  --port 6001 \               # Listen port
  --seed 2:127.0.0.1:6002     # Bootstrap peer(s) (optional)
```

### Configuration Parameters

- **--id**: Must be unique; determines election priority (higher wins)
- **--host**: Listen address (default: 0.0.0.0)
- **--port**: Unique port per peer (P2P uses 6000+)
- **--seed**: Seed peer for joining cluster (format: `id:host:port`, can specify multiple)
- **Heartbeat interval**: 800ms (hardcoded in peer.py)
- **Leader timeout**: 2500ms (hardcoded in peer.py)
- **Log directory**: `data/logs/` (auto-created)

## Demo Scenarios

### Scenario 1: Basic Peer-to-Peer Messaging

1. Start three peers (see Quick Start above)
2. Send messages from any peer
3. Observe messages appear on all peers with sequence numbers

**Expected**: All peers display messages in identical order

### Scenario 2: Leader Failure and Recovery

1. Start three peers (peer 3 becomes leader)
2. Send messages: "Before failure"
3. Kill peer 3 (Ctrl+C)
4. Watch election - peer 2 becomes leader
5. Send: "After failure"
6. Restart peer 3 (rejoins as follower)

**Expected**: Ordering maintained, peer 3 catches up on restart

### Scenario 3: Concurrent Messages

1. Start three peers
2. Rapidly send messages from all three peers simultaneously
3. Observe all peers agree on message order

**Expected**: Single total order across all peers despite concurrent sends

### Scenario 4: Network Partition Healing

1. Start three peers
2. Send messages: "msg1", "msg2"
3. Stop peer 1 (Ctrl+C)
4. Send: "msg3", "msg4" (peer 1 misses these)
5. Restart peer 1 with same seed
6. Peer 1 catches up

**Expected**: Peer 1 receives all missed messages in correct order

## Troubleshooting

### Peers Can't Join Cluster

**Problem**: New peer fails to connect to seed peer

**Solution**:
- Verify seed peer is running: `ps aux | grep peer_tui`
- Check seed peer address/port: `--seed 1:127.0.0.1:6001`
- Ensure bootstrap peer started first
- Check firewall allows connections on port 6000+

### Messages Not Appearing

**Problem**: Message sent but not visible on other peers

**Solution**:
- Run `/status` on all peers to verify cluster membership
- Check that a leader is elected (use `/status`)
- Ensure all peers connected to same cluster
- Verify no firewall blocking peer-to-peer connections

#### P2P Port Conflicts

**Problem**: "Address already in use" when starting peer

**Solution**:
```bash
# Find process using port
lsof -i :6001

# Kill old peer process
kill -9 <PID>

# Or use different port: --port 6010
```

### Client-Server Mode Issues

#### Nodes Can't Connect

**Problem**: Nodes fail to discover each other

**Solution**: 
- Check seed_nodes configuration matches actual hostnames/IPs
- Verify firewall allows TCP connections on configured ports
- For Docker: ensure all containers are on same network
- For local: use `127.0.0.1` or `localhost` in configs

#### No Leader Elected

**Problem**: No node becomes leader

**Solution**:
- Check logs for election messages
- Verify node_ids are unique and properly configured
- Ensure at least one node can contact others
- Check for network connectivity issues

#### Messages Not Delivered

- Check that a leader is elected (use `/status`)
- Ensure all peers connected to same cluster
- Verify no firewall blocking peer-to-peer connections

### Port Conflicts

**Problem**: "Address already in use" when starting peer

**Solution**:
```bash
# Find process using port
lsof -i :6001

# Kill old peer process
kill -9 <PID>

# Or use different port: --port 6010
```

### No Leader Elected

**Problem**: No peer becomes leader

**Solution**:
- Check logs for election messages
- Verify peer IDs are unique and properly configured
- Ensure at least one peer can contact others
- Check for network connectivity issues

### Storage/Permission Errors

**Problem**: Cannot write to log directory

**Solution**:
```bash
# Create directory with proper permissions
mkdir -p data/logs
chmod 755 data/logs
```

## Message Protocol

All messages are JSON over TCP, newline-delimited:

```json
{
  "type": "SEQ_CHAT",
  "sender_id": 1,
  "term": 2,
  "msg_id": "550e8400-e29b-41d4-a716-446655440000",
  "seq_no": 42,
  "room_id": "general",
  "payload": "Hello, world!"
}
```

### Message Types

- **JOIN**: New node joining cluster (includes PeerInfo for connectivity)
- **JOIN_ACK**: Response with membership info
- **HEARTBEAT**: Leader liveness signal
- **ELECTION**: Start Bully election
- **ELECTION_OK**: Higher priority node responding
- **COORDINATOR**: New leader announcement (includes leader PeerInfo for immediate connectivity)
- **CHAT**: Client message (not yet sequenced)
- **SEQ_CHAT**: Sequenced message for delivery
- **CATCHUP_REQ**: Request missed messages
- **CATCHUP_RESP**: Response with historical messages

## Recent Improvements (November 2025)

The following critical bugs were fixed to ensure production-quality code:

1. **Leader PeerInfo Propagation**: COORDINATOR messages now include leader's PeerInfo for immediate connectivity
2. **Follower-to-Leader JOIN Handling**: Leaders properly handle JOIN messages and add nodes to membership
3. **Election Cancellation**: Nodes abort ongoing elections when receiving COORDINATOR from higher-priority node
4. **Duplicate Storage Fix**: Messages stored exactly once via delivery callback (removed duplicate storage points)
5. **Follower last_seq Tracking**: Followers update last_seq on delivery for seamless leader transitions
6. **Import Path Corrections**: Fixed relative imports (`.common` instead of `common`)

**Result**: Zero known critical bugs, 17/17 tests passing, production-ready for educational use.

## Limitations and Future Work

### Current Limitations

1. **Single Room**: Only one global chat room ("general")
   - *Mitigation*: Architecture supports extension to multi-room
2. **No Authentication**: No user authentication or authorization
   - *Mitigation*: TUI client is local-only, suitable for trusted environments
3. **No Encryption**: Messages sent in plaintext
   - *Mitigation*: Can deploy with TLS/VPN for encrypted transport
4. **Static Membership**: Seed nodes configured statically
   - *Mitigation*: Dynamic JOIN protocol allows nodes to join via any peer
5. **Leader Bottleneck**: All messages go through single leader
   - *Mitigation*: Suitable for moderate message rates; fast failover ensures availability
6. **No Byzantine Fault Tolerance**: Assumes honest nodes
   - *Mitigation*: Appropriate for educational/controlled environments
7. **Split-brain Window**: Brief window during network partitions
   - *Mitigation*: Election cancellation reduces risk; term-based deduplication prevents duplicates

### Future Enhancements

1. **Multi-room Support**: Per-room sequence numbers and leaders
2. **Dynamic Membership**: Gossip-based peer discovery
3. **Security**: TLS encryption, JWT authentication
4. **Consensus-based Replication**: Raft or Multi-Paxos for stronger consistency
5. **Metrics**: Prometheus metrics, Grafana dashboards
6. **Web UI**: React/Vue frontend instead of TUI
7. **Message History API**: REST API for message retrieval
8. **Acknowledgments**: Explicit client ACKs for delivery guarantees
9. **Compression**: Message compression for large payloads
10. **Performance Optimizations**: Batching, pipelining, async storage

## References

### Distributed Systems Concepts

- **Total Order Broadcast**: Ensures all nodes deliver messages in same order
- **Bully Algorithm**: Simple leader election for static priority hierarchies
- **Heartbeat Failure Detection**: Timeout-based crash failure detection
- **Sequence Numbers**: Monotonic counters for ordering
- **Idempotence**: Same message delivered once despite retries

### Academic Resources

- *Distributed Systems: Principles and Paradigms* by Tanenbaum & Van Steen
- *Designing Data-Intensive Applications* by Martin Kleppmann
- Leslie Lamport's papers on distributed systems and ordering

## Contributing

This is a university project, but contributions are welcome for learning purposes:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is for educational purposes as part of CSEN 317 - Distributed Systems course.

## Project Status

**Status**: COMPLETE, TESTED, AND PRODUCTION-READY FOR EDUCATIONAL USE

- 17/17 comprehensive tests passing (100%)
- Zero known critical bugs
- All core requirements met and exceeded
- Extensive documentation (6+ markdown files)
- Multiple deployment methods validated (local, Docker, Kubernetes)
- Clean, type-hinted, well-documented code

## Additional Documentation

- **QUICKSTART.md**: Fast 5-minute setup guide
- **ARCHITECTURE.md**: Deep-dive technical documentation
- **PROJECT_SUMMARY.md**: Comprehensive project overview
- **DEMO.md**: Step-by-step demonstration scenarios
- **DELIVERY_CHECKLIST.md**: Requirements validation and extras
- **README-k8s.md**: Kubernetes deployment guide (deploy/k8s/)

## Authors

- Developed for CSEN 317 Distributed Systems Project
- Course: Santa Clara University, Fall 2025

## Acknowledgments

- Course instructors and TAs for guidance
- Python asyncio community for async patterns
- Open source distributed systems projects for inspiration
- Academic research on distributed algorithms

---

**Note**: This is an educational project demonstrating distributed systems concepts. While production-ready for learning purposes, real-world deployment would require additional security hardening, monitoring, and operational considerations.

