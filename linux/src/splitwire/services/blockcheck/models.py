"""
Data models and enums for the blockcheck service.
"""

from dataclasses import dataclass, field
from enum import Enum


class ScanMode(Enum):
    """Blockcheck scan modes."""

    QUICK = "quick"  # basic scan (~1-2 min)
    STANDARD = "standard"  # moderate scan (~5-10 min)
    FULL = "full"  # comprehensive scan (~15-30 min)


class ScanStatus(Enum):
    """Blockcheck scan status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BlockcheckResult:
    """Results from a blockcheck scan."""

    success: bool = False
    scan_mode: ScanMode = ScanMode.QUICK
    duration_seconds: float = 0.0
    recommended_args: str = ""
    recommended_mode: str = "nfqws"
    tested_strategies: list[dict] = field(default_factory=list)
    working_strategies: list[dict] = field(default_factory=list)
    failed_strategies: list[dict] = field(default_factory=list)
    raw_output: str = ""
    error_message: str = ""


@dataclass
class ScanProgress:
    """Progress information during scan."""

    status: ScanStatus = ScanStatus.IDLE
    percent: int = 0
    current_test: str = ""
    tests_completed: int = 0
    tests_total: int = 0
    elapsed_seconds: float = 0.0
