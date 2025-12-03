#!/usr/bin/env python3
"""
Demo 1: Basic Messaging and Total Order
Tests that messages sent from multiple clients are delivered in the same order on all nodes.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transport import TransportLayer


class TestClient:
    """Simple test client for sending/receiving messages"""
    
    def __init__(self, host: str, port: int, client_id: str):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.transport = TransportLayer(node_id=0, host="0.0.0.0", port=0)
        self.received_messages = []
        self.reader = None
        self.writer = None
        
    async def connect(self):
        """Connect to node"""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"[{self.client_id}] Connected to {self.host}:{self.port}")
        
    async def send_chat(self, text: str):
        """Send CHAT message"""
        msg = {
            "type": "CHAT",
            "sender_id": 0,
            "msg_id": f"{self.client_id}_{len(self.received_messages)}",
            "room_id": "general",
            "payload": text
        }
        data = json.dumps(msg) + "\n"
        self.writer.write(data.encode())
        await self.writer.drain()
        print(f"[{self.client_id}] Sent: {text}")
        
    async def receive_messages(self, duration: float = 3.0):
        """Receive messages for specified duration"""
        try:
            end_time = asyncio.get_event_loop().time() + duration
            while asyncio.get_event_loop().time() < end_time:
                try:
                    line = await asyncio.wait_for(self.reader.readline(), timeout=0.5)
                    if not line:
                        break
                    msg = json.loads(line.decode())
                    if msg.get("type") == "SEQ_CHAT":
                        self.received_messages.append(msg)
                        print(f"[{self.client_id}] Received [{msg['seq_no']}]: {msg['payload']}")
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            print(f"[{self.client_id}] Error receiving: {e}")
            
    async def close(self):
        """Close connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


async def run_demo():
    """Run Demo 1: Basic Messaging and Total Order"""
    print("=" * 70)
    print("DEMO 1: Basic Messaging and Total Order")
    print("=" * 70)
    print("\nObjective: Verify all nodes deliver messages in the same order")
    print()
    
    # Connect to all three nodes
    clients = [
        TestClient("127.0.0.1", 5001, "Client1"),
        TestClient("127.0.0.1", 5002, "Client2"),
        TestClient("127.0.0.1", 5003, "Client3"),
    ]
    
    # Connect all clients
    print("Step 1: Connecting clients to all nodes...")
    for client in clients:
        await client.connect()
    await asyncio.sleep(1)
    
    # Send messages from each client
    print("\nStep 2: Sending messages from all clients...")
    messages_to_send = [
        (clients[0], "Hello from Node 1"),
        (clients[1], "Hello from Node 2"),
        (clients[2], "Hello from Node 3"),
        (clients[0], "Second message from Node 1"),
        (clients[1], "Second message from Node 2"),
    ]
    
    for client, text in messages_to_send:
        await client.send_chat(text)
        await asyncio.sleep(0.2)  # Small delay between messages
    
    # Receive messages on all clients
    print("\nStep 3: Receiving messages on all clients...")
    await asyncio.gather(*[client.receive_messages(5.0) for client in clients])
    
    # Verify total order
    print("\n" + "=" * 70)
    print("VERIFICATION: Checking Total Order")
    print("=" * 70)
    
    if not all(client.received_messages for client in clients):
        print("[FAIL] FAIL: Some clients received no messages")
        for i, client in enumerate(clients):
            print(f"  {client.client_id}: {len(client.received_messages)} messages")
        return False
    
    # Extract sequence numbers and payloads
    orders = []
    for client in clients:
        order = [(msg["seq_no"], msg["payload"]) for msg in client.received_messages]
        orders.append(order)
        print(f"\n{client.client_id} order:")
        for seq_no, payload in order:
            print(f"  [{seq_no}] {payload}")
    
    # Check if all orders are identical
    reference_order = orders[0]
    all_match = all(order == reference_order for order in orders)
    
    if all_match:
        print(f"\n[PASS] SUCCESS: All {len(clients)} clients have IDENTICAL message order!")
        print(f"   Total messages: {len(reference_order)}")
        return True
    else:
        print("\n[FAIL] FAIL: Message orders differ across clients!")
        for i, order in enumerate(orders):
            if order != reference_order:
                print(f"  {clients[i].client_id} differs from Client1")
        return False
    
    # Cleanup
    for client in clients:
        await client.close()


if __name__ == "__main__":
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

