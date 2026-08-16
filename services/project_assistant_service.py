"""Project AI Assistant Service for CreativeWorkspace (Phase 5B).

Provides structured, provider-independent project Q&A grounded exclusively in ProjectContext:
1. Grounded Project Context aggregation (Project metadata, assets, version groups, library availability, Knowledge, Lab).
2. Question-driven interpretation and project health summaries.
3. Traceable source extraction providing clickable links to referenced entities.
4. Bounded in-memory conversation history that cleanly resets on project switch.
5. Fully asynchronous, non-blocking AI execution via AIService.

Hard Invariant:
Never executes filesystem-wide scans or external drive probing (os.walk / rglob).
All context is sourced deterministically from ProjectContextService.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import re

from PySide6.QtCore import QObject, Signal

from models.ai import AIMessage, AIRequest, AIResponse
from models.project import Project
from models.project_context import (
    ProjectContext,
    ProjectAssetSummary,
    ProjectLibrarySummary,
    ProjectKnowledgeSummary,
    ProjectLabSummary,
)
from models.project_assistant import (
    ProjectSourceType,
    TraceableSourceItem,
    ProjectAssistantResponse,
)
from services.ai_service import AIService, AIWorker
from services.project_context_service import ProjectContextService


class ProjectAssistantService(QObject):
    """Coordinates free-form conversational Q&A grounded in structured ProjectContext."""

    ask_started = Signal(str)                          # (question)
    ask_finished = Signal(str, object)                 # (question, ProjectAssistantResponse)
    ask_error = Signal(str, str)                       # (question, error_message)
    history_cleared = Signal()

    MAX_HISTORY_MESSAGES = 10  # Maximum recent conversation turns preserved in-memory

    def __init__(
        self,
        ai_service: Optional[AIService] = None,
        project_context_service: Optional[ProjectContextService] = None,
        context=None,
    ):
        super().__init__()
        self.ai_service = ai_service
        self.project_context_service = project_context_service
        self.context = context

        self._history: List[AIMessage] = []
        self._current_project_id: Optional[str] = None

    def set_ai_service(self, ai_service: AIService):
        self.ai_service = ai_service

    def set_project_context_service(self, service: ProjectContextService):
        self.project_context_service = service

    def is_ai_available(self) -> bool:
        """Check if AI is globally enabled and configured."""
        if not self.ai_service:
            return False
        return self.ai_service.is_enabled()

    # -------------------------------------------------------------------------
    # Conversation History Management (In-Memory Only)
    # -------------------------------------------------------------------------

    def get_history(self) -> List[AIMessage]:
        """Return shallow copy of current in-memory conversation history."""
        return list(self._history)

    def add_history_message(self, role: str, content: str):
        """Append a message to the in-memory history, maintaining max bound."""
        self._history.append(AIMessage(role=role, content=content))
        if len(self._history) > self.MAX_HISTORY_MESSAGES:
            self._history = self._history[-self.MAX_HISTORY_MESSAGES:]

    def clear_history(self):
        """Reset conversation history for new project or fresh session."""
        self._history.clear()
        try:
            self.history_cleared.emit()
        except Exception:
            pass

    def set_active_project(self, project_or_id: Any):
        """Update active project anchor; resets history if project identity changed."""
        proj_key = None
        if isinstance(project_or_id, Project):
            proj_key = project_or_id.location or project_or_id.name
        elif isinstance(project_or_id, ProjectContext):
            proj_key = project_or_id.project_path or project_or_id.project_name
        elif isinstance(project_or_id, str):
            proj_key = project_or_id

        if self._current_project_id != proj_key:
            self._current_project_id = proj_key
            self.clear_history()

    # -------------------------------------------------------------------------
    # Context Resolution & Prompt Formatting
    # -------------------------------------------------------------------------

    def resolve_project_context(self, project_or_id: Any) -> Optional[ProjectContext]:
        """Fetch canonical ProjectContext using ProjectContextService or direct object."""
        if isinstance(project_or_id, ProjectContext):
            return project_or_id

        if self.project_context_service:
            return self.project_context_service.get_project_context(project_or_id)

        return None

    def format_project_context_prompt(self, ctx: ProjectContext) -> str:
        """Format complete, structured ProjectContext into a compact prompt section."""
        lines: List[str] = []

        # 1. Project Identity
        lines.append("=== PROJECT IDENTITY ===")
        lines.append(f"Name: {ctx.project_name}")
        if ctx.project_type:
            lines.append(f"Type: {ctx.project_type.capitalize()}")

        status = getattr(ctx, "status", None) or ctx.metadata.get("status", "")
        if status:
            lines.append(f"Status: {status}")

        priority = getattr(ctx, "priority", None) or ctx.metadata.get("priority", "")
        if priority:
            lines.append(f"Priority: {priority}")

        client = getattr(ctx, "client", None) or ctx.metadata.get("client", "")
        if client:
            lines.append(f"Client: {client}")

        deadline = getattr(ctx, "deadline", None) or ctx.metadata.get("deadline", "")
        if deadline:
            lines.append(f"Deadline: {deadline}")

        tags = getattr(ctx, "tags", None) or ctx.metadata.get("tags", [])
        if tags:
            lines.append(f"Tags: {', '.join(tags)}")

        description = getattr(ctx, "description", None) or ctx.metadata.get("description", "")
        if description:
            lines.append(f"Description: {str(description).strip()}")
        lines.append(f"Location Path: {ctx.project_path}")
        lines.append("")

        # 2. Local Assets & Version Sequences
        lines.append("=== PROJECT ASSETS & VERSIONS ===")
        lines.append(f"Total Local Assets: {ctx.asset_summary.total_assets}")
        if ctx.asset_summary.by_category:
            cat_str = ", ".join(f"{k}: {v}" for k, v in ctx.asset_summary.by_category.items())
            lines.append(f"Categories: {cat_str}")
        if ctx.asset_summary.lod_counts:
            lod_str = ", ".join(f"{k}: {v}" for k, v in ctx.asset_summary.lod_counts.items())
            lines.append(f"LODs: {lod_str}")

        if ctx.asset_summary.version_groups:
            lines.append("Detected Version Groups:")
            for grp in ctx.asset_summary.version_groups:
                v_list = ", ".join(grp.get("versions", []))
                lines.append(f"- {grp.get('logical_name')}: {v_list} (Latest: {grp.get('latest')})")
        lines.append("")

        # 3. Library References & Availability Breakdown
        lines.append("=== LIBRARY REFERENCES & PORTABLE DRIVE AVAILABILITY ===")
        lines.append(f"Total References: {ctx.library_summary.total_linked_assets}")
        avail = ctx.availability_summary
        lines.append(f"Availability Status: Available: {avail.online_library_assets}, Offline: {avail.offline_library_assets}, Missing: {avail.missing_library_assets}, Changed: {avail.possibly_changed_assets}")

        linked_refs = ctx.library_summary.linked_assets
        offline_refs = [r for r in linked_refs if r.get("availability_status") == "offline" or not r.get("is_online", True)]
        missing_refs = [r for r in linked_refs if r.get("availability_status") == "missing"]
        changed_refs = [r for r in linked_refs if r.get("availability_status") == "changed"]

        if offline_refs:
            lines.append("Offline Library References:")
            for item in offline_refs:
                drv = item.get("drive_id", "Unknown Drive")
                fn = item.get("filename") or item.get("title", "Asset")
                lines.append(f"- {fn} [OFFLINE on drive: {drv}]")

        if missing_refs:
            lines.append("Missing Library References:")
            for item in missing_refs:
                fn = item.get("filename") or item.get("title", "Asset")
                lines.append(f"- {fn} [MISSING on target drive]")

        if changed_refs:
            lines.append("Possibly Changed References:")
            for item in changed_refs:
                fn = item.get("filename") or item.get("title", "Asset")
                lines.append(f"- {fn} [CHANGED timestamp/size]")
        lines.append("")

        # 4. Knowledge & Documentation
        lines.append("=== KNOWLEDGE & DOCUMENTATION ===")
        lines.append(f"Total Linked Notes: {ctx.knowledge_summary.total_notes} (Favorites: {ctx.knowledge_summary.favorite_notes})")
        if ctx.knowledge_summary.recent_notes:
            lines.append("Related Knowledge Notes:")
            for note in ctx.knowledge_summary.recent_notes:
                fav_str = " [⭐ Favorite]" if note.get("is_favorite") else ""
                tag_str = f" (Tags: {', '.join(note.get('tags', []))})" if note.get("tags") else ""
                lines.append(f"- {note.get('title', 'Untitled Note')}{fav_str}{tag_str}")
        lines.append("")

        # 5. Creative Lab Boards & Tasks
        lines.append("=== CREATIVE LAB & TASKS ===")
        boards_list = ctx.lab_summary.recent_boards or getattr(ctx.lab_summary, "boards", [])
        if boards_list:
            lines.append("Active Boards:")
            for b in boards_list:
                lines.append(f"- {b.get('name', 'Board')} ({b.get('node_count', 0)} nodes)")

        tasks = ctx.lab_summary.task_status
        lines.append(f"Checklist Tasks: {tasks.get('completed', 0)} completed / {tasks.get('total', 0)} total ({tasks.get('pending', 0)} pending)")

        return "\n".join(lines).strip()

    def build_ask_request(
        self,
        question: str,
        project_or_id: Any,
    ) -> Tuple[AIRequest, Optional[ProjectContext]]:
        """Construct grounded, partitioned AIRequest for free-form user question."""
        ctx = self.resolve_project_context(project_or_id)
        if not ctx:
            p_name = str(project_or_id)
            ctx = ProjectContext(project_name=p_name, project_path="")

        self.set_active_project(ctx)

        system_instruction = (
            "You are the Project AI Assistant for CreativeWorkspace.\n"
            "You help the user understand, navigate, and manage their creative project by interpreting its structured, indexed metadata.\n\n"
            "GROUNDING RULES:\n"
            "1. The supplied PROJECT CONTEXT is the definitive ground truth for this project.\n"
            "2. Do NOT invent, hallucinate, or assume unindexed files, external drives, or project state.\n"
            "3. Answer specifically and directly. When mentioning assets, version numbers (e.g. v004), knowledge notes, offline drives, or Lab boards, use their exact names from the context.\n"
            "4. If the user asks about something not present in the project context, explain what is currently indexed and state clearly what information is missing.\n"
            "5. Be concise, structured, and helpful."
        )

        context_body = self.format_project_context_prompt(ctx)

        prompt = (
            f"{context_body}\n\n"
            f"=== USER QUESTION ===\n"
            f"{question.strip()}\n\n"
            f"Please answer the question accurately based on the Project Context above."
        )

        # Include bounded conversation history
        messages: List[AIMessage] = list(self._history)
        messages.append(AIMessage(role="user", content=prompt))

        request = AIRequest(
            prompt=prompt,
            system_instruction=system_instruction,
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
        )

        return request, ctx

    # -------------------------------------------------------------------------
    # Traceable Source Extraction
    # -------------------------------------------------------------------------

    def extract_traceable_sources(
        self,
        question: str,
        answer: str,
        ctx: Optional[ProjectContext],
    ) -> List[TraceableSourceItem]:
        """Extract typed, clickable source references from ProjectContext grounded in the answer."""
        if not ctx:
            return []

        sources: List[TraceableSourceItem] = []
        seen_keys = set()

        def add_source(item: TraceableSourceItem):
            key = f"{item.source_type}:{item.title}:{item.target_id or ''}"
            if key not in seen_keys:
                seen_keys.add(key)
                sources.append(item)

        status = getattr(ctx, "status", None) or ctx.metadata.get("status", "")
        priority = getattr(ctx, "priority", None) or ctx.metadata.get("priority", "")

        # 1. Project root source (always present)
        add_source(TraceableSourceItem(
            source_type=ProjectSourceType.PROJECT.value,
            title=f"Project: {ctx.project_name}",
            target_path=ctx.project_path,
            badge=ctx.project_type.capitalize() if ctx.project_type else "Project",
            metadata={"status": status, "priority": priority},
        ))

        q_lower = question.lower()
        a_lower = answer.lower()
        combined_text = f"{q_lower} {a_lower}"

        # 2. Offline / Missing Library References
        for item in ctx.library_summary.linked_assets:
            status = item.get("availability_status") or ("online" if item.get("is_online", True) else "offline")
            fn = item.get("filename") or item.get("title", "Asset")
            drv = item.get("drive_id", "Drive")

            if status == "offline":
                add_source(TraceableSourceItem(
                    source_type=ProjectSourceType.LIBRARY_ASSET.value,
                    title=fn,
                    target_id=item.get("library_asset_id") or item.get("id"),
                    target_path=item.get("drive_relative_path") or item.get("file_path"),
                    status="offline",
                    badge=f"Offline ({drv})",
                    metadata=item,
                ))
            elif status == "missing":
                add_source(TraceableSourceItem(
                    source_type=ProjectSourceType.LIBRARY_ASSET.value,
                    title=fn,
                    target_id=item.get("library_asset_id") or item.get("id"),
                    status="missing",
                    badge="Missing",
                    metadata=item,
                ))
            elif "library" in q_lower or fn.lower() in combined_text:
                add_source(TraceableSourceItem(
                    source_type=ProjectSourceType.LIBRARY_ASSET.value,
                    title=fn,
                    target_id=item.get("library_asset_id") or item.get("id"),
                    target_path=item.get("drive_relative_path") or item.get("file_path"),
                    status=status,
                    badge="Library",
                    metadata=item,
                ))

        # 3. Version groups mentioned or relevant
        for grp in ctx.asset_summary.version_groups:
            log_name = grp.get("logical_name", "")
            latest = grp.get("latest", "")
            # Check if mentioned or if asking generally about assets/versions
            if log_name.lower() in combined_text or "version" in q_lower or "asset" in q_lower:
                add_source(TraceableSourceItem(
                    source_type=ProjectSourceType.ASSET.value,
                    title=f"{log_name} ({latest})",
                    target_path=log_name,
                    badge=f"Latest: {latest}",
                    metadata=grp,
                ))

        # 4. Knowledge Notes mentioned or relevant
        for note in ctx.knowledge_summary.recent_notes:
            t = note.get("title", "")
            doc_id = note.get("id")
            # If doc title is mentioned or user asked about knowledge/notes
            if t.lower() in combined_text or "knowledge" in q_lower or "note" in q_lower or "lore" in q_lower or "concept" in q_lower:
                badge = "⭐ Favorite" if note.get("is_favorite") else "Note"
                add_source(TraceableSourceItem(
                    source_type=ProjectSourceType.KNOWLEDGE.value,
                    title=t,
                    target_id=doc_id,
                    badge=badge,
                    metadata=note,
                ))

        # 5. Lab Boards mentioned or relevant
        boards_to_check = getattr(ctx.lab_summary, "recent_boards", []) or getattr(ctx.lab_summary, "boards", [])
        for board in boards_to_check:
            b_name = board.get("name", "")
            b_id = board.get("id")
            cnt = board.get("node_count", 0)
            if b_name.lower() in combined_text or "lab" in q_lower or "board" in q_lower or "task" in q_lower:
                add_source(TraceableSourceItem(
                    source_type=ProjectSourceType.LAB_BOARD.value,
                    title=f"Lab Board: {b_name}",
                    target_id=b_id or b_name,
                    badge=f"{cnt} nodes",
                    metadata=board,
                ))

        # 6. Lab Checklist Tasks if tasks mentioned
        tasks = ctx.lab_summary.task_status
        if tasks.get("total", 0) > 0 and ("task" in combined_text or "checklist" in combined_text or "progress" in combined_text):
            comp = tasks.get("completed", 0)
            tot = tasks.get("total", 0)
            add_source(TraceableSourceItem(
                source_type=ProjectSourceType.LAB_TASK.value,
                title="Lab Checklist Tasks",
                badge=f"{comp}/{tot} Done",
                metadata=tasks,
            ))

        return sources

    # -------------------------------------------------------------------------
    # Quick Starter Suggestions
    # -------------------------------------------------------------------------

    def get_quick_suggestions(self, project_or_id: Any) -> List[str]:
        """Generate high-signal starter questions tailored to the project context."""
        ctx = self.resolve_project_context(project_or_id)
        suggestions: List[str] = [
            "What is this project about?",
        ]

        if not ctx:
            suggestions.extend([
                "What assets are currently available?",
                "Which library assets are offline?",
                "What knowledge notes do I have for this project?",
            ])
            return suggestions

        # Offline references present
        if ctx.availability_summary.offline_library_assets > 0:
            suggestions.append("Which library assets are offline and what drives are needed?")
        elif ctx.library_summary.total_linked_assets > 0:
            suggestions.append("What library assets are used in this project?")

        # Versioned assets present
        if ctx.asset_summary.version_groups:
            suggestions.append("What are the latest asset versions in this project?")
        elif ctx.asset_summary.total_assets > 0:
            suggestions.append("What local assets are organized in this project?")

        # Knowledge notes present
        if ctx.knowledge_summary.total_notes > 0:
            suggestions.append("What knowledge and production notes do I have for this project?")

        # Lab boards or tasks present
        if ctx.lab_summary.total_boards > 0 or ctx.lab_summary.task_status.get("total", 0) > 0:
            suggestions.append("What is the current status of Lab boards and tasks?")

        return suggestions[:4]

    # -------------------------------------------------------------------------
    # Execution (Sync & Async)
    # -------------------------------------------------------------------------

    def ask(self, question: str, project_or_id: Any) -> ProjectAssistantResponse:
        """Synchronously ask a question grounded in ProjectContext."""
        if not self.is_ai_available():
            return ProjectAssistantResponse(
                answer="AI capabilities are currently disabled in Settings. Enable AI to ask project questions.",
                sources=[],
                success=False,
                error_message="AI is disabled.",
            )

        try:
            self.ask_started.emit(question)
        except Exception:
            pass

        request, ctx = self.build_ask_request(question, project_or_id)
        ai_resp: AIResponse = self.ai_service.generate(request)

        if not ai_resp.success:
            err_msg = ai_resp.error_message or "AI generation failed."
            try:
                self.ask_error.emit(question, err_msg)
            except Exception:
                pass
            return ProjectAssistantResponse(
                answer=f"Could not generate response: {err_msg}",
                sources=[],
                project_name=ctx.project_name if ctx else "",
                project_path=ctx.project_path if ctx else "",
                success=False,
                error_message=err_msg,
                raw_response=ai_resp,
            )

        answer_text = (ai_resp.text or "").strip()
        sources = self.extract_traceable_sources(question, answer_text, ctx)

        # Update in-memory history
        self.add_history_message("user", question)
        self.add_history_message("assistant", answer_text)

        result = ProjectAssistantResponse(
            answer=answer_text,
            sources=sources,
            project_name=ctx.project_name if ctx else "",
            project_path=ctx.project_path if ctx else "",
            success=True,
            raw_response=ai_resp,
        )

        try:
            self.ask_finished.emit(question, result)
        except Exception:
            pass

        return result

    def ask_async(
        self,
        question: str,
        project_or_id: Any,
        on_finished: Optional[Callable[[str, ProjectAssistantResponse], None]] = None,
        on_error: Optional[Callable[[str, str], None]] = None,
    ) -> Optional[AIWorker]:
        """Asynchronously ask a question on the global thread pool with non-blocking callbacks."""
        if not self.is_ai_available():
            err = "AI capabilities are currently disabled in Settings."
            if on_error:
                on_error(question, err)
            return None

        try:
            self.ask_started.emit(question)
        except Exception:
            pass

        request, ctx = self.build_ask_request(question, project_or_id)

        def _handle_raw_finished(req: AIRequest, resp: AIResponse):
            if not resp.success:
                err_msg = resp.error_message or "AI generation failed."
                try:
                    self.ask_error.emit(question, err_msg)
                except Exception:
                    pass
                if on_error:
                    on_error(question, err_msg)
                return

            answer_text = (resp.text or "").strip()
            sources = self.extract_traceable_sources(question, answer_text, ctx)

            self.add_history_message("user", question)
            self.add_history_message("assistant", answer_text)

            res = ProjectAssistantResponse(
                answer=answer_text,
                sources=sources,
                project_name=ctx.project_name if ctx else "",
                project_path=ctx.project_path if ctx else "",
                success=True,
                raw_response=resp,
            )

            try:
                self.ask_finished.emit(question, res)
            except Exception:
                pass

            if on_finished:
                on_finished(question, res)

        def _handle_raw_error(err_str: str):
            try:
                self.ask_error.emit(question, err_str)
            except Exception:
                pass
            if on_error:
                on_error(question, err_str)

        return self.ai_service.generate_async(
            request=request,
            on_finished=_handle_raw_finished,
            on_error=_handle_raw_error,
        )
