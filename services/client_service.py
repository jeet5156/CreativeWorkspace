import os
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional, Union
from PySide6.QtCore import QObject, Signal

from models.client import Client, ClientContact, ClientActivity, CLIENT_STATUSES, CLIENT_TYPES
from core.paths import get_shared_clients_dir
from core.storage import atomic_write_json, safe_read_json


class ClientService(QObject):
    """Single source of truth for Client lifecycle operations, relationships, and persistence."""

    client_created = Signal(object)
    client_updated = Signal(object)
    client_deleted = Signal(object)
    client_opened = Signal(object)
    project_assigned = Signal(str, str)  # (project_id, client_id)
    project_removed = Signal(str, str)   # (project_id, client_id)

    def __init__(
        self,
        workspace_location: Optional[str] = None,
        storage_dir: Optional[Union[str, Path]] = None,
    ):
        super().__init__()
        self.storage_dir: Optional[Path] = Path(storage_dir).resolve() if storage_dir else None
        self.workspace_location: Optional[str] = workspace_location
        self.clients: List[Client] = []

        if self.storage_dir or self.workspace_location:
            self.load_clients()
        else:
            # Default to shared data directory (<APP_ROOT>/data/clients)
            self.load_clients()

    def set_workspace_location(self, workspace_location: str):
        self.workspace_location = workspace_location
        self.storage_dir = None
        self.load_clients()

    def set_storage_dir(self, storage_dir: Union[str, Path]):
        self.storage_dir = Path(storage_dir).resolve()
        self.load_clients()

    def _get_clients_dir(self, workspace_loc: Optional[str] = None) -> Path:
        if self.storage_dir and not workspace_loc:
            path = self.storage_dir
        elif workspace_loc:
            # Legacy workspace location override
            path = Path(workspace_loc) / ".creativeworkspace" / "clients"
        elif self.workspace_location:
            path = Path(self.workspace_location) / ".creativeworkspace" / "clients"
        else:
            # Default dynamic portable shared location (<APP_ROOT>/data/clients)
            path = get_shared_clients_dir()

        path.mkdir(parents=True, exist_ok=True)
        return path

    def load_clients(self, workspace_loc: Optional[str] = None) -> List[Client]:
        clients_dir = self._get_clients_dir(workspace_loc)
        loaded = []

        if not clients_dir.exists():
            self.clients = []
            return self.clients

        for client_folder in clients_dir.iterdir():
            if client_folder.is_dir():
                client_json = client_folder / "client.json"
                if client_json.exists():
                    data, err = safe_read_json(client_json)
                    if err or not isinstance(data, dict):
                        continue

                    contacts_list = []
                    contacts_json = client_folder / "contacts.json"
                    if contacts_json.exists():
                        cdata, cerr = safe_read_json(contacts_json)
                        if not cerr and isinstance(cdata, list):
                            for c in cdata:
                                if isinstance(c, dict):
                                    contacts_list.append(ClientContact(
                                        name=c.get("name", ""),
                                        role=c.get("role", ""),
                                        email=c.get("email", ""),
                                        notes=c.get("notes", ""),
                                    ))

                    created_dt = datetime.fromisoformat(data.get("created")) if data.get("created") else datetime.now()
                    modified_dt = datetime.fromisoformat(data.get("modified")) if data.get("modified") else datetime.now()

                    client = Client(
                        id=data.get("id", client_folder.name),
                        name=data.get("name", ""),
                        company=data.get("company", ""),
                        role=data.get("role", ""),
                        status=data.get("status", "Active"),
                        priority=data.get("priority", "Medium"),
                        client_type=data.get("client_type", "Game Studio"),
                        industry=data.get("industry", ""),
                        website=data.get("website", ""),
                        country=data.get("country", ""),
                        tags=data.get("tags", []) if isinstance(data.get("tags"), list) else [],
                        notes=data.get("notes", ""),
                        project_ids=data.get("project_ids", []) if isinstance(data.get("project_ids"), list) else [],
                        contacts=contacts_list,
                        created=created_dt,
                        modified=modified_dt,
                    )
                    loaded.append(client)

        self.clients = loaded
        return self.clients

    def create_client(
        self,
        name: str,
        company: str = "",
        client_type: str = "Game Studio",
        status: str = "Active",
        priority: str = "Medium",
        role: str = "",
        industry: str = "",
        website: str = "",
        country: str = "",
        tags: Optional[List[str]] = None,
        notes: str = "",
    ) -> Client:
        client = Client(
            name=name,
            company=company,
            client_type=client_type,
            status=status,
            priority=priority,
            role=role,
            industry=industry,
            website=website,
            country=country,
            tags=tags or [],
            notes=notes,
        )

        self.save_client(client)
        self.clients.append(client)

        try:
            self.client_created.emit(client)
        except Exception:
            pass

        return client

    def duplicate_client(self, client_id: str) -> Optional[Client]:
        original = self.get_client(client_id)
        if not original:
            return None
        new_name = f"{original.name} (Copy)"
        dup = self.create_client(
            name=new_name,
            company=original.company,
            client_type=original.client_type,
            status=original.status,
            priority=original.priority,
            role=original.role,
            industry=original.industry,
            website=original.website,
            country=original.country,
            tags=list(original.tags),
            notes=original.notes,
        )
        return dup

    def save_client(self, client: Client):
        if not client or not client.id:
            return

        client.modified = datetime.now()
        client_folder = self._get_clients_dir() / client.id
        client_folder.mkdir(parents=True, exist_ok=True)

        data = {
            "id": client.id,
            "name": client.name,
            "company": client.company,
            "role": client.role,
            "status": client.status,
            "priority": client.priority,
            "client_type": client.client_type,
            "industry": client.industry,
            "website": client.website,
            "country": client.country,
            "tags": client.tags,
            "notes": client.notes,
            "project_ids": client.project_ids,
            "created": client.created.isoformat() if isinstance(client.created, datetime) else str(client.created),
            "modified": client.modified.isoformat() if isinstance(client.modified, datetime) else str(client.modified),
        }

        atomic_write_json(client_folder / "client.json", data)

        contacts_data = [asdict(c) for c in client.contacts]
        atomic_write_json(client_folder / "contacts.json", contacts_data)

        try:
            self.client_updated.emit(client)
        except Exception:
            pass

    def delete_client(self, client_id: str, project_service=None):
        client = self.get_client(client_id)
        if not client:
            return

        # Deleting a Client MUST NEVER delete Projects. Set project.client_id = "" on associated projects
        if project_service and hasattr(project_service, "projects"):
            for proj in project_service.projects:
                if getattr(proj, "client_id", None) == client_id:
                    proj.client_id = ""
                    try:
                        project_service.save_project(proj)
                    except Exception:
                        pass

        # Remove client directory
        client_folder = self._get_clients_dir() / client_id
        if client_folder.exists():
            import shutil
            try:
                shutil.rmtree(client_folder, ignore_errors=True)
            except Exception:
                pass

        self.clients = [c for c in self.clients if c.id != client_id]

        try:
            self.client_deleted.emit(client_id)
        except Exception:
            pass

    def archive_client(self, client_id: str):
        client = self.get_client(client_id)
        if client:
            client.status = "Archived"
            self.save_client(client)

    def get_client(self, client_id: str) -> Optional[Client]:
        for c in self.clients:
            if c.id == client_id:
                return c
        return None

    def list_clients(self) -> List[Client]:
        return list(self.clients)

    def assign_project_to_client(self, project_id: str, client_id: str, project_service=None):
        client = self.get_client(client_id)
        if client and project_id not in client.project_ids:
            client.project_ids.append(project_id)
            self.save_client(client)

        if project_service and hasattr(project_service, "projects"):
            for proj in project_service.projects:
                proj_identifier = getattr(proj, "id", getattr(proj, "name", ""))
                if proj_identifier == project_id or getattr(proj, "location", "").endswith(project_id):
                    proj.client_id = client_id
                    try:
                        project_service.save_project(proj)
                    except Exception:
                        pass

        try:
            self.project_assigned.emit(project_id, client_id)
        except Exception:
            pass

    def remove_project_from_client(self, project_id: str, client_id: str, project_service=None):
        client = self.get_client(client_id)
        if client and project_id in client.project_ids:
            client.project_ids.remove(project_id)
            self.save_client(client)

        if project_service and hasattr(project_service, "projects"):
            for proj in project_service.projects:
                proj_identifier = getattr(proj, "id", getattr(proj, "name", ""))
                if (proj_identifier == project_id or getattr(proj, "location", "").endswith(project_id)) and getattr(proj, "client_id", None) == client_id:
                    proj.client_id = ""
                    try:
                        project_service.save_project(proj)
                    except Exception:
                        pass

        try:
            self.project_removed.emit(project_id, client_id)
        except Exception:
            pass
