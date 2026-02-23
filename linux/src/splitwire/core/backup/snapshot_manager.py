"""
Snapshot manager for SplitWire-Turkey Linux.

Captures system state before potentially destructive operations
and provides rollback capability.
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .models import SystemSnapshot

logger = logging.getLogger(__name__)


class SnapshotManager:
    """
    Manages system snapshots for rollback capability.

    Used to capture state before potentially destructive operations.
    """

    def __init__(self, snapshot_dir: Path | None = None):
        """
        Initialize snapshot manager.

        Args:
            snapshot_dir: Override snapshot directory
        """
        if snapshot_dir:
            self._snapshot_dir = snapshot_dir
        else:
            xdg_cache = Path.home() / ".cache" / "splitwire"
            self._snapshot_dir = xdg_cache / "snapshots"

        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._current_snapshot: SystemSnapshot | None = None

    def create_snapshot(
        self, operation: str, files: list[str]
    ) -> SystemSnapshot:
        """
        Create a snapshot before an operation.

        Args:
            operation: Description of operation being performed
            files: Files that may be modified

        Returns:
            Created snapshot
        """
        snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        snapshot_path = self._snapshot_dir / snapshot_id

        logger.info(
            "[SNAPSHOT] Creating snapshot for operation: %s", operation
        )

        # Create snapshot directory
        snapshot_path.mkdir(parents=True, exist_ok=True)

        # Backup files
        backed_up = self._backup_files(files, snapshot_path)

        # Capture service states
        services_state = self._capture_services_state()

        # Capture DNS state
        dns_state = self._capture_dns_state()

        snapshot = SystemSnapshot(
            id=snapshot_id,
            timestamp=datetime.now().isoformat(),
            operation=operation,
            files_backed_up=backed_up,
            services_state=services_state,
            dns_state=dns_state,
        )

        # Save snapshot metadata
        meta_path = str(snapshot_path / "snapshot.json")
        snapshot.save_to_file(meta_path)

        self._current_snapshot = snapshot
        logger.info(
            "[SNAPSHOT] Snapshot created: %s (%d files)",
            snapshot_id,
            len(backed_up),
        )
        return snapshot

    @staticmethod
    def _backup_files(
        files: list[str], snapshot_path: Path
    ) -> list[str]:
        """Backup the given files into the snapshot directory."""
        backed_up: list[str] = []
        for file_path in files:
            path = Path(file_path)
            if path.exists():
                dest = snapshot_path / path.name
                shutil.copy2(str(path), str(dest))
                backed_up.append(file_path)
                logger.debug("[SNAPSHOT] Backed up: %s", file_path)
        return backed_up

    def rollback(self, snapshot_id: str | None = None) -> bool:
        """
        Rollback to a snapshot.

        Args:
            snapshot_id: ID of snapshot to rollback to (default: current)

        Returns:
            True if rollback succeeded
        """
        if snapshot_id is None and self._current_snapshot is not None:
            snapshot_id = self._current_snapshot.id

        if snapshot_id is None:
            logger.warning(
                "[SNAPSHOT] No snapshot ID provided for rollback"
            )
            return False

        logger.info(
            "[SNAPSHOT] Rolling back to snapshot: %s", snapshot_id
        )
        snapshot_path = self._snapshot_dir / snapshot_id

        if not snapshot_path.exists():
            logger.error(
                "[SNAPSHOT] Snapshot not found: %s", snapshot_id
            )
            return False

        meta_path = snapshot_path / "snapshot.json"
        if not meta_path.exists():
            logger.error(
                "[SNAPSHOT] Snapshot metadata not found: %s",
                snapshot_id,
            )
            return False

        try:
            return self._restore_snapshot_files(
                snapshot_path, meta_path
            )
        except Exception as e:
            logger.error(
                "[SNAPSHOT] Failed to rollback snapshot: %s", e
            )
            return False

    @staticmethod
    def _restore_snapshot_files(
        snapshot_path: Path, meta_path: Path
    ) -> bool:
        """Restore files from a snapshot directory."""
        with open(meta_path, encoding="utf-8") as f:
            snapshot_data = json.load(f)

        restored_count = 0
        for original_path in snapshot_data["files_backed_up"]:
            original = Path(original_path)
            backup = snapshot_path / original.name

            if backup.exists():
                shutil.copy2(str(backup), str(original))
                logger.debug(
                    "[SNAPSHOT] Restored: %s", original_path
                )
                restored_count += 1

        logger.info(
            "[SNAPSHOT] Rollback completed: %d files restored",
            restored_count,
        )
        return True

    def cleanup_snapshot(
        self, snapshot_id: str | None = None
    ) -> bool:
        """
        Remove a snapshot after successful operation.

        Args:
            snapshot_id: ID of snapshot to cleanup (default: current)

        Returns:
            True if cleanup succeeded
        """
        if snapshot_id is None and self._current_snapshot is not None:
            snapshot_id = self._current_snapshot.id
            self._current_snapshot = None

        if snapshot_id is None:
            return False

        snapshot_path = self._snapshot_dir / snapshot_id

        if snapshot_path.exists():
            shutil.rmtree(snapshot_path)
            return True

        return False

    @staticmethod
    def _capture_services_state() -> dict[str, str]:
        """Capture current service states."""
        services = ["wg-quick@splitwire", "zapret", "ciadpi"]
        states: dict[str, str] = {}

        for service in services:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                states[service] = result.stdout.strip()
            except Exception as e:
                logger.debug(
                    "Failed to get state of %s: %s", service, e
                )
                states[service] = "unknown"

        return states

    @staticmethod
    def _capture_dns_state() -> str | None:
        """Capture current DNS configuration."""
        resolv_conf = Path("/etc/resolv.conf")

        if resolv_conf.exists():
            try:
                return resolv_conf.read_text()
            except OSError:
                pass

        return None
