"""
Common data structures, message schemas, and utility functions.
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Any, Dict


class MessageType(str, Enum):
    """Message types for the distributed chat protocol."""
    JOIN = "JOIN"
    JOIN_ACK = "JOIN_ACK"
    HEARTBEAT = "HEARTBEAT"
    ELECTION = "ELECTION"
    ELECTION_OK = "ELECTION_OK"
    COORDINATOR = "COORDINATOR"
    CHAT = "CHAT"
    SEQ_CHAT = "SEQ_CHAT"
    CATCHUP_REQ = "CATCHUP_REQ"
    CATCHUP_RESP = "CATCHUP_RESP"


class NodeRole(str, Enum):
    """Node role in the cluster."""
    LEADER = "LEADER"
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"


@dataclass
class PeerInfo:
    """Information about a peer node."""
    node_id: int
    host: str
    port: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PeerInfo':
        return cls(
            node_id=data['node_id'],
            host=data['host'],
            port=data['port']
        )
    
    def address(self) -> tuple[str, int]:
        return (self.host, self.port)


@dataclass
class Message:
    """Base message structure for all protocol messages."""
    type: MessageType
    sender_id: int
    term: int
    room_id: str = "general"
    msg_id: Optional[str] = None
    seq_no: Optional[int] = None
    payload: Optional[Any] = None
    membership: Optional[List[Dict[str, Any]]] = None
    last_seq: Optional[int] = None  # for catchup
    leader_id: Optional[int] = None  # current leader
    
    def __post_init__(self):
        if self.msg_id is None and self.type in [MessageType.CHAT, MessageType.SEQ_CHAT]:
            self.msg_id = str(uuid.uuid4())
    
    def to_json(self) -> str:
        """Serialize message to JSON."""
        data = {
            'type': self.type.value,
            'sender_id': self.sender_id,
            'term': self.term,
            'room_id': self.room_id,
        }
        if self.msg_id is not None:
            data['msg_id'] = self.msg_id
        if self.seq_no is not None:
            data['seq_no'] = self.seq_no
        if self.payload is not None:
            data['payload'] = self.payload
        if self.membership is not None:
            data['membership'] = self.membership
        if self.last_seq is not None:
            data['last_seq'] = self.last_seq
        if self.leader_id is not None:
            data['leader_id'] = self.leader_id
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, data: str) -> 'Message':
        """Deserialize message from JSON."""
        obj = json.loads(data)
        return cls(
            type=MessageType(obj['type']),
            sender_id=obj['sender_id'],
            term=obj['term'],
            room_id=obj.get('room_id', 'general'),
            msg_id=obj.get('msg_id'),
            seq_no=obj.get('seq_no'),
            payload=obj.get('payload'),
            membership=obj.get('membership'),
            last_seq=obj.get('last_seq'),
            leader_id=obj.get('leader_id'),
        )


@dataclass
class ChatMessage:
    """Delivered chat message with ordering info."""
    seq_no: int
    term: int
    msg_id: str
    sender_id: int
    room_id: str
    text: str
    timestamp: float = field(default_factory=lambda: 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        return cls(**data)


def get_logger_name(node_id: int) -> str:
    """Get standard logger name for a node."""
    return f"node.{node_id}"

