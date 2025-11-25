"""
Tests for Bully election algorithm.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.election import ElectionManager
from src.membership import MembershipManager
from src.common import Message, MessageType, PeerInfo


@pytest.mark.asyncio
async def test_election_no_higher_peers():
    """Test that node becomes leader when no higher priority peers exist."""
    election = ElectionManager(node_id=3)
    
    # Setup membership with only lower priority peers
    membership = MembershipManager(
        node_id=3,
        host="localhost",
        port=5003,
        seed_nodes=[]
    )
    membership.add_peer(PeerInfo(1, "localhost", 5001))
    membership.add_peer(PeerInfo(2, "localhost", 5002))
    
    # Mock transport
    transport = MagicMock()
    transport.send_to = AsyncMock(return_value=True)
    transport.broadcast = AsyncMock()
    
    became_leader = False
    
    async def on_become_leader(term):
        nonlocal became_leader
        became_leader = True
    
    async def on_new_coordinator(leader_id, term):
        pass
    
    election.set_callbacks(on_become_leader, on_new_coordinator)
    
    # Start election
    result = await election.start_election(transport, membership)
    
    assert result is True
    assert became_leader is True


@pytest.mark.asyncio
async def test_election_with_higher_peers():
    """Test that node waits for higher priority peers to respond."""
    election = ElectionManager(node_id=1)
    
    # Setup membership with higher priority peers
    membership = MembershipManager(
        node_id=1,
        host="localhost",
        port=5001,
        seed_nodes=[]
    )
    membership.add_peer(PeerInfo(2, "localhost", 5002))
    membership.add_peer(PeerInfo(3, "localhost", 5003))
    
    # Mock transport
    transport = MagicMock()
    transport.send_to = AsyncMock(return_value=True)
    transport.broadcast = AsyncMock()
    
    became_leader = False
    
    async def on_become_leader(term):
        nonlocal became_leader
        became_leader = True
    
    async def on_new_coordinator(leader_id, term):
        pass
    
    election.set_callbacks(on_become_leader, on_new_coordinator)
    
    # Reduce timeout for faster testing
    election.election_timeout = 0.1
    
    # Start election in background
    election_task = asyncio.create_task(
        election.start_election(transport, membership)
    )
    
    # Simulate receiving OK from higher peer during election
    await asyncio.sleep(0.05)
    election.received_ok = True
    
    # Wait for election to complete
    result = await election_task
    
    # Should not become leader since higher peer responded
    assert result is False
    assert became_leader is False


@pytest.mark.asyncio
async def test_handle_election_from_lower_peer():
    """Test handling ELECTION message from lower priority node."""
    election = ElectionManager(node_id=3)
    
    membership = MembershipManager(
        node_id=3,
        host="localhost",
        port=5003,
        seed_nodes=[]
    )
    membership.add_peer(PeerInfo(1, "localhost", 5001))
    
    # Mock transport
    transport = MagicMock()
    transport.send_to = AsyncMock(return_value=True)
    transport.broadcast = AsyncMock()
    
    # Create ELECTION message from lower priority node
    msg = Message(
        type=MessageType.ELECTION,
        sender_id=1,
        term=1
    )
    
    # Handle the election message
    await election.handle_election_message(msg, transport, membership)
    
    # Should have sent ELECTION_OK back
    assert transport.send_to.called


@pytest.mark.asyncio  
async def test_coordinator_announcement():
    """Test handling COORDINATOR message."""
    election = ElectionManager(node_id=1)
    
    membership = MembershipManager(
        node_id=1,
        host="localhost",
        port=5001,
        seed_nodes=[]
    )
    
    new_coordinator_id = None
    new_term = None
    
    async def on_become_leader(term):
        pass
    
    async def on_new_coordinator(leader_id, term):
        nonlocal new_coordinator_id, new_term
        new_coordinator_id = leader_id
        new_term = term
    
    election.set_callbacks(on_become_leader, on_new_coordinator)
    
    # Create COORDINATOR message with peer info
    leader_peer = PeerInfo(3, "localhost", 5003)
    msg = Message(
        type=MessageType.COORDINATOR,
        sender_id=3,
        term=5,
        membership=[leader_peer.to_dict()]
    )
    
    await election.handle_coordinator_message(msg, membership)
    
    assert membership.leader_id == 3
    assert election.current_term == 5
    assert new_coordinator_id == 3
    assert new_term == 5
    # Verify leader peer was added to membership
    leader = membership.get_leader()
    assert leader is not None
    assert leader.node_id == 3


@pytest.mark.asyncio
async def test_election_cancelled_by_coordinator():
    """Test that ongoing election is cancelled when COORDINATOR arrives."""
    election = ElectionManager(node_id=2)
    
    membership = MembershipManager(
        node_id=2,
        host="localhost",
        port=5002,
        seed_nodes=[]
    )
    membership.add_peer(PeerInfo(3, "localhost", 5003))
    
    # Mock transport
    transport = MagicMock()
    transport.send_to = AsyncMock(return_value=True)
    transport.broadcast = AsyncMock()
    
    became_leader = False
    received_coordinator = False
    
    async def on_become_leader(term):
        nonlocal became_leader
        became_leader = True
    
    async def on_new_coordinator(leader_id, term):
        nonlocal received_coordinator
        received_coordinator = True
    
    election.set_callbacks(on_become_leader, on_new_coordinator)
    
    # Reduce timeout for faster testing
    election.election_timeout = 0.2
    
    # Start election in background
    election_task = asyncio.create_task(
        election.start_election(transport, membership)
    )
    
    # Wait a bit then send COORDINATOR
    await asyncio.sleep(0.05)
    
    leader_peer = PeerInfo(3, "localhost", 5003)
    coordinator_msg = Message(
        type=MessageType.COORDINATOR,
        sender_id=3,
        term=2,
        membership=[leader_peer.to_dict()]
    )
    
    await election.handle_coordinator_message(coordinator_msg, membership)
    
    # Wait for election to complete
    result = await election_task
    
    # Election should be cancelled, node should not become leader
    assert result is False
    assert became_leader is False
    assert received_coordinator is True
    assert membership.leader_id == 3


