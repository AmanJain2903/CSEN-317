#!/usr/bin/env python3
"""
Demo 2: Leader Failure and Election
Tests automatic leader election when the leader crashes.
"""

import asyncio
import json
import sys
import subprocess
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient


async def find_leader(clients):
    """Determine which node is the leader by checking logs or behavior"""
    # Send a message and see which node sequences it
    # For simplicity, assume node 3 (highest ID) starts as leader
    return 3


async def kill_node(node_id: int):
    """Kill a node process"""
    print(f"\n Killing Node {node_id}...")
    # Find process by port
    port = 5000 + node_id
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            pid = result.stdout.strip()
            subprocess.run(["kill", "-9", pid])
            print(f"   Killed process {pid} on port {port}")
            return True
    except Exception as e:
        print(f"   Could not kill node: {e}")
    return False


async def run_demo():
    """Run Demo 2: Leader Failure and Election"""
    print("=" * 70)
    print("DEMO 2: Leader Failure and Election")
    print("=" * 70)
    print("\nObjective: Verify automatic leader election after leader crash")
    print()
    
    # Connect clients to nodes 1 and 2 (we'll kill node 3)
    clients = [
        TestClient("127.0.0.1", 5001, "Client1"),
        TestClient("127.0.0.1", 5002, "Client2"),
    ]
    
    print("Step 1: Connecting to Node 1 and Node 2...")
    for client in clients:
        await client.connect()
    await asyncio.sleep(1)
    
    # Send initial messages with leader alive
    print("\nStep 2: Sending messages with Node 3 (leader) alive...")
    await clients[0].send_chat("Message before leader failure")
    await asyncio.sleep(1)
    
    # Receive the message
    await asyncio.gather(*[client.receive_messages(2.0) for client in clients])
    initial_count = len(clients[0].received_messages)
    print(f"   Received {initial_count} messages successfully")
    
    # Kill the leader (Node 3)
    print("\nStep 3: Simulating leader failure...")
    killed = await kill_node(3)
    if not killed:
        print("   [WARNING]  Could not kill Node 3 - may already be stopped")
        print("   Please ensure Node 3 is stopped manually")
    
    # Wait for failure detection and election
    print("\nStep 4: Waiting for failure detection and election...")
    print("   (Timeout: ~2.5s, Election: ~0.5s)")
    await asyncio.sleep(4)  # Wait for timeout (2.5s) + election (0.5s)
    
    # Send messages after election
    print("\nStep 5: Sending messages after election (should work)...")
    test_messages = [
        "Message 1 after election",
        "Message 2 after election",
        "Message 3 after election"
    ]
    
    for msg in test_messages:
        await clients[0].send_chat(msg)
        await asyncio.sleep(0.5)
    
    # Receive messages
    print("\nStep 6: Receiving messages...")
    await asyncio.gather(*[client.receive_messages(4.0) for client in clients])
    
    # Verify
    print("\n" + "=" * 70)
    print("VERIFICATION: Checking Leader Election Success")
    print("=" * 70)
    
    final_count = len(clients[0].received_messages)
    new_messages = final_count - initial_count
    
    print(f"\nMessages before failure: {initial_count}")
    print(f"Messages after failure:  {new_messages}")
    print(f"Total messages received: {final_count}")
    
    if new_messages >= len(test_messages):
        print(f"\n[PASS] SUCCESS: System recovered from leader failure!")
        print(f"   New leader elected (likely Node 2)")
        print(f"   All {new_messages} post-failure messages delivered")
        success = True
    else:
        print(f"\n[FAIL] FAIL: Only {new_messages}/{len(test_messages)} messages delivered after failure")
        success = False
    
    # Cleanup
    for client in clients:
        await client.close()
    
    return success


if __name__ == "__main__":
    print("\n[WARNING]  PREREQUISITE: Ensure Nodes 1, 2, and 3 are running before starting!")
    print("   Run: python -m src.node --config configs/node{1,2,3}.yml")
    input("\nPress Enter when all nodes are ready...")
    
    try:
        success = asyncio.run(run_demo())
        print("\n\n[WARNING]  NOTE: Restart Node 3 manually if needed:")
        print("   python -m src.node --config configs/node3.yml")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

