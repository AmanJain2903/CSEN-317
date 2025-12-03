#!/usr/bin/env python3
"""
Master Test Runner for Distributed Chat System

Runs all test suites:
- Unit tests (pytest)
- Demo scenarios (8 demos)
- Load tests
- Stress tests

Usage:
    python tests/run_all_tests.py --all
    python tests/run_all_tests.py --unit
    python tests/run_all_tests.py --demos
    python tests/run_all_tests.py --load
    python tests/run_all_tests.py --stress
"""

import sys
import asyncio
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRunner:
    """Master test runner"""
    
    def __init__(self):
        self.results: Dict[str, bool] = {}
        self.tests_dir = Path(__file__).parent
        
    def run_command(self, cmd: List[str], name: str) -> bool:
        """Run a command and capture result"""
        print(f"\n{'='*70}")
        print(f"RUNNING: {name}")
        print(f"{'='*70}\n")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.tests_dir.parent,
                capture_output=False,
                text=True
            )
            success = result.returncode == 0
            self.results[name] = success
            return success
        except Exception as e:
            print(f"\n[FAIL] Error running {name}: {e}")
            self.results[name] = False
            return False
    
    def run_unit_tests(self) -> bool:
        """Run pytest unit tests"""
        return self.run_command(
            ["pytest", "tests/", "-v", "--tb=short", 
             "-k", "not demo_ and not load_test and not stress_test"],
            "Unit Tests (pytest)"
        )
    
    def run_demo(self, demo_num: int, demo_name: str) -> bool:
        """Run a single demo script"""
        script = self.tests_dir / f"demo_{demo_num:02d}_{demo_name}.py"
        if not script.exists():
            print(f"[WARNING]  Demo script not found: {script}")
            return False
        
        return self.run_command(
            ["python", str(script)],
            f"Demo {demo_num}: {demo_name.replace('_', ' ').title()}"
        )
    
    def run_all_demos(self) -> bool:
        """Run all demo scenarios"""
        demos = [
            (1, "basic_messaging"),
            (2, "leader_failure"),
            (3, "rejoin_as_follower"),
            (4, "concurrent_clients"),
            (5, "out_of_order"),
            (6, "persistence"),
            (7, "network_monitoring"),
            (8, "client_reconnection"),
        ]
        
        print(f"\n{'='*70}")
        print("DEMO SCENARIOS TEST SUITE")
        print(f"{'='*70}\n")
        
        print("[WARNING]  NOTE: Some demos require manual actions (restarting nodes).")
        print("    You may need to interact during these tests.\n")
        
        all_passed = True
        for num, name in demos:
            if not self.run_demo(num, name):
                all_passed = False
                print(f"\n[FAIL] Demo {num} failed. Continue with remaining demos? (y/n): ", end="")
                response = input()
                if response.lower() != 'y':
                    break
            
            # Pause between demos
            if num < len(demos):
                print("\nPausing 5 seconds before next demo...")
                import time
                time.sleep(5)
        
        return all_passed
    
    def run_load_tests(self) -> bool:
        """Run load tests"""
        return self.run_command(
            ["python", "tests/load_test.py"],
            "Load Tests"
        )
    
    def run_stress_tests(self) -> bool:
        """Run stress tests"""
        return self.run_command(
            ["python", "tests/stress_test.py"],
            "Stress Tests"
        )
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print()
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for name, result in self.results.items():
            status = "[PASS] PASS" if result else "[FAIL] FAIL"
            print(f"{status} - {name}")
        
        print()
        print(f"Total: {passed}/{total} test suites passed")
        print(f"Success rate: {(passed/total)*100:.1f}%" if total > 0 else "No tests run")
        print("="*70)
        
        return all(self.results.values())


def check_prerequisites():
    """Check if nodes are running"""
    print("="*70)
    print("PREREQUISITE CHECK")
    print("="*70)
    print()
    print("Checking if nodes are running...")
    
    import socket
    
    nodes_running = []
    for port in [5001, 5002, 5003]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:
                nodes_running.append(port)
            sock.close()
        except:
            pass
    
    if len(nodes_running) == 3:
        print(f"[PASS] All 3 nodes are running (ports {nodes_running})")
        return True
    elif len(nodes_running) > 0:
        print(f"[WARNING]  Only {len(nodes_running)} node(s) running: {nodes_running}")
        print("   Some tests may fail without all 3 nodes.")
        return False
    else:
        print("[FAIL] No nodes are running!")
        print("\nTo start nodes:")
        print("  Terminal 1: python -m src.node --config configs/node1.yml")
        print("  Terminal 2: python -m src.node --config configs/node2.yml")
        print("  Terminal 3: python -m src.node --config configs/node3.yml")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run tests for Distributed Chat System"
    )
    parser.add_argument(
        '--all', action='store_true',
        help='Run all test suites (unit, demos, load, stress)'
    )
    parser.add_argument(
        '--unit', action='store_true',
        help='Run unit tests only'
    )
    parser.add_argument(
        '--demos', action='store_true',
        help='Run demo scenarios only'
    )
    parser.add_argument(
        '--load', action='store_true',
        help='Run load tests only'
    )
    parser.add_argument(
        '--stress', action='store_true',
        help='Run stress tests only'
    )
    parser.add_argument(
        '--skip-check', action='store_true',
        help='Skip prerequisite check'
    )
    
    args = parser.parse_args()
    
    # If no args, show help
    if not any([args.all, args.unit, args.demos, args.load, args.stress]):
        parser.print_help()
        print("\n" + "="*70)
        print("Quick Start:")
        print("  python tests/run_all_tests.py --unit     # Fast, no nodes needed")
        print("  python tests/run_all_tests.py --demos    # Interactive demos")
        print("  python tests/run_all_tests.py --load     # Performance tests")
        print("  python tests/run_all_tests.py --all      # Everything")
        print("="*70)
        return
    
    runner = TestRunner()
    
    # Check prerequisites for non-unit tests
    if not args.unit and not args.skip_check:
        if not check_prerequisites():
            print("\n[FAIL] Prerequisites not met. Start nodes or use --skip-check")
            sys.exit(1)
        
        print("\nPress Enter to continue with tests...")
        input()
    
    # Run requested test suites
    try:
        if args.unit or args.all:
            runner.run_unit_tests()
        
        if args.demos or args.all:
            runner.run_all_demos()
        
        if args.load or args.all:
            runner.run_load_tests()
        
        if args.stress or args.all:
            runner.run_stress_tests()
        
        # Print summary
        runner.print_summary()
        
        # Exit with appropriate code
        success = all(runner.results.values())
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n[WARNING]  Tests interrupted by user")
        runner.print_summary()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Test runner failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

