#!/usr/bin/env python3
"""
Demo 5: Out-of-Order Message Handling
Tests that nodes can handle out-of-order message delivery and buffer correctly.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient


async def run_demo():
    """Run Demo 5: Out-of-Order Message Handling"""
    print("=" * 70)
    print("DEMO 5: Out-of-Order Message Handling")
    print("=" * 70)
    print("\nObjective: Verify nodes handle out-of-order messages with buffering")
    print()
    
    print("NOTE: Out-of-order handling is internal to nodes.")
    print("      This demo verifies eventual consistent ordering despite network delays.")
    print()
    
    # Create clients with varying delays
    clients = [
        TestClient("127.0.0.1", 5001, "Client1"),
        TestClient("127.0.0.1", 5002, "Client2"),
        TestClient("127.0.0.1", 5003, "Client3"),
    ]
    
    print("Step 1: Connecting clients to all nodes...")
    for client in clients:
        await client.connect()
    await asyncio.sleep(1)
    
    # Send burst of messages rapidly
    print("\nStep 2: Sending rapid burst of messages (may arrive out of order)...")
    messages = [
        f"Burst message {i+1}" for i in range(10)
    ]
    
    for msg in messages:
        await clients[0].send_chat(msg)
        # Very small delay - messages may arrive out of order
        await asyncio.sleep(0.01)
    
    print(f"   Sent {len(messages)} messages in rapid succession")
    
    # Wait for all messages to be delivered
    print("\nStep 3: Waiting for all nodes to deliver messages in order...")
    await asyncio.sleep(3)
    
    # Receive messages on all clients
    await asyncio.gather(*[client.receive_messages(3.0) for client in clients])
    
    # Verify
    print("\n" + "=" * 70)
    print("VERIFICATION: Checking Message Delivery Order")
    print("=" * 70)
    
    # Check each client
    for client in clients:
        count = len(client.received_messages)
        print(f"\n{client.client_id}: {count} messages")
        
        if count > 0:
            # Check sequence numbers are monotonic
            seq_numbers = [msg["seq_no"] for msg in client.received_messages]
            is_monotonic = all(seq_numbers[i] < seq_numbers[i+1] for i in range(len(seq_numbers) - 1))
            
            print(f"  Sequence numbers: {seq_numbers[:10]}{'...' if len(seq_numbers) > 10 else ''}")
            print(f"  Monotonically increasing: {'✓' if is_monotonic else '✗'}")
    
    # Extract orders
    orders = []
    for client in clients:
        order = [(msg["seq_no"], msg["payload"]) for msg in client.received_messages]
        orders.append(order)
    
    # Check if all orders match
    reference_order = orders[0]
    all_match = all(order == reference_order for order in orders)
    
    # Check sequence numbers are monotonic
    all_monotonic = True
    for client in clients:
        seq_nums = [msg["seq_no"] for msg in client.received_messages]
        if not all(seq_nums[i] < seq_nums[i+1] for i in range(len(seq_nums) - 1)):
            all_monotonic = False
            break
    
    if all_match and all_monotonic:
        print(f"\n[PASS] SUCCESS: Out-of-order messages handled correctly!")
        print(f"   - All nodes have identical order")
        print(f"   - Sequence numbers are monotonically increasing")
        print(f"   - Buffering mechanism working properly")
        success = True
    else:
        print(f"\n[FAIL] FAIL: Order inconsistency detected")
        if not all_match:
            print("   - Nodes have different message orders")
        if not all_monotonic:
            print("   - Sequence numbers not monotonic on some nodes")
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

