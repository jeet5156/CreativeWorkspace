import os
import json
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

from models.client import Client, ClientContact, ClientActivity, CLIENT_STATUSES, CLIENT_TYPES


class ClientService(QObject):
    """Single source of truth for Client lifecycle operations, relationships, and persistence."""

    client_created = Signal(object)
    client_updated = Signal(object)
    client_deleted = Signal(object)
    client_opened = Signal(object)
    project_assigned = Signal(str, str)  # (project_id, client_id)
    project_removed = Signal(str, str)   # (project_id, client_id)

    def __init__(self, workspace_location: Optional[str] = None):
        super().__init__()
        self.workspace_location: Optional[str] = workspace_location
        self.clients: List[Client] = []

        if workspace_location:
            self.load_clients(workspace_location)

    def set_workspace_location(self, workspace_location: str):
        self.workspace_location = workspace_location
        self.load_clients(workspace_location)

    def _get_clients_dir(self, workspace_loc: Optional[str] = None) -> Path:
        base = workspace_loc or self.workspace_location or os.getcwd()
        path = Path(base) / ".creativeworkspace" / "clients"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def load_clients(self, workspace_loc: Optional[str] = None) -> List[Client]:
        clients_dir = self._get_clients_dir(workspace_loc)
        loaded = []

        for client_folder in clients_dir.iterdir():
            if client_folder.is_dir():
                client_json = client_folder / "client.json"
                if client_json.exists():
                    try:
                        with open(client_json, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        contacts_list = []
                        contacts_json = client_folder / "contacts.json"
                        if contacts_json.exists():
                            with open(contacts_json, "r", encoding="utf-8") as cf:
                                cdata = json.load(cf)
                                for c in cdata:
                                    contacts_list.append(ClientContact(
                                        name=c.get("name", ""),
                                        role=c.get("role", ""),
                                        email=c.get("email", ""),
                                        notes=c.get("notes", "")
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
                            tags=data.get("tags", []),
                            notes=data.get("notes", ""),
                            project_ids=data.get("project_ids", []),
                            contacts=contacts_list,
                            created=created_dt,
                            modified=modified_dt,
                        )
                        loaded.append(client)
                    except Exception:
                        pass

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

        with open(client_folder / "client.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        contacts_data = [asdict(c) for c in client.contacts]
        with open(client_folder / "contacts.json", "w", encoding="utf-8") as f:
            json.dump(contacts_data, f, indent=2)

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
