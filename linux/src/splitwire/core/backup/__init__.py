"""
Backup and rollback system for SplitWire-Turkey Linux.

Provides:
- Configuration backup and restore
- System state snapshots before changes
- Rollback capability for failed operations
"""

from .backup_manager import BackupManager
from .models import (
    BackupError,
    BackupMetadata,
    BackupType,
    SystemSnapshot,
)
from .snapshot_manager import SnapshotManager

__all__ = [
    "BackupError",
    "BackupManager",
    "BackupMetadata",
    "BackupType",
    "SnapshotManager",
    "SystemSnapshot",
    "create_backup",
    "get_backup_manager",
    "get_snapshot_manager",
    "list_backups",
    "restore_backup",
]

# Global instances
_backup_manager: BackupManager | None = None
_snapshot_manager: SnapshotManager | None = None


def get_backup_manager() -> BackupManager:
    """Get the global BackupManager instance."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager


def get_snapshot_manager() -> SnapshotManager:
    """Get the global SnapshotManager instance."""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = SnapshotManager()
    return _snapshot_manager


# Convenience functions


def create_backup(
    backup_type: BackupType = BackupType.CONFIG,
    description: str = "",
) -> BackupMetadata:
    """Create a backup (convenience function)."""
    return get_backup_manager().create_backup(backup_type, description)


def restore_backup(backup_id: str) -> list[str]:
    """Restore a backup (convenience function)."""
    return get_backup_manager().restore_backup(backup_id)


def list_backups(
    backup_type: BackupType | None = None,
) -> list[BackupMetadata]:
    """List backups (convenience function)."""
    return get_backup_manager().list_backups(backup_type)
