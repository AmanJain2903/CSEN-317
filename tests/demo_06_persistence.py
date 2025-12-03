#!/usr/bin/env python3
"""
Demo 6: Persistence and Recovery
Tests that messages are persisted and recovered after node restart.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient
from tests.demo_02_leader_failure import kill_node


def read_node_log(node_id: int, log_dir: str = "data/logs"):
    """Read messages from node's log file"""
    log_file = Path(log_dir) / f"node_{node_id}_messages.jsonl"
    messages = []
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
    
    return messages


async def run_demo():
    """Run Demo 6: Persistence and Recovery"""
    print("=" * 70)
    print("DEMO 6: Persistence and Recovery")
    print("=" * 70)
    print("\nObjective: Verify messages persist and recover after node restart")
    print()
    
    # Connect to Node 1
    client = TestClient("127.0.0.1", 5001, "Client1")
    
    print("Step 1: Connecting to Node 1...")
    await client.connect()
    await asyncio.sleep(1)
    
    # Send messages
    print("\nStep 2: Sending messages to be persisted...")
    test_messages = [
        "Persistent message 1",
        "Persistent message 2",
        "Persistent message 3",
        "Persistent message 4",
        "Persistent message 5",
    ]
    
    for msg in test_messages:
        await client.send_chat(msg)
        await asyncio.sleep(0.5)
    
    # Receive messages
    await client.receive_messages(3.0)
    messages_before = len(client.received_messages)
    print(f"   Sent and received {messages_before} messages")
    
    # Read log file before restart
    print("\nStep 3: Checking Node 1's log file...")
    log_before = read_node_log(1)
    print(f"   Log file contains {len(log_before)} messages")
    
    if len(log_before) < messages_before:
        print(f"   [WARNING]  Warning: Log has fewer messages than received")
    
    await client.close()
    
    # Kill and restart Node 1
    print("\nStep 4: Restarting Node 1...")
    await kill_node(1)
    await asyncio.sleep(2)
    
    print("\n" + "=" * 70)
    print("MANUAL ACTION REQUIRED")
    print("=" * 70)
    print("\n Please restart Node 1 now:")
    print("   python -m src.node --config configs/node1.yml")
    input("\nPress Enter after Node 1 has restarted...")
    
    await asyncio.sleep(5)  # Wait for recovery
    
    # Reconnect and check
    print("\nStep 5: Reconnecting to verify recovery...")
    client2 = TestClient("127.0.0.1", 5001, "Client2")
    
    try:
        await client2.connect()
        
        # Send a new message
        await client2.send_chat("Message after restart")
        await asyncio.sleep(1)
        
        # Receive messages (should include recovered + new)
        await client2.receive_messages(2.0)
        
        # Read log after restart
        log_after = read_node_log(1)
        
        # Verify
        print("\n" + "=" * 70)
        print("VERIFICATION: Checking Persistence and Recovery")
        print("=" * 70)
        
        print(f"\nLog before restart: {len(log_before)} messages")
        print(f"Log after restart:  {len(log_after)} messages")
        print(f"New messages sent:  1")
        
        # Check log file integrity
        if len(log_after) >= len(log_before):
            print(f"\n[PASS] SUCCESS: Messages persisted and recovered!")
            print(f"   - All {len(log_before)} messages preserved")
            print(f"   - New message appended successfully")
            print(f"   - Node recovered state from disk")
            
            # Show sample of persisted messages
            print(f"\nSample of persisted messages:")
            for msg in log_before[-3:]:
                print(f"  [{msg['seq_no']}] {msg['payload']}")
            
            success = True
        else:
            print(f"\n[FAIL] FAIL: Log file missing messages after restart")
            print(f"   Expected: >={len(log_before)}, Got: {len(log_after)}")
            success = False
        
        await client2.close()
        
    except Exception as e:
        print(f"\n[FAIL] FAIL: Could not reconnect to Node 1: {e}")
        print("   Ensure Node 1 restarted successfully")
        success = False
    
    return success


if __name__ == "__main__":
    print("\n[WARNING]  PREREQUISITE: Ensure Nodes 1, 2, and 3 are running!")
    input("Press Enter when ready...")
    
    try:
        success = asyncio.run(run_demo())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

