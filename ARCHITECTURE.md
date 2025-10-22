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
     - X broadcasts COORDINATOR to all
  4. Any node receiving ELECTION from lower ID:
     - Responds with ELECTION_OK
     - Starts its own election
```

**Properties**:
- Higher node_id always wins
- Deterministic leader selection
- Eventually consistent (may have brief periods without leader)

**Terms**: 
- Each new leader increments term number
- Messages with old terms are ignored
- Prevents split-brain scenarios

### 5. Ordering Manager (`ordering.py`)

**Responsibility**: Assign and enforce total message order

**Leader Role**:
```python
On receive CHAT:
  seq_no = ++last_seq
  Create SEQ_CHAT(seq_no, term, msg)
  Write to log (sync)
  Broadcast SEQ_CHAT to all peers
```

**Follower Role**:
```python
On receive SEQ_CHAT(seq_no):
  If seq_no == next_expected:
    Deliver message
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
    HEARTBEAT -> Update failure detector
    ELECTION -> Process election message
    COORDINATOR -> Accept new leader
    CHAT -> Forward to leader (or sequence if leader)
    SEQ_CHAT -> Deliver in order
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
  |------ELECTION------>| (no response)
  |<-----ELECTION_OK----|
  |                     |
  ... timeout ...       |
  |                     |
  |----COORDINATOR----->|
  | Become leader       |
  |                     |
  |------HEARTBEAT----->|
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

**Detection**: Followers miss heartbeats
**Recovery**: Bully election selects new leader
**Consistency**: Messages in old leader's buffer may be lost, but all delivered messages maintain order

### 2. Follower Crashes

**Detection**: Leader notices failed connections (optional)
**Recovery**: Follower restarts, recovers from log, requests catch-up
**Consistency**: No impact on other nodes

### 3. Network Partition

**Current behavior**: Partition heals when network reconnects
**Limitation**: No partition tolerance guarantees (split-brain possible in theory)
**Future work**: Use terms and majority quorums

### 4. Message Loss

**Scenario**: Leader crashes after assigning seq_no but before broadcasting
**Impact**: Gap in sequence numbers
**Detection**: Followers buffer messages, request catch-up
**Mitigation**: New leader may need to reassign (future work)

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

### Unit Tests
- Each component tested in isolation
- Mock dependencies
- Focus on edge cases

### Integration Tests
- Multiple components together
- In-process nodes (no network)
- Verify end-to-end flows

### System Tests
- Full Docker deployment
- Real network latency
- Chaos testing (kill nodes randomly)

### Test Coverage
- Ordering: In-order, out-of-order, duplicates
- Election: No higher peers, with responses, coordinator announcement
- Failure: Heartbeat recording, timeout detection
- Storage: Persistence, recovery

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
- O(n) for n messages
- Append-only, no compaction
- Log rotation needed for long-running systems

## Operational Aspects

### Monitoring
- Log node_id, role, term, seq_no
- Track message delivery rate
- Monitor heartbeat intervals

### Debugging
- All nodes log same seq_no for same message
- Terms identify which leader assigned sequence
- Catch-up logs show recovery

### Deployment
- Docker Compose for local dev/test
- Kubernetes for production-like environment
- StatefulSet for stable network identities

## References

- **Total Order Broadcast**: Group communication literature
- **Bully Algorithm**: Garcia-Molina (1982)
- **Heartbeat Failure Detection**: Chandra & Toueg (1996)
- **Sequencer-based Ordering**: Classic distributed systems technique

---

For implementation details, see the source code in `src/`.
For deployment instructions, see `README.md` and `deploy/k8s/README-k8s.md`.

