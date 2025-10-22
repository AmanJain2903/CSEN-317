#!/usr/bin/env python3
"""
Simple script to verify all imports are correct.
"""
import sys

print("Verifying Python syntax and imports...")
print("-" * 50)

# Test basic Python imports
try:
    import asyncio
    import logging
    import argparse
    import json
    import time
    import uuid
    from pathlib import Path
    from dataclasses import dataclass
    from enum import Enum
    from typing import Optional, List, Dict, Any
    print("✓ Standard library imports OK")
except ImportError as e:
    print(f"✗ Standard library import error: {e}")
    sys.exit(1)

# Test our module structure
try:
    from src.common import Message, MessageType, NodeRole, PeerInfo, ChatMessage
    print("✓ src.common imports OK")
except Exception as e:
    print(f"✗ src.common import error: {e}")
    sys.exit(1)

print("-" * 50)
print("All basic verifications passed!")
print("")
print("To fully test the system, install dependencies:")
print("  python3 -m venv venv")
print("  source venv/bin/activate")
print("  pip install -r requirements.txt")
print("")
print("Then start nodes:")
print("  python3 -m src.node --config configs/node1_local.yml")

