"""
Integration tests for the distributed chat system.
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from src.common import Message, MessageType
from src.ordering import OrderingManager
from src.storage import StorageManager


@pytest.mark.asyncio
async def test_ordering_with_storage():
    """Test that ordering and storage work together."""
    # Create temporary directory for logs
    temp_dir = tempfile.mkdtemp()
    
    try:
        ordering = OrderingManager(node_id=1)
        storage = StorageManager(node_id=1, log_dir=temp_dir)
        
        delivered_messages = []
        
        async def on_deliver(msg):
            delivered_messages.append(msg)
            # Persist delivered message
            await storage.append_message(msg)
        
        ordering.set_deliver_handler(on_deliver)
        
        # Deliver some messages
        for i in range(1, 6):
            msg = Message(
                type=MessageType.SEQ_CHAT,
                sender_id=1,
                term=1,
                seq_no=i,
                msg_id=f"msg_{i}",
                payload=f"Message {i}"
            )
            await ordering.handle_seq_chat(msg)
        
        assert len(delivered_messages) == 5
        
        # Load messages from storage
        loaded_messages = await storage.load_messages()
        assert len(loaded_messages) == 5
        
        # Verify order
        for i, msg in enumerate(loaded_messages):
            assert msg.seq_no == i + 1
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_storage_recovery():
    """Test that state can be recovered from storage."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create storage and add some messages
        storage1 = StorageManager(node_id=1, log_dir=temp_dir)
        ordering1 = OrderingManager(node_id=1)
        
        async def on_deliver(msg):
            await storage1.append_message(msg)
        
        ordering1.set_deliver_handler(on_deliver)
        
        # Deliver messages
        for i in range(1, 4):
            msg = Message(
                type=MessageType.SEQ_CHAT,
                sender_id=1,
                term=1,
                seq_no=i,
                msg_id=f"msg_{i}",
                payload=f"Message {i}"
            )
            await ordering1.handle_seq_chat(msg)
        
        # Create new storage/ordering instances (simulating restart)
        storage2 = StorageManager(node_id=1, log_dir=temp_dir)
        ordering2 = OrderingManager(node_id=1)
        
        # Recover state
        last_seq, messages = await storage2.recover_state()
        ordering2.set_last_seq(last_seq)
        
        assert last_seq == 3
        assert len(messages) == 3
        assert ordering2.next_expected_seq == 4
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_catchup_scenario():
    """Test catch-up functionality."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Leader's storage
        leader_storage = StorageManager(node_id=1, log_dir=temp_dir)
        leader_ordering = OrderingManager(node_id=1)
        
        async def on_deliver_leader(msg):
            await leader_storage.append_message(msg)
        
        leader_ordering.set_deliver_handler(on_deliver_leader)
        
        # Leader delivers 5 messages
        for i in range(1, 6):
            msg = Message(
                type=MessageType.SEQ_CHAT,
                sender_id=1,
                term=1,
                seq_no=i,
                msg_id=f"msg_{i}",
                payload=f"Message {i}"
            )
            await leader_ordering.handle_seq_chat(msg)
        
        # Follower has only seen first 2 messages
        follower_ordering = OrderingManager(node_id=2)
        follower_ordering.set_last_seq(2)
        
        # Get catch-up messages
        missing_messages = await leader_storage.get_messages_after(2)
        
        assert len(missing_messages) == 3
        assert missing_messages[0].seq_no == 3
        assert missing_messages[1].seq_no == 4
        assert missing_messages[2].seq_no == 5
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_concurrent_message_buffering():
    """Test that concurrent out-of-order messages are handled correctly."""
    ordering = OrderingManager(node_id=1)
    
    delivered_messages = []
    
    async def on_deliver(msg):
        delivered_messages.append(msg)
    
    ordering.set_deliver_handler(on_deliver)
    
    # Send messages in random order concurrently
    messages = []
    for seq in [1, 5, 3, 2, 4]:
        msg = Message(
            type=MessageType.SEQ_CHAT,
            sender_id=1,
            term=1,
            seq_no=seq,
            msg_id=f"msg_{seq}",
            payload=f"Message {seq}"
        )
        messages.append(msg)
    
    # Handle all messages
    tasks = [ordering.handle_seq_chat(msg) for msg in messages]
    await asyncio.gather(*tasks)
    
    # All should eventually be delivered in order
    assert len(delivered_messages) == 5
    for i, msg in enumerate(delivered_messages):
        assert msg.seq_no == i + 1

