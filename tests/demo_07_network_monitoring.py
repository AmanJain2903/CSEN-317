#!/usr/bin/env python3
"""
Demo 7: Network Monitoring
Tests network statistics and monitors message latency, throughput, etc.
"""

import asyncio
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient


class MonitoringClient(TestClient):
    """Extended client with monitoring capabilities"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_times = {}
        self.latencies = []
        
    async def send_chat_monitored(self, text: str):
        """Send message and record timestamp"""
        msg_id = f"{self.client_id}_{len(self.send_times)}"
        send_time = time.time()
        self.send_times[text] = send_time
        
        await self.send_chat(text)
        
    async def receive_messages_monitored(self, duration: float = 3.0):
        """Receive messages and calculate latencies"""
        try:
            end_time = asyncio.get_event_loop().time() + duration
            while asyncio.get_event_loop().time() < end_time:
                try:
                    line = await asyncio.wait_for(self.reader.readline(), timeout=0.5)
                    if not line:
                        break
                    
                    receive_time = time.time()
                    msg = json.loads(line.decode())
                    
                    if msg.get("type") == "SEQ_CHAT":
                        self.received_messages.append(msg)
                        
                        # Calculate latency if we sent this message
                        payload = msg["payload"]
                        if payload in self.send_times:
                            latency = (receive_time - self.send_times[payload]) * 1000  # ms
                            self.latencies.append(latency)
                        
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            print(f"[{self.client_id}] Error: {e}")


async def run_demo():
    """Run Demo 7: Network Monitoring"""
    print("=" * 70)
    print("DEMO 7: Network Monitoring")
    print("=" * 70)
    print("\nObjective: Monitor network performance and message statistics")
    print()
    
    # Create monitoring clients
    clients = [
        MonitoringClient("127.0.0.1", 5001, "Monitor1"),
        MonitoringClient("127.0.0.1", 5002, "Monitor2"),
        MonitoringClient("127.0.0.1", 5003, "Monitor3"),
    ]
    
    print("Step 1: Connecting monitoring clients...")
    for client in clients:
        await client.connect()
    await asyncio.sleep(1)
    
    # Send test messages and measure
    print("\nStep 2: Sending messages and measuring latency...")
    num_messages = 20
    
    start_time = time.time()
    
    for i in range(num_messages):
        client = clients[i % len(clients)]
        msg = f"Monitored message {i+1}"
        await client.send_chat_monitored(msg)
        await asyncio.sleep(0.1)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Receive messages
    print("\nStep 3: Receiving and analyzing...")
    import json  # Need this for MonitoringClient
    await asyncio.gather(*[client.receive_messages_monitored(4.0) for client in clients])
    
    # Collect statistics
    print("\n" + "=" * 70)
    print("NETWORK STATISTICS")
    print("=" * 70)
    
    total_received = sum(len(c.received_messages) for c in clients)
    total_latency_samples = sum(len(c.latencies) for c in clients)
    
    print(f"\n Message Statistics:")
    print(f"   Messages sent:     {num_messages}")
    print(f"   Messages received: {total_received}")
    print(f"   Send duration:     {duration:.2f}s")
    print(f"   Throughput:        {num_messages/duration:.1f} msg/s")
    
    print(f"\n  Latency Statistics:")
    if total_latency_samples > 0:
        all_latencies = []
        for client in clients:
            all_latencies.extend(client.latencies)
        
        all_latencies.sort()
        avg_latency = sum(all_latencies) / len(all_latencies)
        min_latency = min(all_latencies)
        max_latency = max(all_latencies)
        p50 = all_latencies[len(all_latencies) // 2]
        p95 = all_latencies[int(len(all_latencies) * 0.95)]
        p99 = all_latencies[int(len(all_latencies) * 0.99)]
        
        print(f"   Samples:      {total_latency_samples}")
        print(f"   Min:          {min_latency:.2f}ms")
        print(f"   Max:          {max_latency:.2f}ms")
        print(f"   Average:      {avg_latency:.2f}ms")
        print(f"   P50 (median): {p50:.2f}ms")
        print(f"   P95:          {p95:.2f}ms")
        print(f"   P99:          {p99:.2f}ms")
    else:
        print("   No latency samples (clients sent to other nodes)")
    
    print(f"\n Per-Client Statistics:")
    for client in clients:
        print(f"   {client.client_id}:")
        print(f"     Received:  {len(client.received_messages)} messages")
        if client.latencies:
            print(f"     Latency:   {sum(client.latencies)/len(client.latencies):.2f}ms avg")
    
    # Verify
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    success = True
    
    if total_received >= num_messages:
        print(f"\n[PASS] All messages delivered successfully")
    else:
        print(f"\n[WARNING]  Only {total_received}/{num_messages} messages delivered")
        success = False
    
    if total_latency_samples > 0 and avg_latency < 1000:
        print(f"[PASS] Average latency acceptable ({avg_latency:.2f}ms < 1000ms)")
    elif total_latency_samples > 0:
        print(f"[WARNING]  Average latency high ({avg_latency:.2f}ms)")
    
    if num_messages / duration > 5:
        print(f"[PASS] Throughput acceptable ({num_messages/duration:.1f} msg/s)")
    else:
        print(f"[WARNING]  Throughput low ({num_messages/duration:.1f} msg/s)")
    
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

