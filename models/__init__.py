from dataclasses import dataclass
from datetime import datetime


@dataclass
class Project:
    name: str
    location: str
    created: datetime
    modified: datetime