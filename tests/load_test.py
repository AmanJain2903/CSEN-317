#!/usr/bin/env python3
"""
Load Testing Script for Distributed Chat System

Tests system performance under various load conditions:
- Message throughput
- Concurrent clients
- Latency under load
- Resource utilization
"""

import asyncio
import json
import sys
import time
import statistics
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class LoadTestResult:
    """Results from a load test run"""
    test_name: str
    num_clients: int
    messages_sent: int
    messages_received: int
    duration: float
    throughput: float  # msg/s
    latencies: List[float]  # milliseconds
    avg_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    max_latency: float
    errors: int
    success: bool


class LoadTestClient:
    """High-performance test client"""
    
    def __init__(self, client_id: int, host: str, port: int):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.messages_sent = 0
        self.messages_received = 0
        self.send_times: Dict[str, float] = {}
        self.latencies: List[float] = []
        self.errors = 0
        
    async def connect(self):
        """Connect to node"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            return True
        except Exception as e:
            print(f"Client {self.client_id} connection failed: {e}")
            self.errors += 1
            return False
    
    async def send_message(self, msg_num: int):
        """Send a single message"""
        try:
            payload = f"Load test msg {msg_num} from client {self.client_id}"
            msg = {
                "type": "CHAT",
                "sender_id": self.client_id,
                "msg_id": f"load_{self.client_id}_{msg_num}",
                "room_id": "general",
                "payload": payload
            }
            
            send_time = time.time()
            self.send_times[payload] = send_time
            
            data = json.dumps(msg) + "\n"
            self.writer.write(data.encode())
            await self.writer.drain()
            
            self.messages_sent += 1
            
        except Exception as e:
            self.errors += 1
    
    async def receive_loop(self, duration: float):
        """Receive messages for specified duration"""
        end_time = time.time() + duration
        
        try:
            while time.time() < end_time:
                try:
                    line = await asyncio.wait_for(
                        self.reader.readline(), 
                        timeout=0.1
                    )
                    
                    if not line:
                        break
                    
                    receive_time = time.time()
                    msg = json.loads(line.decode())
                    
                    if msg.get("type") == "SEQ_CHAT":
                        self.messages_received += 1
                        
                        # Calculate latency if we sent this
                        payload = msg.get("payload", "")
                        if payload in self.send_times:
                            latency_ms = (receive_time - self.send_times[payload]) * 1000
                            self.latencies.append(latency_ms)
                            del self.send_times[payload]
                            
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    self.errors += 1
                    
        except Exception as e:
            self.errors += 1
    
    async def close(self):
        """Close connection"""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass


async def load_test_sustained_throughput(
    num_clients: int = 10,
    messages_per_client: int = 50,
    rate_limit: float = 0.01  # seconds between messages
) -> LoadTestResult:
    """Test sustained message throughput"""
    
    print(f"\n{'='*70}")
    print(f"LOAD TEST: Sustained Throughput")
    print(f"  Clients: {num_clients}")
    print(f"  Messages per client: {messages_per_client}")
    print(f"  Total messages: {num_clients * messages_per_client}")
    print(f"{'='*70}\n")
    
    # Create clients distributed across nodes
    clients = []
    for i in range(num_clients):
        port = 5001 + (i % 3)
        client = LoadTestClient(i, "127.0.0.1", port)
        clients.append(client)
    
    # Connect all clients
    print("Connecting clients...")
    connect_results = await asyncio.gather(*[c.connect() for c in clients])
    connected = sum(connect_results)
    print(f"Connected: {connected}/{num_clients}")
    
    if connected < num_clients * 0.8:
        print("[FAIL] Too many connection failures")
        return LoadTestResult(
            "sustained_throughput", num_clients, 0, 0, 0, 0, [], 0, 0, 0, 0, 0, 
            num_clients - connected, False
        )
    
    # Start receiving on all clients
    receive_tasks = [c.receive_loop(60.0) for c in clients]
    
    # Send messages
    print(f"Sending {num_clients * messages_per_client} messages...")
    start_time = time.time()
    
    async def send_from_client(client, count):
        for i in range(count):
            await client.send_message(i)
            await asyncio.sleep(rate_limit)
    
    send_tasks = [send_from_client(c, messages_per_client) for c in clients]
    await asyncio.gather(*send_tasks)
    
    # Wait for messages to be received
    print("Waiting for message delivery...")
    await asyncio.sleep(5)
    
    # Stop receiving
    for task in receive_tasks:
        task.cancel()
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Collect results
    total_sent = sum(c.messages_sent for c in clients)
    total_received = sum(c.messages_received for c in clients)
    total_errors = sum(c.errors for c in clients)
    all_latencies = []
    for c in clients:
        all_latencies.extend(c.latencies)
    
    # Calculate statistics
    throughput = total_sent / duration if duration > 0 else 0
    
    if all_latencies:
        all_latencies.sort()
        avg = statistics.mean(all_latencies)
        p50 = all_latencies[len(all_latencies) // 2]
        p95 = all_latencies[int(len(all_latencies) * 0.95)]
        p99 = all_latencies[int(len(all_latencies) * 0.99)]
        max_lat = max(all_latencies)
    else:
        avg = p50 = p95 = p99 = max_lat = 0
    
    # Cleanup
    for client in clients:
        await client.close()
    
    success = (
        total_sent >= num_clients * messages_per_client * 0.9 and
        total_received >= total_sent * 0.8 and
        total_errors < total_sent * 0.1
    )
    
    return LoadTestResult(
        "sustained_throughput",
        num_clients,
        total_sent,
        total_received,
        duration,
        throughput,
        all_latencies,
        avg, p50, p95, p99, max_lat,
        total_errors,
        success
    )


async def load_test_burst_traffic(
    num_clients: int = 20,
    messages_per_client: int = 10
) -> LoadTestResult:
    """Test system under burst load (no rate limiting)"""
    
    print(f"\n{'='*70}")
    print(f"LOAD TEST: Burst Traffic")
    print(f"  Clients: {num_clients}")
    print(f"  Messages per client: {messages_per_client}")
    print(f"  Total messages: {num_clients * messages_per_client}")
    print(f"{'='*70}\n")
    
    # Create clients
    clients = []
    for i in range(num_clients):
        port = 5001 + (i % 3)
        client = LoadTestClient(i, "127.0.0.1", port)
        clients.append(client)
    
    # Connect
    print("Connecting clients...")
    await asyncio.gather(*[c.connect() for c in clients])
    
    # Start receiving
    receive_tasks = [c.receive_loop(30.0) for c in clients]
    
    # Send burst
    print(f"Sending burst of {num_clients * messages_per_client} messages...")
    start_time = time.time()
    
    async def burst_send(client, count):
        for i in range(count):
            await client.send_message(i)
            # No delay - send as fast as possible
    
    await asyncio.gather(*[burst_send(c, messages_per_client) for c in clients])
    
    print("Waiting for delivery...")
    await asyncio.sleep(10)
    
    for task in receive_tasks:
        task.cancel()
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Results
    total_sent = sum(c.messages_sent for c in clients)
    total_received = sum(c.messages_received for c in clients)
    total_errors = sum(c.errors for c in clients)
    all_latencies = []
    for c in clients:
        all_latencies.extend(c.latencies)
    
    throughput = total_sent / duration if duration > 0 else 0
    
    if all_latencies:
        all_latencies.sort()
        avg = statistics.mean(all_latencies)
        p50 = all_latencies[len(all_latencies) // 2]
        p95 = all_latencies[int(len(all_latencies) * 0.95)]
        p99 = all_latencies[int(len(all_latencies) * 0.99)]
        max_lat = max(all_latencies)
    else:
        avg = p50 = p95 = p99 = max_lat = 0
    
    # Cleanup
    for client in clients:
        await client.close()
    
    success = (
        total_sent >= num_clients * messages_per_client * 0.9 and
        total_errors < total_sent * 0.2  # Allow more errors in burst
    )
    
    return LoadTestResult(
        "burst_traffic",
        num_clients,
        total_sent,
        total_received,
        duration,
        throughput,
        all_latencies,
        avg, p50, p95, p99, max_lat,
        total_errors,
        success
    )


async def load_test_concurrent_connections(
    num_clients: int = 50
) -> LoadTestResult:
    """Test maximum concurrent connections"""
    
    print(f"\n{'='*70}")
    print(f"LOAD TEST: Concurrent Connections")
    print(f"  Target clients: {num_clients}")
    print(f"{'='*70}\n")
    
    clients = []
    start_time = time.time()
    
    # Try to connect all clients
    print(f"Connecting {num_clients} clients...")
    for i in range(num_clients):
        port = 5001 + (i % 3)
        client = LoadTestClient(i, "127.0.0.1", port)
        clients.append(client)
    
    results = await asyncio.gather(*[c.connect() for c in clients])
    connected = sum(results)
    
    print(f"Successfully connected: {connected}/{num_clients}")
    
    # Send one message from each connected client
    print("Sending test messages...")
    send_tasks = []
    for client in clients:
        if client.writer:
            send_tasks.append(client.send_message(1))
    
    await asyncio.gather(*send_tasks, return_exceptions=True)
    
    # Receive
    await asyncio.sleep(3)
    receive_tasks = [c.receive_loop(3.0) for c in clients if c.reader]
    await asyncio.gather(*receive_tasks, return_exceptions=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Results
    total_sent = sum(c.messages_sent for c in clients)
    total_received = sum(c.messages_received for c in clients)
    total_errors = sum(c.errors for c in clients)
    
    # Cleanup
    for client in clients:
        await client.close()
    
    success = connected >= num_clients * 0.8
    
    return LoadTestResult(
        "concurrent_connections",
        num_clients,
        total_sent,
        total_received,
        duration,
        0,
        [],
        0, 0, 0, 0, 0,
        total_errors,
        success
    )


def print_results(result: LoadTestResult):
    """Print load test results"""
    print(f"\n{'='*70}")
    print(f"RESULTS: {result.test_name}")
    print(f"{'='*70}")
    
    print(f"\n Messages:")
    print(f"   Sent:     {result.messages_sent}")
    print(f"   Received: {result.messages_received}")
    if result.messages_sent > 0:
        delivery_rate = (result.messages_received / result.messages_sent) * 100
        print(f"   Delivery: {delivery_rate:.1f}%")
    
    print(f"\n Performance:")
    print(f"   Duration:   {result.duration:.2f}s")
    print(f"   Throughput: {result.throughput:.1f} msg/s")
    
    if result.latencies:
        print(f"\n  Latency:")
        print(f"   Average: {result.avg_latency:.2f}ms")
        print(f"   P50:     {result.p50_latency:.2f}ms")
        print(f"   P95:     {result.p95_latency:.2f}ms")
        print(f"   P99:     {result.p99_latency:.2f}ms")
        print(f"   Max:     {result.max_latency:.2f}ms")
    
    print(f"\n[FAIL] Errors: {result.errors}")
    
    status = "[PASS] PASS" if result.success else "[FAIL] FAIL"
    print(f"\n{status}\n")


async def run_all_load_tests():
    """Run all load tests"""
    print("="*70)
    print("DISTRIBUTED CHAT SYSTEM - LOAD TESTING SUITE")
    print("="*70)
    
    results = []
    
    # Test 1: Sustained throughput
    result = await load_test_sustained_throughput(
        num_clients=10,
        messages_per_client=50,
        rate_limit=0.01
    )
    print_results(result)
    results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 2: Burst traffic
    result = await load_test_burst_traffic(
        num_clients=20,
        messages_per_client=10
    )
    print_results(result)
    results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 3: Concurrent connections
    result = await load_test_concurrent_connections(
        num_clients=50
    )
    print_results(result)
    results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("LOAD TEST SUMMARY")
    print("="*70)
    
    for result in results:
        status = "[PASS]" if result.success else "[FAIL]"
        print(f"{status} {result.test_name}")
        print(f"   {result.throughput:.1f} msg/s, {result.messages_received}/{result.messages_sent} delivered")
    
    all_passed = all(r.success for r in results)
    
    if all_passed:
        print(f"\n[PASS] All load tests PASSED")
        return True
    else:
        print(f"\n[FAIL] Some load tests FAILED")
        return False


if __name__ == "__main__":
    print("\n[WARNING]  PREREQUISITE: Ensure Nodes 1, 2, and 3 are running!")
    print("   This test will create heavy load on the system.")
    input("\nPress Enter to start load testing...")
    
    try:
        success = asyncio.run(run_all_load_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nLoad test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Load test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

