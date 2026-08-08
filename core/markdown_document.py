import re
import html
from typing import List, Dict, Any, Optional, Set


class MarkdownDocument:
    """Decoupled model for parsing, structuring, and converting raw Markdown text into clean Qt HTML."""

    CALLOUT_STYLES = {
        "INFO": {
            "border": "#3B82F6",
            "bg": "#1E293B",
            "title_color": "#60A5FA",
            "icon": "ℹ️",
            "title": "INFO",
        },
        "TIP": {
            "border": "#22C55E",
            "bg": "#14382B",
            "title_color": "#4ADE80",
            "icon": "💡",
            "title": "TIP",
        },
        "WARNING": {
            "border": "#F59E0B",
            "bg": "#3B2D1B",
            "title_color": "#FBBF24",
            "icon": "⚠️",
            "title": "WARNING",
        },
        "IDEA": {
            "border": "#A855F7",
            "bg": "#2E1C48",
            "title_color": "#C084FC",
            "icon": "💡",
            "title": "IDEA",
        },
        "DECISION": {
            "border": "#06B6D4",
            "bg": "#153E4D",
            "title_color": "#22D3EE",
            "icon": "🎯",
            "title": "DECISION",
        },
    }

    def __init__(self, raw_text: str = ""):
        self._raw_text: str = raw_text or ""

    @property
    def raw_text(self) -> str:
        return self._raw_text

    @raw_text.setter
    def raw_text(self, text: str):
        self._raw_text = text or ""

    @staticmethod
    def toggle_checkbox_at_line(raw_text: str, line_index: int) -> str:
        """Toggle '- [ ]' <-> '- [x]' at specified line_index in raw markdown text."""
        lines = (raw_text or "").splitlines()
        if 0 <= line_index < len(lines):
            line = lines[line_index]
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]

            if stripped.startswith("- [ ] "):
                lines[line_index] = indent + "- [x] " + stripped[6:]
            elif stripped.startswith("* [ ] "):
                lines[line_index] = indent + "* [x] " + stripped[6:]
            elif stripped.startswith("- [x] ") or stripped.startswith("- [X] "):
                lines[line_index] = indent + "- [ ] " + stripped[6:]
            elif stripped.startswith("* [x] ") or stripped.startswith("* [X] "):
                lines[line_index] = indent + "* [ ] " + stripped[6:]
        return "\n".join(lines)

    @staticmethod
    def extract_missing_wiki_links(raw_text: str, existing_titles: Set[str]) -> List[str]:
        """Return list of unique missing target titles referenced in [[Wiki Links]]."""
        if not raw_text:
            return []
        matches = re.findall(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", raw_text)
        existing_lower = {t.lower() for t in existing_titles if t}
        missing = []
        for m in matches:
            target_title = m[0].strip()
            if target_title and target_title.lower() not in existing_lower:
                if target_title not in missing:
                    missing.append(target_title)
        return missing

    def to_html(self, existing_node_titles: Optional[Set[str]] = None) -> str:
        """Convert raw markdown text into styled dark-theme HTML compatible with QTextDocument."""
        if not self._raw_text.strip():
            return "<span style='color: #64748B; font-style: italic;'>Double-click to edit note...</span>"

        lines = self._raw_text.splitlines()
        html_lines: List[str] = []
        in_code_block = False
        code_block_lines: List[str] = []

        # ---------------------------------------------------------------------
        # Table of Contents Generation (only if >= 4 headings)
        # ---------------------------------------------------------------------
        headings = []
        for l in lines:
            ls = l.strip()
            if ls.startswith("# ") or ls.startswith("## ") or ls.startswith("### "):
                level = 1 if ls.startswith("# ") else (2 if ls.startswith("## ") else 3)
                h_text = ls.lstrip("#").strip()
                headings.append((level, h_text))

        if len(headings) >= 4:
            toc_entries = []
            for idx, (lvl, h_text) in enumerate(headings):
                indent_px = (lvl - 1) * 12 + 6
                slug = f"heading-{idx}"
                toc_entries.append(
                    f"<div style='margin: 2px 0 2px {indent_px}px;'>"
                    f"<a href='#{slug}' style='color: #60A5FA; text-decoration: none; font-size: 12px;'>• {html.escape(h_text)}</a>"
                    f"</div>"
                )

            toc_html = (
                f"<div style='background-color: #1E293B; border: 1px solid #334155; border-radius: 6px; "
                f"padding: 8px 12px; margin: 6px 0 10px 0;'>"
                f"<div style='font-weight: bold; color: #94A3B8; font-size: 11px; margin-bottom: 4px; "
                f"text-transform: uppercase; letter-spacing: 0.5px;'>Contents</div>"
                f"{''.join(toc_entries)}</div>"
            )
            html_lines.append(toc_html)

        # ---------------------------------------------------------------------
        # Line-by-Line Markdown Parser
        # ---------------------------------------------------------------------
        heading_counter = 0
        i = 0
        while i < len(lines):
            line = lines[i]

            # Code block toggle
            if line.strip().startswith("```"):
                if in_code_block:
                    in_code_block = False
                    code_content = html.escape("\n".join(code_block_lines), quote=False)
                    html_lines.append(
                        f"<pre style='background-color: #0F172A; color: #38BDF8; font-family: monospace; "
                        f"padding: 6px; border-radius: 4px; margin: 4px 0;'><code>{code_content}</code></pre>"
                    )
                    code_block_lines = []
                else:
                    in_code_block = True
                    code_block_lines = []
                i += 1
                continue

            if in_code_block:
                code_block_lines.append(line)
                i += 1
                continue

            # Empty line
            if not line.strip():
                html_lines.append("<br/>")
                i += 1
                continue

            # Callouts: > [!TYPE] Title
            if line.strip().startswith("> [!"):
                callout_match = re.match(r"^>\s*\[!([A-Za-z0-9_-]+)\]\s*(.*)$", line.strip())
                if callout_match:
                    raw_type = callout_match.group(1).upper()
                    custom_title = callout_match.group(2).strip()

                    style_info = self.CALLOUT_STYLES.get(
                        raw_type,
                        {
                            "border": "#3B82F6",
                            "bg": "#1E293B",
                            "title_color": "#60A5FA",
                            "icon": "ℹ️",
                            "title": raw_type,
                        },
                    )

                    display_title = custom_title if custom_title else style_info["title"]
                    body_lines = []

                    # Consume subsequent callout blockquote lines
                    i += 1
                    while i < len(lines) and lines[i].strip().startswith(">"):
                        sub_line = lines[i].strip()
                        if sub_line.startswith("> "):
                            body_lines.append(sub_line[2:])
                        elif sub_line == ">":
                            body_lines.append("")
                        else:
                            body_lines.append(sub_line[1:])
                        i += 1

                    parsed_body = "<br/>".join(self._parse_inline(bl, existing_node_titles) for bl in body_lines) if body_lines else ""
                    body_html = f"<div style='color: #CBD5E1; margin-top: 4px; line-height: 1.4;'>{parsed_body}</div>" if parsed_body else ""

                    border_col = style_info["border"]
                    bg_col = style_info["bg"]
                    title_col = style_info["title_color"]
                    icon_sym = style_info["icon"]

                    html_lines.append(
                        f"<div style='border-left: 4px solid {border_col}; "
                        f"background-color: {bg_col}; padding: 8px 12px; margin: 6px 0; border-radius: 6px;'>"
                        f"<div style='font-weight: bold; color: {title_col};'>{icon_sym} &nbsp;{display_title}</div>"
                        f"{body_html}</div>"
                    )
                    continue

            # Horizontal Rules
            if line.strip() in ("---", "***", "___"):
                html_lines.append("<hr style='border: none; border-top: 1px solid #334155; margin: 8px 0;'/>")
                i += 1
                continue

            # Standard Block Quotes
            if line.strip().startswith("> "):
                content = self._parse_inline(line.strip()[2:], existing_node_titles)
                html_lines.append(f"<blockquote style='border-left: 3px solid #6366F1; padding-left: 8px; margin: 4px 0; color: #94A3B8; font-style: italic;'>{content}</blockquote>")
                i += 1
                continue

            # Headings
            if line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
                anchor_tag = f"<a name='heading-{heading_counter}'></a>" if len(headings) >= 4 else ""
                heading_counter += 1

                if line.startswith("# "):
                    html_lines.append(f"{anchor_tag}<h1 style='color: #F8FAFC; font-size: 16px; font-weight: bold; margin: 6px 0 2px 0;'>{self._parse_inline(line[2:], existing_node_titles)}</h1>")
                elif line.startswith("## "):
                    html_lines.append(f"{anchor_tag}<h2 style='color: #E2E8F0; font-size: 14px; font-weight: bold; margin: 5px 0 2px 0;'>{self._parse_inline(line[3:], existing_node_titles)}</h2>")
                elif line.startswith("### "):
                    html_lines.append(f"{anchor_tag}<h3 style='color: #CBD5E1; font-size: 13px; font-weight: bold; margin: 4px 0 2px 0;'>{self._parse_inline(line[4:], existing_node_titles)}</h3>")
                i += 1
                continue

            # Interactive Checklists
            if line.strip().startswith("- [ ] ") or line.strip().startswith("* [ ] "):
                content = self._parse_inline(line.strip()[6:], existing_node_titles)
                html_lines.append(
                    f"<div style='margin: 3px 0; color: #CBD5E1;'>"
                    f"<a href='toggle_check:{i}' style='text-decoration: none; color: #94A3B8; font-weight: bold; font-family: monospace;'>[ &nbsp; ]</a> {content}</div>"
                )
                i += 1
                continue
            elif line.strip().startswith("- [x] ") or line.strip().startswith("- [X] ") or line.strip().startswith("* [x] ") or line.strip().startswith("* [X] "):
                content = self._parse_inline(line.strip()[6:], existing_node_titles)
                html_lines.append(
                    f"<div style='margin: 3px 0; color: #64748B;'>"
                    f"<a href='toggle_check:{i}' style='text-decoration: none; color: #22C55E; font-weight: bold; font-family: monospace;'>[✓]</a> <s>{content}</s></div>"
                )
                i += 1
                continue

            # Bullet Lists
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                content = self._parse_inline(line.strip()[2:], existing_node_titles)
                html_lines.append(f"<div style='margin: 2px 0 2px 12px; color: #CBD5E1;'>• {content}</div>")
                i += 1
                continue

            # Numbered Lists
            num_match = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
            if num_match:
                num = num_match.group(1)
                content = self._parse_inline(num_match.group(2), existing_node_titles)
                html_lines.append(f"<div style='margin: 2px 0 2px 12px; color: #CBD5E1;'>{num}. {content}</div>")
                i += 1
                continue

            # Normal Paragraph line
            html_lines.append(f"<div style='margin: 2px 0; color: #CBD5E1; line-height: 1.4;'>{self._parse_inline(line, existing_node_titles)}</div>")
            i += 1

        if in_code_block and code_block_lines:
            code_content = html.escape("\n".join(code_block_lines))
            html_lines.append(
                f"<pre style='background-color: #0F172A; color: #38BDF8; font-family: monospace; "
                f"padding: 6px; border-radius: 4px; margin: 4px 0;'><code>{code_content}</code></pre>"
            )

        return "".join(html_lines)

    def _parse_inline(self, text: str, existing_node_titles: Optional[Set[str]] = None) -> str:
        """Parse inline markdown elements (bold, italic, inline code, links, wiki links, mentions, smart dates)."""
        escaped = html.escape(text, quote=False)

        # Inline Code: `code`
        escaped = re.sub(
            r"`([^`]+)`",
            r"<code style='background-color: #1E293B; color: #A5B4FC; padding: 1px 4px; border-radius: 3px; font-family: monospace;'>\1</code>",
            escaped,
        )

        # Bold + Italic: ***text***
        escaped = re.sub(r"\*\*\*([^\*]+)\*\*\*", r"<b><i>\1</i></b>", escaped)

        # Bold: **text**
        escaped = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", escaped)

        # Italic: *text*
        escaped = re.sub(r"\*([^\*]+)\*", r"<i>\1</i>", escaped)

        # Smart Dates: @today, @tomorrow, @yesterday (case-insensitive)
        escaped = re.sub(
            r"(?<!\w)@(today|tomorrow|yesterday)\b",
            r"<span style='background-color: #1E3A8A; color: #93C5FD; padding: 1px 6px; border-radius: 10px; font-weight: bold; font-size: 11px;'>@\1</span>",
            escaped,
            flags=re.IGNORECASE,
        )

        # Mentions: @Word (e.g. @Client, @Team, @Rana)
        escaped = re.sub(
            r"(?<!\w)@(?!(?:today|tomorrow|yesterday)\b)([A-Za-z0-9_]+)\b",
            r"<span style='background-color: #312E81; color: #C7D2FE; padding: 1px 6px; border-radius: 10px; font-weight: bold; font-size: 11px;'>@\1</span>",
            escaped,
        )

        # Wiki Links: [[Target]] or [[Target|Alias]]
        existing_lower = {t.lower() for t in existing_node_titles} if existing_node_titles else None

        def _replace_wiki_link(match):
            raw_target = match.group(1).strip()
            raw_alias = match.group(2).strip() if match.group(2) else None
            display_text = raw_alias if raw_alias else raw_target

            # Determine whether target node exists on canvas
            is_existing = False
            if existing_lower is not None:
                is_existing = raw_target.lower() in existing_lower

            if is_existing:
                return (
                    f"<a href='wiki_link:{html.escape(raw_target)}' "
                    f"style='background-color: #312E81; color: #A5B4FC; padding: 1px 6px; border-radius: 4px; "
                    f"font-weight: bold; text-decoration: none;'>[[ {html.escape(display_text)} ]]</a>"
                )
            else:
                return (
                    f"<a href='wiki_link_missing:{html.escape(raw_target)}' "
                    f"style='background-color: #450A0A; color: #FCA5A5; border: 1px dashed #EF4444; padding: 1px 6px; border-radius: 4px; "
                    f"font-weight: bold; text-decoration: none;'>[[ {html.escape(display_text)} ]]</a>"
                )

        escaped = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _replace_wiki_link, escaped)

        # Standard Markdown Links: [label](url)
        escaped = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r"<a href='\2' style='color: #60A5FA; text-decoration: underline;'>\1</a>",
            escaped,
        )

        return escaped
