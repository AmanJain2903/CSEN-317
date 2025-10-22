"""
Leader election using the Bully algorithm.
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable
from .common import Message, MessageType, NodeRole


class ElectionManager:
    """
    Implements the Bully algorithm for leader election.
    Higher node_id has higher priority.
    """
    
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.logger = logging.getLogger(f"election.{node_id}")
        self.current_term = 0
        self.election_in_progress = False
        self.election_timeout = 2.0  # seconds to wait for responses
        self.received_ok = False
        
        # Callbacks
        self.on_become_leader: Optional[Callable[[int], Awaitable[None]]] = None
        self.on_new_coordinator: Optional[Callable[[int, int], Awaitable[None]]] = None
    
    def set_callbacks(
        self,
        on_become_leader: Callable[[int], Awaitable[None]],
        on_new_coordinator: Callable[[int, int], Awaitable[None]]
    ):
        """Set callbacks for election outcomes."""
        self.on_become_leader = on_become_leader
        self.on_new_coordinator = on_new_coordinator
    
    async def start_election(self, transport, membership) -> bool:
        """
        Start a new election using the Bully algorithm.
        Returns True if this node becomes the leader.
        """
        if self.election_in_progress:
            self.logger.debug("Election already in progress")
            return False
        
        self.election_in_progress = True
        self.received_ok = False
        self.current_term += 1
        
        self.logger.info(f"Starting election for term {self.current_term}")
        
        # Get peers with higher priority (higher node_id)
        higher_peers = membership.get_higher_priority_peers()
        
        if not higher_peers:
            # No higher priority peers, become leader immediately
            self.logger.info("No higher priority peers, declaring victory")
            await self._become_coordinator(transport, membership)
            self.election_in_progress = False
            return True
        
        # Send ELECTION message to all higher priority peers
        election_msg = Message(
            type=MessageType.ELECTION,
            sender_id=self.node_id,
            term=self.current_term,
        )
        
        for peer in higher_peers:
            await transport.send_to(peer.host, peer.port, election_msg)
            self.logger.debug(f"Sent ELECTION to node_{peer.node_id}")
        
        # Wait for responses
        try:
            await asyncio.sleep(self.election_timeout)
        except asyncio.CancelledError:
            self.election_in_progress = False
            return False
        
        # Check if we received any OK responses
        if not self.received_ok:
            # No responses from higher priority nodes, we win
            self.logger.info("No OK responses received, declaring victory")
            await self._become_coordinator(transport, membership)
            self.election_in_progress = False
            return True
        else:
            # Someone with higher priority is alive, they will coordinate
            self.logger.info("Received OK from higher priority node, waiting for COORDINATOR")
            self.election_in_progress = False
            return False
    
    async def handle_election_message(
        self,
        message: Message,
        transport,
        membership
    ):
        """Handle an incoming ELECTION message."""
        sender_id = message.sender_id
        
        if sender_id < self.node_id:
            # We have higher priority, respond with OK and start our own election
            self.logger.info(f"Received ELECTION from lower priority node_{sender_id}, responding with OK")
            
            # Send ELECTION_OK
            ok_msg = Message(
                type=MessageType.ELECTION_OK,
                sender_id=self.node_id,
                term=self.current_term,
            )
            
            sender_peer = membership.get_peer(sender_id)
            if sender_peer:
                await transport.send_to(sender_peer.host, sender_peer.port, ok_msg)
            
            # Start our own election if not already in progress
            if not self.election_in_progress:
                asyncio.create_task(self.start_election(transport, membership))
    
    def handle_election_ok(self, message: Message):
        """Handle an incoming ELECTION_OK message."""
        self.logger.info(f"Received ELECTION_OK from node_{message.sender_id}")
        self.received_ok = True
    
    async def handle_coordinator_message(
        self,
        message: Message,
        membership
    ):
        """Handle an incoming COORDINATOR message."""
        new_leader_id = message.sender_id
        new_term = message.term
        
        self.logger.info(f"Received COORDINATOR from node_{new_leader_id}, term={new_term}")
        
        # Accept the new coordinator if term is valid
        if new_term >= self.current_term:
            self.current_term = new_term
            membership.set_leader(new_leader_id)
            
            if self.on_new_coordinator:
                await self.on_new_coordinator(new_leader_id, new_term)
    
    async def _become_coordinator(self, transport, membership):
        """Become the coordinator and announce to all peers."""
        self.logger.info(f"Becoming coordinator for term {self.current_term}")
        
        membership.set_leader(self.node_id)
        
        # Broadcast COORDINATOR message
        coordinator_msg = Message(
            type=MessageType.COORDINATOR,
            sender_id=self.node_id,
            term=self.current_term,
        )
        
        peers = membership.get_other_peers()
        peer_addrs = [p.address() for p in peers]
        await transport.broadcast(peer_addrs, coordinator_msg)
        
        if self.on_become_leader:
            await self.on_become_leader(self.current_term)

