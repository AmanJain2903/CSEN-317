"""
Failure detection using heartbeats and timeouts.
"""
import asyncio
import logging
import time
from typing import Optional, Callable, Awaitable
from .common import Message, MessageType, NodeRole


class FailureDetector:
    """
    Detects leader failures through heartbeat monitoring.
    """
    
    def __init__(
        self,
        node_id: int,
        heartbeat_interval_ms: int,
        leader_timeout_ms: int,
    ):
        self.node_id = node_id
        self.heartbeat_interval = heartbeat_interval_ms / 1000.0
        self.leader_timeout = leader_timeout_ms / 1000.0
        self.logger = logging.getLogger(f"failure.{node_id}")
        
        self.role = NodeRole.FOLLOWER
        self.current_term = 0
        self.last_heartbeat_time: Optional[float] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Callback for when leader is suspected dead
        self.on_leader_timeout: Optional[Callable[[], Awaitable[None]]] = None
    
    def set_role(self, role: NodeRole, term: int):
        """Update the node's role and term."""
        self.role = role
        self.current_term = term
        self.logger.info(f"Role changed to {role.value}, term={term}")
    
    def set_timeout_handler(self, handler: Callable[[], Awaitable[None]]):
        """Set callback for leader timeout events."""
        self.on_leader_timeout = handler
    
    def record_heartbeat(self, term: int):
        """Record receiving a heartbeat from the leader."""
        if term >= self.current_term:
            self.last_heartbeat_time = time.time()
            self.logger.debug(f"Heartbeat received from leader, term={term}")
    
    async def start_heartbeat_sender(self, transport, membership):
        """Start sending periodic heartbeats (for leader)."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        self.heartbeat_task = asyncio.create_task(
            self._heartbeat_sender_loop(transport, membership)
        )
        self.logger.info("Started heartbeat sender")
    
    async def _heartbeat_sender_loop(self, transport, membership):
        """Periodic task to send heartbeats to all followers."""
        try:
            while True:
                if self.role == NodeRole.LEADER:
                    # Send heartbeat to all peers
                    peers = membership.get_other_peers()
                    heartbeat_msg = Message(
                        type=MessageType.HEARTBEAT,
                        sender_id=self.node_id,
                        term=self.current_term,
                    )
                    
                    peer_addrs = [p.address() for p in peers]
                    await transport.broadcast(peer_addrs, heartbeat_msg)
                    self.logger.debug(f"Sent heartbeat to {len(peers)} peers")
                    
                    # Check for failed peers and remove them from membership
                    failed_peers = transport.get_failed_peers()
                    for addr in failed_peers:
                        # Find the node_id for this address
                        host, port = addr
                        for peer in peers:
                            if peer.host == host and peer.port == port:
                                self.logger.warning(
                                    f"Removing unresponsive peer: node_{peer.node_id} at {host}:{port}"
                                )
                                membership.remove_peer(peer.node_id)
                                # Reset failure count after removal
                                transport.reset_failure_count(host, port)
                                break
                
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            self.logger.info("Heartbeat sender stopped")
        except Exception as e:
            self.logger.error(f"Heartbeat sender error: {e}")
    
    def start_heartbeat_monitor(self):
        """Start monitoring for leader heartbeats (for followers)."""
        if self.monitor_task:
            self.monitor_task.cancel()
        
        # Initialize last heartbeat time
        self.last_heartbeat_time = time.time()
        
        self.monitor_task = asyncio.create_task(self._heartbeat_monitor_loop())
        self.logger.info("Started heartbeat monitor")
    
    async def _heartbeat_monitor_loop(self):
        """Periodic task to check if leader is alive."""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self.role == NodeRole.FOLLOWER:
                    if self.last_heartbeat_time is None:
                        continue
                    
                    elapsed = time.time() - self.last_heartbeat_time
                    if elapsed > self.leader_timeout:
                        self.logger.warning(
                            f"Leader timeout! No heartbeat for {elapsed:.2f}s"
                        )
                        if self.on_leader_timeout:
                            await self.on_leader_timeout()
                        # Reset to avoid triggering multiple elections
                        self.last_heartbeat_time = time.time()
        except asyncio.CancelledError:
            self.logger.info("Heartbeat monitor stopped")
        except Exception as e:
            self.logger.error(f"Heartbeat monitor error: {e}")
    
    def stop_heartbeat_sender(self):
        """Stop sending heartbeats."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
    
    def stop_heartbeat_monitor(self):
        """Stop monitoring heartbeats."""
        if self.monitor_task:
            self.monitor_task.cancel()
            self.monitor_task = None
    
    async def stop(self):
        """Stop all failure detection tasks."""
        self.stop_heartbeat_sender()
        self.stop_heartbeat_monitor()

