"""
Async TCP transport layer for sending and receiving JSON messages.
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable
from .common import Message


class Connection:
    """Represents a TCP connection to a peer."""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.peer_addr = writer.get_extra_info('peername')
    
    async def send(self, message: Message) -> bool:
        """Send a message over the connection."""
        try:
            data = message.to_json()
            self.writer.write(data.encode('utf-8') + b'\n')
            await self.writer.drain()
            return True
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            return False
    
    async def recv(self) -> Optional[Message]:
        """Receive a message from the connection."""
        try:
            data = await self.reader.readline()
            if not data:
                return None
            return Message.from_json(data.decode('utf-8').strip())
        except Exception as e:
            logging.debug(f"Failed to receive message: {e}")
            return None
    
    def close(self):
        """Close the connection."""
        try:
            self.writer.close()
        except Exception:
            pass


class TransportLayer:
    """
    Manages async TCP server and client connections.
    """
    
    def __init__(self, host: str, port: int, node_id: int):
        self.host = host
        self.port = port
        self.node_id = node_id
        self.logger = logging.getLogger(f"transport.{node_id}")
        self.server: Optional[asyncio.Server] = None
        self.connections: dict[tuple[str, int], Connection] = {}
        self.message_handler: Optional[Callable[[Message, Connection], Awaitable[None]]] = None
        # Track connection failures to detect dead peers
        self.failure_counts: dict[tuple[str, int], int] = {}
        self.max_failures: int = 3  # Remove peer after this many failures
    
    def set_message_handler(self, handler: Callable[[Message, Connection], Awaitable[None]]):
        """Set the callback for handling incoming messages."""
        self.message_handler = handler
    
    async def start_server(self):
        """Start the TCP server to accept incoming connections."""
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        self.logger.info(f"Server started on {self.host}:{self.port}")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle an incoming client connection."""
        conn = Connection(reader, writer)
        peer_addr = conn.peer_addr
        self.logger.debug(f"New connection from {peer_addr}")
        
        try:
            while True:
                message = await conn.recv()
                if message is None:
                    break
                if self.message_handler:
                    await self.message_handler(message, conn)
        except Exception as e:
            self.logger.error(f"Error handling client {peer_addr}: {e}")
        finally:
            conn.close()
            self.logger.debug(f"Connection closed from {peer_addr}")
    
    async def connect(self, host: str, port: int) -> Optional[Connection]:
        """Connect to a remote peer."""
        addr = (host, port)
        if addr in self.connections:
            return self.connections[addr]
        
        try:
            reader, writer = await asyncio.open_connection(host, port)
            conn = Connection(reader, writer)
            self.connections[addr] = conn
            # Reset failure count on successful connection
            if addr in self.failure_counts:
                del self.failure_counts[addr]
            self.logger.debug(f"Connected to {host}:{port}")
            return conn
        except Exception as e:
            # Track failures
            addr = (host, port)
            self.failure_counts[addr] = self.failure_counts.get(addr, 0) + 1
            
            # Only log error on first few failures
            if self.failure_counts[addr] <= 2:
                self.logger.warning(f"Failed to connect to {host}:{port}: {e}")
            else:
                self.logger.debug(f"Failed to connect to {host}:{port}: {e}")
            return None
    
    async def send_to(self, host: str, port: int, message: Message) -> bool:
        """Send a message to a specific peer. Returns True if successful."""
        conn = await self.connect(host, port)
        if conn:
            success = await conn.send(message)
            if not success:
                # Remove failed connection
                addr = (host, port)
                if addr in self.connections:
                    del self.connections[addr]
                self.failure_counts[addr] = self.failure_counts.get(addr, 0) + 1
            else:
                # Reset failure count on successful send
                addr = (host, port)
                if addr in self.failure_counts:
                    del self.failure_counts[addr]
            return success
        return False
    
    def get_failed_peers(self) -> list[tuple[str, int]]:
        """Get list of peers that have exceeded failure threshold."""
        return [addr for addr, count in self.failure_counts.items() 
                if count >= self.max_failures]
    
    def reset_failure_count(self, host: str, port: int):
        """Reset failure count for a peer."""
        addr = (host, port)
        if addr in self.failure_counts:
            del self.failure_counts[addr]
    
    async def broadcast(self, peers: list[tuple[str, int]], message: Message):
        """Broadcast a message to multiple peers."""
        tasks = [self.send_to(host, port, message) for host, port in peers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop the transport layer and close all connections."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for conn in list(self.connections.values()):
            conn.close()
        self.connections.clear()
        self.logger.info("Transport layer stopped")

