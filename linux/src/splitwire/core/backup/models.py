"""
Data models for the backup system.

Contains enums, dataclasses, and exceptions used across
the backup and snapshot modules.
"""

import json
from dataclasses import asdict, dataclass
from enum import Enum


class BackupType(Enum):
    """Type of backup."""

    CONFIG = "config"  # Application configuration
    DNS = "dns"  # DNS settings
    WIREGUARD = "wireguard"  # WireGuard configs
    ZAPRET = "zapret"  # Zapret settings
    SERVICES = "services"  # Service states
    FULL = "full"  # Everything


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    id: str
    type: BackupType
    timestamp: str
    description: str
    version: str
    files: list[str]
    size: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
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
    def from_dict(cls, data: dict) -> "BackupMetadata":
        """Create from dictionary."""
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
    """Snapshot of system state before an operation."""

    id: str
    timestamp: str
    operation: str
    files_backed_up: list[str]
    services_state: dict[str, str]
    dns_state: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def save_to_file(self, path: str) -> None:
        """Save snapshot metadata to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class BackupError(Exception):
    """Exception raised for backup-related errors."""
