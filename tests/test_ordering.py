"""
Tests for total order message delivery.
"""
import pytest
import asyncio
from src.common import Message, MessageType, ChatMessage
from src.ordering import OrderingManager


@pytest.mark.asyncio
async def test_in_order_delivery():
    """Test that messages delivered in order are processed immediately."""
    ordering = OrderingManager(node_id=1)
    
    delivered_messages = []
    
    async def on_deliver(msg: ChatMessage):
        delivered_messages.append(msg)
    
    ordering.set_deliver_handler(on_deliver)
    
    # Send messages in order
    for i in range(1, 4):
        msg = Message(
            type=MessageType.SEQ_CHAT,
            sender_id=1,
            term=1,
            seq_no=i,
            msg_id=f"msg_{i}",
            payload=f"Message {i}"
        )
        await ordering.handle_seq_chat(msg)
    
    # All should be delivered
    assert len(delivered_messages) == 3
    assert delivered_messages[0].seq_no == 1
    assert delivered_messages[1].seq_no == 2
    assert delivered_messages[2].seq_no == 3


@pytest.mark.asyncio
async def test_out_of_order_buffering():
    """Test that out-of-order messages are buffered and delivered when gap is filled."""
    ordering = OrderingManager(node_id=1)
    
    delivered_messages = []
    
    async def on_deliver(msg: ChatMessage):
        delivered_messages.append(msg)
    
    ordering.set_deliver_handler(on_deliver)
    
    # Send messages out of order: 1, 3, 2
    msg1 = Message(
        type=MessageType.SEQ_CHAT,
        sender_id=1,
        term=1,
        seq_no=1,
        msg_id="msg_1",
        payload="Message 1"
    )
    await ordering.handle_seq_chat(msg1)
    assert len(delivered_messages) == 1
    
    # Send seq_no 3 (should be buffered)
    msg3 = Message(
        type=MessageType.SEQ_CHAT,
        sender_id=1,
        term=1,
        seq_no=3,
        msg_id="msg_3",
        payload="Message 3"
    )
    await ordering.handle_seq_chat(msg3)
    assert len(delivered_messages) == 1  # Still only 1 delivered
    
    # Send seq_no 2 (should trigger delivery of both 2 and 3)
    msg2 = Message(
        type=MessageType.SEQ_CHAT,
        sender_id=1,
        term=1,
        seq_no=2,
        msg_id="msg_2",
        payload="Message 2"
    )
    await ordering.handle_seq_chat(msg2)
    assert len(delivered_messages) == 3  # Now all 3 delivered
    assert delivered_messages[0].seq_no == 1
    assert delivered_messages[1].seq_no == 2
    assert delivered_messages[2].seq_no == 3


@pytest.mark.asyncio
async def test_duplicate_detection():
    """Test that duplicate messages are ignored."""
    ordering = OrderingManager(node_id=1)
    
    delivered_messages = []
    
    async def on_deliver(msg: ChatMessage):
        delivered_messages.append(msg)
    
    ordering.set_deliver_handler(on_deliver)
    
    # Send same message twice
    msg = Message(
        type=MessageType.SEQ_CHAT,
        sender_id=1,
        term=1,
        seq_no=1,
        msg_id="msg_1",
        payload="Message 1"
    )
    
    await ordering.handle_seq_chat(msg)
    await ordering.handle_seq_chat(msg)
    
    # Should only be delivered once
    assert len(delivered_messages) == 1


@pytest.mark.asyncio
async def test_sequence_number_assignment():
    """Test that leader assigns sequential sequence numbers."""
    ordering = OrderingManager(node_id=1)
    
    # Assign sequence numbers
    msg1 = ordering.assign_sequence_number("msg_1", 1, "Hello", 1)
    assert msg1.seq_no == 1
    
    msg2 = ordering.assign_sequence_number("msg_2", 2, "World", 1)
    assert msg2.seq_no == 2
    
    msg3 = ordering.assign_sequence_number("msg_3", 1, "!", 1)
    assert msg3.seq_no == 3
    
    assert ordering.get_last_seq() == 3

