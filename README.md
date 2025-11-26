# Distributed Chat System

A production-like distributed chat application demonstrating key distributed systems concepts including total order broadcast, leader election, and failure detection.

## Project Overview

This project implements a distributed chat system where multiple peer nodes form a cluster, maintain total message ordering through a sequencer-based approach, handle leader failures through the Bully algorithm, and provide eventual consistency across all nodes.

### Key Features

- **Total Order Broadcast**: Messages are delivered in the same order across all nodes using sequence numbers assigned by a leader
- **Leader Election**: Bully algorithm for automatic leader election based on node priority with election cancellation
- **Failure Detection**: Heartbeat-based monitoring with automatic failover
- **Persistence**: Append-only log files for crash recovery
- **Catch-up Protocol**: Nodes can request missing messages when rejoining
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
│   Node 1    │◄───────►│   Node 2    │◄───────►│   Node 3    │
│  (Follower) │         │  (Follower) │         │   (Leader)  │
└─────────────┘         └─────────────┘         └─────────────┘
       │                       │                       │
       │                       │                       │
       └───────────────────────┴───────────────────────┘
                    All communicate via TCP
```

### Message Flow

1. **Client sends CHAT** → Local node
2. **Follower forwards** → Leader  
3. **Leader assigns seq_no** → Broadcasts SEQ_CHAT to all nodes
4. **All nodes deliver in order** → Based on sequence number
5. **Persist to log** → Append-only file storage

### Components

- `common.py`: Data structures, message schemas, enums
- `transport.py`: Async TCP communication layer
- `membership.py`: Cluster membership management
- `failure.py`: Heartbeat-based failure detection
- `election.py`: Bully algorithm implementation
- `ordering.py`: Sequence number assignment and ordered delivery
- `storage.py`: Persistent message logs
- `node.py`: Main node orchestrator
- `client_tui.py`: Terminal UI client

## Quick Start

### Local Development

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

# Verify setup (optional)
./verify_setup.sh
```

#### 2. Create Data Directory

```bash
mkdir -p data/logs
```

#### 3. Start Three Nodes

Open three terminal windows and run:

```bash
# Terminal 1 - Node 1
python -m src.node --config configs/node1.yml

# Terminal 2 - Node 2
python -m src.node --config configs/node2.yml

# Terminal 3 - Node 3 (will become leader due to highest priority)
python -m src.node --config configs/node3.yml
```

You should see logs indicating:
- Nodes discovering each other
- Election process
- Node 3 becoming the leader
- Heartbeats being sent/received

#### 4. Connect Client and Send Messages

Open a fourth terminal:

```bash
# Connect to node 1
python -m src.client_tui --host 127.0.0.1 --port 5001

# Type messages and press Enter
> Hello from client!
> This message will have the same order on all nodes
```

Check all three node terminals - they should all display messages in the same order with identical sequence numbers.

### Docker Compose Deployment

#### 1. Build and Start Cluster

```bash
cd deploy
docker compose up --build
```

This starts three nodes (chat_node1, chat_node2, chat_node3) in a Docker network.

#### 2. View Logs

```bash
# All nodes
docker compose logs -f

# Specific node
docker compose logs -f chat_node1
```

#### 3. Connect Client to a Node

```bash
# Exec into a container
docker exec -it chat_node1 bash

# Inside container, run client
python -m src.client_tui --host chat_node2 --port 5002
```

Or from host machine:

```bash
python -m src.client_tui --host 127.0.0.1 --port 5001
```

#### 4. Test Leader Failure

```bash
# Check which node is leader (highest node_id = 3)
docker compose logs chat_node3 | grep LEADER

# Kill the leader
docker stop chat_node3

# Watch election in remaining nodes
docker compose logs -f chat_node2

# Node 2 should become new leader

# Restart node 3
docker start chat_node3

# It will rejoin as follower and catch up
```

#### 5. Stop Cluster

```bash
docker compose down

# Remove volumes too (deletes logs)
docker compose down -v
```

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

## Configuration Reference

Each node requires a YAML configuration file:

```yaml
node_id: 3              # Unique integer ID (higher = higher priority)
host: 0.0.0.0          # Listen address
port: 5003             # Listen port
seed_nodes:            # Bootstrap peers
  - { node_id: 1, host: "chat_node1", port: 5001 }
  - { node_id: 2, host: "chat_node2", port: 5002 }
heartbeat_interval_ms: 800    # How often leader sends heartbeats
leader_timeout_ms: 2500       # When followers suspect leader failure
log_dir: "/data/logs"         # Directory for message logs
```

### Configuration Parameters

- **node_id**: Must be unique; determines election priority (higher wins)
- **host**: Usually `0.0.0.0` to listen on all interfaces
- **port**: Unique port per node
- **seed_nodes**: List of peers to contact on startup (excluding self)
- **heartbeat_interval_ms**: Leader heartbeat frequency (default: 800ms)
- **leader_timeout_ms**: Follower timeout threshold (default: 2500ms)
- **log_dir**: Path for persistent message storage

## Demo Scenarios

### Scenario 1: Normal Operation

1. Start all three nodes
2. Connect client to any node
3. Send messages
4. Verify all nodes show identical order

**Expected**: All nodes display messages with same sequence numbers

### Scenario 2: Leader Failure and Recovery

1. Start all three nodes (node 3 is leader)
2. Send some messages
3. Kill node 3 (leader)
4. Watch election logs - node 2 becomes leader
5. Send more messages - ordering continues
6. Restart node 3 - rejoins as follower, catches up

**Expected**: No message loss, ordering maintained across leadership change

### Scenario 3: Network Partition Healing

1. Start all nodes
2. Send messages
3. Stop node 1 temporarily
4. Send more messages (node 1 misses these)
5. Restart node 1
6. Node 1 requests catch-up

**Expected**: Node 1 receives all missed messages in order

### Scenario 4: Concurrent Messages

1. Start all nodes
2. Connect multiple clients to different nodes
3. Send messages concurrently from all clients

**Expected**: All nodes agree on a single total order

## Troubleshooting

### Nodes Can't Connect

**Problem**: Nodes fail to discover each other

**Solution**: 
- Check seed_nodes configuration matches actual hostnames/IPs
- Verify firewall allows TCP connections on configured ports
- For Docker: ensure all containers are on same network
- For local: use `127.0.0.1` or `localhost` in configs

### No Leader Elected

**Problem**: No node becomes leader

**Solution**:
- Check logs for election messages
- Verify node_ids are unique and properly configured
- Ensure at least one node can contact others
- Check for network connectivity issues

### Messages Not Delivered

**Problem**: Messages sent but not appearing on all nodes

**Solution**:
- Verify leader is elected (check logs)
- Ensure all nodes are connected (check membership logs)
- Check for errors in transport layer logs
- Verify follower can reach leader

### Port Already in Use

**Problem**: "Address already in use" error

**Solution**:
```bash
# Find process using port
lsof -i :5001

# Kill the process
kill -9 <PID>

# Or use different ports in config
```

### Storage/Permission Errors

**Problem**: Cannot write to log directory

**Solution**:
```bash
# Create directory with proper permissions
mkdir -p data/logs
chmod 755 data/logs

# For Docker, ensure volumes are mounted correctly
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

**Status**: ✅ **COMPLETE, TESTED, AND PRODUCTION-READY FOR EDUCATIONAL USE**

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

