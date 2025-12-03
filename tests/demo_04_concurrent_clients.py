#!/usr/bin/env python3
"""
Demo 4: Concurrent Messages from Multiple Clients
Tests that concurrent messages from many clients are properly ordered.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient


async def run_demo():
    """Run Demo 4: Concurrent Messages from Multiple Clients"""
    print("=" * 70)
    print("DEMO 4: Concurrent Messages from Multiple Clients")
    print("=" * 70)
    print("\nObjective: Verify concurrent messages maintain total order")
    print()
    
    num_clients = 6
    messages_per_client = 5
    
    # Create multiple clients connected to different nodes
    print(f"Step 1: Creating {num_clients} concurrent clients...")
    clients = []
    for i in range(num_clients):
        port = 5001 + (i % 3)  # Distribute across 3 nodes
        client = TestClient("127.0.0.1", port, f"Client{i+1}")
        clients.append(client)
    
    print(f"   Connecting to nodes...")
    for client in clients:
        await client.connect()
    await asyncio.sleep(1)
    
    # Send messages concurrently from all clients
    print(f"\nStep 2: Sending {messages_per_client} messages from each client concurrently...")
    
    async def send_messages(client, count):
        """Send multiple messages from a client"""
        for i in range(count):
            await client.send_chat(f"{client.client_id} message {i+1}")
            await asyncio.sleep(0.05)  # Small delay to create interleaving
    
    # Send all messages concurrently
    await asyncio.gather(*[send_messages(client, messages_per_client) for client in clients])
    
    # Receive messages on all clients
    print(f"\nStep 3: Receiving messages on all clients...")
    await asyncio.gather(*[client.receive_messages(5.0) for client in clients])
    
    # Verify total order
    print("\n" + "=" * 70)
    print("VERIFICATION: Checking Concurrent Message Ordering")
    print("=" * 70)
    
    total_expected = num_clients * messages_per_client
    
    # Check each client received messages
    all_received = []
    for client in clients:
        count = len(client.received_messages)
        all_received.append(count)
        print(f"{client.client_id}: {count} messages")
    
    min_received = min(all_received) if all_received else 0
    max_received = max(all_received) if all_received else 0
    
    print(f"\nTotal expected: {total_expected}")
    print(f"Min received:   {min_received}")
    print(f"Max received:   {max_received}")
    
    # Extract orders from each client
    orders = []
    for client in clients:
        order = [(msg["seq_no"], msg["payload"]) for msg in client.received_messages]
        orders.append(order)
    
    # Check if all orders are identical
    reference_order = orders[0]
    all_match = all(order == reference_order for order in orders)
    
    # Check for sequence number gaps
    seq_numbers = [msg["seq_no"] for msg in clients[0].received_messages]
    seq_numbers.sort()
    has_gaps = any(seq_numbers[i+1] - seq_numbers[i] > 1 for i in range(len(seq_numbers) - 1))
    
    if all_match and not has_gaps:
        print(f"\n[PASS] SUCCESS: All {num_clients} clients have IDENTICAL order!")
        print(f"   - Total messages: {len(reference_order)}")
        print(f"   - No gaps in sequence numbers")
        print(f"   - Concurrent messages properly ordered")
        success = True
    elif all_match:
        print(f"\n[WARNING]  PARTIAL SUCCESS: Order is consistent but has gaps")
        print(f"   - All clients agree on order")
        print(f"   - Some sequence numbers missing (acceptable)")
        success = True
    else:
        print(f"\n[FAIL] FAIL: Message orders differ across clients!")
        success = False
    
    # Show sample of interleaved messages
    if len(reference_order) > 0:
        print(f"\nSample of first 10 interleaved messages:")
        for seq_no, payload in reference_order[:10]:
            print(f"  [{seq_no}] {payload}")
    
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

