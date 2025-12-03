#!/usr/bin/env python3
"""
Demo 8: Client Reconnection
Tests that clients can disconnect and reconnect without issues.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.demo_01_basic_messaging import TestClient


async def run_demo():
    """Run Demo 8: Client Reconnection"""
    print("=" * 70)
    print("DEMO 8: Client Reconnection")
    print("=" * 70)
    print("\nObjective: Verify clients can disconnect and reconnect seamlessly")
    print()
    
    # Initial connection
    print("Step 1: Initial connection...")
    client = TestClient("127.0.0.1", 5001, "Client1")
    await client.connect()
    await asyncio.sleep(1)
    
    # Send messages
    print("\nStep 2: Sending messages in first session...")
    for i in range(3):
        await client.send_chat(f"Message {i+1} from first session")
        await asyncio.sleep(0.3)
    
    await client.receive_messages(2.0)
    first_session_count = len(client.received_messages)
    print(f"   Received {first_session_count} messages in first session")
    
    # Disconnect
    print("\nStep 3: Disconnecting client...")
    await client.close()
    await asyncio.sleep(2)
    print("   Client disconnected")
    
    # Reconnect
    print("\nStep 4: Reconnecting same client...")
    client2 = TestClient("127.0.0.1", 5001, "Client1-Reconnected")
    await client2.connect()
    await asyncio.sleep(1)
    print("   Client reconnected successfully")
    
    # Send more messages
    print("\nStep 5: Sending messages in second session...")
    for i in range(3):
        await client2.send_chat(f"Message {i+1} from second session")
        await asyncio.sleep(0.3)
    
    await client2.receive_messages(2.0)
    second_session_count = len(client2.received_messages)
    print(f"   Received {second_session_count} messages in second session")
    
    # Multiple rapid reconnections
    print("\nStep 6: Testing multiple rapid reconnections...")
    await client2.close()
    
    for reconnect_num in range(3):
        print(f"   Reconnection {reconnect_num + 1}...")
        temp_client = TestClient("127.0.0.1", 5002, f"RapidClient{reconnect_num}")
        await temp_client.connect()
        await temp_client.send_chat(f"Rapid reconnect {reconnect_num + 1}")
        await asyncio.sleep(0.5)
        await temp_client.close()
        await asyncio.sleep(0.3)
    
    print("   Completed rapid reconnections")
    
    # Final verification connection
    print("\nStep 7: Final verification connection...")
    client3 = TestClient("127.0.0.1", 5003, "VerificationClient")
    await client3.connect()
    await client3.send_chat("Final verification message")
    await asyncio.sleep(1)
    await client3.receive_messages(3.0)
    
    # Verify
    print("\n" + "=" * 70)
    print("VERIFICATION: Checking Reconnection Success")
    print("=" * 70)
    
    print(f"\nFirst session messages:  {first_session_count}")
    print(f"Second session messages: {second_session_count}")
    print(f"Final session messages:  {len(client3.received_messages)}")
    
    # Check we received messages in all sessions
    all_successful = (
        first_session_count >= 3 and
        second_session_count >= 3 and
        len(client3.received_messages) >= 1
    )
    
    if all_successful:
        print(f"\n[PASS] SUCCESS: Client reconnection working perfectly!")
        print(f"   - First session: {first_session_count} messages")
        print(f"   - Second session: {second_session_count} messages")
        print(f"   - Rapid reconnections: successful")
        print(f"   - No connection errors during reconnects")
        success = True
    else:
        print(f"\n[FAIL] FAIL: Some reconnection issues detected")
        if first_session_count < 3:
            print(f"   - First session incomplete")
        if second_session_count < 3:
            print(f"   - Second session incomplete")
        success = False
    
    # Show all messages received in final session
    if client3.received_messages:
        print(f"\nAll messages visible in final session:")
        for msg in client3.received_messages[-10:]:
            print(f"  [{msg['seq_no']}] {msg['payload']}")
    
    await client3.close()
    
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

