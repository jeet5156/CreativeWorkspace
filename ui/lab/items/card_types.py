from enum import Enum


class CardType(Enum):
    NOTE = "note"
    IMAGE = "image"
    ASSET = "asset"
    AI = "ai"
    CHECKLIST = "checklist"


class NoteType(Enum):
    BLANK = "blank"
    GOAL = "goal"
    IDEA = "idea"
    TASK = "task"
    PROBLEM = "problem"
    DECISION = "decision"


# Notion / Linear studio-grade visual configurations
NOTE_TYPE_CONFIGS = {
    NoteType.BLANK: {
        "label": "Note",
        "icon": "📝",
        "accent": "#94A3B8",      # Slate
        "badge_bg": "#1E293B",
        "badge_text": "#94A3B8",
    },
    NoteType.GOAL: {
        "label": "Goal",
        "icon": "🎯",
        "accent": "#3B82F6",      # Royal Blue
        "badge_bg": "#1E2E4A",
        "badge_text": "#60A5FA",
    },
    NoteType.IDEA: {
        "label": "Idea",
        "icon": "💡",
        "accent": "#F59E0B",      # Amber
        "badge_bg": "#3B2D1B",
        "badge_text": "#FBBF24",
    },
    NoteType.TASK: {
        "label": "Task",
        "icon": "📌",
        "accent": "#22C55E",      # Emerald Green
        "badge_bg": "#14382B",
        "badge_text": "#34D399",
    },
    NoteType.PROBLEM: {
        "label": "Problem",
        "icon": "⚠️",
        "accent": "#EF4444",      # Rose Red
        "badge_bg": "#3F1D24",
        "badge_text": "#F87171",
    },
    NoteType.DECISION: {
        "label": "Decision",
        "icon": "✦",
        "accent": "#A855F7",      # Violet Purple
        "badge_bg": "#2E1C48",
        "badge_text": "#C084FC",
    },
}
