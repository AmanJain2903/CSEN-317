"""
Peer TUI - Terminal User Interface for P2P chat
Each instance is a full peer in the distributed system
"""
import asyncio
import argparse
import sys
import aioconsole

from .peer import ChatPeer
from .common import ChatMessage


class PeerTUI:
    """Terminal UI for a peer node"""
    
    def __init__(self, peer: ChatPeer):
        self.peer = peer
        self.running = False
        
    def on_message_delivered(self, msg: ChatMessage):
        """Callback when a message is delivered"""
        print(f"\r[seq={msg.seq_no}] <peer_{msg.sender_id}>: {msg.text}")
        print(f"peer_{self.peer.peer_id}> ", end='', flush=True)
        
    async def start(self):
        """Start the TUI"""
        self.running = True
        self.peer.set_message_callback(self.on_message_delivered)
        
        await self.peer.start()
        
        print(f"\n{'='*60}")
        print(f"P2P Distributed Chat - Peer {self.peer.peer_id}")
        print(f"Listening on {self.peer.host}:{self.peer.port}")
        print(f"Role: {self.peer.role.value}")
        print(f"{'='*60}")
        print("Commands:")
        print("  Type your message and press Enter to send")
        print("  /quit - Exit the chat")
        print("  /status - Show peer status")
        print(f"{'='*60}\n")
        
        await self.input_loop()
    
    async def input_loop(self):
        """Main input loop"""
        while self.running:
            try:
                text = await aioconsole.ainput(f"peer_{self.peer.peer_id}> ")
                
                if not text:
                    continue
                
                if text.startswith('/'):
                    await self.handle_command(text)
                else:
                    await self.peer.send_chat_message(text)
                        
            except (EOFError, KeyboardInterrupt):
                break
        
        await self.peer.stop()
    
    async def handle_command(self, cmd: str):
        """Handle special commands"""
        if cmd == '/quit':
            print("Exiting...")
            self.running = False
        elif cmd == '/status':
            self.print_status()
        else:
            print(f"Unknown command: {cmd}")
    
    def print_status(self):
        """Print peer status"""
        print(f"\nPeer Status:")
        print(f"  Peer ID: {self.peer.peer_id}")
        print(f"  Role: {self.peer.role.value}")
        print(f"  Term: {self.peer.current_term}")
        print(f"  Address: {self.peer.host}:{self.peer.port}")
        
        leader = self.peer.membership.get_leader()
        if leader:
            print(f"  Leader: peer_{leader.node_id}")
        else:
            print(f"  Leader: Unknown")
        
        peers = self.peer.membership.get_all_peers()
        print(f"  Known peers: {len(peers)}")
        for p in peers:
            if p.node_id != self.peer.peer_id:
                print(f"    - peer_{p.node_id} at {p.host}:{p.port}")
        print()


async def main():
    parser = argparse.ArgumentParser(description='P2P Distributed Chat Peer')
    parser.add_argument('--id', type=int, required=True, help='Peer ID')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind')
    parser.add_argument('--port', type=int, required=True, help='Port to bind')
    parser.add_argument('--log-dir', default='data/logs', help='Log directory')
    parser.add_argument('--port-range', default='6001-6010', help='Port range to scan for peers (e.g., 6001-6010)')
    
    args = parser.parse_args()
    
    # Parse port range
    port_start, port_end = map(int, args.port_range.split('-'))
    
    peer = ChatPeer(
        peer_id=args.id,
        host=args.host,
        port=args.port,
        log_dir=args.log_dir,
        port_range=(port_start, port_end)
    )
    
    tui = PeerTUI(peer)
    
    try:
        await tui.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await peer.stop()


if __name__ == '__main__':
    asyncio.run(main())
