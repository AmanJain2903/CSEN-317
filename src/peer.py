"""
Peer node that acts as both client and server in a P2P distributed chat system.
Each peer participates in leader election, failure detection, and message ordering.
"""
import asyncio
import logging
import uuid
import yaml
from pathlib import Path
from typing import Optional, Callable

from .common import Message, MessageType, NodeRole, ChatMessage
from .transport import TransportLayer, Connection
from .membership import MembershipManager
from .failure import FailureDetector
from .election import ElectionManager
from .ordering import OrderingManager
from .storage import StorageManager


class ChatPeer:
    """
    A peer node that combines client and server functionality.
    Each peer can send messages and participates in distributed consensus.
    """
    
    def __init__(self, peer_id: int, host: str, port: int, 
                 log_dir: str = "data/logs", 
                 heartbeat_interval_ms: int = 800,
                 leader_timeout_ms: int = 2500,
                 port_range: tuple = (6001, 6010)):
        
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.current_term = 0
        self.role = NodeRole.FOLLOWER
        self.port_range = port_range  # Range of ports to scan for other peers
        
        advertise_host = host if host != '0.0.0.0' else '127.0.0.1'
        
        self._setup_logging()
        self.logger = logging.getLogger(f"peer.{peer_id}")
        self.logger.info(f"Initializing peer_{peer_id} on {host}:{port}")
        
        self.transport = TransportLayer(host, port, peer_id)
        # Start with empty seed_peers - will auto-discover
        self.membership = MembershipManager(peer_id, advertise_host, port, [])
        self.failure = FailureDetector(
            peer_id,
            heartbeat_interval_ms,
            leader_timeout_ms
        )
        self.election = ElectionManager(peer_id)
        self.ordering = OrderingManager(peer_id)
        self.storage = StorageManager(peer_id, log_dir)
        
        self.transport.set_message_handler(self._handle_message)
        self.failure.set_timeout_handler(self._on_leader_timeout)
        self.election.set_callbacks(self._on_become_leader, self._on_new_coordinator)
        self.ordering.set_deliver_handler(self._on_deliver_message)
        
        self.message_callback: Optional[Callable[[ChatMessage], None]] = None
        self.running = False
        
    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def set_message_callback(self, callback: Callable[[ChatMessage], None]):
        """Set callback for when messages are delivered"""
        self.message_callback = callback
    
    async def start(self):
        """Start the peer node"""
        self.running = True
        self.logger.info("Starting peer...")
        
        # Load messages from disk
        messages = await self.storage.load_messages()
        last_seq = await self.storage.get_last_seq()
        
        # Initialize ordering manager state
        self.ordering.last_seq = last_seq
        self.ordering.next_expected_seq = last_seq + 1
        
        # Mark loaded messages as already delivered to avoid re-delivery
        for msg in messages:
            self.ordering.delivered[(msg.seq_no, msg.term)] = True
            self.logger.debug(f"Loaded message seq_no={msg.seq_no} from disk")
        
        self.logger.info(f"Loaded {len(messages)} messages from disk, last_seq={last_seq}")
        
        await self.transport.start_server()
        
        await self._join_cluster()
        
        self.failure.set_role(self.role, self.current_term)
        self.failure.start_heartbeat_monitor()
        
        self.logger.info(f"Peer started as {self.role.value}")
    
    async def stop(self):
        """Stop the peer node"""
        self.running = False
        self.logger.info("Stopping peer...")
    
    async def send_chat_message(self, payload: str, room_id: str = "general") -> bool:
        """Send a chat message (as client)"""
        if self.role == NodeRole.LEADER:
            return await self._handle_chat_as_leader(payload, room_id)
        else:
            return await self._forward_to_leader(payload, room_id)
    
    async def _handle_chat_as_leader(self, payload: str, room_id: str) -> bool:
        """Handle chat message when we are the leader"""
        msg_id = str(uuid.uuid4())
        
        # Assign sequence number and create ChatMessage
        chat_msg = self.ordering.assign_sequence_number(
            msg_id=msg_id,
            sender_id=self.peer_id,
            text=payload,
            term=self.current_term
        )
        
        # Broadcast SEQ_CHAT to all peers
        seq_msg = Message(
            type=MessageType.SEQ_CHAT,
            sender_id=self.peer_id,
            term=self.current_term,
            seq_no=chat_msg.seq_no,
            msg_id=msg_id,
            room_id=room_id,
            payload=payload
        )
        
        # Deliver locally first
        await self.ordering.handle_seq_chat(seq_msg)
        
        # Then broadcast to all peers
        await self._broadcast_to_all(seq_msg)
        
        self.logger.info(f"Leader assigned seq_no={chat_msg.seq_no} to message")
        return True
    
    async def _forward_to_leader(self, payload: str, room_id: str) -> bool:
        """Forward chat message to leader"""
        leader = self.membership.get_leader()
        if not leader:
            self.logger.warning("No leader known, cannot send message")
            return False
        
        msg = Message(
            type=MessageType.CHAT,
            sender_id=self.peer_id,
            term=self.current_term,
            msg_id=str(uuid.uuid4()),
            room_id=room_id,
            payload=payload
        )
        
        try:
            await self.transport.send_to(leader.host, leader.port, msg)
            self.logger.debug(f"Forwarded CHAT to leader peer_{leader.node_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to forward to leader: {e}")
            return False
    
    async def _discover_peers(self):
        """Auto-discover existing peers by scanning the port range"""
        self.logger.info(f"Scanning ports {self.port_range[0]}-{self.port_range[1]} for existing peers...")
        
        discovered_peers = []
        
        for scan_port in range(self.port_range[0], self.port_range[1] + 1):
            # Skip our own port
            if scan_port == self.port:
                continue
            
            try:
                # Try to connect to this port
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection('127.0.0.1', scan_port),
                    timeout=0.5
                )
                writer.close()
                await writer.wait_closed()
                
                # Someone is listening on this port - add as discovered peer
                # We'll learn the actual peer_id from JOIN_ACK
                from .common import PeerInfo
                peer = PeerInfo(
                    node_id=0,  # Unknown for now, will be updated
                    host='127.0.0.1',
                    port=scan_port
                )
                discovered_peers.append(peer)
                self.logger.info(f"Discovered peer at port {scan_port}")
                
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                # No peer at this port, continue
                pass
        
        return discovered_peers
    
    async def _join_cluster(self):
        """Join the distributed cluster or start new one if none exists"""
        
        # Auto-discover existing peers
        discovered_peers = await self._discover_peers()
        
        if not discovered_peers:
            # No existing cluster found - start as first peer
            self.logger.info("No existing peers found, starting as first peer in new cluster")
            await self.election.start_election(self.transport, self.membership)
            return
        
        # Found existing cluster - join as follower
        self.logger.info(f"Found {len(discovered_peers)} existing peer(s), joining cluster...")
        
        self_peer = self.membership.get_peer(self.peer_id)
        if not self_peer:
            return
        
        join_msg = Message(
            type=MessageType.JOIN,
            sender_id=self.peer_id,
            term=self.current_term,
            membership=[self_peer.to_dict()]
        )
        
        # Send JOIN to all discovered peers
        for peer in discovered_peers:
            try:
                await self.transport.send_to(peer.host, peer.port, join_msg)
                self.logger.info(f"Sent JOIN to peer at {peer.host}:{peer.port}")
            except Exception as e:
                self.logger.warning(f"Failed to send JOIN to {peer.host}:{peer.port}: {e}")
        
        # Wait longer for JOIN_ACK responses to arrive
        await asyncio.sleep(2.0)
        
        # Check if we discovered a leader
        current_leader = self.membership.get_leader()
        if current_leader:
            self.logger.info(f"Discovered leader: peer_{current_leader.node_id}, joining as FOLLOWER")
            # Request catchup for any messages we missed while offline
            await self._request_catchup()
            return
        
        # No leader found, start election
        if self.role == NodeRole.FOLLOWER:
            self.logger.info("No leader after JOIN, starting election")
            # Still request catchup from peers before becoming leader
            await self._request_catchup()
            # Give catchup response time to arrive
            await asyncio.sleep(1.0)
            await self.election.start_election(self.transport, self.membership)
    
    async def _handle_message(self, message: Message, conn: Connection):
        """Handle incoming messages"""
        msg_type = message.type
        
        self.logger.debug(f"Received {msg_type.value} from peer_{message.sender_id}")
        
        if msg_type == MessageType.JOIN:
            await self._handle_join(message, conn)
        elif msg_type == MessageType.JOIN_ACK:
            await self._handle_join_ack(message)
        elif msg_type == MessageType.HEARTBEAT:
            self.failure.record_heartbeat(message.term)
            if message.term > self.current_term:
                self.current_term = message.term
        elif msg_type == MessageType.ELECTION:
            await self.election.handle_election_message(message, self.transport, self.membership)
        elif msg_type == MessageType.ELECTION_OK:
            self.election.handle_election_ok(message)
        elif msg_type == MessageType.COORDINATOR:
            await self.election.handle_coordinator_message(message, self.membership)
        elif msg_type == MessageType.CHAT:
            await self._handle_chat_from_peer(message)
        elif msg_type == MessageType.SEQ_CHAT:
            await self.ordering.handle_seq_chat(message)
        elif msg_type == MessageType.CATCHUP_REQ:
            await self._handle_catchup_req(message)
        elif msg_type == MessageType.CATCHUP_RESP:
            await self._handle_catchup_resp(message)
    
    async def _handle_join(self, message: Message, conn: Connection):
        """Handle JOIN from another peer"""
        sender_id = message.sender_id
        self.logger.info(f"Received JOIN from peer_{sender_id}")
        
        if message.membership:
            self.membership.update_from_membership_list(message.membership)
        
        # Include current leader in JOIN_ACK
        current_leader = self.membership.leader_id
        self.logger.info(f"Sending JOIN_ACK with leader_id={current_leader}, role={self.role.value}")
        
        join_ack = Message(
            type=MessageType.JOIN_ACK,
            sender_id=self.peer_id,
            term=self.current_term,
            membership=self.membership.get_membership_list(),
            leader_id=current_leader,
        )
        
        sender_peer = self.membership.get_peer(sender_id)
        if sender_peer:
            await self.transport.send_to(sender_peer.host, sender_peer.port, join_ack)
            self.logger.info(f"Sent JOIN_ACK to peer_{sender_id}")
        
        # If we are the leader, also send COORDINATOR message
        if self.role == NodeRole.LEADER:
            self.logger.info(f"We are leader, sending COORDINATOR to peer_{sender_id}")
            self_peer = self.membership.get_peer(self.peer_id)
            membership_list = [self_peer.to_dict()] if self_peer else []
            
            coordinator_msg = Message(
                type=MessageType.COORDINATOR,
                sender_id=self.peer_id,
                term=self.current_term,
                membership=membership_list,
            )
            
            peer = self.membership.get_peer(sender_id)
            if peer:
                await self.transport.send_to(peer.host, peer.port, coordinator_msg)
                self.logger.info(f"Sent COORDINATOR to peer_{sender_id}")
                await self.transport.send_to(peer.host, peer.port, coordinator_msg)
    
    async def _handle_join_ack(self, message: Message):
        """Handle JOIN_ACK"""
        self.logger.info(f"Received JOIN_ACK from peer_{message.sender_id}, term={message.term}")
        
        if message.membership:
            num_peers = len(message.membership)
            self.logger.info(f"Updating membership with {num_peers} peers from JOIN_ACK")
            self.membership.update_from_membership_list(message.membership)
        
        # Set leader if provided in JOIN_ACK
        if message.leader_id is not None:
            self.logger.info(f"JOIN_ACK indicates leader is peer_{message.leader_id}")
            self.membership.set_leader(message.leader_id)
            
            # Transition to follower role if we learned about a leader
            if self.role != NodeRole.FOLLOWER:
                self.logger.info(f"Transitioning to FOLLOWER (leader is peer_{message.leader_id})")
                self.role = NodeRole.FOLLOWER
                self.failure.set_role(NodeRole.FOLLOWER, message.term)
        else:
            self.logger.warning("JOIN_ACK did not include leader_id")
        
        if message.term > self.current_term:
            self.logger.info(f"Updating term from {self.current_term} to {message.term}")
            self.current_term = message.term
    
    async def _handle_chat_from_peer(self, message: Message):
        """Handle CHAT message from another peer (they want us to sequence it)"""
        if self.role != NodeRole.LEADER:
            self.logger.warning(f"Received CHAT but not leader, ignoring")
            return
        
        # Assign sequence number using the ordering manager
        chat_msg = self.ordering.assign_sequence_number(
            msg_id=message.msg_id or str(uuid.uuid4()),
            sender_id=message.sender_id,
            text=message.payload or "",
            term=self.current_term
        )
        
        seq_msg = Message(
            type=MessageType.SEQ_CHAT,
            sender_id=message.sender_id,
            term=self.current_term,
            seq_no=chat_msg.seq_no,
            msg_id=message.msg_id,
            room_id=message.room_id,
            payload=message.payload
        )
        
        await self.ordering.handle_seq_chat(seq_msg)
        await self._broadcast_to_all(seq_msg)
        
        self.logger.info(f"Sequenced CHAT from peer_{message.sender_id} as seq_no={chat_msg.seq_no}")
    
    async def _handle_catchup_req(self, message: Message):
        """Handle catchup request"""
        from_seq = message.last_seq or 0
        messages = await self.storage.get_messages_after(from_seq)
        
        self.logger.info(f"Sending {len(messages)} messages to peer_{message.sender_id} for catchup from seq={from_seq}")
        
        response = Message(
            type=MessageType.CATCHUP_RESP,
            sender_id=self.peer_id,
            term=self.current_term,
            payload=[msg.to_dict() for msg in messages]
        )
        
        peer = self.membership.get_peer(message.sender_id)
        if peer:
            await self.transport.send_to(peer.host, peer.port, response)
    
    async def _handle_catchup_resp(self, message: Message):
        """Handle catchup response with missed messages"""
        if not message.payload:
            self.logger.info("Received CATCHUP_RESP with no messages (already up to date)")
            return
        
        self.logger.info(f"Received CATCHUP_RESP from peer_{message.sender_id} with {len(message.payload)} messages")
        
        from .common import ChatMessage
        
        # Process each missed message
        for msg_dict in message.payload:
            chat_msg = ChatMessage.from_dict(msg_dict)
            
            # Deliver through ordering manager to maintain proper order
            # Convert ChatMessage back to SEQ_CHAT Message for processing
            seq_msg = Message(
                type=MessageType.SEQ_CHAT,
                sender_id=chat_msg.sender_id,
                term=chat_msg.term,
                seq_no=chat_msg.seq_no,
                msg_id=chat_msg.msg_id,
                payload=chat_msg.text
            )
            
            await self.ordering.handle_seq_chat(seq_msg)
            self.logger.debug(f"Caught up message seq_no={chat_msg.seq_no}")
        
        self.logger.info(f"Catchup complete! Now at seq_no={self.ordering.last_seq}")
    
    async def _request_catchup(self):
        """Request catchup from leader or any peer"""
        # Get our current sequence number
        my_last_seq = await self.storage.get_last_seq()
        
        self.logger.info(f"Requesting catchup from seq_no={my_last_seq}")
        
        # First try to get catchup from leader
        leader = self.membership.get_leader()
        if leader:
            catchup_req = Message(
                type=MessageType.CATCHUP_REQ,
                sender_id=self.peer_id,
                term=self.current_term,
                last_seq=my_last_seq
            )
            
            try:
                await self.transport.send_to(leader.host, leader.port, catchup_req)
                self.logger.info(f"Sent CATCHUP_REQ to leader peer_{leader.node_id}")
                return
            except Exception as e:
                self.logger.warning(f"Failed to send CATCHUP_REQ to leader: {e}")
        
        # If leader not available, try any other peer
        other_peers = self.membership.get_other_peers()
        if other_peers:
            peer = other_peers[0]  # Just pick the first one
            catchup_req = Message(
                type=MessageType.CATCHUP_REQ,
                sender_id=self.peer_id,
                term=self.current_term,
                last_seq=my_last_seq
            )
            
            try:
                await self.transport.send_to(peer.host, peer.port, catchup_req)
                self.logger.info(f"Sent CATCHUP_REQ to peer_{peer.node_id}")
            except Exception as e:
                self.logger.warning(f"Failed to send CATCHUP_REQ to peer_{peer.node_id}: {e}")
    
    async def _on_deliver_message(self, chat_msg: ChatMessage):
        """Callback when message is delivered in order"""
        await self.storage.append_message(chat_msg)
        
        self.logger.info(
            f"[seq={chat_msg.seq_no}] <peer_{chat_msg.sender_id}>: {chat_msg.text}"
        )
        
        if self.message_callback:
            self.message_callback(chat_msg)
    
    async def _on_become_leader(self, term: int):
        """Called when this peer becomes the leader"""
        self.logger.info(f"Became LEADER for term {term}")
        self.role = NodeRole.LEADER
        self.current_term = term
        self.failure.set_role(NodeRole.LEADER, term)
        self.membership.set_leader(self.peer_id)
        
        self.failure.stop_heartbeat_monitor()
        await self.failure.start_heartbeat_sender(self.transport, self.membership)
    
    async def _on_new_coordinator(self, leader_id: int, term: int):
        """Called when a new coordinator is announced"""
        self.logger.info(f"New coordinator: peer_{leader_id}, term={term}")
        self.role = NodeRole.FOLLOWER
        self.current_term = term
        self.failure.set_role(NodeRole.FOLLOWER, term)
        self.membership.set_leader(leader_id)
        
        self.failure.stop_heartbeat_sender()
        self.failure.start_heartbeat_monitor()
    
    async def _on_leader_timeout(self):
        """Callback when leader timeout detected"""
        self.logger.warning("Leader timeout detected, starting election")
        await self.election.start_election(self.transport, self.membership)
    
    async def _broadcast_to_all(self, message: Message):
        """Broadcast message to all known peers"""
        peers = self.membership.get_all_peers()
        for peer in peers:
            if peer.node_id != self.peer_id:
                try:
                    await self.transport.send_to(peer.host, peer.port, message)
                except Exception as e:
                    self.logger.debug(f"Failed to send to peer_{peer.node_id}: {e}")
