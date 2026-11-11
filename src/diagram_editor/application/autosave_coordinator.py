"""Framework-neutral debounce scheduler contract implemented with Qt timers in UI."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AutosavePolicy:
    debounce_ms: int = 1000
    retry_initial_ms: int = 2000
    retry_max_ms: int = 30000


@dataclass(frozen=True)
class ValidationPolicy:
    debounce_ms: int = 350
