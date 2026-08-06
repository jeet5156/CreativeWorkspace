import time
from typing import Callable, Any


class PerformanceLogger:
    """Lightweight performance logger for tracking UI and service execution times."""

    @staticmethod
    def measure(action_name: str, fn: Callable[[], Any]) -> Any:
        return fn()

    @staticmethod
    def log(action_name: str, elapsed_ms: float, extra_info: str = ""):
        pass
