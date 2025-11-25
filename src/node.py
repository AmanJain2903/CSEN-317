"""
Main node process that orchestrates all components.
"""
import asyncio
import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import Optional

from .common import Message, MessageType, NodeRole, ChatMessage
from .transport import TransportLayer, Connection
from .membership import MembershipManager
from .failure import FailureDetector
from .election import ElectionManager
from .ordering import OrderingManager
from .storage import StorageManager


class ChatNode:
    """
    Main distributed chat node that coordinates all subsystems.
    """
    
    def __init__(self, config_path: str):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.node_id = self.config['node_id']
        self.host = self.config['host']
        self.port = self.config['port']
        
        # For local testing: if binding to 0.0.0.0, advertise 127.0.0.1 to peers
        advertise_host = self.host if self.host != '0.0.0.0' else '127.0.0.1'
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(f"node.{self.node_id}")
        self.logger.info(f"Initializing node_{self.node_id} on {self.host}:{self.port}")
        if advertise_host != self.host:
            self.logger.info(f"  Advertising to peers as {advertise_host}:{self.port}")
        
        # Initialize components
        self.transport = TransportLayer(self.host, self.port, self.node_id)
        self.membership = MembershipManager(
            self.node_id,
            advertise_host,  # Use advertise_host instead of self.host
            self.port,
            self.config.get('seed_nodes', [])
        )
        self.failure = FailureDetector(
            self.node_id,
            self.config.get('heartbeat_interval_ms', 800),
            self.config.get('leader_timeout_ms', 2500),
        )
        self.election = ElectionManager(self.node_id)
        self.ordering = OrderingManager(self.node_id)
        self.storage = StorageManager(
            self.node_id,
            self.config.get('log_dir', './data/logs')
        )
        
        # Current state
        self.role = NodeRole.FOLLOWER
        self.current_term = 0
        self.running = False
        
        # Setup callbacks
        self.transport.set_message_handler(self._handle_message)
        self.failure.set_timeout_handler(self._on_leader_timeout)
        self.election.set_callbacks(self._on_become_leader, self._on_new_coordinator)
        self.ordering.set_deliver_handler(self._on_deliver_message)
    
    def _setup_logging(self):
        """Configure logging for the node."""
        log_format = (
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    async def start(self):
        """Start the node and all its components."""
        self.running = True
        self.logger.info("Starting node...")
        
        # Recover state from storage
        last_seq, messages = await self.storage.recover_state()
        self.ordering.set_last_seq(last_seq)
        self.logger.info(f"Recovered {len(messages)} messages, last_seq={last_seq}")
        
        # Start transport layer
        await self.transport.start_server()
        
        # Bootstrap join the cluster
        await asyncio.sleep(0.5)  # Brief delay for server to be ready
        await self.membership.bootstrap_join(self.transport)
        
        # Start failure detection
        if self.membership.is_leader():
            await self._on_become_leader(self.current_term + 1)
        else:
            # Start as follower
            await self.failure.start_heartbeat_monitor()
            
            # Wait briefly for any COORDINATOR messages to arrive
            await asyncio.sleep(2.0)
            
            # Check if we found a leader
            leader = self.membership.get_leader()
            other_peers = self.membership.get_other_peers()
            
            if leader:
                # Found existing leader, request catch-up
                self.logger.info(f"Found existing leader: node_{leader.node_id}")
                await self.ordering.request_catchup(
                    self.transport,
                    leader,
                    self.current_term
                )
            else:
                # No leader found - check if we're alone or have peers
                if len(other_peers) == 0:
                    # We're truly alone - become leader immediately
                    self.logger.info("No other peers found, starting election to become leader")
                    await self.election.start_election(self.transport, self.membership)
                else:
                    # Peers exist but no leader announced yet
                    # Don't rush to election - leader might announce soon
                    # or failure detector will trigger election if truly no leader
                    self.logger.info(
                        f"Found {len(other_peers)} peers but no leader yet. "
                        f"Waiting for leader announcement or timeout."
                    )
        
        self.logger.info(
            f"Node started: role={self.role.value}, "
            f"term={self.current_term}, "
            f"peers={len(self.membership.peers)}"
        )
    
    async def _handle_message(self, message: Message, conn: Connection):
        """Handle incoming messages from peers."""
        msg_type = message.type
        
        self.logger.debug(
            f"Received {msg_type.value} from node_{message.sender_id}, "
            f"term={message.term}"
        )
        
        # Handle different message types
        if msg_type == MessageType.JOIN:
            await self._handle_join(message, conn)
        
        elif msg_type == MessageType.JOIN_ACK:
            await self._handle_join_ack(message)
        
        elif msg_type == MessageType.HEARTBEAT:
            self.failure.record_heartbeat(message.term)
            # Update term if necessary
            if message.term > self.current_term:
                self.current_term = message.term
        
        elif msg_type == MessageType.ELECTION:
            await self.election.handle_election_message(
                message, self.transport, self.membership
            )
        
        elif msg_type == MessageType.ELECTION_OK:
            self.election.handle_election_ok(message)
        
        elif msg_type == MessageType.COORDINATOR:
            self.logger.info(f"Dispatching COORDINATOR from node_{message.sender_id} to election handler")
            await self.election.handle_coordinator_message(message, self.membership)
        
        elif msg_type == MessageType.CHAT:
            await self._handle_chat(message)
        
        elif msg_type == MessageType.SEQ_CHAT:
            delivered = await self.ordering.handle_seq_chat(message)
            if delivered:
                # Store the delivered message
                chat_msg = ChatMessage(
                    seq_no=message.seq_no or 0,
                    term=message.term,
                    msg_id=message.msg_id or "",
                    sender_id=message.sender_id,
                    room_id=message.room_id,
                    text=message.payload or "",
                )
                await self.storage.append_message(chat_msg)
        
        elif msg_type == MessageType.CATCHUP_REQ:
            await self._handle_catchup_req(message)
    
    async def _handle_join(self, message: Message, conn: Connection):
        """Handle a JOIN request from a new node."""
        sender_id = message.sender_id
        self.logger.info(f"Received JOIN from node_{sender_id}")
        
        # Update membership with new peer
        if message.membership:
            self.membership.update_from_membership_list(message.membership)
        
        # Send JOIN_ACK with current membership and leader info
        join_ack = Message(
            type=MessageType.JOIN_ACK,
            sender_id=self.node_id,
            term=self.current_term,
            membership=self.membership.get_membership_list(),
        )
        
        # Send JOIN_ACK to the sender's server (not through this connection)
        sender_peer = self.membership.get_peer(sender_id)
        if sender_peer:
            await self.transport.send_to(sender_peer.host, sender_peer.port, join_ack)
            self.logger.info(f"Sent JOIN_ACK to node_{sender_id}")
        else:
            # Fallback: try to send through the existing connection
            await conn.send(join_ack)
            self.logger.info(f"Sent JOIN_ACK to node_{sender_id} via connection")
        
        # If we're the leader, immediately announce it to the new node
        if self.role == NodeRole.LEADER:
            # Include own peer info so joiner knows how to contact the leader
            self_peer = self.membership.get_peer(self.node_id)
            membership_list = [self_peer.to_dict()] if self_peer else []
            
            coordinator_msg = Message(
                type=MessageType.COORDINATOR,
                sender_id=self.node_id,
                term=self.current_term,
                membership=membership_list,
            )
            
            # Send to the joining node
            peer = self.membership.get_peer(sender_id)
            if peer:
                try:
                    await self.transport.send_to(peer.host, peer.port, coordinator_msg)
                    self.logger.info(f"Sent COORDINATOR to joining node_{sender_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to send COORDINATOR to node_{sender_id}: {e}")
    
    async def _handle_join_ack(self, message: Message):
        """Handle JOIN_ACK response containing membership list."""
        sender_id = message.sender_id
        self.logger.info(f"Received JOIN_ACK from node_{sender_id}")
        
        # Update our membership with the list from the responder
        if message.membership:
            self.membership.update_from_membership_list(message.membership)
            self.logger.info(
                f"Updated membership from JOIN_ACK, now have {len(self.membership.peers)} total peers"
            )
    
    async def _handle_chat(self, message: Message):
        """Handle a CHAT message from a client or follower."""
        self.logger.debug(f"Handling CHAT message, role={self.role}, leader_id={self.membership.leader_id}")
        
        if self.role == NodeRole.LEADER:
            # Leader assigns sequence number and broadcasts
            chat_msg = self.ordering.assign_sequence_number(
                msg_id=message.msg_id or "",
                sender_id=message.sender_id,
                text=message.payload or "",
                term=self.current_term,
            )
            
            # Store first
            await self.storage.append_message(chat_msg)
            
            # Broadcast SEQ_CHAT to all peers (including self-delivery)
            seq_chat_msg = Message(
                type=MessageType.SEQ_CHAT,
                sender_id=message.sender_id,
                term=self.current_term,
                msg_id=chat_msg.msg_id,
                seq_no=chat_msg.seq_no,
                room_id=chat_msg.room_id,
                payload=chat_msg.text,
            )
            
            # Broadcast to followers
            peers = self.membership.get_other_peers()
            peer_addrs = [p.address() for p in peers]
            await self.transport.broadcast(peer_addrs, seq_chat_msg)
            
            # Self-deliver
            await self.ordering.handle_seq_chat(seq_chat_msg)
            
        else:
            # Follower forwards to leader
            leader = self.membership.get_leader()
            if leader:
                self.logger.debug(f"Forwarding CHAT to leader node_{leader.node_id}")
                await self.transport.send_to(leader.host, leader.port, message)
            else:
                self.logger.warning("No known leader to forward CHAT message")
    
    async def _handle_catchup_req(self, message: Message):
        """Handle a catch-up request (leader only)."""
        if self.role == NodeRole.LEADER:
            requester_peer = self.membership.get_peer(message.sender_id)
            if requester_peer:
                await self.ordering.handle_catchup_request(
                    message,
                    self.transport,
                    self.storage,
                    requester_peer
                )
    
    async def _on_leader_timeout(self):
        """Called when leader heartbeat times out."""
        self.logger.warning("Leader timeout detected, starting election")
        await self.election.start_election(self.transport, self.membership)
    
    async def _on_become_leader(self, term: int):
        """Called when this node becomes the leader."""
        self.logger.info(f"Became LEADER for term {term}")
        self.role = NodeRole.LEADER
        self.current_term = term
        self.failure.set_role(NodeRole.LEADER, term)
        
        # Stop monitoring heartbeats, start sending them
        self.failure.stop_heartbeat_monitor()
        await self.failure.start_heartbeat_sender(self.transport, self.membership)
    
    async def _on_new_coordinator(self, leader_id: int, term: int):
        """Called when a new coordinator is announced."""
        self.logger.info(f"New coordinator: node_{leader_id}, term={term}")
        self.role = NodeRole.FOLLOWER
        self.current_term = term
        self.failure.set_role(NodeRole.FOLLOWER, term)
        
        # Stop sending heartbeats, start monitoring
        self.failure.stop_heartbeat_sender()
        await self.failure.start_heartbeat_monitor()
        
        # Request catch-up from new leader
        leader = self.membership.get_leader()
        if leader:
            await asyncio.sleep(0.5)  # Brief delay
            await self.ordering.request_catchup(self.transport, leader, term)
    
    async def _on_deliver_message(self, chat_msg: ChatMessage):
        """Called when a message is delivered in order."""
        # Store message to disk
        await self.storage.append_message(chat_msg)
        
        # Print to console for visibility
        print(
            f"[seq={chat_msg.seq_no}] node_{chat_msg.sender_id}: {chat_msg.text}"
        )
    
    async def send_chat_message(self, text: str):
        """Send a chat message (for local client)."""
        chat_msg = Message(
            type=MessageType.CHAT,
            sender_id=self.node_id,
            term=self.current_term,
            payload=text,
        )
        
        # Handle locally
        await self._handle_chat(chat_msg)
    
    async def stop(self):
        """Stop the node and cleanup."""
        self.logger.info("Stopping node...")
        self.running = False
        
        await self.failure.stop()
        await self.transport.stop()
        
        self.logger.info("Node stopped")
    
    async def run(self):
        """Main run loop."""
        await self.start()
        
        try:
            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            await self.stop()


async def main():
    """Entry point for running a chat node."""
    parser = argparse.ArgumentParser(description='Distributed Chat Node')
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to node configuration file'
    )
    
    args = parser.parse_args()
    
    node = ChatNode(args.config)
    await node.run()


if __name__ == '__main__':
    asyncio.run(main())

