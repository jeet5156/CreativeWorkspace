"""Knowledge AI Assistant Service for CreativeWorkspace.

Coordinates interactive, free-form Q&A with indexed workspace context:
1. Question-driven Context Retrieval via ContextRetrievalService
2. Primary Subject Grounding (Knowledge notes, Library assets, Projects, Lab nodes)
3. In-memory Conversation History (bounded multi-turn context)
4. Structured Prompt Grounding preventing hallucinations and ungrounded claims
5. Fully provider-agnostic execution via AIService

Hard Invariant:
Queries use metadata and local indexes only. No filesystem-wide scans, binary file parsing,
or physical drive probing occur.
"""

from enum import Enum
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from PySide6.QtCore import QObject, Signal

from models.ai import AIContext, AIMessage, AIRequest, AIResponse
from models.ai_context import ContextItem, ContextQuery, ContextResult, ContextScope, ContextSource
from models.knowledge import KnowledgeDocument
from services.ai_service import AIService, AIWorker
from services.context_retrieval_service import ContextRetrievalService
from services.knowledge_ai_service import KnowledgeAIContextMode


class KnowledgeAssistantService(QObject):
    """Coordinates free-form conversational Q&A grounded in indexed workspace context."""

    ask_started = Signal(str)                          # (question)
    ask_finished = Signal(str, object)                 # (question, AIResponse)
    ask_error = Signal(str, str)                       # (question, error_message)
    history_cleared = Signal()

    MAX_HISTORY_MESSAGES = 10  # Maximum recent conversation turns preserved in-memory

    def __init__(
        self,
        ai_service: Optional[AIService] = None,
        knowledge_service=None,
        context_retrieval_service: Optional[ContextRetrievalService] = None,
    ):
        super().__init__()
        self.ai_service = ai_service
        self.knowledge_service = knowledge_service
        self.context_retrieval_service = context_retrieval_service
        self._history: List[AIMessage] = []
        self._current_subject_type: Optional[str] = None
        self._current_subject_id: Optional[str] = None

    def set_ai_service(self, ai_service: AIService):
        self.ai_service = ai_service

    def set_context_retrieval_service(self, service: ContextRetrievalService):
        self.context_retrieval_service = service

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
        """Reset conversation history for new subject or fresh session."""
        self._history.clear()
        self.history_cleared.emit()

    def set_primary_subject(self, subject_type: Optional[str], subject_id: Optional[str]):
        """Update active subject anchor; resets history if subject identity changed."""
        if self._current_subject_type != subject_type or self._current_subject_id != subject_id:
            self._current_subject_type = subject_type
            self._current_subject_id = subject_id
            self.clear_history()

    # -------------------------------------------------------------------------
    # Question-Driven Context Retrieval & Compacting
    # -------------------------------------------------------------------------

    def resolve_context_for_question(
        self,
        question: str,
        document: Optional[KnowledgeDocument] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        project_id: Optional[str] = None,
        mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
    ) -> Tuple[Optional[ContextResult], str]:
        """Retrieve and compact workspace context matching the user's question and subject."""
        if not self.is_ai_available():
            return None, ""

        if isinstance(mode, str):
            try:
                mode = KnowledgeAIContextMode(mode.lower())
            except ValueError:
                mode = KnowledgeAIContextMode.RELATED

        if mode == KnowledgeAIContextMode.NONE:
            return None, ""

        if not self.context_retrieval_service:
            return None, ""

        scope_map = {
            KnowledgeAIContextMode.CURRENT: ContextScope.CURRENT_PROJECT,
            KnowledgeAIContextMode.RELATED: ContextScope.RELATED_ONLY,
            KnowledgeAIContextMode.PROJECT: ContextScope.CURRENT_PROJECT,
            KnowledgeAIContextMode.WORKSPACE: ContextScope.WORKSPACE,
        }
        target_scope = scope_map.get(mode, ContextScope.RELATED_ONLY)

        doc_id = document.id if document else (subject_id if subject_type in ("knowledge", "document") else None)
        active_proj_id = project_id or (document.project_ids[0] if (document and document.project_ids) else None)

        query = ContextQuery(
            text=question.strip(),
            document_id=doc_id,
            project_id=active_proj_id,
            scope=target_scope,
            max_items=15,
            max_knowledge_items=4,
            max_library_assets=6,
            max_project_assets=6,
            max_lab_nodes=5,
            max_projects=2,
        )

        try:
            retrieved = self.context_retrieval_service.retrieve(query)
            compact_text = self._compact_context_result(retrieved, active_doc_id=doc_id)
            return retrieved, compact_text
        except Exception:
            return None, ""

    def _compact_context_result(self, result: Optional[ContextResult], active_doc_id: Optional[str] = None) -> str:
        """Compact retrieved candidates into high-signal, token-efficient workspace context."""
        if not result or not result.items:
            return ""

        sections: List[str] = []

        # 1. Projects
        projects = [it for it in result.items if it.source_type in (ContextSource.PROJECT, "project")]
        if projects:
            p_lines = ["PROJECT:"]
            for p in projects:
                p_lines.append(f"- {p.title}")
                if p.description and p.description != p.title:
                    p_lines.append(f"  Description: {p.description[:120].strip()}")
            sections.append("\n".join(p_lines))

        # 2. Related Knowledge (exclude active document if already present as primary subject)
        notes = [
            it for it in result.items
            if it.source_type in (ContextSource.KNOWLEDGE, "knowledge")
            and (not active_doc_id or it.id != active_doc_id)
        ]
        if notes:
            k_lines = ["RELATED KNOWLEDGE:"]
            for k in notes:
                k_lines.append(f"- {k.title}")
                tags = k.metadata.get("tags")
                if tags:
                    k_lines.append(f"  Tags: {', '.join(tags)}")
                if k.description and k.description != k.title:
                    k_lines.append(f"  Snippet: {k.description[:150].strip()}")
            sections.append("\n".join(k_lines))

        # 3. Library Assets
        lib_assets = [it for it in result.items if it.source_type in (ContextSource.LIBRARY_ASSET, "library_asset")]
        if lib_assets:
            l_lines = ["LIBRARY ASSETS:"]
            for l in lib_assets:
                l_lines.append(f"- {l.title}")
                loc = l.path_hint or l.metadata.get("drive_relative_path")
                if loc:
                    l_lines.append(f"  Location: {loc}")
                status = l.availability or ("Online" if l.metadata.get("is_online", True) else "Offline")
                l_lines.append(f"  Status: {status.capitalize()}")
                tags = l.metadata.get("tags")
                if tags:
                    l_lines.append(f"  Tags: {', '.join(tags)}")
            sections.append("\n".join(l_lines))

        # 4. Project Assets
        proj_assets = [it for it in result.items if it.source_type in (ContextSource.PROJECT_ASSET, "project_asset")]
        if proj_assets:
            pa_lines = ["PROJECT ASSETS:"]
            for pa in proj_assets:
                pa_lines.append(f"- {pa.title}")
                cat = pa.metadata.get("category")
                if cat:
                    pa_lines.append(f"  Category: {cat}")
                tags = pa.metadata.get("tags")
                if tags:
                    pa_lines.append(f"  Tags: {', '.join(tags)}")
            sections.append("\n".join(pa_lines))

        # 5. Lab
        lab_nodes = [it for it in result.items if it.source_type in (ContextSource.LAB_NODE, ContextSource.LAB_BOARD, "lab_node", "lab_board")]
        if lab_nodes:
            lb_lines = ["LAB:"]
            for lb in lab_nodes:
                bname = lb.metadata.get("board_name") or "Lab Board"
                lb_lines.append(f"- {bname}")
                ntype = lb.metadata.get("node_type")
                if ntype:
                    lb_lines.append(f"  Node: {lb.title} ({ntype})")
                else:
                    lb_lines.append(f"  Node: {lb.title}")
                if lb.description and lb.description != lb.title:
                    lb_lines.append(f"  Details: {lb.description[:100].strip()}")
            sections.append("\n".join(lb_lines))

        return "\n\n".join(sections).strip()

    # -------------------------------------------------------------------------
    # Structured Prompt Construction
    # -------------------------------------------------------------------------

    def build_ask_request(
        self,
        question: str,
        document: Optional[KnowledgeDocument] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
    ) -> AIRequest:
        """Construct grounded, partitioned AIRequest for free-form user question."""
        ctx_res, workspace_context_str = self.resolve_context_for_question(
            question=question,
            document=document,
            subject_type=subject_type,
            subject_id=subject_id,
            project_id=project_id,
            mode=context_mode,
        )

        system_instruction = (
            "You are an intelligent knowledge and creative assistant for CreativeWorkspace.\n"
            "The supplied workspace context is the authoritative available workspace information.\n"
            "Answer the user's question using the supplied context and current subject.\n"
            "Do not invent assets, projects, files, nodes, relationships, or facts.\n"
            "If the available context is insufficient, say so clearly (e.g. 'I couldn't find enough indexed workspace information to answer that confidently.').\n"
            "Distinguish between verified catalog facts and reasonable interpretation.\n"
            "Do not claim to have opened or inspected binary/media files that were not supplied in the context."
        )

        prompt_parts: List[str] = []

        # 1. Primary Subject & Document Anchor
        if document:
            title = document.title or "Untitled Note"
            tags_str = ", ".join(document.tags) if document.tags else "None"
            content = document.content or ""
            prompt_parts.append(
                f"CURRENT DOCUMENT (PRIMARY SUBJECT):\nTitle: {title}\nTags: {tags_str}\nContent:\n\"\"\"\n{content}\n\"\"\"\n"
            )
        elif subject_type and subject_id:
            prompt_parts.append(
                f"PRIMARY SUBJECT:\nType: {subject_type}\nID/Name: {subject_id}\n"
            )

        # 2. Conversation History (if multi-turn follow-up)
        if self._history:
            history_lines = ["CONVERSATION HISTORY:"]
            for msg in self._history:
                speaker = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"{speaker}: {msg.content}")
            prompt_parts.append("\n".join(history_lines) + "\n")

        # 3. Retrieved Workspace Context
        if workspace_context_str:
            prompt_parts.append(f"WORKSPACE CONTEXT:\n{workspace_context_str}\n")

        # 4. User Question
        prompt_parts.append(f"USER QUESTION:\n{question.strip()}")

        full_prompt = "\n".join(prompt_parts)

        # Attach structured context metadata
        context = AIContext(
            document_ids=[document.id] if (document and document.id) else [],
            document_titles=[document.title] if (document and document.title) else [],
            document_id=document.id if document else None,
            project_id=project_id,
            workspace_context=workspace_context_str if workspace_context_str else None,
            extra={
                "question": question.strip(),
                "subject_type": subject_type or ("knowledge" if document else None),
                "subject_id": subject_id or (document.id if document else None),
                "context_mode": context_mode.value if isinstance(context_mode, KnowledgeAIContextMode) else str(context_mode),
                "context_result": ctx_res.to_dict() if ctx_res else None,
            },
        )

        return AIRequest(
            prompt=full_prompt,
            system_instruction=system_instruction,
            context=context,
            temperature=0.3,
            max_tokens=1024,
        )

    # -------------------------------------------------------------------------
    # Execution (Sync & Async)
    # -------------------------------------------------------------------------

    def ask(
        self,
        question: str,
        document: Optional[KnowledgeDocument] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        provider_id: Optional[str] = None,
    ) -> AIResponse:
        """Synchronously ask a question with retrieved workspace context."""
        cleaned_q = (question or "").strip()
        if not cleaned_q:
            return AIResponse(success=False, error_message="Please enter a question.")

        if not self.is_ai_available():
            return AIResponse(
                success=False,
                error_message="AI is not configured. Open Settings → AI to connect a provider.",
            )

        request = self.build_ask_request(
            question=cleaned_q,
            document=document,
            subject_type=subject_type,
            subject_id=subject_id,
            project_id=project_id,
            context_mode=context_mode,
        )

        self.ask_started.emit(cleaned_q)
        response = self.ai_service.generate(request, provider_id=provider_id)

        # Attach context result for UI transparency
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        if ctx_dict:
            response.raw_response = response.raw_response or {}
            response.raw_response["context_result"] = ctx_dict

        if response.success:
            self.add_history_message("user", cleaned_q)
            self.add_history_message("assistant", response.text.strip())

        self.ask_finished.emit(cleaned_q, response)
        return response

    def ask_async(
        self,
        question: str,
        on_finished: Callable[[str, AIResponse], None],
        on_error: Optional[Callable[[str], None]] = None,
        document: Optional[KnowledgeDocument] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        provider_id: Optional[str] = None,
    ) -> Optional[AIWorker]:
        """Asynchronously ask a question with background AI generation."""
        cleaned_q = (question or "").strip()
        if not cleaned_q:
            err = "Please enter a question."
            if on_error:
                on_error(err)
            return None

        if not self.is_ai_available():
            err = "AI is not configured. Open Settings → AI to connect a provider."
            if on_error:
                on_error(err)
            return None

        request = self.build_ask_request(
            question=cleaned_q,
            document=document,
            subject_type=subject_type,
            subject_id=subject_id,
            project_id=project_id,
            context_mode=context_mode,
        )

        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        self.ask_started.emit(cleaned_q)

        def _handle_finished(req: AIRequest, resp: AIResponse):
            if ctx_dict:
                resp.raw_response = resp.raw_response or {}
                resp.raw_response["context_result"] = ctx_dict

            if resp.success:
                self.add_history_message("user", cleaned_q)
                self.add_history_message("assistant", resp.text.strip())

            self.ask_finished.emit(cleaned_q, resp)
            try:
                on_finished(cleaned_q, resp)
            except Exception:
                pass

        def _handle_error(err_msg: str):
            self.ask_error.emit(cleaned_q, err_msg)
            if on_error:
                try:
                    on_error(err_msg)
                except Exception:
                    pass

        return self.ai_service.generate_async(
            request,
            on_finished=_handle_finished,
            on_error=_handle_error,
            provider_id=provider_id,
        )
