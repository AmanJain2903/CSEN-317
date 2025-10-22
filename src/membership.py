"""
Membership management: joining, seed bootstrap, and peer tracking.
"""
import asyncio
import logging
from typing import Optional, List
from .common import Message, MessageType, PeerInfo


class MembershipManager:
    """
    Manages cluster membership and peer information.
    """
    
    def __init__(self, node_id: int, host: str, port: int, seed_nodes: List[dict]):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.logger = logging.getLogger(f"membership.{node_id}")
        
        # Parse seed nodes
        self.seed_peers: List[PeerInfo] = []
        for seed in seed_nodes:
            if seed.get('node_id') != node_id:  # Don't include self
                self.seed_peers.append(PeerInfo(
                    node_id=seed.get('node_id', 0),
                    host=seed['host'],
                    port=seed['port']
                ))
        
        # Current known peers (including self)
        self.peers: dict[int, PeerInfo] = {
            node_id: PeerInfo(node_id=node_id, host=host, port=port)
        }
        
        self.leader_id: Optional[int] = None
    
    def add_peer(self, peer: PeerInfo):
        """Add or update a peer in the membership."""
        if peer.node_id != self.node_id:
            self.peers[peer.node_id] = peer
            self.logger.info(f"Added peer: node_{peer.node_id} at {peer.host}:{peer.port}")
    
    def remove_peer(self, node_id: int):
        """Remove a peer from membership."""
        if node_id in self.peers and node_id != self.node_id:
            peer = self.peers.pop(node_id)
            self.logger.info(f"Removed peer: node_{peer.node_id}")
    
    def get_peer(self, node_id: int) -> Optional[PeerInfo]:
        """Get peer information by node ID."""
        return self.peers.get(node_id)
    
    def get_all_peers(self) -> List[PeerInfo]:
        """Get all known peers including self."""
        return list(self.peers.values())
    
    def get_other_peers(self) -> List[PeerInfo]:
        """Get all peers except self."""
        return [p for p in self.peers.values() if p.node_id != self.node_id]
    
    def get_higher_priority_peers(self) -> List[PeerInfo]:
        """Get peers with higher priority (higher node_id) for Bully election."""
        return [p for p in self.peers.values() if p.node_id > self.node_id]
    
    def set_leader(self, leader_id: int):
        """Set the current leader."""
        self.leader_id = leader_id
        self.logger.info(f"Leader set to node_{leader_id}")
    
    def get_leader(self) -> Optional[PeerInfo]:
        """Get the current leader peer info."""
        if self.leader_id is not None:
            return self.peers.get(self.leader_id)
        return None
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self.leader_id == self.node_id
    
    def update_from_membership_list(self, membership: List[dict]):
        """Update membership from a received membership list."""
        for peer_data in membership:
            if peer_data['node_id'] != self.node_id:
                peer = PeerInfo.from_dict(peer_data)
                self.add_peer(peer)
    
    def get_membership_list(self) -> List[dict]:
        """Get serializable membership list."""
        return [p.to_dict() for p in self.peers.values()]
    
    async def bootstrap_join(self, transport) -> bool:
        """
        Bootstrap by contacting seed nodes to join the cluster.
        Returns True if successfully joined.
        """
        if not self.seed_peers:
            # No seeds, become leader immediately
            self.logger.info("No seed nodes, becoming initial leader")
            self.set_leader(self.node_id)
            return True
        
        # Try to contact seed nodes
        for seed in self.seed_peers:
            self.logger.info(f"Attempting to join via seed node_{seed.node_id} at {seed.host}:{seed.port}")
            
            join_msg = Message(
                type=MessageType.JOIN,
                sender_id=self.node_id,
                term=0,
                membership=[self.peers[self.node_id].to_dict()]
            )
            
            try:
                # Try to send JOIN and wait briefly for response
                success = await transport.send_to(seed.host, seed.port, join_msg)
                if success:
                    self.logger.info(f"Sent JOIN to seed node_{seed.node_id}")
                    # Give some time for JOIN_ACK to arrive
                    await asyncio.sleep(0.5)
                    # Check if we learned about peers
                    if len(self.peers) > 1 or self.leader_id is not None:
                        self.logger.info("Successfully joined cluster")
                        return True
            except Exception as e:
                self.logger.warning(f"Failed to join via seed {seed.node_id}: {e}")
                continue
        
        # If no seeds responded, we might be the first node
        self.logger.info("Could not contact any seed nodes, starting as initial node")
        return False

