"""
P2P Scalability Test
Start multiple peers, have them send messages, verify ordering, and cleanup logs
"""
import asyncio
import random
import argparse
import json
import shutil
import socket
from pathlib import Path
from src.peer import ChatPeer

def is_port_available(port, host='127.0.0.1'):
    """Check if a port is available for binding"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False

def find_available_port(start_port, host='127.0.0.1', max_attempts=100):
    """Find the next available port starting from start_port"""
    for offset in range(max_attempts):
        port = start_port + offset
        if is_port_available(port, host):
            return port
    raise RuntimeError(f"Could not find available port starting from {start_port}")

def allocate_ports(base_port, num_ports, host='127.0.0.1'):
    """Allocate a list of available ports"""
    allocated = []
    current_port = base_port
    
    for i in range(num_ports):
        port = find_available_port(current_port, host)
        allocated.append(port)
        current_port = port + 1
        print(f"  Allocated port {port} for peer {i + 1}")
    
    return allocated

async def run_peer(peer_id, port, num_messages, log_dir, port_range):
    """Run a single peer and send messages"""
    peer = ChatPeer(
        peer_id=peer_id,
        host='127.0.0.1',
        port=port,
        log_dir=log_dir,
        port_range=port_range
    )
    
    await peer.start()
    await asyncio.sleep(2)
    
    for i in range(num_messages):
        await peer.send_chat_message(f"Peer{peer_id}_Msg{i}")
        await asyncio.sleep(random.uniform(0.01, 0.05))
    
    await asyncio.sleep(5)
    await peer.stop()
    
    return peer_id

def load_messages_from_log(log_file):
    """Load messages from a log file"""
    messages = []
    if not log_file.exists():
        return messages
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    messages.append(data)
    except Exception as e:
        print(f"Error loading {log_file}: {e}")
    
    return messages

def verify_logs(log_dir, num_peers):
    """Verify that all log files have the same sequence and ordering"""
    log_path = Path(log_dir)
    
    if not log_path.exists():
        print(f"❌ Log directory {log_dir} does not exist")
        return False
    
    print(f"\n{'='*60}")
    print("VERIFICATION PHASE")
    print(f"{'='*60}")
    
    # Load messages from all peer logs
    peer_messages = {}
    for peer_id in range(1, num_peers + 1):
        log_file = log_path / f"node_{peer_id}_messages.jsonl"
        messages = load_messages_from_log(log_file)
        peer_messages[peer_id] = messages
        print(f"Peer {peer_id}: {len(messages)} messages")
    
    # Check if all peers have messages
    if not all(peer_messages.values()):
        print("\n❌ Some peers have no messages")
        return False
    
    # Check if all peers have the same number of messages
    message_counts = [len(msgs) for msgs in peer_messages.values()]
    if len(set(message_counts)) > 1:
        print(f"\n⚠️  Warning: Different message counts: {message_counts}")
        print("This might be expected if some peers joined late or left early")
    
    # Compare sequences
    print("\nVerifying message sequences...")
    reference_peer = 1
    reference_messages = peer_messages[reference_peer]
    
    if not reference_messages:
        print(f"❌ Reference peer {reference_peer} has no messages")
        return False
    
    # Sort messages by sequence number
    reference_seq = sorted(reference_messages, key=lambda m: m['seq_no'])
    
    all_match = True
    for peer_id, messages in peer_messages.items():
        if peer_id == reference_peer:
            continue
        
        peer_seq = sorted(messages, key=lambda m: m['seq_no'])
        
        # Compare common messages
        common_length = min(len(reference_seq), len(peer_seq))
        
        mismatches = 0
        for i in range(common_length):
            ref_msg = reference_seq[i]
            peer_msg = peer_seq[i]
            
            if ref_msg['seq_no'] != peer_msg['seq_no']:
                print(f"❌ Peer {peer_id}: Sequence mismatch at index {i}")
                print(f"   Reference: seq_no={ref_msg['seq_no']}")
                print(f"   Peer {peer_id}: seq_no={peer_msg['seq_no']}")
                mismatches += 1
                all_match = False
            elif ref_msg['text'] != peer_msg['text']:
                print(f"❌ Peer {peer_id}: Content mismatch at seq_no={ref_msg['seq_no']}")
                print(f"   Reference: {ref_msg['text']}")
                print(f"   Peer {peer_id}: {peer_msg['text']}")
                mismatches += 1
                all_match = False
        
        if mismatches == 0:
            print(f"✅ Peer {peer_id}: All {common_length} messages match")
        else:
            print(f"❌ Peer {peer_id}: {mismatches} mismatches found")
    
    if all_match:
        print(f"\n{'='*60}")
        print("✅ SUCCESS: All peers have consistent message ordering!")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("❌ FAILURE: Message ordering inconsistencies detected")
        print(f"{'='*60}")
    
    return all_match

def cleanup_logs(log_dir):
    """Delete all log files"""
    log_path = Path(log_dir)
    
    if not log_path.exists():
        print(f"\nNo logs to clean up at {log_dir}")
        return
    
    print(f"\nCleaning up logs in {log_dir}...")
    
    try:
        # Remove all .jsonl files
        for log_file in log_path.glob("*.jsonl"):
            log_file.unlink()
            print(f"  Deleted: {log_file.name}")
        
        # Remove the directory if it's empty
        if not any(log_path.iterdir()):
            log_path.rmdir()
            print(f"  Removed empty directory: {log_dir}")
        
        print("✅ Cleanup complete")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

async def main():
    parser = argparse.ArgumentParser(description='P2P Scalability Test')
    parser.add_argument('num_peers', type=int, help='Number of peers to start')
    parser.add_argument('messages_per_peer', type=int, help='Number of messages each peer sends')
    parser.add_argument('--base-port', type=int, default=7000, help='Base port number (default: 7000)')
    parser.add_argument('--log-dir', type=str, default='data/p2p_logs', help='Log directory (default: data/p2p_logs)')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip log cleanup after verification')
    
    args = parser.parse_args()
    
    num_peers = args.num_peers
    messages_per_peer = args.messages_per_peer
    base_port = args.base_port
    log_dir = args.log_dir
    
    # Cleanup old logs before starting
    print("Cleaning up old logs before starting...")
    cleanup_logs(log_dir)
    
    print(f"\n{'='*60}")
    print(f"STARTING SCALABILITY TEST")
    print(f"{'='*60}")
    print(f"Number of peers: {num_peers}")
    print(f"Messages per peer: {messages_per_peer}")
    print(f"Base port: {base_port}")
    print(f"{'='*60}")
    
    # Allocate available ports
    print("\nAllocating ports...")
    try:
        ports = allocate_ports(base_port, num_peers)
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        return 1
    
    # Calculate port range for auto-discovery
    min_port = min(ports)
    max_port = max(ports)
    port_range = (min_port, max_port)
    
    print(f"\nPort range for discovery: {min_port} - {max_port}")
    print(f"Total expected messages: {num_peers * messages_per_peer}")
    print(f"{'='*60}\n")
    
    tasks = []
    for i in range(num_peers):
        peer_id = i + 1
        port = ports[i]
        tasks.append(run_peer(peer_id, port, messages_per_peer, log_dir, port_range))
    
    print("Starting all peers...")
    results = await asyncio.gather(*tasks)
    
    print(f"\n{'='*60}")
    print(f"All {len(results)} peers completed")
    print(f"{'='*60}")
    
    # Wait a bit for any pending writes
    await asyncio.sleep(2)
    
    # Verify logs
    verification_passed = verify_logs(log_dir, num_peers)
    
    # Cleanup logs
    if not args.no_cleanup:
        cleanup_logs(log_dir)
    else:
        print(f"\nLogs preserved in {log_dir} (use --no-cleanup flag was set)")
    
    return 0 if verification_passed else 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
