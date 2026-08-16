# -----------------------------------------------------------------------------
# CreativeWorkspace Theme Tokens
# -----------------------------------------------------------------------------
BG_DARK = "#1B1D27"
CARD_BG = "#202334"
CARD_HOVER = "#262A3E"
BORDER_COLOR = "#313652"
TEXT_PRIMARY = "#F1F5F9"
TEXT_MUTED = "#94A3B8"
ACCENT = "#6366F1"

DARK_THEME = f"""
QMainWindow {{
    background-color: {BG_DARK};
}}

QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-size: 10pt;
}}

QMenuBar {{
    background-color: #14161D;
    color: {TEXT_PRIMARY};
}}

QMenuBar::item:selected {{
    background-color: {CARD_HOVER};
}}

QMenu {{
    background-color: {CARD_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
}}

QToolBar {{
    background-color: #14161D;
    border: none;
    spacing: 6px;
}}

QStatusBar {{
    background-color: #14161D;
}}

QTreeWidget {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER_COLOR};
    color: {TEXT_PRIMARY};
}}

QLabel {{
    color: {TEXT_PRIMARY};
}}

QToolTip {{
    background-color: {CARD_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}
"""