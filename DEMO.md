# Demo Guide

Step-by-step guide to demonstrate the Distributed Chat System features.

## Setup

Choose one of these methods:

### Method 1: Docker Compose (Easiest)

```bash
cd deploy
docker compose up --build
```

### Method 2: Local Python

```bash
# Terminal 1
python3 -m src.node --config configs/node1_local.yml

# Terminal 2
python3 -m src.node --config configs/node2_local.yml

# Terminal 3
python3 -m src.node --config configs/node3_local.yml
```

## Demo 1: Basic Messaging and Total Order

**Goal**: Show that all nodes deliver messages in the same order

**Steps**:

1. **Start all three nodes** (using method above)

2. **Observe the logs**:
   ```
   Node 3 should become the leader (highest priority)
   Nodes 1 and 2 become followers
   ```

3. **Connect a client**:
   ```bash
   python3 -m src.client_tui --host 127.0.0.1 --port 5001
   ```

4. **Send several messages**:
   ```
   > Hello from node 1!
   > This is message 2
   > And message 3
   ```

5. **Check all three node terminals**:
   - Each should display: `[seq=1] node_9999: Hello from node 1!`
   - Then: `[seq=2] node_9999: This is message 2`
   - Then: `[seq=3] node_9999: And message 3`

**Expected Result**: All nodes show identical sequence numbers and order

## Demo 2: Leader Failure and Election

**Goal**: Show automatic leader election when leader fails

**Steps**:

1. **Identify the current leader** (Node 3)
   - Look for logs saying "Became LEADER"

2. **Send a few messages** to establish baseline
   ```
   > Message before failure
   ```

3. **Kill the leader**:
   - Docker: `docker stop chat_node3`
   - Local: Press `Ctrl+C` in Node 3 terminal

4. **Watch the election process** in Node 1 and Node 2 terminals:
   ```
   2024-10-21 12:34:56 - failure.2 - WARNING - Leader timeout!
   2024-10-21 12:34:56 - election.2 - INFO - Starting election for term 2
   2024-10-21 12:34:58 - election.2 - INFO - Becoming coordinator for term 2
   2024-10-21 12:34:58 - node.2 - INFO - Became LEADER for term 2
   ```

5. **Send more messages**:
   ```
   > Message after leader change
   > Ordering should continue!
   ```

6. **Verify ordering continues**:
   - If last message was seq=5, next should be seq=6
   - No gaps in sequence numbers

**Expected Result**: Node 2 becomes new leader, messaging continues seamlessly

## Demo 3: Leader Rejoining as Follower

**Goal**: Show that old leader rejoins as follower

**Steps**:

1. **After Demo 2, restart Node 3**:
   - Docker: `docker start chat_node3`
   - Local: Restart in Terminal 3

2. **Watch Node 3 logs**:
   ```
   2024-10-21 12:35:10 - node.3 - INFO - Starting node...
   2024-10-21 12:35:10 - membership.3 - INFO - Attempting to join...
   2024-10-21 12:35:11 - election.3 - INFO - Received COORDINATOR from node_2
   2024-10-21 12:35:11 - node.3 - INFO - New coordinator: node_2, term=2
   2024-10-21 12:35:11 - ordering.3 - INFO - Requesting catch-up from seq_no=5
   ```

3. **Verify catch-up**:
   - Node 3 should receive all messages it missed
   - Node 3 logs should show same seq_no as other nodes

4. **Send new message**:
   ```
   > Testing after node 3 rejoined
   ```

5. **All three nodes** should display it with same seq_no

**Expected Result**: Node 3 rejoins as follower, catches up, and participates normally

## Demo 4: Concurrent Messages from Multiple Clients

**Goal**: Show total ordering of concurrent messages

**Steps**:

1. **Connect three clients** (in separate terminals):
   ```bash
   # Client 1 -> Node 1
   python3 -m src.client_tui --host 127.0.0.1 --port 5001 --client-id 101
   
   # Client 2 -> Node 2
   python3 -m src.client_tui --host 127.0.0.1 --port 5002 --client-id 102
   
   # Client 3 -> Node 3
   python3 -m src.client_tui --host 127.0.0.1 --port 5003 --client-id 103
   ```

2. **Send messages rapidly** from all clients simultaneously:
   ```
   Client 1: > Message from client 1
   Client 2: > Message from client 2
   Client 3: > Message from client 3
   Client 1: > Another from client 1
   Client 2: > Another from client 2
   ```

3. **Check all node terminals**:
   - Messages may arrive at leader in different orders
   - But all nodes deliver them in the SAME order
   - Sequence numbers are contiguous (no gaps)

**Expected Result**: Despite concurrency, all nodes agree on message order

## Demo 5: Out-of-Order Message Handling

**Goal**: Show message buffering and ordered delivery

This is harder to demo visually but happens internally. To observe:

1. **Enable debug logging** (modify `node.py` to set log level to DEBUG)

2. **Send messages quickly** from multiple clients

3. **Look for debug logs** like:
   ```
   ordering.1 - DEBUG - Buffered out-of-order message seq_no=8 (expected 7)
   ordering.1 - DEBUG - Delivering seq_no=7
   ordering.1 - DEBUG - Delivering seq_no=8 from buffer
   ```

**Expected Result**: System handles out-of-order delivery transparently

## Demo 6: Persistence and Recovery

**Goal**: Show messages survive node restarts

**Steps**:

1. **Send some messages** (at least 10)

2. **Stop ALL nodes**:
   - Docker: `docker compose down` (NOT `down -v`)
   - Local: `Ctrl+C` all terminals

3. **Check log files**:
   ```bash
   # Docker
   docker run -v deploy_node1_data:/data alpine ls -l /data/logs
   
   # Local
   ls -l data/logs/
   cat data/logs/node_1_messages.jsonl
   ```

4. **Restart all nodes**

5. **Check logs for recovery**:
   ```
   storage.1 - INFO - Loaded 10 messages from log
   ordering.1 - INFO - Set last_seq=10, next_expected=11
   ```

6. **Send new message** - should start at seq=11

**Expected Result**: Nodes recover state from disk, continue numbering

## Demo 7: Network Monitoring

**Goal**: Show heartbeat mechanism

**Steps**:

1. **Start all nodes with INFO logging**

2. **Watch for heartbeat logs**:
   ```
   failure.3 - DEBUG - Sent heartbeat to 2 peers
   failure.1 - DEBUG - Heartbeat received from leader, term=1
   failure.2 - DEBUG - Heartbeat received from leader, term=1
   ```

3. **Delay happens** every ~800ms (configured heartbeat_interval)

**Expected Result**: Regular heartbeats visible in logs

## Demo 8: Client Reconnection

**Goal**: Show client can disconnect and reconnect

**Steps**:

1. **Connect client, send message**
   ```
   > Test message 1
   ```

2. **Disconnect** (Ctrl+C)

3. **Reconnect to different node**:
   ```bash
   python3 -m src.client_tui --host 127.0.0.1 --port 5002
   ```

4. **Send another message**
   ```
   > Test message 2
   ```

**Expected Result**: Client can connect to any node, messages always ordered

## Performance Demo

**Goal**: Show system can handle reasonable load

**Steps**:

1. **Create a simple load script**:
   ```python
   # load_test.py
   import asyncio
   from src.transport import Connection
   from src.common import Message, MessageType
   
   async def send_messages():
       reader, writer = await asyncio.open_connection('127.0.0.1', 5001)
       conn = Connection(reader, writer)
       
       for i in range(100):
           msg = Message(
               type=MessageType.CHAT,
               sender_id=9999,
               term=0,
               payload=f"Load test message {i}"
           )
           await conn.send(msg)
           await asyncio.sleep(0.01)  # 100 msgs/sec
       
       conn.close()
   
   asyncio.run(send_messages())
   ```

2. **Run the load test**

3. **Verify all 100 messages** delivered in order across all nodes

**Expected Result**: System handles sustained load without message loss

## Troubleshooting Tips

### Demo not working?

1. **Check logs carefully** - they're very informative
2. **Verify ports** aren't already in use
3. **For Docker**: Ensure containers are on same network
4. **For local**: Use `127.0.0.1` not `localhost` in configs
5. **Clean state**: Remove old log files if testing recovery

### What to look for in logs

- `"Became LEADER"` - Election successful
- `"Sent JOIN_ACK"` - Node joining cluster
- `"Delivering seq_no=X"` - Message delivered
- `"Failed to connect"` - Network problem
- `"Leader timeout"` - Expected during failure demo

## Presentation Tips

1. **Have terminals arranged** side-by-side for easy viewing
2. **Use larger font** for demos
3. **Clear logs** between demos for clarity
4. **Prepare configs** in advance
5. **Have backup** Docker setup if local fails

## Questions to Answer During Demo

- **Q: What happens if two nodes think they're leader?**
  - A: Term numbers prevent this. Followers only accept messages from current term.

- **Q: Can messages be lost?**
  - A: Messages in leader's buffer during crash can be lost. Delivered messages are durable.

- **Q: How fast can it handle messages?**
  - A: Depends on network and hardware. Leader is bottleneck (~1000-10k msg/s).

- **Q: What if network partitions?**
  - A: Current implementation may have issues. Future: use quorums.

- **Q: Why not use Raft/Paxos?**
  - A: Simpler algorithms for educational purposes. Bully + sequencer easier to understand.

---

Good luck with your demo!

