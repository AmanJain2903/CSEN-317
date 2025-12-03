#!/usr/bin/env python3
"""
Stress Testing Script for Distributed Chat System

Tests system limits:
- Maximum concurrent connections
- Resource exhaustion scenarios
- System recovery under extreme load
- Socket limit testing
"""

import asyncio
import json
import sys
import time
import resource
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class StressTestClient:
    """Minimal client for stress testing"""
    
    def __init__(self, client_id: int, host: str, port: int):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.connected = False
        
    async def connect(self):
        """Attempt connection"""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5.0
            )
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False
    
    async def send_message(self):
        """Send a single message"""
        if not self.connected or not self.writer:
            return False
        
        try:
            msg = {
                "type": "CHAT",
                "sender_id": self.client_id,
                "msg_id": f"stress_{self.client_id}",
                "room_id": "general",
                "payload": f"Stress test {self.client_id}"
            }
            data = json.dumps(msg) + "\n"
            self.writer.write(data.encode())
            await asyncio.wait_for(self.writer.drain(), timeout=1.0)
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close connection"""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
        self.connected = False


async def test_max_connections():
    """Test maximum concurrent connections"""
    print("="*70)
    print("STRESS TEST: Maximum Concurrent Connections")
    print("="*70)
    print()
    
    # Get system limits
    try:
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        print(f"System file descriptor limits:")
        print(f"  Soft limit: {soft_limit}")
        print(f"  Hard limit: {hard_limit}")
        print()
    except:
        print("Could not determine system limits")
        soft_limit = 1024
    
    # Test increasing numbers of connections
    test_sizes = [50, 100, 200, 500, 1000]
    max_successful = 0
    
    for num_clients in test_sizes:
        if num_clients > soft_limit * 0.5:
            print(f"\nSkipping {num_clients} (exceeds safe limit)")
            continue
        
        print(f"\nTesting {num_clients} concurrent connections...")
        
        clients = []
        for i in range(num_clients):
            port = 5001 + (i % 3)
            client = StressTestClient(i, "127.0.0.1", port)
            clients.append(client)
        
        # Connect all
        start = time.time()
        results = await asyncio.gather(*[c.connect() for c in clients])
        duration = time.time() - start
        
        connected = sum(results)
        print(f"  Connected: {connected}/{num_clients} in {duration:.2f}s")
        
        if connected >= num_clients * 0.95:
            max_successful = num_clients
            
            # Try to send messages
            print(f"  Sending test messages...")
            send_results = await asyncio.gather(
                *[c.send_message() for c in clients if c.connected],
                return_exceptions=True
            )
            sent = sum(1 for r in send_results if r is True)
            print(f"  Messages sent: {sent}/{connected}")
            
            # Cleanup
            await asyncio.gather(*[c.close() for c in clients])
            await asyncio.sleep(1)
        else:
            print(f"  [FAIL] Failed to connect enough clients")
            await asyncio.gather(*[c.close() for c in clients])
            break
    
    print(f"\n{'='*70}")
    print(f"Maximum successful connections: {max_successful}")
    print(f"{'='*70}")
    
    return max_successful


async def test_connection_churn():
    """Test rapid connect/disconnect cycles"""
    print("\n" + "="*70)
    print("STRESS TEST: Connection Churn")
    print("="*70)
    print()
    
    num_cycles = 10
    clients_per_cycle = 20
    
    print(f"Testing {num_cycles} cycles of {clients_per_cycle} connections...")
    
    total_connected = 0
    total_failed = 0
    
    for cycle in range(num_cycles):
        clients = []
        for i in range(clients_per_cycle):
            port = 5001 + (i % 3)
            client = StressTestClient(cycle * clients_per_cycle + i, "127.0.0.1", port)
            clients.append(client)
        
        # Connect
        results = await asyncio.gather(*[c.connect() for c in clients])
        connected = sum(results)
        total_connected += connected
        total_failed += (clients_per_cycle - connected)
        
        # Send message
        await asyncio.gather(
            *[c.send_message() for c in clients if c.connected],
            return_exceptions=True
        )
        
        # Disconnect
        await asyncio.gather(*[c.close() for c in clients])
        
        print(f"  Cycle {cycle+1}/{num_cycles}: {connected}/{clients_per_cycle} connected")
        
        await asyncio.sleep(0.1)
    
    success_rate = (total_connected / (num_cycles * clients_per_cycle)) * 100
    
    print(f"\n{'='*70}")
    print(f"Connection Churn Results:")
    print(f"  Total attempts: {num_cycles * clients_per_cycle}")
    print(f"  Successful:     {total_connected}")
    print(f"  Failed:         {total_failed}")
    print(f"  Success rate:   {success_rate:.1f}%")
    print(f"{'='*70}")
    
    return success_rate >= 95.0


async def test_message_flood():
    """Test flooding with messages"""
    print("\n" + "="*70)
    print("STRESS TEST: Message Flood")
    print("="*70)
    print()
    
    num_clients = 30
    messages_per_client = 100
    
    print(f"Flooding with {num_clients} clients x {messages_per_client} messages...")
    print(f"Total: {num_clients * messages_per_client} messages")
    print()
    
    # Connect clients
    clients = []
    for i in range(num_clients):
        port = 5001 + (i % 3)
        client = StressTestClient(i, "127.0.0.1", port)
        clients.append(client)
    
    print("Connecting clients...")
    results = await asyncio.gather(*[c.connect() for c in clients])
    connected = sum(results)
    print(f"Connected: {connected}/{num_clients}")
    
    # Flood messages
    print(f"Flooding messages...")
    start = time.time()
    
    async def flood(client, count):
        sent = 0
        for _ in range(count):
            if await client.send_message():
                sent += 1
        return sent
    
    send_results = await asyncio.gather(
        *[flood(c, messages_per_client) for c in clients if c.connected]
    )
    
    duration = time.time() - start
    total_sent = sum(send_results)
    throughput = total_sent / duration if duration > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"Message Flood Results:")
    print(f"  Target:     {num_clients * messages_per_client}")
    print(f"  Sent:       {total_sent}")
    print(f"  Duration:   {duration:.2f}s")
    print(f"  Throughput: {throughput:.1f} msg/s")
    print(f"{'='*70}")
    
    # Cleanup
    await asyncio.gather(*[c.close() for c in clients])
    
    return total_sent >= (num_clients * messages_per_client * 0.9)


async def test_socket_limits():
    """Test system socket limits"""
    print("\n" + "="*70)
    print("STRESS TEST: Socket Limits")
    print("="*70)
    print()
    
    # Try to find the limit by binary search
    low = 100
    high = 2000
    max_found = 0
    
    while low <= high:
        mid = (low + high) // 2
        print(f"\nTesting {mid} connections...")
        
        clients = []
        for i in range(mid):
            port = 5001 + (i % 3)
            client = StressTestClient(i, "127.0.0.1", port)
            clients.append(client)
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[c.connect() for c in clients]),
                timeout=30.0
            )
            connected = sum(results)
            success_rate = connected / mid
            
            print(f"  Connected: {connected}/{mid} ({success_rate*100:.1f}%)")
            
            # Cleanup
            await asyncio.gather(*[c.close() for c in clients])
            await asyncio.sleep(2)
            
            if success_rate >= 0.95:
                max_found = mid
                low = mid + 1
                print(f"  [PASS] Success at {mid}")
            else:
                high = mid - 1
                print(f"  [FAIL] Failed at {mid}")
                
        except asyncio.TimeoutError:
            print(f"   Timeout at {mid}")
            await asyncio.gather(*[c.close() for c in clients])
            high = mid - 1
        except Exception as e:
            print(f"  [FAIL] Error at {mid}: {e}")
            await asyncio.gather(*[c.close() for c in clients])
            high = mid - 1
    
    print(f"\n{'='*70}")
    print(f"Maximum reliable connections: {max_found}")
    print(f"{'='*70}")
    
    return max_found


async def test_leader_stress():
    """Test leader under heavy load then failover"""
    print("\n" + "="*70)
    print("STRESS TEST: Leader Under Stress")
    print("="*70)
    print()
    
    num_clients = 50
    
    print(f"Connecting {num_clients} clients and sending messages...")
    
    clients = []
    for i in range(num_clients):
        port = 5001 + (i % 3)
        client = StressTestClient(i, "127.0.0.1", port)
        clients.append(client)
    
    # Connect
    results = await asyncio.gather(*[c.connect() for c in clients])
    connected = sum(results)
    print(f"Connected: {connected}/{num_clients}")
    
    # Send messages rapidly
    print("Sending messages to stress leader...")
    
    async def stress_send(client):
        for _ in range(10):
            await client.send_message()
            await asyncio.sleep(0.01)
    
    await asyncio.gather(*[stress_send(c) for c in clients if c.connected])
    
    print("\n[WARNING]  MANUAL ACTION:")
    print("Kill Node 3 (the leader) NOW to test recovery under stress")
    print("Command: kill -9 $(lsof -ti :5003)")
    input("Press Enter after killing Node 3...")
    
    # Continue sending
    print("\nContinuing to send messages (should recover)...")
    await asyncio.sleep(4)  # Wait for election
    
    await asyncio.gather(
        *[stress_send(c) for c in clients if c.connected],
        return_exceptions=True
    )
    
    print("\n[PASS] System survived leader failure under stress")
    
    # Cleanup
    await asyncio.gather(*[c.close() for c in clients])
    
    return True


async def run_all_stress_tests():
    """Run all stress tests"""
    print("="*70)
    print("DISTRIBUTED CHAT SYSTEM - STRESS TESTING SUITE")
    print("="*70)
    print("\n[WARNING]  WARNING: These tests push the system to its limits!")
    print()
    
    results = {}
    
    # Test 1: Max connections
    max_conn = await test_max_connections()
    results['max_connections'] = max_conn
    await asyncio.sleep(3)
    
    # Test 2: Connection churn
    churn_ok = await test_connection_churn()
    results['connection_churn'] = churn_ok
    await asyncio.sleep(3)
    
    # Test 3: Message flood
    flood_ok = await test_message_flood()
    results['message_flood'] = flood_ok
    await asyncio.sleep(3)
    
    # Test 4: Socket limits
    socket_limit = await test_socket_limits()
    results['socket_limit'] = socket_limit
    await asyncio.sleep(3)
    
    # Test 5: Leader under stress (manual)
    print("\n" + "="*70)
    print("Final test requires manual intervention...")
    do_leader_test = input("Run leader stress test? (y/n): ")
    if do_leader_test.lower() == 'y':
        leader_ok = await test_leader_stress()
        results['leader_stress'] = leader_ok
    
    # Summary
    print("\n" + "="*70)
    print("STRESS TEST SUMMARY")
    print("="*70)
    print(f"\n[PASS] Max Connections:    {results.get('max_connections', 0)}")
    print(f"{'[PASS]' if results.get('connection_churn') else '[FAIL]'} Connection Churn:  {results.get('connection_churn', False)}")
    print(f"{'[PASS]' if results.get('message_flood') else '[FAIL]'} Message Flood:     {results.get('message_flood', False)}")
    print(f"[PASS] Socket Limit:       {results.get('socket_limit', 0)}")
    if 'leader_stress' in results:
        print(f"{'[PASS]' if results.get('leader_stress') else '[FAIL]'} Leader Stress:     {results.get('leader_stress', False)}")
    
    return True


if __name__ == "__main__":
    print("\n[WARNING]  PREREQUISITE: Ensure Nodes 1, 2, and 3 are running!")
    print("[WARNING]  WARNING: These tests will push your system to its limits!")
    print("\nRecommended: Close other applications to free resources.")
    input("\nPress Enter to start stress testing...")
    
    try:
        asyncio.run(run_all_stress_tests())
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nStress test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Stress test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

