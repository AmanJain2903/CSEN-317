#!/usr/bin/env python3
"""
Demo 3: Leader Rejoining as Follower
Tests that a crashed leader rejoins as follower and catches up.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient
from tests.demo_02_leader_failure import kill_node


async def run_demo():
    """Run Demo 3: Leader Rejoining as Follower"""
    print("=" * 70)
    print("DEMO 3: Leader Rejoining as Follower")
    print("=" * 70)
    print("\nObjective: Verify crashed leader rejoins as follower and catches up")
    print()
    
    # Connect to nodes
    clients = [
        TestClient("127.0.0.1", 5001, "Client1"),
        TestClient("127.0.0.1", 5002, "Client2"),
    ]
    
    print("Step 1: Connecting to Node 1 and Node 2...")
    for client in clients:
        await client.connect()
    await asyncio.sleep(1)
    
    # Send messages before killing leader
    print("\nStep 2: Sending messages with Node 3 alive...")
    for i in range(3):
        await clients[0].send_chat(f"Message {i+1} before crash")
        await asyncio.sleep(0.3)
    
    await asyncio.gather(*[client.receive_messages(2.0) for client in clients])
    count_before = len(clients[0].received_messages)
    print(f"   Received {count_before} messages")
    
    # Kill Node 3
    print("\nStep 3: Killing Node 3 (leader)...")
    await kill_node(3)
    await asyncio.sleep(4)  # Wait for election
    
    # Send messages while Node 3 is down
    print("\nStep 4: Sending messages while Node 3 is down...")
    for i in range(3):
        await clients[0].send_chat(f"Message {i+1} while down")
        await asyncio.sleep(0.3)
    
    await asyncio.gather(*[client.receive_messages(2.0) for client in clients])
    count_during = len(clients[0].received_messages) - count_before
    print(f"   Sent {count_during} messages while Node 3 was down")
    
    # Manual step: Restart Node 3
    print("\n" + "=" * 70)
    print("MANUAL ACTION REQUIRED")
    print("=" * 70)
    print("\n Please restart Node 3 now:")
    print("   python -m src.node --config configs/node3.yml")
    print("\nWaiting 10 seconds for Node 3 to rejoin and catch up...")
    input("Press Enter after restarting Node 3...")
    
    await asyncio.sleep(10)  # Wait for rejoin and catch-up
    
    # Connect client to Node 3 to verify it caught up
    print("\nStep 5: Connecting to Node 3 to verify catch-up...")
    client3 = TestClient("127.0.0.1", 5003, "Client3")
    try:
        await client3.connect()
        
        # Send a new message
        await client3.send_chat("Test message after rejoin")
        await asyncio.sleep(1)
        
        # Receive messages on Node 3
        await client3.receive_messages(3.0)
        
        # Verify
        print("\n" + "=" * 70)
        print("VERIFICATION: Checking Catch-up Success")
        print("=" * 70)
        
        node3_messages = len(client3.received_messages)
        expected_minimum = count_before + count_during
        
        print(f"\nNode 3 received: {node3_messages} messages")
        print(f"Expected minimum: {expected_minimum} messages")
        
        if node3_messages >= expected_minimum:
            print(f"\n[PASS] SUCCESS: Node 3 rejoined as follower and caught up!")
            print(f"   - Received all {expected_minimum}+ historical messages")
            print(f"   - Now functioning as follower")
            success = True
        else:
            print(f"\n[FAIL] FAIL: Node 3 only received {node3_messages}/{expected_minimum} messages")
            success = False
        
        await client3.close()
    except Exception as e:
        print(f"\n[FAIL] FAIL: Could not connect to Node 3: {e}")
        print("   Ensure Node 3 is running and rejoined successfully")
        success = False
    
    # Cleanup
    for client in clients:
        await client.close()
    
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

