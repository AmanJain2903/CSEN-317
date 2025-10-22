"""
Terminal UI client for sending and receiving chat messages.
"""
import asyncio
import argparse
import sys
import logging
from typing import Optional

from .common import Message, MessageType
from .transport import Connection


class ChatClient:
    """
    Simple terminal-based chat client.
    """
    
    def __init__(self, host: str, port: int, client_id: int = 9999):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connection: Optional[Connection] = None
        self.running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('chat_client')
    
    async def connect(self):
        """Connect to the chat node."""
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            self.connection = Connection(reader, writer)
            print(f"Connected to chat node at {self.host}:{self.port}")
            print("Type your messages and press Enter to send.")
            print("Press Ctrl+C to exit.\n")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    async def receive_messages(self):
        """Receive and display messages from the server."""
        if not self.connection:
            return
        
        try:
            while self.running:
                message = await self.connection.recv()
                if message is None:
                    print("\nConnection closed by server")
                    self.running = False
                    break
                
                # Display SEQ_CHAT messages
                if message.type == MessageType.SEQ_CHAT:
                    print(
                        f"\r[seq={message.seq_no}] "
                        f"node_{message.sender_id}: {message.payload}"
                    )
                    # Reprint prompt
                    print("> ", end='', flush=True)
        except Exception as e:
            self.logger.error(f"Error receiving messages: {e}")
            self.running = False
    
    async def send_messages(self):
        """Read input from user and send chat messages."""
        if not self.connection:
            return
        
        try:
            # Use a thread to read from stdin without blocking
            loop = asyncio.get_event_loop()
            
            while self.running:
                print("> ", end='', flush=True)
                
                # Read line from stdin
                try:
                    text = await loop.run_in_executor(None, sys.stdin.readline)
                    text = text.strip()
                    
                    if not text:
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
                        print("Failed to send message")
                        self.running = False
                        break
                
                except EOFError:
                    break
        except Exception as e:
            self.logger.error(f"Error sending messages: {e}")
            self.running = False
    
    async def run(self):
        """Main client loop."""
        if not await self.connect():
            return
        
        self.running = True
        
        try:
            # Run receiver and sender concurrently
            await asyncio.gather(
                self.receive_messages(),
                self.send_messages(),
            )
        except KeyboardInterrupt:
            print("\n\nExiting...")
        finally:
            if self.connection:
                self.connection.close()


async def main():
    """Entry point for the chat client."""
    parser = argparse.ArgumentParser(description='Distributed Chat Client')
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Node host to connect to'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5001,
        help='Node port to connect to'
    )
    parser.add_argument(
        '--client-id',
        type=int,
        default=9999,
        help='Client ID'
    )
    
    args = parser.parse_args()
    
    client = ChatClient(args.host, args.port, args.client_id)
    await client.run()


if __name__ == '__main__':
    asyncio.run(main())

