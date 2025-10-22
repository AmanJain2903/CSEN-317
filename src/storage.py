"""
Persistent storage for chat messages using append-only log files.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional
from .common import ChatMessage


class StorageManager:
    """
    Manages persistent storage of chat messages in an append-only log.
    """
    
    def __init__(self, node_id: int, log_dir: str):
        self.node_id = node_id
        self.log_dir = Path(log_dir)
        self.logger = logging.getLogger(f"storage.{node_id}")
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file path
        self.log_file = self.log_dir / f"node_{node_id}_messages.jsonl"
        
        # Lock for file operations
        self.write_lock = asyncio.Lock()
    
    async def append_message(self, chat_msg: ChatMessage):
        """Append a chat message to the log file."""
        async with self.write_lock:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(chat_msg.to_dict()) + '\n')
                self.logger.debug(f"Appended seq_no={chat_msg.seq_no} to log")
            except Exception as e:
                self.logger.error(f"Failed to append message to log: {e}")
    
    async def load_messages(self) -> List[ChatMessage]:
        """Load all messages from the log file."""
        messages = []
        
        if not self.log_file.exists():
            self.logger.info("No existing log file found")
            return messages
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        messages.append(ChatMessage.from_dict(data))
            
            self.logger.info(f"Loaded {len(messages)} messages from log")
        except Exception as e:
            self.logger.error(f"Failed to load messages from log: {e}")
        
        return messages
    
    async def get_last_seq(self) -> int:
        """Get the last sequence number from the log."""
        messages = await self.load_messages()
        if messages:
            return max(msg.seq_no for msg in messages)
        return 0
    
    async def get_messages_after(self, seq_no: int) -> List[ChatMessage]:
        """Get all messages with sequence number greater than seq_no."""
        all_messages = await self.load_messages()
        return [msg for msg in all_messages if msg.seq_no > seq_no]
    
    async def recover_state(self) -> tuple[int, List[ChatMessage]]:
        """
        Recover state from persistent storage.
        Returns (last_seq, messages).
        """
        messages = await self.load_messages()
        last_seq = 0
        if messages:
            last_seq = max(msg.seq_no for msg in messages)
        
        self.logger.info(f"Recovered state: last_seq={last_seq}, messages={len(messages)}")
        return last_seq, messages

