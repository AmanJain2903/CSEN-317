# System Architecture

Detailed architecture documentation for the Distributed Chat System.

## Overview

The system implements a distributed chat application using a **sequencer-based total order broadcast** protocol with **leader-based coordination**. Failure detection and recovery are handled through **heartbeat monitoring** and the **Bully election algorithm**.

## Design Principles

1. **Simplicity**: Use straightforward algorithms that are easy to understand and reason about
2. **Modularity**: Separate concerns into distinct, testable components
3. **Asynchronous**: Non-blocking I/O using Python's asyncio
4. **Persistence**: Crash-recovery through append-only logs
5. **Idempotence**: Same message can be processed multiple times safely

## Core Components

### 1. Transport Layer (`transport.py`)

**Responsibility**: Low-level TCP communication

**Key Features**:
- Async TCP server for accepting connections
- Connection pooling for outbound connections  
- JSON message serialization/deserialization
- Broadcast primitive for multi-peer messaging

**Implementation**:
```python
TransportLayer
├── start_server()      # Listen for incoming connections
├── connect()           # Establish connection to peer
├── send_to()          # Send message to specific peer
└── broadcast()        # Send message to multiple peers
```

**Protocol**: JSON messages delimited by newlines over TCP

### 2. Membership Manager (`membership.py`)

**Responsibility**: Track cluster members and leader

**Key Features**:
- Bootstrap join via seed nodes
- Dynamic membership updates
- Leader tracking
- Priority-based peer queries for election

**State**:
```python
{
  node_id: int,
  peers: Dict[int, PeerInfo],  # All known peers
  leader_id: Optional[int],    # Current leader
  seed_peers: List[PeerInfo]   # Bootstrap nodes
}
```

**Operations**:
- `add_peer()`: Add/update peer info
- `get_higher_priority_peers()`: For Bully algorithm
- `bootstrap_join()`: Initial cluster join
- `get_leader()`: Returns PeerInfo of current leader (None if not in peers)
- `set_leader()`: Update leader_id

### 3. Failure Detector (`failure.py`)

**Responsibility**: Detect leader failures via heartbeats

**Algorithm**:
```
Leader:
  Every heartbeat_interval_ms:
    Send HEARTBEAT to all followers

Follower:
  On receive HEARTBEAT:
    Update last_seen_time
  
  Every monitoring_interval:
    If (now - last_seen_time) > leader_timeout_ms:
      Trigger election
```

**Configuration**:
- `heartbeat_interval_ms`: How often leader sends heartbeats (default: 800ms)
- `leader_timeout_ms`: How long before follower suspects failure (default: 2500ms)

**Failure Model**: Crash-stop failures (no Byzantine faults)

### 4. Election Manager (`election.py`)

**Responsibility**: Elect new leader via Bully algorithm

**Bully Algorithm**:
```
On timeout or startup without leader:
  1. Node X sends ELECTION to all nodes with higher IDs
  2. If any node responds with ELECTION_OK:
     - X waits for COORDINATOR message
  3. If no responses after timeout:
     - X becomes coordinator
     - X broadcasts COORDINATOR(with own PeerInfo) to all
  4. Any node receiving ELECTION from lower ID:
     - Responds with ELECTION_OK
     - Starts its own election
  5. On receiving COORDINATOR during election:
     - Cancel ongoing election
     - Accept announced leader
```

**Properties**:
- Higher node_id always wins
- Deterministic leader selection
- Eventually consistent (may have brief periods without leader)
- Election cancellation prevents split-brain
- COORDINATOR includes leader's PeerInfo for immediate connectivity

**Terms**: 
- Each new leader increments term number
- Messages with old terms are ignored
- Prevents split-brain scenarios
- Followers track highest term seen

### 5. Ordering Manager (`ordering.py`)

**Responsibility**: Assign and enforce total message order

**Leader Role**:
```python
On receive CHAT:
  seq_no = ++last_seq
  Create SEQ_CHAT(seq_no, term, msg)
  Broadcast SEQ_CHAT to all peers
  Self-deliver via ordering manager
  # Storage happens in delivery callback
```

**Follower Role**:
```python
On receive CHAT:
  Forward to leader

On receive SEQ_CHAT(seq_no):
  If seq_no == next_expected:
    Deliver message
    Store to log via callback
    Update last_seq = max(last_seq, seq_no)  # Critical for failover!
    Deliver buffered messages in order
  Else if seq_no > next_expected:
    Buffer message
  Else:
    Ignore (duplicate or out of sync)
```

**Guarantees**:
- All nodes deliver messages in same order
- No message reordering
- Idempotent delivery (dedupe by seq_no + term)
- Followers track last_seq for seamless leader promotion

**Catch-up Protocol**:
```python
New/rejoining node:
  Send CATCHUP_REQ(last_seq)
  
Leader:
  Send all SEQ_CHAT messages where seq_no > last_seq
```

### 6. Storage Manager (`storage.py`)

**Responsibility**: Persist messages to disk

**Format**: Newline-delimited JSON (JSONL)
```json
{"seq_no": 1, "term": 1, "sender_id": 1, "text": "Hello", ...}
{"seq_no": 2, "term": 1, "sender_id": 2, "text": "World", ...}
```

**Operations**:
- `append_message()`: Add message to log (append-only)
- `load_messages()`: Read all messages on startup
- `get_messages_after(seq)`: For catch-up

**Recovery**:
- On startup, read log to find last_seq
- Leader uses last_seq to continue numbering
- Followers use it to request catch-up

### 7. Node Orchestrator (`node.py`)

**Responsibility**: Coordinate all components

**Lifecycle**:
```
1. Load config
2. Initialize all components
3. Start transport server
4. Bootstrap join cluster
5. Recover state from storage
6. Start as follower or leader
7. Run forever (handling messages)
8. On interrupt, cleanup and stop
```

**Message Routing**:
```python
on_receive_message(msg):
  match msg.type:
    JOIN -> Handle join request
           If leader: send JOIN_ACK + COORDINATOR(with PeerInfo)
           If follower: send JOIN_ACK + COORDINATOR(about leader)
    JOIN_ACK -> Update membership from received list
    HEARTBEAT -> Update failure detector
    ELECTION -> Process election message
    ELECTION_OK -> Mark response received
    COORDINATOR -> Accept new leader, add PeerInfo, cancel election
    CHAT -> Forward to leader (or sequence if leader)
    SEQ_CHAT -> Deliver in order (storage via callback)
    CATCHUP_REQ -> Send missing messages
```

## Message Flow Diagrams

### Normal Operation

```
Client   Node1(F)   Node2(F)   Node3(L)
  |         |          |          |
  |--CHAT-->|          |          |
  |         |-------CHAT--------->|
  |         |          |          | Assign seq=42
  |         |          |          | Write to log
  |         |<------SEQ_CHAT------|
  |         |          |<-SEQ_CHAT|
  |<-display|          |          |
            |--display |          |
                       |--display |
                       
All nodes display: [seq=42] node_1: message
```

### Leader Failure and Recovery

```
Node1(F)   Node2(F)   Node3(L)
  |          |          |
  |<------HEARTBEAT-----|
  |          |          | [CRASH]
  |          |          |
  ... timeout ...       |
  |                     |
  | Start election      |
  |------ELECTION------>| (no response)
  |          |          |
  ... timeout (0.5s) ...|
  |                     |
  | No OK received      |
  |----COORDINATOR(PeerInfo)-->|
  | Become leader       | Accept leader
  |                     | Add Node2's PeerInfo
  |------HEARTBEAT----->| Update role to FOLLOWER
  |                     |
  
Note: COORDINATOR now includes leader's PeerInfo so followers
      can immediately contact the new leader for message forwarding
```

### Out-of-Order Delivery

```
Node receives: SEQ_CHAT(seq=5)
Buffer state: {}
next_expected: 1

Action: Buffer seq=5

---

Node receives: SEQ_CHAT(seq=1)
Buffer state: {5}
next_expected: 1

Action: Deliver seq=1, next_expected=2

---

Node receives: SEQ_CHAT(seq=3)
Buffer state: {3, 5}
next_expected: 2

Action: Buffer seq=3

---

Node receives: SEQ_CHAT(seq=2)
Buffer state: {3, 5}
next_expected: 2

Action: 
  - Deliver seq=2
  - Deliver seq=3 from buffer
  - next_expected=4

---

Node receives: SEQ_CHAT(seq=4)
Buffer state: {5}
next_expected: 4

Action:
  - Deliver seq=4
  - Deliver seq=5 from buffer
  - next_expected=6
```

## Failure Scenarios

### 1. Leader Crashes

**Detection**: Followers miss heartbeats (leader_timeout_ms)
**Recovery**: Bully election selects new leader
**Consistency**: 
- All delivered messages maintain order across all nodes
- New leader uses last_seq from followers (via recovery state)
- Messages in crashed leader's buffer (not yet broadcasted) are lost
- Sequence numbers continue monotonically from highest seen

### 2. Follower Crashes

**Detection**: Leader notices failed send attempts (logged but not blocking)
**Recovery**: 
1. Follower restarts, recovers last_seq from log
2. Sends JOIN to seed nodes
3. Receives JOIN_ACK with full membership list
4. Receives COORDINATOR with leader's PeerInfo
5. Requests catch-up for messages after last_seq
6. Continues normal operation as follower
**Consistency**: No impact on other nodes during crash or rejoin

### 3. Network Partition

**Current behavior**: Partition heals when network reconnects
**Limitation**: No partition tolerance guarantees (split-brain possible in theory)
**Future work**: Use terms and majority quorums

### 4. Message Loss

**Scenario**: Leader crashes after assigning seq_no but before broadcasting
**Impact**: Gap in sequence numbers (leader had seq_no N, but N was never sent)
**Detection**: New leader starts from highest seq_no seen by any node
**Result**: Gap is skipped (seq N is lost forever)
**Mitigation**: 
- Accept message loss for uncommitted messages
- OR implement 2-phase commit (future work)
- OR use replicated log (Raft/Paxos) for durability

### 5. Split-Brain Prevention

**Scenario**: Network partition causes multiple leaders
**Prevention**:
- Terms prevent old leaders from being accepted
- Election cancellation when COORDINATOR received
- Higher term always wins
**Limitation**: Brief period of dual leaders possible (eventually resolved)
**Future work**: Majority quorum for leader election

## Consistency Model

### Total Order

**Definition**: All nodes deliver messages in the same order

**Guarantee**: If node A delivers m1 before m2, then all nodes deliver m1 before m2

**Implementation**: Single sequencer assigns monotonic sequence numbers

### Eventual Consistency

**Definition**: All nodes eventually converge to same state

**Guarantee**: Once system stabilizes (no crashes, no partitions), all nodes have same message log

**Catch-up**: Ensures nodes that fall behind can recover

### Idempotence

**Definition**: Processing same message multiple times has same effect as once

**Implementation**: Deduplicate by (seq_no, term) tuple

## Scalability Considerations

### Current Limitations

1. **Leader Bottleneck**: All messages go through single leader
   - Throughput limited by leader's processing capacity
   - Latency includes network round-trip to leader

2. **Full Mesh**: Each node connects to all others
   - O(n²) connections for n nodes
   - Doesn't scale beyond ~100 nodes

3. **No Sharding**: Single global message log
   - Can't partition load across multiple sequences

### Scaling Strategies (Future Work)

1. **Multi-leader**: Partition messages by room/topic
2. **Replication**: Use Raft/Multi-Paxos for fault-tolerance
3. **Hierarchical**: Regions with local leaders
4. **Gossip**: Replace full mesh with epidemic broadcast

## Security Considerations

### Current State (Insecure)

- No authentication
- No encryption
- No authorization
- Nodes trust each other

### Hardening (Future Work)

1. **TLS**: Encrypt all TCP connections
2. **Mutual TLS**: Authenticate peer identities
3. **JWT Tokens**: Authenticate clients
4. **ACLs**: Control who can send/receive
5. **Rate Limiting**: Prevent DoS attacks
6. **Signed Messages**: Prevent tampering

## Testing Strategy

### Unit Tests (`tests/test_*.py`)
- Each component tested in isolation
- Mock dependencies (AsyncMock for transport)
- Focus on edge cases
- **17 tests total** covering:
  - `test_election.py`: Bully algorithm, coordinator announcement, election cancellation
  - `test_failure.py`: Heartbeat recording, timeout detection, role changes
  - `test_ordering.py`: In-order delivery, out-of-order buffering, duplicates, sequence assignment
  - `test_integration_local.py`: Storage recovery, catch-up scenario, concurrent buffering

**Run tests**: `make test` or `source DS/bin/activate && pytest tests/ -v`

### Integration Tests
- Multiple components together (ordering + storage)
- In-process nodes (no network)
- Verify end-to-end flows

### System Tests (Manual)
- Full Docker deployment (`docker compose up`)
- Real network latency and failures
- Test scenarios:
  1. Normal operation with 3 nodes
  2. Leader failure and election
  3. Node rejoin and catch-up
  4. Concurrent clients
  5. Persistent storage verification
  6. Network partition simulation

### Test Coverage
- ✅ Ordering: In-order, out-of-order, duplicates, concurrent messages
- ✅ Election: No higher peers, with responses, coordinator with PeerInfo, election cancellation
- ✅ Failure: Heartbeat recording, timeout detection, role transitions
- ✅ Storage: Persistence, recovery, catch-up protocol
- ✅ Integration: Storage + ordering, recovery scenario

## Performance Characteristics

### Latency
- Client to leader: 1 RTT
- Follower to leader: 1 RTT
- Leader broadcast: 1 RTT (parallel)
- **Total**: 2-3 RTTs for end-to-end delivery

### Throughput
- Limited by leader's CPU and network
- ~1000-10000 messages/sec on modern hardware (single leader)

### Storage
- O(n) for n messages (single file per node)
- Append-only JSONL format, no compaction
- Each message stored exactly once (fixed duplicate storage bug)
- Log rotation needed for long-running systems
- Storage happens via delivery callback (_on_deliver_message)

## Operational Aspects

### Monitoring
- Log node_id, role, term, seq_no
- Track message delivery rate
- Monitor heartbeat intervals

### Debugging
- All nodes log same seq_no for same message
- Terms identify which leader assigned sequence (term increments with each new leader)
- Catch-up logs show recovery (e.g., "Requesting catch-up from seq_no=X")
- Debug logging shows role, leader_id, and peer count
- Message logs are human-readable JSONL for easy inspection

### Deployment
- Docker Compose for local dev/test
- Kubernetes for production-like environment
- StatefulSet for stable network identities

## Recent Fixes and Improvements

### 1. Leader PeerInfo Propagation (Critical)
**Problem**: After election, followers didn't know new leader's address  
**Solution**: COORDINATOR message now includes leader's PeerInfo in membership field  
**Impact**: Followers can immediately forward messages to new leader

### 2. Follower-to-Leader JOIN Handling
**Problem**: Node rejoining via follower didn't learn about leader  
**Solution**: Followers send COORDINATOR on behalf of leader during JOIN  
**Impact**: Rejoining nodes discover leader regardless of which node they contact

### 3. Election Cancellation
**Problem**: Node could become leader even after receiving COORDINATOR  
**Solution**: Check `election_in_progress` flag after timeout, cancel if COORDINATOR received  
**Impact**: Prevents split-brain scenarios during concurrent elections

### 4. Duplicate Message Storage
**Problem**: Messages stored 2-3 times (leader, SEQ_CHAT handler, delivery callback)  
**Solution**: Consolidate to single storage point in `_on_deliver_message` callback  
**Impact**: Clean logs, no duplicates, consistent storage across all nodes

### 5. Follower last_seq Tracking
**Problem**: Followers didn't update last_seq, causing duplicate seq_no after promotion  
**Solution**: Update `last_seq = max(last_seq, seq_no)` in `_deliver_message`  
**Impact**: Seamless leader promotion with continuous sequence numbers

### 6. Import Path Errors
**Problem**: `from common import PeerInfo` (missing dot) crashed COORDINATOR handler  
**Solution**: Fixed to `from .common import PeerInfo`  
**Impact**: COORDINATOR messages now process correctly, role changes work

## References

- **Total Order Broadcast**: Group communication literature
- **Bully Algorithm**: Garcia-Molina (1982) - Extended with PeerInfo propagation
- **Heartbeat Failure Detection**: Chandra & Toueg (1996)
- **Sequencer-based Ordering**: Classic distributed systems technique
- **Implementation**: Python 3.10+ with asyncio

---

For implementation details, see the source code in `src/`.  
For deployment instructions, see `README.md` and `deploy/k8s/README-k8s.md`.  
For testing, run `make test` or see `tests/` directory.

