import re
import html
from typing import List, Dict, Any


class MarkdownDocument:
    """Decoupled model for parsing, structuring, and converting raw Markdown text into clean Qt HTML."""

    def __init__(self, raw_text: str = ""):
        self._raw_text: str = raw_text or ""

    @property
    def raw_text(self) -> str:
        return self._raw_text

    @raw_text.setter
    def raw_text(self, text: str):
        self._raw_text = text or ""

    def to_html(self) -> str:
        """Convert raw markdown text into styled dark-theme HTML compatible with QTextDocument."""
        if not self._raw_text.strip():
            return "<span style='color: #64748B; font-style: italic;'>Double-click to edit note...</span>"

        lines = self._raw_text.splitlines()
        html_lines: List[str] = []
        in_code_block = False
        code_block_lines: List[str] = []

        for line in lines:
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
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Empty line
            if not line.strip():
                html_lines.append("<br/>")
                continue

            # Horizontal Rules
            if line.strip() in ("---", "***", "___"):
                html_lines.append("<hr style='border: none; border-top: 1px solid #334155; margin: 8px 0;'/>")
                continue

            # Block Quotes
            if line.strip().startswith("> "):
                content = self._parse_inline(line.strip()[2:])
                html_lines.append(f"<blockquote style='border-left: 3px solid #6366F1; padding-left: 8px; margin: 4px 0; color: #94A3B8; font-style: italic;'>{content}</blockquote>")
                continue

            # Headings
            if line.startswith("# "):
                html_lines.append(f"<h1 style='color: #F8FAFC; font-size: 16px; font-weight: bold; margin: 6px 0 2px 0;'>{self._parse_inline(line[2:])}</h1>")
                continue
            elif line.startswith("## "):
                html_lines.append(f"<h2 style='color: #E2E8F0; font-size: 14px; font-weight: bold; margin: 5px 0 2px 0;'>{self._parse_inline(line[3:])}</h2>")
                continue
            elif line.startswith("### "):
                html_lines.append(f"<h3 style='color: #CBD5E1; font-size: 13px; font-weight: bold; margin: 4px 0 2px 0;'>{self._parse_inline(line[4:])}</h3>")
                continue

            # Checklists
            if line.strip().startswith("- [ ] ") or line.strip().startswith("* [ ] "):
                content = self._parse_inline(line.strip()[6:])
                html_lines.append(
                    f"<div style='margin: 2px 0; color: #CBD5E1;'><span style='color: #94A3B8; font-family: monospace;'>☐</span> {content}</div>"
                )
                continue
            elif line.strip().startswith("- [x] ") or line.strip().startswith("- [X] ") or line.strip().startswith("* [x] "):
                content = self._parse_inline(line.strip()[6:])
                html_lines.append(
                    f"<div style='margin: 2px 0; color: #64748B;'><span style='color: #22C55E;'>☑</span> <s>{content}</s></div>"
                )
                continue

            # Bullet Lists
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                content = self._parse_inline(line.strip()[2:])
                html_lines.append(f"<div style='margin: 2px 0 2px 12px; color: #CBD5E1;'>• {content}</div>")
                continue

            # Numbered Lists
            num_match = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
            if num_match:
                num = num_match.group(1)
                content = self._parse_inline(num_match.group(2))
                html_lines.append(f"<div style='margin: 2px 0 2px 12px; color: #CBD5E1;'>{num}. {content}</div>")
                continue

            # Normal Paragraph line
            html_lines.append(f"<div style='margin: 2px 0; color: #CBD5E1; line-height: 1.4;'>{self._parse_inline(line)}</div>")

        if in_code_block and code_block_lines:
            code_content = html.escape("\n".join(code_block_lines))
            html_lines.append(
                f"<pre style='background-color: #0F172A; color: #38BDF8; font-family: monospace; "
                f"padding: 6px; border-radius: 4px; margin: 4px 0;'><code>{code_content}</code></pre>"
            )

        return "".join(html_lines)

    def _parse_inline(self, text: str) -> str:
        """Parse inline markdown elements (bold, italic, inline code, links)."""
        escaped = html.escape(text, quote=False)

        # Inline Code: `code`
        escaped = re.sub(
            r"`([^`]+)`",
            r"<code style='background-color: #1E293B; color: #A5B4FC; padding: 1px 4px; border-radius: 3px; font-family: monospace;'>\1</code>",
            escaped
        )

        # Bold + Italic: ***text***
        escaped = re.sub(r"\*\*\*([^\*]+)\*\*\*", r"<b><i>\1</i></b>", escaped)

        # Bold: **text**
        escaped = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", escaped)

        # Italic: *text*
        escaped = re.sub(r"\*([^\*]+)\*", r"<i>\1</i>", escaped)

        # Standard Markdown Links: [label](url)
        escaped = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r"<a href='\2' style='color: #60A5FA; text-decoration: underline;'>\1</a>",
            escaped
        )

        # Wiki Links: [[Node Title]]
        escaped = re.sub(
            r"\[\[([^\]]+)\]\]",
            r"<span style='background-color: #312E81; color: #A5B4FC; padding: 1px 5px; border-radius: 4px; font-weight: bold;'>[[ \1 ]]</span>",
            escaped
        )

        return escaped
