from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Project:
    name: str
    project_type: str
    location: str
    description: str = ""

    created: datetime = field(default_factory=datetime.now)