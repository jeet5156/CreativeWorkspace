# Client System Architecture Specification

## Executive Summary

This document specifies the complete system architecture for the **Client Management Module** within CreativeWorkspace.

In creative studios, game production houses, and agency pipelines, **Clients** represent top-level organizational entities (Companies, Brands, Studios, or Internal Franchises) that own one or multiple **Projects**.

This architecture is designed to integrate seamlessly with the existing CreativeWorkspace architecture (Single Source of Truth, Modular Services, Data-Driven Registries, and Capability Adapters) while remaining fully extensible for future email communications and calendar scheduling without requiring major refactoring.

---

## 1. System Architecture & Component Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MainWindow / UI Shell                           │
├───────────────────┬──────────────────────┬─────────────────────────────┤
│  Explorer Panel   │     ClientPanel      │       Inspector Panel       │
│ ("Where do I go?")│ ("What is happening?")│    ("What can I edit?")     │
│   ├── Projects    │   ├── Client Cards   │   └── ClientInspectable     │
│   └── Clients     │   └── Project Grids  │       (IInspectable)        │
└───────────────────┴──────────┬───────────┴─────────────────────────────┘
                               │ Delegates actions
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        ClientService Layer                             │
├────────────────────────────────────────────────────────────────────────┤
│ • Client CRUD & State Management                                       │
│ • Project Association & Relationship Mapping                           │
│ • Workspace Persistence (.creativeworkspace/clients/clients.json)     │
│ • Event Emissions (client_created, client_updated, project_assigned)  │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ Extensible Interfaces
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Future Expansion Interfaces (Protocols)                  │
├──────────────────────────────────────┬─────────────────────────────────┤
│    IEmailIntegrationService          │    ICalendarIntegrationService  │
│ (Client Email History & Threading)   │(Milestones, Meetings, Deliverables)│
└──────────────────────────────────────┴─────────────────────────────────┘
```

---

## 2. Data Model Specification

### 2.1 Core Domain Models (`models/client.py`)

#### `Client` Dataclass
```python
@dataclass
class Client:
    id: str                              # Unique UUID v4 identifier
    name: str                            # User-facing Client Name (e.g. "Warner Bros")
    company: str                         # Company / Entity Name (e.g. "Warner Bros Entertainment")
    avatar_path: Optional[str] = None    # Path to client logo / avatar image
    email: str = ""                      # Primary contact email address
    phone: str = ""                      # Primary contact phone number
    website: str = ""                    # Corporate website URL
    notes: str = ""                      # Rich text / markdown client notes
    status: str = "active"               # "active", "lead", "archived", "on_hold"
    tags: List[str] = field(default_factory=list) # Custom tags (e.g. ["VFX", "Tier 1"])
    project_ids: List[str] = field(default_factory=list) # Associated Project UUIDs
    created_at: str = ""                 # ISO 8601 creation timestamp
    updated_at: str = ""                 # ISO 8601 last modified timestamp
```

#### `ClientContact` Dataclass (Secondary Contacts)
```python
@dataclass
class ClientContact:
    id: str
    client_id: str
    name: str
    role: str                            # e.g. "Art Director", "Producer"
    email: str
    phone: str
    is_primary: bool = False
```

#### `ClientBillingInfo` Dataclass
```python
@dataclass
class ClientBillingInfo:
    client_id: str
    hourly_rate: float = 0.0
    currency: str = "USD"
    contract_type: str = "fixed"         # "hourly", "fixed", "retainer"
    payment_terms: str = "Net 30"
```

---

## 3. Folder Structure Specification

To preserve low coupling and modular cohesion, all Client module files follow the established CreativeWorkspace directory conventions:

```
creativeworkspace/
├── models/
│   ├── project.py                   <-- Existing Project domain model
│   └── client.py                    <-- Client, ClientContact, ClientBillingInfo
├── services/
│   ├── client_service.py            <-- Business logic, relationships, CRUD
│   ├── folder_service.py            <-- File system operations
│   ├── lab_service.py               <-- Canvas board storage
│   └── interfaces/
│       ├── communication_interface.py <-- Abstract Email/Calendar extension hooks
│       └── storage_interface.py
├── ui/
│   ├── panels/
│   │   ├── client_panel.py          <-- Main client management dashboard view
│   │   ├── explorer_panel.py        <-- Updated explorer with Client section
│   │   └── lab_panel.py
│   ├── widgets/
│   │   ├── client_card.py           <-- Client overview card item
│   │   ├── client_project_card.py   <-- Project card filtered by client
│   │   └── client_timeline.py       <-- Client milestones & activity feed
│   └── dialogs/
│       └── client_dialog.py         <-- Create/Edit Client dialog window
├── core/
│   ├── inspectable_interface.py    <-- Base IInspectable protocol
│   ├── inspectable_adapters.py      <-- NodeInspectable & ProjectInspectable
│   └── client_inspectable.py        <-- ClientInspectable adapter
└── docs/
    └── CLIENT_SYSTEM_ARCHITECTURE.md <-- This specification
```

---

## 4. Services Layer (`ClientService`)

`ClientService` (`services/client_service.py`) owns all business logic and persistence for Clients.

### Key Responsibilities
1. **CRUD Operations**: `create_client()`, `update_client()`, `delete_client()`, `get_client()`.
2. **Project Relationships**:
   - `assign_project_to_client(project_id, client_id)`
   - `unassign_project_from_client(project_id, client_id)`
   - `get_projects_for_client(client_id)`
3. **Workspace Storage**: Persistence under `.creativeworkspace/clients/clients.json` in workspace root.

### Persistence Format (`.creativeworkspace/clients/clients.json`)
```json
{
  "version": 1,
  "updated_at": "2026-08-05T21:00:00",
  "clients": [
    {
      "id": "c71e077a-5044-4eb0-e9e8-a630c860a2e9",
      "name": "Warner Bros",
      "company": "Warner Bros Entertainment",
      "email": "production@warnerbros.com",
      "phone": "+1-555-0199",
      "website": "https://warnerbros.com",
      "status": "active",
      "tags": ["VFX", "Feature Film"],
      "project_ids": [
        "batman-previz-uuid",
        "dune-references-uuid"
      ],
      "billing": {
        "hourly_rate": 150.0,
        "currency": "USD",
        "contract_type": "hourly",
        "payment_terms": "Net 30"
      },
      "created_at": "2026-08-01T09:00:00",
      "updated_at": "2026-08-05T21:00:00"
    }
  ]
}
```

---

## 5. Signals & Event System

`ClientService` inherits from `QObject` and exposes typed PySide6 signals to keep UI components decoupled:

```python
class ClientService(QObject):
    # Signals
    client_created = Signal(object)              # Emits newly created Client object
    client_updated = Signal(object)              # Emits updated Client object
    client_deleted = Signal(str)                 # Emits deleted client_id UUID
    project_assigned = Signal(str, str)          # Emits (project_id, client_id)
    project_unassigned = Signal(str, str)        # Emits (project_id, client_id)
    clients_reloaded = Signal()                  # Emits on bulk reload
```

---

## 6. UI Hierarchy & Navigation

### 6.1 Explorer Integration
- **`ExplorerPanel`**: Includes a top-level expandable category `"Clients"` alongside `"Projects"`.
- Expanding `"Clients"` lists registered Clients with status indicators (`● Active`, `● On Hold`, `● Archived`).
- Clicking a Client in the Explorer navigates the central view to `ClientPanel` showing the selected client details.

### 6.2 Central View Navigation Stack
`MainWindow` manages navigation across central views using `QStackedWidget`:
- `Index 0`: `HomeWorkspacePanel` (Dashboard)
- `Index 1`: `AssetWorkspacePanel` (Assets)
- `Index 2`: `LabPanel` (Canvas)
- `Index 3`: `ClientPanel` (Clients Management) [NEW]

---

## 7. Inspector Integration (`ClientInspectable`)

Conforming to `IInspectable` (`core/inspectable_interface.py`), selecting a Client populates the Inspector Panel:

```python
class ClientInspectable(IInspectable):
    def __init__(self, client: Client, client_service: ClientService):
        self.client = client
        self.service = client_service

    def get_title(self) -> str:
        return self.client.name

    def get_subtitle(self) -> str:
        return self.client.company or "Client Entity"

    def get_inspection_sections(self) -> List[InspectableSection]:
        return [
            InspectableSection("Client Details", [
                InspectableField("name", "Name", "string", value=self.client.name),
                InspectableField("company", "Company", "string", value=self.client.company),
                InspectableField("status", "Status", "enum", value=self.client.status, options=["active", "lead", "archived", "on_hold"]),
                InspectableField("email", "Email", "string", value=self.client.email),
                InspectableField("phone", "Phone", "string", value=self.client.phone),
                InspectableField("website", "Website", "string", value=self.client.website),
            ]),
            InspectableSection("Billing & Contract", [
                InspectableField("billing.rate", "Hourly Rate", "number", value=getattr(self.client, "billing_rate", 0.0)),
                InspectableField("billing.currency", "Currency", "enum", value="USD", options=["USD", "EUR", "GBP", "CAD"]),
                InspectableField("billing.contract", "Contract Type", "enum", value="fixed", options=["fixed", "hourly", "retainer"]),
            ]),
            InspectableSection("Associated Projects", [
                InspectableField("project_count", "Total Projects", "readonly", value=str(len(self.client.project_ids))),
            ])
        ]
```

---

## 8. Project Relationships

### 8.1 Bi-Directional Mapping
- `Client.project_ids`: List of associated Project UUIDs.
- `Project.client_id`: Single Client UUID (or `None` for unassigned projects).

### 8.2 Safe Deletion & Cascade Policy
- **Deleting a Client**: Does **NOT** delete project files or boards on disk.
- Sets `Project.client_id = None` across all associated projects, preserving project data while marking projects as unassigned.

---

## 9. Future Email & Calendar Compatibility

To support future email tracking and milestone calendars without refactoring:

### 9.1 Email Communication Protocol (`services/interfaces/communication_interface.py`)
```python
@dataclass
class EmailMessage:
    id: str
    client_id: str
    sender: str
    recipients: List[str]
    subject: str
    body_text: str
    sent_at: str
    thread_id: Optional[str] = None
    has_attachments: bool = False

class IEmailService(Protocol):
    def get_messages_for_client(self, client_id: str) -> List[EmailMessage]: ...
    def send_email(self, message: EmailMessage) -> bool: ...
```

### 9.2 Calendar & Milestone Protocol (`models/calendar_event.py`)
```python
@dataclass
class CalendarEvent:
    id: str
    client_id: str
    project_id: Optional[str]
    title: str                           # e.g. "Dune Rough Cut Review"
    event_type: str                      # "deadline", "meeting", "deliverable", "milestone"
    start_time: str                      # ISO 8601
    end_time: str                        # ISO 8601
    status: str                          # "scheduled", "completed", "cancelled"
```

---

## 10. Summary & Extensibility Roadmap

By adhering to this architecture:
1. **Zero UI/Business Logic Code Invalidation**: Future implementation of `ClientPanel`, `ClientService`, and `ClientInspectable` requires no refactoring of existing canvas, node, or thumbnail logic.
2. **Scalable Model Schema**: JSON-based storage allows adding email threads, milestone calendars, and billing reports cleanly as optional schema extensions.
