from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid


@dataclass
class ClientContact:
    name: str = ""
    role: str = ""
    email: str = ""
    notes: str = ""


@dataclass
class ClientActivity:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    type: str = "info"
    payload: Dict[str, Any] = field(default_factory=dict)


CLIENT_STATUSES = [
    "Prospect",
    "Reached Out",
    "Conversation",
    "Negotiation",
    "Active",
    "Completed",
    "Returning",
    "Archived",
]

CLIENT_TYPES = [
    "Game Studio",
    "Indie Studio",
    "Publisher",
    "Agency",
    "Individual",
    "Education",
    "Other",
]

CLIENT_PRIORITIES = [
    "High",
    "Medium",
    "Low",
]


@dataclass
class Client:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    company: str = ""
    role: str = ""
    status: str = "Active"
    priority: str = "Medium"
    client_type: str = "Game Studio"
    industry: str = ""
    website: str = ""
    country: str = ""
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    project_ids: List[str] = field(default_factory=list)
    contacts: List[ClientContact] = field(default_factory=list)

    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)

