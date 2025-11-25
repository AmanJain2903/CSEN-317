"""
Terminal UI client for sending and receiving chat messages.
"""
import asyncio
import argparse
import sys
import logging
from typing import Optional, List, Tuple

from .common import Message, MessageType
from .transport import Connection


class ChatClient:
    """
    Simple terminal-based chat client with automatic failover.
    """
    
    def __init__(self, nodes: List[Tuple[str, int]], client_id: int = 9999):
        self.nodes = nodes  # List of (host, port) tuples
        self.current_node_index = 0
        self.client_id = client_id
        self.connection: Optional[Connection] = None
        self.running = False
        self.reconnect_delay = 2.0  # seconds
        
        # Setup logging
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('chat_client')
    
    async def connect(self) -> bool:
        """
        Connect to any available node in the cluster.
        Tries all nodes in round-robin fashion.
        """
        attempts_per_node = 2
        total_nodes = len(self.nodes)
        
        for cycle in range(attempts_per_node):
            for i in range(total_nodes):
                node_index = (self.current_node_index + i) % total_nodes
                host, port = self.nodes[node_index]
                
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port),
                        timeout=3.0
                    )
                    self.connection = Connection(reader, writer)
                    self.current_node_index = node_index
                    
                    print(f"✓ Connected to node at {host}:{port}")
                    if cycle == 0 and i == 0:
                        print("Type your messages and press Enter to send.")
                        print("Press Ctrl+C to exit.\n")
                    else:
                        print("✓ Reconnected!\n")
                    
                    return True
                
                except (OSError, asyncio.TimeoutError) as e:
                    self.logger.debug(f"Node {host}:{port} unavailable: {e}")
                    continue
                except Exception as e:
                    self.logger.warning(f"Failed to connect to {host}:{port}: {e}")
                    continue
            
            # All nodes failed this cycle, wait before retry
            if cycle < attempts_per_node - 1:
                print(f"All nodes unavailable, retrying in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
        
        print("✗ Could not connect to any node in the cluster")
        return False
    
    async def reconnect(self) -> bool:
        """
        Attempt to reconnect after connection loss.
        Uses exponential backoff and round-robin node selection.
        """
        print("\n! Connection lost. Attempting to reconnect...")
        
        # Close old connection
        if self.connection:
            self.connection.close()
            self.connection = None
        
        # Try next node in the list for immediate failover
        self.current_node_index = (self.current_node_index + 1) % len(self.nodes)
        
        # Try to reconnect with exponential backoff
        delay = self.reconnect_delay
        max_delay = 30.0
        attempt = 1
        
        while self.running:
            print(f"Reconnection attempt {attempt}...")
            
            if await self.connect():
                return True
            
            print(f"Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, max_delay)  # Exponential backoff
            attempt += 1
        
        return False
    
    async def receive_messages(self):
        """Receive and display messages from the server."""
        while self.running:
            if not self.connection:
                await asyncio.sleep(0.1)
                continue
            
            try:
                message = await self.connection.recv()
                
                if message is None:
                    print("\n! Connection closed by server")
                    if not await self.reconnect():
                        self.running = False
                    continue
                
                # Display SEQ_CHAT messages
                if message.type == MessageType.SEQ_CHAT:
                    print(
                        f"\r[seq={message.seq_no}] "
                        f"node_{message.sender_id}: {message.payload}"
                    )
                    # Reprint prompt
                    print("> ", end='', flush=True)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error receiving messages: {e}")
                if not await self.reconnect():
                    self.running = False
                    break
    
    async def send_messages(self):
        """Read input from user and send chat messages."""
        loop = asyncio.get_event_loop()
        
        while self.running:
            # Wait for connection
            while self.running and not self.connection:
                await asyncio.sleep(0.1)
            
            if not self.running:
                break
            
            try:
                print("> ", end='', flush=True)
                
                # Read line from stdin
                try:
                    text = await loop.run_in_executor(None, sys.stdin.readline)
                    text = text.strip()
                    
                    if not text:
                        continue
                    
                    # Wait for connection if lost during typing
                    if not self.connection:
                        print("Waiting for connection...")
                        continue
                    
                    # Send CHAT message
                    chat_msg = Message(
                        type=MessageType.CHAT,
                        sender_id=self.client_id,
                        term=0,
                        payload=text,
                    )
                    
                    success = await self.connection.send(chat_msg)
                    if not success:
                        print("! Failed to send message, reconnecting...")
                        await self.reconnect()
                
                except EOFError:
                    break
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error sending messages: {e}")
                await self.reconnect()
    
    async def run(self):
        """Main client loop."""
        if not await self.connect():
            print("\n✗ Could not establish initial connection. Exiting.")
            return
        
        self.running = True
        
        try:
            # Run receiver and sender concurrently
            receive_task = asyncio.create_task(self.receive_messages())
            send_task = asyncio.create_task(self.send_messages())
            
            await asyncio.gather(receive_task, send_task)
        
        except KeyboardInterrupt:
            print("\n\nExiting...")
        finally:
            self.running = False
            if self.connection:
                self.connection.close()


async def main():
    """Entry point for the chat client."""
    parser = argparse.ArgumentParser(description='Distributed Chat Client')
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Primary node host to connect to'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5001,
        help='Primary node port to connect to'
    )
    parser.add_argument(
        '--nodes',
        type=str,
        help='Comma-separated list of nodes (host:port,host:port,...). '
             'Overrides --host and --port if provided. '
             'Example: 127.0.0.1:5001,127.0.0.1:5002,127.0.0.1:5003'
    )
    parser.add_argument(
        '--client-id',
        type=int,
        default=9999,
        help='Client ID'
    )
    
    args = parser.parse_args()
    
    # Parse node list
    if args.nodes:
        # User provided explicit node list
        nodes = []
        for node_str in args.nodes.split(','):
            try:
                host, port = node_str.strip().split(':')
                nodes.append((host, int(port)))
            except ValueError:
                print(f"Invalid node format: {node_str}. Use host:port format.")
                return
    else:
        # Use default three-node cluster with primary from args
        nodes = [
            (args.host, args.port),  # Primary node
        ]
        # Add other standard ports if using default localhost
        if args.host == '127.0.0.1' or args.host == 'localhost':
            for port in [5001, 5002, 5003]:
                if port != args.port:
                    nodes.append(('127.0.0.1', port))
    
    print(f"Node cluster: {', '.join([f'{h}:{p}' for h, p in nodes])}")
    
    client = ChatClient(nodes, args.client_id)
    await client.run()


if __name__ == '__main__':
    asyncio.run(main())

