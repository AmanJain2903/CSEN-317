# Testing Guide

Comprehensive testing documentation for the Distributed Chat System.

## Table of Contents

- [Overview](#overview)
- [Test Types](#test-types)
- [Quick Start](#quick-start)
- [Unit Tests](#unit-tests)
- [Demo Scenarios](#demo-scenarios)
- [Load Testing](#load-testing)
- [Stress Testing](#stress-testing)
- [Running All Tests](#running-all-tests)

## Overview

The project includes multiple test suites:

1. **Unit Tests**: Component-level tests (17 tests)
2. **Demo Scenarios**: End-to-end functional tests (8 scenarios)
3. **Load Tests**: Performance under normal load (3 tests)
4. **Stress Tests**: System limits and recovery (5 tests)

## Test Types

### Unit Tests (No nodes required)
- Fast, isolated component tests
- Mock external dependencies
- 17 tests covering all core modules
- Run with: `pytest tests/`

### Demo Scenarios (Requires 3 nodes)
- End-to-end functional validation
- Tests real distributed behavior
- Some require manual intervention
- 8 comprehensive scenarios

### Load Tests (Requires 3 nodes)
- Performance under realistic load
- Measures throughput and latency
- Tests concurrent clients
- 3 load profiles

### Stress Tests (Requires 3 nodes)
- Push system to limits
- Find breaking points
- Test recovery mechanisms
- 5 extreme scenarios

## Quick Start

### 1. Run Unit Tests (Fastest)

No nodes required:

```bash
# Simple
make test

# Or directly
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### 2. Run Demo Scenarios

Start nodes first:

```bash
# Terminal 1
python -m src.node --config configs/node1.yml

# Terminal 2
python -m src.node --config configs/node2.yml

# Terminal 3
python -m src.node --config configs/node3.yml

# Terminal 4 - Run demos
python tests/run_all_tests.py --demos
```

### 3. Run Load Tests

With nodes running:

```bash
python tests/load_test.py
```

### 4. Run Stress Tests

With nodes running:

```bash
python tests/stress_test.py
```

### 5. Run Everything

```bash
# Start nodes first, then:
python tests/run_all_tests.py --all
```

## Unit Tests

### Coverage

- [PASS] **Ordering** (`test_ordering.py`): 4 tests
  - Sequence number assignment
  - In-order delivery
  - Out-of-order buffering
  - Duplicate detection

- [PASS] **Election** (`test_election.py`): 5 tests
  - Bully algorithm
  - Coordinator announcement
  - Election cancellation
  - Higher priority handling

- [PASS] **Failure Detection** (`test_failure.py`): 4 tests
  - Heartbeat recording
  - Timeout detection
  - Role changes
  - Recovery

- [PASS] **Integration** (`test_integration_local.py`): 4 tests
  - Storage persistence
  - Catch-up protocol
  - Recovery scenarios
  - End-to-end flows

### Running Unit Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_ordering.py -v

# With coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Stop on first failure
pytest tests/ -x

# Run in parallel (faster)
pytest tests/ -n auto
```

## Demo Scenarios

### Prerequisites

All 3 nodes must be running on ports 5001, 5002, 5003.

### Demo 1: Basic Messaging and Total Order

**Objective**: Verify total order guarantee

```bash
python tests/demo_01_basic_messaging.py
```

**What it tests**:
- Messages from multiple clients
- All nodes receive in same order
- Sequence numbers are consistent

**Expected result**: [PASS] All clients have identical order

---

### Demo 2: Leader Failure and Election

**Objective**: Test automatic failover

```bash
python tests/demo_02_leader_failure.py
```

**What it tests**:
- Detects leader crash
- Bully election runs
- New leader takes over
- Messages continue to be delivered

**Expected result**: [PASS] System recovers, new leader elected

**Note**: This demo kills Node 3 automatically

---

### Demo 3: Leader Rejoining as Follower

**Objective**: Test crashed leader recovery

```bash
python tests/demo_03_rejoin_as_follower.py
```

**What it tests**:
- Crashed leader rejoins as follower
- Catch-up protocol retrieves missed messages
- Node continues as follower

**Expected result**: [PASS] Node 3 catches up with all messages

**Note**: Requires manual restart of Node 3

---

### Demo 4: Concurrent Messages from Multiple Clients

**Objective**: Test high concurrency

```bash
python tests/demo_04_concurrent_clients.py
```

**What it tests**:
- 6+ clients sending simultaneously
- Messages interleave correctly
- Total order maintained despite concurrency

**Expected result**: [PASS] All clients agree on interleaved order

---

### Demo 5: Out-of-Order Message Handling

**Objective**: Test buffering mechanism

```bash
python tests/demo_05_out_of_order.py
```

**What it tests**:
- Rapid message bursts
- Messages may arrive out of order
- Nodes buffer and reorder correctly

**Expected result**: [PASS] All nodes deliver in monotonic sequence order

---

### Demo 6: Persistence and Recovery

**Objective**: Test crash recovery

```bash
python tests/demo_06_persistence.py
```

**What it tests**:
- Messages persist to disk
- Node recovers state after crash
- Log files are intact

**Expected result**: [PASS] All messages recovered from log

**Note**: Requires manual restart of Node 1

---

### Demo 7: Network Monitoring

**Objective**: Measure performance metrics

```bash
python tests/demo_07_network_monitoring.py
```

**What it tests**:
- Message latency (avg, p50, p95, p99)
- Throughput (messages/second)
- Per-client statistics

**Expected result**: [PASS] Latency < 1s, throughput > 5 msg/s

---

### Demo 8: Client Reconnection

**Objective**: Test client resilience

```bash
python tests/demo_08_client_reconnection.py
```

**What it tests**:
- Clients disconnect and reconnect
- Multiple rapid reconnections
- Messages continue to flow

**Expected result**: [PASS] All reconnections successful

---

## Load Testing

### Overview

Tests system under realistic load:

1. **Sustained Throughput**: 10 clients, 50 msgs each, rate-limited
2. **Burst Traffic**: 20 clients, 10 msgs each, no rate limit
3. **Concurrent Connections**: 50+ simultaneous clients

### Running Load Tests

```bash
# Ensure nodes are running
python tests/load_test.py
```

### Metrics Collected

- **Throughput**: Messages per second
- **Latency**: Average, P50, P95, P99, Max
- **Delivery Rate**: % of messages delivered
- **Error Rate**: Failed operations

### Expected Performance

- **Throughput**: > 100 msg/s
- **Latency**: < 100ms average
- **Delivery**: > 95%
- **Errors**: < 5%

### Sample Output

```
LOAD TEST: Sustained Throughput
  Clients: 10
  Messages per client: 50
  Total messages: 500

 Messages:
   Sent:     500
   Received: 498
   Delivery: 99.6%

 Performance:
   Duration:   5.23s
   Throughput: 95.6 msg/s

  Latency:
   Average: 45.23ms
   P50:     42.10ms
   P95:     67.89ms
   P99:     89.12ms
   Max:     123.45ms

[PASS] PASS
```

## Stress Testing

### Overview

Pushes system to breaking point:

1. **Max Connections**: Find connection limit (50, 100, 200, 500, 1000)
2. **Connection Churn**: Rapid connect/disconnect cycles
3. **Message Flood**: 30 clients × 100 messages
4. **Socket Limits**: Binary search for max reliable connections
5. **Leader Under Stress**: Heavy load + leader failure

### Running Stress Tests

```bash
# WARNING: Heavy system load
python tests/stress_test.py
```

### What Gets Tested

- Maximum concurrent connections
- System recovery under extreme load
- Resource exhaustion handling
- Socket limit discovery
- Leader failover under stress

### Expected Limits

- **Connections**: 200-500+ (depends on system)
- **Churn Rate**: > 95% success
- **Flood**: > 90% delivery
- **Recovery**: System continues after leader failure

### Sample Output

```
STRESS TEST: Maximum Concurrent Connections

Testing 100 concurrent connections...
  Connected: 100/100 in 2.34s
  Messages sent: 100/100

Testing 200 concurrent connections...
  Connected: 198/200 in 4.56s
  Messages sent: 198/198

Maximum successful connections: 200

[PASS] PASS
```

## Running All Tests

### Master Test Runner

```bash
# Run everything
python tests/run_all_tests.py --all

# Or selectively
python tests/run_all_tests.py --unit     # Just unit tests
python tests/run_all_tests.py --demos    # Just demos
python tests/run_all_tests.py --load     # Just load tests
python tests/run_all_tests.py --stress   # Just stress tests
```

### Complete Test Suite

1. Start all nodes
2. Run master test runner
3. Wait for completion (may take 30+ minutes)
4. Review summary

### Test Order

1. **Unit Tests** (2-3 minutes)
2. **Demo Scenarios** (10-15 minutes, some manual)
3. **Load Tests** (5-10 minutes)
4. **Stress Tests** (10-20 minutes)

## Continuous Integration

### GitHub Actions (if configured)

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```

### Docker-based Testing

```bash
# Run tests in Docker
cd deploy
docker compose up -d

# Wait for nodes to start
sleep 10

# Run tests against Docker nodes
python tests/load_test.py

# Cleanup
docker compose down
```

## Troubleshooting

### Tests Fail: "Connection refused"

**Problem**: Nodes not running

**Solution**:
```bash
# Start all nodes
python -m src.node --config configs/node1.yml
python -m src.node --config configs/node2.yml
python -m src.node --config configs/node3.yml
```

### Tests Timeout

**Problem**: Nodes not electing leader

**Solution**:
- Check logs for election messages
- Ensure node_ids are unique (1, 2, 3)
- Verify network connectivity

### High Latency

**Problem**: System under load or slow network

**Solution**:
- Close other applications
- Ensure nodes run locally (not over network)
- Check system resources (CPU, memory)

### Socket Errors

**Problem**: Too many open files

**Solution**:
```bash
# macOS/Linux: Increase file descriptor limit
ulimit -n 4096

# Check current limit
ulimit -n
```

### Import Errors

**Problem**: Module not found

**Solution**:
```bash
# Ensure in project root
cd /path/to/CSEN317-Distributed-Systems

# Activate venv if using one
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Best Practices

### Before Testing

1. [PASS] Start fresh: Kill old node processes
2. [PASS] Clean logs: `rm -rf data/logs/*.jsonl`
3. [PASS] Check ports: `lsof -i :5001-5003`
4. [PASS] Increase limits: `ulimit -n 4096`

### During Testing

1.  Monitor logs in separate terminals
2.  Watch for errors or warnings
3.  Note timing of failures
4.  Save logs if tests fail

### After Testing

1.  Stop all nodes cleanly (Ctrl+C)
2.  Archive logs for analysis
3.  Document any failures
4.  Clean up for next run

## Test Results Reference

### Expected Pass Rates

- **Unit Tests**: 100% (17/17)
- **Demo Scenarios**: 100% (8/8) with manual steps
- **Load Tests**: > 95%
- **Stress Tests**: System-dependent, recovery validated

### Performance Benchmarks

- **Latency**: < 100ms average
- **Throughput**: 100-500 msg/s (single leader)
- **Connections**: 200+ concurrent
- **Recovery**: < 5 seconds after leader failure

---

## Summary

| Test Suite | Tests | Duration | Prerequisites | Automation |
|------------|-------|----------|---------------|------------|
| Unit | 17 | 2-3 min | None | [PASS] Full |
| Demos | 8 | 10-15 min | 3 nodes | [WARNING] Partial |
| Load | 3 | 5-10 min | 3 nodes | [PASS] Full |
| Stress | 5 | 10-20 min | 3 nodes | [WARNING] Partial |

**Total**: 33+ test scenarios covering all requirements

For questions or issues, refer to main [README.md](README.md) or [ARCHITECTURE.md](ARCHITECTURE.md).

