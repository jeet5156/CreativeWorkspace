import os
import uuid

SESSION_ID = str(uuid.uuid4())[:6].upper()


def get_md5(file_path) -> str:
    return "N/A"


def log_debug(tag: str, details: str):
    pass


def log_project_identity(tag: str, project):
    pass


def report_divergence(expected: str, actual: str, reason: str):
    pass


def get_caller_info() -> str:
    return "N/A"
