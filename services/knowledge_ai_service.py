"""Knowledge AI Service for CreativeWorkspace with Context Retrieval.

Coordinates AI-assisted actions for Knowledge documents:
1. Summarize Document (concise overview of document content, enriched with related workspace context)
2. Generate Tags (suggests relevant, deduplicated categorization tags)
3. Key Takeaways (structured bullet-point takeaways and action items)

Context Modes:
- NONE: Only the current document.
- CURRENT: Current document + current project metadata if available.
- RELATED: Current document + explicit relationships + closely related indexed entities.
- PROJECT: Current document + related entities within the current project.
- WORKSPACE: Current document + broader indexed workspace search (subject to strict limits).

All methods are non-blocking and safe: existing documents, tags, and relationships
remain completely untouched unless the user explicitly applies the results.
"""

from enum import Enum
import json
import re
from typing import Callable, Dict, List, Optional, Tuple, Union, Any

from PySide6.QtCore import QObject, Signal

from models.ai import AIContext, AIMessage, AIRequest, AIResponse
from models.ai_context import ContextItem, ContextQuery, ContextResult, ContextScope, ContextSource
from models.knowledge import KnowledgeDocument
from services.ai_service import AIService, AIWorker
from services.context_retrieval_service import ContextRetrievalService


class KnowledgeAIContextMode(str, Enum):
    """Context retrieval scopes for Knowledge AI actions."""
    NONE = "none"
    CURRENT = "current"
    RELATED = "related"
    PROJECT = "project"
    WORKSPACE = "workspace"


class KnowledgeAIService(QObject):
    """Service providing context retrieval, prompt construction, execution, and parsing for Knowledge AI."""

    action_started = Signal(str, object)   # (action_name, KnowledgeDocument)
    action_finished = Signal(str, object, object)  # (action_name, KnowledgeDocument, AIResponse)
    action_error = Signal(str, object, str)  # (action_name, KnowledgeDocument, error_message)

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

    def set_ai_service(self, ai_service: AIService):
        self.ai_service = ai_service

    def set_context_retrieval_service(self, service: ContextRetrievalService):
        self.context_retrieval_service = service

    def is_ai_available(self) -> bool:
        """Check if AI is enabled and configured."""
        if not self.ai_service:
            return False
        return self.ai_service.is_enabled()

    # -------------------------------------------------------------------------
    # Context Retrieval & Compacting Helpers
    # -------------------------------------------------------------------------

    def resolve_context_for_action(
        self,
        doc: KnowledgeDocument,
        mode: Union[KnowledgeAIContextMode, str],
        project_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
    ) -> Tuple[Optional[ContextResult], str]:
        """Retrieve and format compact AI context based on mode and active document."""
        if not self.is_ai_available():
            return None, ""

        if isinstance(mode, str):
            try:
                mode = KnowledgeAIContextMode(mode.lower())
            except ValueError:
                mode = KnowledgeAIContextMode.NONE

        if mode == KnowledgeAIContextMode.NONE:
            return None, ""

        if context_result is not None:
            return context_result, self._compact_context_result(context_result)

        if not self.context_retrieval_service:
            return None, ""

        # Map KnowledgeAIContextMode to ContextScope
        scope_map = {
            KnowledgeAIContextMode.CURRENT: ContextScope.CURRENT_PROJECT,
            KnowledgeAIContextMode.RELATED: ContextScope.RELATED_ONLY,
            KnowledgeAIContextMode.PROJECT: ContextScope.CURRENT_PROJECT,
            KnowledgeAIContextMode.WORKSPACE: ContextScope.WORKSPACE,
        }
        target_scope = scope_map.get(mode, ContextScope.RELATED_ONLY)

        query = ContextQuery(
            text=doc.title or "",
            document_id=doc.id,
            project_id=project_id,
            scope=target_scope,
            max_items=15,
            max_knowledge_items=3,
            max_library_assets=5,
            max_project_assets=5,
            max_lab_nodes=5,
            max_projects=2,
        )

        try:
            retrieved = self.context_retrieval_service.retrieve(query)
            compact_text = self._compact_context_result(retrieved)
            return retrieved, compact_text
        except Exception:
            return None, ""

    def _compact_context_result(self, result: Optional[ContextResult]) -> str:
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
                    snippet = p.description[:120].strip()
                    p_lines.append(f"  Description: {snippet}")
            sections.append("\n".join(p_lines))

        # 2. Related Knowledge
        notes = [it for it in result.items if it.source_type in (ContextSource.KNOWLEDGE, "knowledge")]
        if notes:
            k_lines = ["RELATED KNOWLEDGE:"]
            for k in notes:
                k_lines.append(f"- {k.title}")
                tags = k.metadata.get("tags")
                if tags:
                    k_lines.append(f"  Tags: {', '.join(tags)}")
                if k.description and k.description != k.title:
                    snippet = k.description[:150].strip()
                    k_lines.append(f"  Snippet: {snippet}")
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
                    snippet = lb.description[:100].strip()
                    lb_lines.append(f"  Details: {snippet}")
            sections.append("\n".join(lb_lines))

        return "\n\n".join(sections).strip()

    # -------------------------------------------------------------------------
    # Request Builders
    # -------------------------------------------------------------------------

    def build_summary_request(
        self,
        doc: KnowledgeDocument,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        project_id: Optional[str] = None,
    ) -> AIRequest:
        """Build provider-agnostic request for document summarization with optional workspace context."""
        title = doc.title or "Untitled Note"
        content = doc.content or ""
        tags_str = ", ".join(doc.tags) if doc.tags else "None"

        ctx_res, workspace_context_str = self.resolve_context_for_action(
            doc, mode=context_mode, project_id=project_id, context_result=context_result
        )

        system_instruction = (
            "You are an intelligent knowledge assistant for creative artists, game developers, and writers. "
            "Your task is to summarize documents clearly, concisely, and objectively.\n"
            "The current document is the primary source. Use workspace context only when it is relevant. "
            "Do not invent facts that are not present in the current document or supplied workspace context. "
            "If workspace context conflicts with the document, do not silently resolve the conflict; state the uncertainty."
        )

        prompt_parts = [
            "Please provide a concise, high-level summary of the following knowledge document.\n",
            f"CURRENT DOCUMENT:\nTitle: {title}\nTags: {tags_str}\nContent:\n\"\"\"\n{content}\n\"\"\"\n",
        ]

        if workspace_context_str:
            prompt_parts.append(f"RELATED WORKSPACE CONTEXT:\n{workspace_context_str}\n")

        prompt_parts.append(
            "Provide a clear, cohesive summary (1-3 paragraphs) highlighting the core concept, purpose, and key details."
        )
        prompt = "\n".join(prompt_parts)

        context = AIContext(
            document_ids=[doc.id] if doc.id else [],
            document_titles=[title],
            document_id=doc.id,
            project_id=project_id,
            workspace_context=workspace_context_str if workspace_context_str else None,
            extra={
                "tags": doc.tags,
                "context_mode": context_mode.value if isinstance(context_mode, KnowledgeAIContextMode) else str(context_mode),
                "context_result": ctx_res.to_dict() if ctx_res else None,
            },
        )

        return AIRequest(
            prompt=prompt,
            system_instruction=system_instruction,
            context=context,
            temperature=0.4,
            max_tokens=1024,
        )

    def build_tags_request(
        self,
        doc: KnowledgeDocument,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.CURRENT,
        project_id: Optional[str] = None,
    ) -> AIRequest:
        """Build provider-agnostic request for tag generation with optional workspace context."""
        title = doc.title or "Untitled Note"
        content = doc.content or ""
        existing_tags_str = ", ".join(doc.tags) if doc.tags else "None"

        ctx_res, workspace_context_str = self.resolve_context_for_action(
            doc, mode=context_mode, project_id=project_id, context_result=context_result
        )

        system_instruction = (
            "You are a taxonomy and categorization assistant for a creative workspace. "
            "Your task is to generate relevant, concise, single-word or short-phrase tags for organizing documents.\n"
            "The current document is the primary source. Use workspace context only when it is relevant. "
            "Do not invent facts that are not present in the current document or supplied workspace context."
        )

        prompt_parts = [
            "Analyze the following knowledge document and suggest 3 to 8 relevant, concise categorization tags.\n",
            f"CURRENT DOCUMENT:\nTitle: {title}\nExisting Tags: {existing_tags_str}\nContent:\n\"\"\"\n{content}\n\"\"\"\n",
        ]

        if workspace_context_str:
            prompt_parts.append(f"RELATED WORKSPACE CONTEXT:\n{workspace_context_str}\n")

        prompt_parts.append(
            "Guidelines:\n"
            "- Output ONLY a comma-separated list of tags (e.g. gameplay, combat, lore, mechanics, shader, audio).\n"
            "- Do not include markdown formatting, bullet points, numbers, or explanation.\n"
            "- Suggest tags in lower case without hashtags."
        )
        prompt = "\n".join(prompt_parts)

        context = AIContext(
            document_ids=[doc.id] if doc.id else [],
            document_titles=[title],
            document_id=doc.id,
            project_id=project_id,
            workspace_context=workspace_context_str if workspace_context_str else None,
            extra={
                "existing_tags": doc.tags,
                "context_mode": context_mode.value if isinstance(context_mode, KnowledgeAIContextMode) else str(context_mode),
                "context_result": ctx_res.to_dict() if ctx_res else None,
            },
        )

        return AIRequest(
            prompt=prompt,
            system_instruction=system_instruction,
            context=context,
            temperature=0.3,
            max_tokens=256,
        )

    def build_takeaways_request(
        self,
        doc: KnowledgeDocument,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        project_id: Optional[str] = None,
    ) -> AIRequest:
        """Build provider-agnostic request for key takeaways extraction with optional workspace context."""
        title = doc.title or "Untitled Note"
        content = doc.content or ""
        tags_str = ", ".join(doc.tags) if doc.tags else "None"

        ctx_res, workspace_context_str = self.resolve_context_for_action(
            doc, mode=context_mode, project_id=project_id, context_result=context_result
        )

        system_instruction = (
            "You are an analytical assistant for creative projects and knowledge management. "
            "Your task is to extract core takeaways, key decisions, and actionable items from notes and documentation.\n"
            "The current document is the primary source. Use workspace context only when it is relevant. "
            "Do not invent facts that are not present in the current document or supplied workspace context. "
            "If workspace context conflicts with the document, do not silently resolve the conflict; state the uncertainty."
        )

        prompt_parts = [
            "Extract the key takeaways, decisions, and action items from the following document:\n",
            f"CURRENT DOCUMENT:\nTitle: {title}\nTags: {tags_str}\nContent:\n\"\"\"\n{content}\n\"\"\"\n",
        ]

        if workspace_context_str:
            prompt_parts.append(f"RELATED WORKSPACE CONTEXT:\n{workspace_context_str}\n")

        prompt_parts.append(
            "Format the output as clear, concise bullet points (using '• ' or '- '). "
            "Group into Action Items or Core Principles if applicable."
        )
        prompt = "\n".join(prompt_parts)

        context = AIContext(
            document_ids=[doc.id] if doc.id else [],
            document_titles=[title],
            document_id=doc.id,
            project_id=project_id,
            workspace_context=workspace_context_str if workspace_context_str else None,
            extra={
                "tags": doc.tags,
                "context_mode": context_mode.value if isinstance(context_mode, KnowledgeAIContextMode) else str(context_mode),
                "context_result": ctx_res.to_dict() if ctx_res else None,
            },
        )

        return AIRequest(
            prompt=prompt,
            system_instruction=system_instruction,
            context=context,
            temperature=0.3,
            max_tokens=1024,
        )

    # -------------------------------------------------------------------------
    # Response Parsing Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_tags_from_text(raw_text: str, existing_tags: Optional[List[str]] = None) -> List[str]:
        """Parse raw AI output into a list of clean, distinct tag suggestions."""
        if not raw_text or not raw_text.strip():
            return []

        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("[") and cleaned_text.endswith("]"):
            try:
                items = json.loads(cleaned_text)
                if isinstance(items, list):
                    raw_tags = [str(item) for item in items]
                else:
                    raw_tags = []
            except Exception:
                raw_tags = cleaned_text.strip("[]").split(",")
        else:
            lines = cleaned_text.splitlines()
            raw_tags = []
            for line in lines:
                sub = re.sub(r"^[\s\-\*•\d\.\)]+", "", line).strip()
                if sub:
                    parts = sub.split(",")
                    for p in parts:
                        raw_tags.append(p)

        existing_lower = set(t.strip().lower() for t in (existing_tags or []) if t.strip())

        parsed_tags = []
        seen = set()
        for tag_candidate in raw_tags:
            t = tag_candidate.strip().strip("\"'`#*_-").strip()
            t = " ".join(t.split())
            if not t:
                continue
            t_lower = t.lower()
            if t_lower not in existing_lower and t_lower not in seen:
                seen.add(t_lower)
                parsed_tags.append(t_lower)

        return parsed_tags

    # -------------------------------------------------------------------------
    # 1. Summarize Document
    # -------------------------------------------------------------------------

    def summarize_document(
        self,
        doc: KnowledgeDocument,
        provider_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        project_id: Optional[str] = None,
    ) -> AIResponse:
        """Synchronously generate a summary for a Knowledge document with workspace context."""
        if not self.is_ai_available():
            return AIResponse(
                success=False,
                error_message="AI is disabled or not configured. Open Settings → AI to configure.",
            )
        request = self.build_summary_request(
            doc, context_result=context_result, context_mode=context_mode, project_id=project_id
        )
        self.action_started.emit("summarize", doc)
        response = self.ai_service.generate(request, provider_id=provider_id)
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        if ctx_dict:
            response.raw_response = response.raw_response or {}
            response.raw_response["context_result"] = ctx_dict
        self.action_finished.emit("summarize", doc, response)
        return response

    def summarize_document_async(
        self,
        doc: KnowledgeDocument,
        on_finished: Callable[[KnowledgeDocument, AIResponse], None],
        on_error: Optional[Callable[[str], None]] = None,
        provider_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        project_id: Optional[str] = None,
    ) -> Optional[AIWorker]:
        """Asynchronously generate a summary for a Knowledge document in a background thread."""
        if not self.is_ai_available():
            err = "AI is disabled or not configured. Open Settings → AI to configure."
            if on_error:
                on_error(err)
            return None

        request = self.build_summary_request(
            doc, context_result=context_result, context_mode=context_mode, project_id=project_id
        )
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        self.action_started.emit("summarize", doc)

        def _handle_finished(req: AIRequest, resp: AIResponse):
            if ctx_dict:
                resp.raw_response = resp.raw_response or {}
                resp.raw_response["context_result"] = ctx_dict
            self.action_finished.emit("summarize", doc, resp)
            try:
                on_finished(doc, resp)
            except Exception:
                pass

        def _handle_error(err_msg: str):
            self.action_error.emit("summarize", doc, err_msg)
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

    # -------------------------------------------------------------------------
    # 2. Generate Tags
    # -------------------------------------------------------------------------

    def generate_tags(
        self,
        doc: KnowledgeDocument,
        provider_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.CURRENT,
        project_id: Optional[str] = None,
    ) -> Tuple[AIResponse, List[str]]:
        """Synchronously generate tag recommendations for a Knowledge document."""
        if not self.is_ai_available():
            resp = AIResponse(
                success=False,
                error_message="AI is disabled or not configured. Open Settings → AI to configure.",
            )
            return resp, []

        request = self.build_tags_request(
            doc, context_result=context_result, context_mode=context_mode, project_id=project_id
        )
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        self.action_started.emit("generate_tags", doc)
        response = self.ai_service.generate(request, provider_id=provider_id)
        if ctx_dict:
            response.raw_response = response.raw_response or {}
            response.raw_response["context_result"] = ctx_dict
        self.action_finished.emit("generate_tags", doc, response)

        suggested_tags = self.parse_tags_from_text(response.text, existing_tags=doc.tags) if response.success else []
        return response, suggested_tags

    def generate_tags_async(
        self,
        doc: KnowledgeDocument,
        on_finished: Callable[[KnowledgeDocument, AIResponse, List[str]], None],
        on_error: Optional[Callable[[str], None]] = None,
        provider_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.CURRENT,
        project_id: Optional[str] = None,
    ) -> Optional[AIWorker]:
        """Asynchronously generate tag recommendations for a Knowledge document."""
        if not self.is_ai_available():
            err = "AI is disabled or not configured. Open Settings → AI to configure."
            if on_error:
                on_error(err)
            return None

        request = self.build_tags_request(
            doc, context_result=context_result, context_mode=context_mode, project_id=project_id
        )
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        self.action_started.emit("generate_tags", doc)

        def _handle_finished(req: AIRequest, resp: AIResponse):
            if ctx_dict:
                resp.raw_response = resp.raw_response or {}
                resp.raw_response["context_result"] = ctx_dict
            self.action_finished.emit("generate_tags", doc, resp)
            suggested_tags = self.parse_tags_from_text(resp.text, existing_tags=doc.tags) if resp.success else []
            try:
                on_finished(doc, resp, suggested_tags)
            except Exception:
                pass

        def _handle_error(err_msg: str):
            self.action_error.emit("generate_tags", doc, err_msg)
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

    # -------------------------------------------------------------------------
    # 3. Key Takeaways
    # -------------------------------------------------------------------------

    def extract_key_takeaways(
        self,
        doc: KnowledgeDocument,
        provider_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        project_id: Optional[str] = None,
    ) -> AIResponse:
        """Synchronously extract key takeaways from a Knowledge document."""
        if not self.is_ai_available():
            return AIResponse(
                success=False,
                error_message="AI is disabled or not configured. Open Settings → AI to configure.",
            )

        request = self.build_takeaways_request(
            doc, context_result=context_result, context_mode=context_mode, project_id=project_id
        )
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        self.action_started.emit("key_takeaways", doc)
        response = self.ai_service.generate(request, provider_id=provider_id)
        if ctx_dict:
            response.raw_response = response.raw_response or {}
            response.raw_response["context_result"] = ctx_dict
        self.action_finished.emit("key_takeaways", doc, response)
        return response

    def extract_key_takeaways_async(
        self,
        doc: KnowledgeDocument,
        on_finished: Callable[[KnowledgeDocument, AIResponse], None],
        on_error: Optional[Callable[[str], None]] = None,
        provider_id: Optional[str] = None,
        context_result: Optional[ContextResult] = None,
        context_mode: Union[KnowledgeAIContextMode, str] = KnowledgeAIContextMode.RELATED,
        project_id: Optional[str] = None,
    ) -> Optional[AIWorker]:
        """Asynchronously extract key takeaways from a Knowledge document."""
        if not self.is_ai_available():
            err = "AI is disabled or not configured. Open Settings → AI to configure."
            if on_error:
                on_error(err)
            return None

        request = self.build_takeaways_request(
            doc, context_result=context_result, context_mode=context_mode, project_id=project_id
        )
        ctx_dict = request.context.extra.get("context_result") if (request and request.context) else None
        self.action_started.emit("key_takeaways", doc)

        def _handle_finished(req: AIRequest, resp: AIResponse):
            if ctx_dict:
                resp.raw_response = resp.raw_response or {}
                resp.raw_response["context_result"] = ctx_dict
            self.action_finished.emit("key_takeaways", doc, resp)
            try:
                on_finished(doc, resp)
            except Exception:
                pass

        def _handle_error(err_msg: str):
            self.action_error.emit("key_takeaways", doc, err_msg)
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
