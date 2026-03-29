"""
Data models for the backup system.

Contains enums, dataclasses, and exceptions used across
the backup and snapshot modules.
"""

import json
from dataclasses import asdict, dataclass
from enum import Enum


class BackupType(Enum):
    """Type of backup content to include.

    Attributes:
        CONFIG: Application configuration only.
        DNS: DNS settings backup.
        WIREGUARD: WireGuard configuration files.
        ZAPRET: Zapret settings and scripts.
        SERVICES: Service state snapshot.
        FULL: All of the above combined.
    """

    CONFIG = "config"
    DNS = "dns"
    WIREGUARD = "wireguard"
    ZAPRET = "zapret"
    SERVICES = "services"
    FULL = "full"


@dataclass
class BackupMetadata:
    """Metadata describing a single backup archive.

    Attributes:
        id: Unique backup identifier (timestamp + hash).
        type: Category of backup content.
        timestamp: ISO-8601 creation timestamp.
        description: Human-readable backup description.
        version: Application version at backup time.
        files: List of absolute file paths included.
        size: Archive size in bytes.
    """

    id: str
    type: BackupType
    timestamp: str
    description: str
    version: str
    files: list[str]
    size: int = 0

    def to_dict(self) -> dict[str, object]:
        """Convert metadata to a JSON-serializable dictionary.

        Returns:
            Dictionary with all metadata fields.
        """
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "description": self.description,
            "version": self.version,
            "files": self.files,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BackupMetadata":
        """Create a BackupMetadata instance from a dictionary.

        Args:
            data: Dictionary with backup metadata fields.

        Returns:
            Populated BackupMetadata instance.
        """
        return cls(
            id=data["id"],
            type=BackupType(data["type"]),
            timestamp=data["timestamp"],
            description=data["description"],
            version=data["version"],
            files=data.get("files", []),
            size=data.get("size", 0),
        )


@dataclass
class SystemSnapshot:
    """Snapshot of system state before a destructive operation.

    Attributes:
        id: Unique snapshot identifier.
        timestamp: ISO-8601 creation timestamp.
        operation: Description of the triggering operation.
        files_backed_up: Paths of files saved in snapshot.
        services_state: Service name to status mapping.
        dns_state: Contents of /etc/resolv.conf or None.
    """

    id: str
    timestamp: str
    operation: str
    files_backed_up: list[str]
    services_state: dict[str, str]
    dns_state: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all snapshot fields.
        """
        return asdict(self)

    def save_to_file(self, path: str) -> None:
        """Save snapshot metadata to a JSON file.

        Args:
            path: Destination file path for the JSON output.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class BackupError(Exception):
    """Exception raised for backup-related errors."""
