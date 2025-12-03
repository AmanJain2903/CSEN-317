# Tests Directory

Comprehensive test suite for the Distributed Chat System.

## Quick Start

```bash
# Unit tests (fast, no nodes needed)
make test

# Demo scenarios (requires 3 nodes)
make test-demos

# Load tests (requires 3 nodes)
make test-load

# Stress tests (requires 3 nodes)
make test-stress

# Everything
make test-all
```

## Test Files

### Unit Tests
- `test_ordering.py` - Message ordering and sequencing
- `test_election.py` - Bully algorithm and leader election
- `test_failure.py` - Heartbeat and failure detection
- `test_integration_local.py` - End-to-end integration tests

### Demo Scenarios
- `demo_01_basic_messaging.py` - Total order validation
- `demo_02_leader_failure.py` - Leader failure and election
- `demo_03_rejoin_as_follower.py` - Crashed leader recovery
- `demo_04_concurrent_clients.py` - Concurrent message ordering
- `demo_05_out_of_order.py` - Out-of-order buffering
- `demo_06_persistence.py` - Crash recovery and persistence
- `demo_07_network_monitoring.py` - Performance metrics
- `demo_08_client_reconnection.py` - Client reconnection

### Performance Tests
- `load_test.py` - Load testing with metrics
- `stress_test.py` - Stress testing and limits

### Test Runner
- `run_all_tests.py` - Master test orchestrator

## Running Individual Tests

```bash
# Specific unit test
pytest tests/test_ordering.py -v

# Specific demo
python tests/demo_01_basic_messaging.py

# Load test
python tests/load_test.py

# Stress test
python tests/stress_test.py
```

## Prerequisites

### For Unit Tests
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`
- No nodes required

### For Demo/Load/Stress Tests
- All 3 nodes must be running:
  ```bash
  # Terminal 1
  python -m src.node --config configs/node1.yml
  
  # Terminal 2
  python -m src.node --config configs/node2.yml
  
  # Terminal 3
  python -m src.node --config configs/node3.yml
  ```

## Documentation

See **[../TESTING.md](../TESTING.md)** for complete testing guide.

See **[../TEST_SUITE_SUMMARY.md](../TEST_SUITE_SUMMARY.md)** for detailed test inventory.

## Test Coverage

Run with coverage:
```bash
make test-coverage
open htmlcov/index.html
```

## Troubleshooting

### Connection Refused
Start all 3 nodes before running demos/load/stress tests.

### Too Many Open Files
```bash
ulimit -n 4096
```

### Timeout Errors
Ensure nodes are connected and leader is elected. Check logs.

### Import Errors
```bash
pip install -r requirements.txt
```

## Test Statistics

- **Unit Tests**: 17 tests, ~3 seconds
- **Demo Scenarios**: 8 scenarios, ~15 minutes
- **Load Tests**: 3 profiles, ~10 minutes
- **Stress Tests**: 5 scenarios, ~20 minutes
- **Total Coverage**: 33+ test scenarios

---

For more details, see [TESTING.md](../TESTING.md).

