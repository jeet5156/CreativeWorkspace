from typing import Dict, List

class FindService:
    """Search across projects and asset/reference filenames.

    API:
      search(query, context) -> Dict[str, List[dict]]
    """

    def __init__(self, context):
        self.context = context

    def _match(self, text: str, q: str) -> bool:
        if not text:
            return False
        return q.lower() in text.lower()

    def search(self, query: str) -> Dict[str, List[dict]]:
        q = (query or "").strip()
        results = {"projects": [], "assets": [], "references": []}
        if not q:
            return results

        # search projects by name and description
        try:
            for p in self.context.project_service.all_projects():
                if self._match(p.name, q) or self._match(getattr(p, 'description', ''), q):
                    results["projects"].append({"type": "project", "project": p, "label": p.name})
        except Exception:
            pass

        # search asset index entries
        try:
            for p in self.context.project_service.all_projects():
                assets = self.context.asset_service._ensure_index_loaded(p)
                for a in assets:
                    filename = a.get("filename", "")
                    rel = a.get("relative_path", "")
                    cat = a.get("category", "")
                    if self._match(filename, q) or self._match(rel, q):
                        entry = {"type": "asset", "project": p, "asset_id": a.get("id"), "label": f"{a.get('filename')} — {p.name}", "category": cat}
                        if cat.lower() == 'references' or rel.lower().startswith('references/'):
                            results["references"].append(entry)
                        else:
                            results["assets"].append(entry)
        except Exception:
            pass

        # Rank results: 1. Exact title matches, 2. Pinned items, 3. Normal relevance
        def rank_key(item):
            label = item.get("label", "")
            is_exact = (label.lower().strip() == q.lower())
            proj = item.get("project")
            is_pinned = False
            if proj and getattr(proj, "is_pinned", False):
                is_pinned = True
            elif item.get("is_pinned") or item.get("pinned"):
                is_pinned = True
            return (not is_exact, not is_pinned, label.lower())

        results["projects"].sort(key=rank_key)
        results["assets"].sort(key=rank_key)
        results["references"].sort(key=rank_key)

        return results
