"""
Backup manager for SplitWire-Turkey Linux.

Handles creation, restoration, listing, and cleanup of
configuration backups stored as compressed tarballs.
"""

import hashlib
import json
import logging
import tarfile
from datetime import datetime
from pathlib import Path

from .models import BackupError, BackupMetadata, BackupType

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages backups and rollback operations.

    Backups are stored in ~/.local/share/splitwire/backups/
    """

    APP_VERSION = "1.0.0"
    MAX_BACKUPS = 10  # Maximum number of backups to keep
    METADATA_FILE = "backup_metadata.json"

    def __init__(
        self,
        backup_dir: Path | None = None,
        config_dir: Path | None = None,
    ):
        """
        Initialize backup manager.

        Args:
            backup_dir: Override backup directory
            config_dir: Override config directory (for determining what to backup)
        """
        # Determine directories
        if backup_dir:
            self._backup_dir = backup_dir
        else:
            xdg_data = Path.home() / ".local" / "share" / "splitwire"
            self._backup_dir = xdg_data / "backups"

        if config_dir:
            self._config_dir = config_dir
        else:
            xdg_config = Path.home() / ".config" / "splitwire"
            self._config_dir = xdg_config

        # Data directory (WireGuard configs, Zapret, etc.)
        self._data_dir = Path.home() / ".local" / "share" / "splitwire"

        # Ensure directories exist
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backup_dir(self) -> Path:
        """Get backup directory path."""
        return self._backup_dir

    def _generate_backup_id(self) -> str:
        """Generate unique backup ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_input = f"{timestamp}_{id(self)}".encode()
        short_hash = hashlib.md5(hash_input).hexdigest()[:8]  # noqa: S324 -- non-cryptographic ID
        return f"{timestamp}_{short_hash}"

    def _get_backup_path(self, backup_id: str) -> Path:
        """Get path for a backup."""
        return self._backup_dir / f"{backup_id}.tar.gz"

    def _get_metadata_path(self, backup_id: str) -> Path:
        """Get path for backup metadata."""
        return self._backup_dir / f"{backup_id}.json"

    def create_backup(
        self,
        backup_type: BackupType = BackupType.CONFIG,
        description: str = "",
    ) -> BackupMetadata:
        """
        Create a new backup.

        Args:
            backup_type: Type of backup to create
            description: Human-readable description

        Returns:
            Backup metadata

        Raises:
            BackupError: If backup fails
        """
        backup_id = self._generate_backup_id()
        backup_path = self._get_backup_path(backup_id)
        timestamp = datetime.now().isoformat()

        logger.info(
            "[BACKUP] Creating %s backup: %s",
            backup_type.value,
            backup_id,
        )

        # Determine files to backup
        files_to_backup = self._get_files_for_backup(backup_type)

        if not files_to_backup:
            logger.error(
                "[BACKUP] No files found for backup type: %s",
                backup_type.value,
            )
            raise BackupError(
                f"No files found for backup type: {backup_type.value}"
            )

        logger.debug("[BACKUP] Files to backup: %d", len(files_to_backup))

        # Create tarball
        self._create_archive(backup_path, files_to_backup)

        # Get backup size
        backup_size = backup_path.stat().st_size

        # Create and save metadata
        metadata = BackupMetadata(
            id=backup_id,
            type=backup_type,
            timestamp=timestamp,
            description=description or f"{backup_type.value} backup",
            version=self.APP_VERSION,
            files=[str(f) for f in files_to_backup],
            size=backup_size,
        )
        self._save_metadata(backup_id, metadata)

        # Cleanup old backups
        self._cleanup_old_backups()

        logger.info(
            "[BACKUP] Backup created successfully: %s (%d bytes)",
            backup_id,
            backup_size,
        )
        return metadata

    def _create_archive(
        self, backup_path: Path, files: list[Path]
    ) -> None:
        """Create a compressed tar archive of the given files."""
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                for file_path in files:
                    path = Path(file_path)
                    if path.exists():
                        arcname = self._to_archive_name(path)
                        tar.add(str(path), arcname=arcname)
                        logger.debug("[BACKUP] Added: %s", path)
        except Exception as e:
            logger.error("[BACKUP] Failed to create archive: %s", e)
            if backup_path.exists():
                backup_path.unlink()
            raise BackupError(
                f"Failed to create backup archive: {e}"
            ) from e

    @staticmethod
    def _to_archive_name(path: Path) -> str:
        """Convert a filesystem path to a portable archive name."""
        home_str = str(Path.home())
        path_str = str(path)
        if path_str.startswith(home_str):
            return "__USER_HOME__" + path_str[len(home_str):]
        return path_str

    @staticmethod
    def _from_archive_name(name: str) -> str:
        """Convert an archive name back to a real filesystem path."""
        if name.startswith("__USER_HOME__"):
            return str(Path.home()) + name[len("__USER_HOME__"):]
        if name.startswith("HOME"):
            # Legacy support for old backups
            return str(Path.home()) + name[4:]
        return name

    def _get_files_for_backup(
        self, backup_type: BackupType
    ) -> list[Path]:
        """Get list of files to backup for a given type."""
        files: list[Path] = []

        if backup_type in (BackupType.CONFIG, BackupType.FULL):
            config_file = self._config_dir / "config.json"
            if config_file.exists():
                files.append(config_file)

        if backup_type in (BackupType.DNS, BackupType.FULL):
            resolv_backup = self._data_dir / "dns_backup"
            if resolv_backup.exists():
                files.append(resolv_backup)

        if backup_type in (BackupType.WIREGUARD, BackupType.FULL):
            wg_dir = self._data_dir / "wireguard"
            if wg_dir.exists():
                files.extend(wg_dir.glob("*.conf"))

        if backup_type in (BackupType.ZAPRET, BackupType.FULL):
            zapret_dir = self._data_dir / "zapret"
            if zapret_dir.exists():
                for pattern in ["*.conf", "*.config", "*.txt", "*.sh"]:
                    files.extend(zapret_dir.glob(f"**/{pattern}"))

        if backup_type == BackupType.SERVICES:
            services_file = self._data_dir / "services_state.json"
            if services_file.exists():
                files.append(services_file)

        return files

    def _save_metadata(
        self, backup_id: str, metadata: BackupMetadata
    ) -> None:
        """Save backup metadata to disk."""
        metadata_path = self._get_metadata_path(backup_id)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    def restore_backup(
        self, backup_id: str, dry_run: bool = False
    ) -> list[str]:
        """
        Restore a backup.

        Args:
            backup_id: ID of backup to restore
            dry_run: If True, only list files that would be restored

        Returns:
            List of restored file paths

        Raises:
            BackupError: If restore fails
        """
        backup_path = self._get_backup_path(backup_id)

        if not backup_path.exists():
            logger.error("[BACKUP] Backup not found: %s", backup_id)
            raise BackupError(f"Backup not found: {backup_id}")

        metadata = self.get_backup_metadata(backup_id)
        if metadata is None:
            logger.error(
                "[BACKUP] Backup metadata not found: %s", backup_id
            )
            raise BackupError(
                f"Backup metadata not found: {backup_id}"
            )

        logger.info(
            "[BACKUP] Restoring backup: %s (dry_run=%s)",
            backup_id,
            dry_run,
        )

        try:
            restored = self._extract_archive(
                backup_path, dry_run=dry_run
            )
        except Exception as e:
            logger.error("[BACKUP] Failed to restore backup: %s", e)
            raise BackupError(
                f"Failed to restore backup: {e}"
            ) from e

        logger.info(
            "[BACKUP] Restore completed: %d files", len(restored)
        )
        return restored

    def _extract_archive(
        self, backup_path: Path, *, dry_run: bool = False
    ) -> list[str]:
        """Extract files from a backup archive."""
        restored_files: list[str] = []

        with tarfile.open(backup_path, "r:gz") as tar:
            for member in tar.getmembers():
                real_path = self._from_archive_name(member.name)
                restored_files.append(real_path)

                if not dry_run:
                    Path(real_path).parent.mkdir(
                        parents=True, exist_ok=True
                    )
                    member.name = real_path
                    tar.extract(member, path="/")
                    logger.debug("[BACKUP] Restored: %s", real_path)

        return restored_files

    def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a backup.

        Args:
            backup_id: ID of backup to delete

        Returns:
            True if deleted successfully
        """
        backup_path = self._get_backup_path(backup_id)
        metadata_path = self._get_metadata_path(backup_id)

        deleted = False
        if backup_path.exists():
            backup_path.unlink()
            deleted = True
        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        return deleted

    def list_backups(
        self, backup_type: BackupType | None = None
    ) -> list[BackupMetadata]:
        """
        List all backups.

        Args:
            backup_type: Filter by type (optional)

        Returns:
            List of backup metadata, sorted by timestamp (newest first)
        """
        backups: list[BackupMetadata] = []

        for metadata_file in self._backup_dir.glob("*.json"):
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    data = json.load(f)
                    metadata = BackupMetadata.from_dict(data)
                    if backup_type is None or metadata.type == backup_type:
                        backups.append(metadata)
            except (json.JSONDecodeError, KeyError):
                continue

        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups

    def get_backup_metadata(
        self, backup_id: str
    ) -> BackupMetadata | None:
        """
        Get metadata for a specific backup.

        Args:
            backup_id: Backup ID

        Returns:
            Backup metadata or None if not found
        """
        metadata_path = self._get_metadata_path(backup_id)

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, encoding="utf-8") as f:
                data = json.load(f)
                return BackupMetadata.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def get_latest_backup(
        self, backup_type: BackupType | None = None
    ) -> BackupMetadata | None:
        """
        Get the most recent backup.

        Args:
            backup_type: Filter by type (optional)

        Returns:
            Latest backup metadata or None
        """
        backups = self.list_backups(backup_type)
        return backups[0] if backups else None

    def _cleanup_old_backups(self) -> int:
        """
        Remove old backups exceeding MAX_BACKUPS.

        Returns:
            Number of backups removed
        """
        backups = self.list_backups()

        if len(backups) <= self.MAX_BACKUPS:
            return 0

        removed = 0
        for backup in backups[self.MAX_BACKUPS:]:
            if self.delete_backup(backup.id):
                removed += 1
        return removed

    def get_total_backup_size(self) -> int:
        """
        Get total size of all backups in bytes.

        Returns:
            Total size in bytes
        """
        total = 0
        for backup_file in self._backup_dir.glob("*.tar.gz"):
            total += backup_file.stat().st_size
        return total
