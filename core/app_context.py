from services.project_service import ProjectService
from services.settings_service import SettingsService
from services.asset_service import AssetService
from services.status_service import StatusService
from services.app_state import AppState
from services.activity_service import ActivityService


class AppContext:

    def __init__(self):
        self.project_service = ProjectService()
        self.settings_service = SettingsService()
        # AssetService uses ProjectService for project locations and folder structure
        self.asset_service = AssetService(self.project_service)
        # StatusService provides enum-based folder status reporting
        self.status_service = StatusService(self.project_service)

        # Central app state and activity tracking
        self.app_state = AppState()
        self.activity_service = ActivityService()

        # Lab service (Lab board persistence)
        try:
            from services.lab_service import LabService
            self.lab_service = LabService(self.project_service, activity_service=self.activity_service)
        except Exception:
            self.lab_service = None

        # Client service (Client management persistence & relationships)
        try:
            from services.client_service import ClientService
            self.client_service = ClientService()
        except Exception:
            self.client_service = None

        # Thumbnail service (background generation & cache)
        try:
            from services.thumbnail_service import ThumbnailService
            self.thumbnail_service = ThumbnailService(self.asset_service)
        except Exception:
            self.thumbnail_service = None

        # Folder service: manages folders and updates indices/thumbnails
        try:
            from services.folder_service import FolderService
            self.folder_service = FolderService(self.project_service, self.asset_service, activity_service=self.activity_service, thumbnail_service=self.thumbnail_service)
        except Exception:
            self.folder_service = None

        # AssetOperationsService handles file-level operations and coordinates updates
        try:
            from services.asset_operations_service import AssetOperationsService
            self.asset_operations = AssetOperationsService(self.asset_service, self.activity_service, self.project_service, app_state=self.app_state, thumbnail_service=self.thumbnail_service)
            # expose folder service through asset_operations for UI convenience
            try:
                if self.folder_service:
                    self.asset_operations.folder_service = self.folder_service
            except Exception:
                pass
        except Exception:
            self.asset_operations = None

        # Global Asset Library & Drive Detection
        try:
            from services.drive_detection_service import DriveDetectionService
            from services.library_service import LibraryService
            self.drive_detection_service = DriveDetectionService()
            self.library_service = LibraryService(drive_detector=self.drive_detection_service)
        except Exception:
            self.drive_detection_service = None
            self.library_service = None

        # Knowledge Service
        try:
            from services.knowledge_service import KnowledgeService
            self.knowledge_service = KnowledgeService()
        except Exception:
            self.knowledge_service = None

        # AI Service
        try:
            from services.ai_service import AIService
            self.ai_service = AIService()
        except Exception:
            self.ai_service = None

        # AI Context Retrieval Service (Metadata & Index-Based)
        try:
            from services.context_retrieval_service import ContextRetrievalService
            self.context_retrieval_service = ContextRetrievalService(
                context=self,
                knowledge_service=self.knowledge_service,
                library_service=self.library_service,
                asset_service=self.asset_service,
                project_service=self.project_service,
                lab_service=self.lab_service,
            )
        except Exception:
            self.context_retrieval_service = None

        # Knowledge AI Service
        try:
            from services.knowledge_ai_service import KnowledgeAIService
            self.knowledge_ai_service = KnowledgeAIService(
                self.ai_service,
                self.knowledge_service,
                context_retrieval_service=self.context_retrieval_service,
            )
        except Exception:
            self.knowledge_ai_service = None

        # Knowledge AI Assistant Service (Interactive Q&A)
        try:
            from services.knowledge_assistant_service import KnowledgeAssistantService
            self.knowledge_assistant_service = KnowledgeAssistantService(
                self.ai_service,
                self.knowledge_service,
                context_retrieval_service=self.context_retrieval_service,
            )
        except Exception:
            self.knowledge_assistant_service = None

        # Project Context Service (Structured Project Context & Metrics Aggregation)
        try:
            from services.project_context_service import ProjectContextService
            self.project_context_service = ProjectContextService(
                context=self,
                project_service=self.project_service,
                asset_service=self.asset_service,
                library_service=self.library_service,
                knowledge_service=self.knowledge_service,
                lab_service=self.lab_service,
            )
        except Exception:
            self.project_context_service = None

        # Project AI Assistant Service (Phase 5B)
        try:
            from services.project_assistant_service import ProjectAssistantService
            self.project_assistant_service = ProjectAssistantService(
                ai_service=self.ai_service,
                project_context_service=self.project_context_service,
                context=self,
            )
        except Exception:
            self.project_assistant_service = None

        self.current_project = None

    def set_current_project(self, project):
        self.current_project = project
        try:
            self.app_state.set_current_project(project)
        except Exception:
            pass

    def load_workspace_clients(self, workspace_location: str):
        if self.client_service:
            try:
                self.client_service.set_workspace_location(workspace_location)
            except Exception:
                pass