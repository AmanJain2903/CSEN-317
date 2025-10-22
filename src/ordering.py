"""
Total order broadcast using sequence numbers and message buffering.
"""
import asyncio
import logging
import time
from typing import Optional, Dict, List, Callable, Awaitable
from .common import Message, MessageType, ChatMessage


class OrderingManager:
    """
    Manages sequence number assignment (leader) and ordered delivery (all nodes).
    """
    
    def __init__(self, node_id: int, room_id: str = "general"):
        self.node_id = node_id
        self.room_id = room_id
        self.logger = logging.getLogger(f"ordering.{node_id}")
        
        # Leader state: last assigned sequence number
        self.last_seq: int = 0
        
        # Follower state: next expected sequence number for delivery
        self.next_expected_seq: int = 1
        
        # Buffer for out-of-order messages: seq_no -> ChatMessage
        self.message_buffer: Dict[int, ChatMessage] = {}
        
        # Delivered messages by (seq_no, term) for idempotence
        self.delivered: Dict[tuple[int, int], bool] = {}
        
        # Callback for when a message is delivered
        self.on_deliver: Optional[Callable[[ChatMessage], Awaitable[None]]] = None
    
    def set_deliver_handler(self, handler: Callable[[ChatMessage], Awaitable[None]]):
        """Set callback for message delivery."""
        self.on_deliver = handler
    
    def assign_sequence_number(self, msg_id: str, sender_id: int, text: str, term: int) -> ChatMessage:
        """
        Assign the next sequence number to a chat message (leader only).
        """
        self.last_seq += 1
        chat_msg = ChatMessage(
            seq_no=self.last_seq,
            term=term,
            msg_id=msg_id,
            sender_id=sender_id,
            room_id=self.room_id,
            text=text,
            timestamp=time.time(),
        )
        self.logger.info(f"Assigned seq_no={self.last_seq} to msg_id={msg_id}")
        return chat_msg
    
    async def handle_seq_chat(self, message: Message) -> bool:
        """
        Handle an incoming SEQ_CHAT message with an assigned sequence number.
        Buffers out-of-order messages and delivers in order.
        Returns True if message was newly delivered.
        """
        seq_no = message.seq_no
        term = message.term
        
        if seq_no is None:
            self.logger.warning("Received SEQ_CHAT without seq_no")
            return False
        
        # Check for duplicate delivery
        if (seq_no, term) in self.delivered:
            self.logger.debug(f"Ignoring duplicate seq_no={seq_no}, term={term}")
            return False
        
        # Create ChatMessage
        chat_msg = ChatMessage(
            seq_no=seq_no,
            term=term,
            msg_id=message.msg_id or "",
            sender_id=message.sender_id,
            room_id=message.room_id,
            text=message.payload or "",
            timestamp=time.time(),
        )
        
        # Check if this is the next expected message
        if seq_no == self.next_expected_seq:
            # Deliver immediately
            await self._deliver_message(chat_msg)
            
            # Try to deliver buffered messages
            await self._deliver_buffered_messages()
            return True
        elif seq_no > self.next_expected_seq:
            # Buffer for later delivery
            self.message_buffer[seq_no] = chat_msg
            self.logger.debug(
                f"Buffered out-of-order message seq_no={seq_no} "
                f"(expected {self.next_expected_seq})"
            )
            return False
        else:
            # Old message, might be duplicate or out of sync
            self.logger.debug(f"Received old message seq_no={seq_no}, ignoring")
            return False
    
    async def _deliver_message(self, chat_msg: ChatMessage):
        """Deliver a message in order."""
        self.logger.info(
            f"Delivering seq_no={chat_msg.seq_no}: "
            f"node_{chat_msg.sender_id}: {chat_msg.text}"
        )
        
        # Mark as delivered
        self.delivered[(chat_msg.seq_no, chat_msg.term)] = True
        self.next_expected_seq = chat_msg.seq_no + 1
        
        # Callback
        if self.on_deliver:
            await self.on_deliver(chat_msg)
    
    async def _deliver_buffered_messages(self):
        """Deliver any buffered messages that are now in order."""
        while self.next_expected_seq in self.message_buffer:
            chat_msg = self.message_buffer.pop(self.next_expected_seq)
            await self._deliver_message(chat_msg)
    
    def get_last_seq(self) -> int:
        """Get the last sequence number (for leader) or last delivered (for follower)."""
        if self.last_seq > 0:
            return self.last_seq
        else:
            return self.next_expected_seq - 1
    
    def set_last_seq(self, seq: int):
        """Set the last sequence number (recovery from storage)."""
        self.last_seq = max(self.last_seq, seq)
        self.next_expected_seq = max(self.next_expected_seq, seq + 1)
        self.logger.info(f"Set last_seq={self.last_seq}, next_expected={self.next_expected_seq}")
    
    async def request_catchup(self, transport, leader_peer, term: int):
        """Request catch-up messages from the leader."""
        last_seq = self.next_expected_seq - 1
        
        self.logger.info(f"Requesting catch-up from seq_no={last_seq + 1}")
        
        catchup_req = Message(
            type=MessageType.CATCHUP_REQ,
            sender_id=self.node_id,
            term=term,
            last_seq=last_seq,
        )
        
        await transport.send_to(leader_peer.host, leader_peer.port, catchup_req)
    
    async def handle_catchup_request(
        self,
        message: Message,
        transport,
        storage,
        requester_peer
    ):
        """Handle a catch-up request from a follower (leader only)."""
        last_seq = message.last_seq or 0
        
        self.logger.info(
            f"Catch-up request from node_{message.sender_id} "
            f"for messages after seq_no={last_seq}"
        )
        
        # Get messages from storage
        messages = await storage.get_messages_after(last_seq)
        
        # Send each message as SEQ_CHAT
        for chat_msg in messages:
            seq_chat_msg = Message(
                type=MessageType.SEQ_CHAT,
                sender_id=chat_msg.sender_id,
                term=chat_msg.term,
                msg_id=chat_msg.msg_id,
                seq_no=chat_msg.seq_no,
                room_id=chat_msg.room_id,
                payload=chat_msg.text,
            )
            await transport.send_to(
                requester_peer.host,
                requester_peer.port,
                seq_chat_msg
            )
        
        self.logger.info(f"Sent {len(messages)} catch-up messages to node_{message.sender_id}")

