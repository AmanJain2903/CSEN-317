"""
Tests for failure detection with heartbeats.
"""
import pytest
import asyncio
import time
from src.failure import FailureDetector
from src.common import NodeRole


@pytest.mark.asyncio
async def test_heartbeat_recording():
    """Test that heartbeats are properly recorded."""
    detector = FailureDetector(
        node_id=1,
        heartbeat_interval_ms=100,
        leader_timeout_ms=500
    )
    
    # Record a heartbeat
    detector.record_heartbeat(term=1)
    
    assert detector.last_heartbeat_time is not None
    last_time = detector.last_heartbeat_time
    
    # Wait and record another
    await asyncio.sleep(0.1)
    detector.record_heartbeat(term=1)
    
    assert detector.last_heartbeat_time > last_time


@pytest.mark.asyncio
async def test_leader_timeout_detection():
    """Test that leader timeout is detected."""
    detector = FailureDetector(
        node_id=1,
        heartbeat_interval_ms=50,
        leader_timeout_ms=200
    )
    
    detector.set_role(NodeRole.FOLLOWER, term=1)
    
    timeout_detected = False
    
    async def on_timeout():
        nonlocal timeout_detected
        timeout_detected = True
    
    detector.set_timeout_handler(on_timeout)
    
    # Start monitoring
    await detector.start_heartbeat_monitor()
    
    # Wait longer than timeout
    await asyncio.sleep(0.3)
    
    # Stop monitoring
    await detector.stop()
    
    assert timeout_detected is True


@pytest.mark.asyncio
async def test_no_timeout_with_heartbeats():
    """Test that timeout doesn't occur when heartbeats are received."""
    detector = FailureDetector(
        node_id=1,
        heartbeat_interval_ms=50,
        leader_timeout_ms=200
    )
    
    detector.set_role(NodeRole.FOLLOWER, term=1)
    
    timeout_detected = False
    
    async def on_timeout():
        nonlocal timeout_detected
        timeout_detected = True
    
    detector.set_timeout_handler(on_timeout)
    
    # Start monitoring
    await detector.start_heartbeat_monitor()
    
    # Send periodic heartbeats
    for _ in range(5):
        await asyncio.sleep(0.05)
        detector.record_heartbeat(term=1)
    
    # Stop monitoring
    await detector.stop()
    
    assert timeout_detected is False


@pytest.mark.asyncio
async def test_role_change():
    """Test that role changes are properly handled."""
    detector = FailureDetector(
        node_id=1,
        heartbeat_interval_ms=100,
        leader_timeout_ms=500
    )
    
    # Start as follower
    detector.set_role(NodeRole.FOLLOWER, term=1)
    assert detector.role == NodeRole.FOLLOWER
    assert detector.current_term == 1
    
    # Become leader
    detector.set_role(NodeRole.LEADER, term=2)
    assert detector.role == NodeRole.LEADER
    assert detector.current_term == 2

