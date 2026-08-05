from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Project:
    name: str
    project_type: str
    location: str
    description: str = ""
    priority: str = "medium"
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    client: str = ""
    repository: str = ""
    deadline: str = ""
    is_pinned: bool = False

    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    last_opened: datetime = field(default_factory=datetime.now)
