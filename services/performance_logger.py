import time
from typing import Callable, Any


class PerformanceLogger:
    """Lightweight performance logger for tracking UI and service execution times."""

    @staticmethod
    def measure(action_name: str, fn: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        result = fn()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(f"[PERF] {action_name} completed in {elapsed_ms:.1f} ms")
        return result

    @staticmethod
    def log(action_name: str, elapsed_ms: float, extra_info: str = ""):
        info_str = f" ({extra_info})" if extra_info else ""
        print(f"[PERF] {action_name} in {elapsed_ms:.1f} ms{info_str}")
