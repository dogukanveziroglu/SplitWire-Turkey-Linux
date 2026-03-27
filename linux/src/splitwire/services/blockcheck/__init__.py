"""
SplitWire blockcheck service package.

Re-exports all public names so that existing imports like
``from splitwire.services.blockcheck import BlockcheckService``
continue to work.
"""

from splitwire.core import get_shell
from splitwire.core.logger import get_logger

from .constants import (
    BLOCKCHECK_RESULTS,
    BLOCKCHECK_SCRIPT,
    FULL_TARGETS,
    QUICK_TARGETS,
    STANDARD_TARGETS,
)
from .models import (
    BlockcheckResult,
    ScanMode,
    ScanProgress,
    ScanStatus,
)
from .service import BlockcheckService

# Singleton instance
_blockcheck_service: BlockcheckService | None = None


def get_blockcheck_service() -> BlockcheckService:
    """Get the singleton Blockcheck service instance."""
    global _blockcheck_service
    if _blockcheck_service is None:
        _blockcheck_service = BlockcheckService()
    return _blockcheck_service


__all__ = [
    "BLOCKCHECK_RESULTS",
    "BLOCKCHECK_SCRIPT",
    "BlockcheckResult",
    "BlockcheckService",
    "FULL_TARGETS",
    "QUICK_TARGETS",
    "STANDARD_TARGETS",
    "ScanMode",
    "ScanProgress",
    "ScanStatus",
    "get_blockcheck_service",
]
