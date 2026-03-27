"""
Core modules for SplitWire-Turkey Linux.

This package contains:
- config: Configuration management (XDG paths, JSON storage)
- language: Localization and translation
- logger: Logging system
- shell: Shell command execution
- backup: Backup and rollback system

Uses PEP 562 lazy imports for backup and shell modules to avoid
loading them at package import time.
"""

from __future__ import annotations

import importlib

from .config import (
    AppConfig,
    ByeDPIConfig,
    ConfigManager,
    DNSConfig,
    Language,
    Theme,
    WireGuardConfig,
    ZapretConfig,
    get_config,
    get_config_manager,
    save_config,
)
from .language import (
    LanguageError,
    LanguageManager,
    format_text,
    get_current_language,
    get_language_manager,
    get_text,
    init_language_manager,
    set_language,
)
from .logger import (
    ColoredFormatter,
    SplitWireLogger,
    get_component_logger,
    get_logger,
    init_logger,
    setup_logging,
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "BackupError": (".backup", "BackupError"),
    "BackupManager": (".backup", "BackupManager"),
    "BackupMetadata": (".backup", "BackupMetadata"),
    "BackupType": (".backup", "BackupType"),
    "CommandResult": (".shell", "CommandResult"),
    "CommandStatus": (".shell", "CommandStatus"),
    "ShellExecutor": (".shell", "ShellExecutor"),
    "SnapshotManager": (".backup", "SnapshotManager"),
    "SystemSnapshot": (".backup", "SystemSnapshot"),
    "command_exists": (".shell", "command_exists"),
    "create_backup": (".backup", "create_backup"),
    "get_backup_manager": (".backup", "get_backup_manager"),
    "get_shell": (".shell", "get_shell"),
    "get_snapshot_manager": (".backup", "get_snapshot_manager"),
    "list_backups": (".backup", "list_backups"),
    "restore_backup": (".backup", "restore_backup"),
    "run": (".shell", "run"),
    "run_async": (".shell", "run_async"),
}

__all__ = [
    "AppConfig",
    "BackupError",
    "BackupManager",
    "BackupMetadata",
    "BackupType",
    "ByeDPIConfig",
    "ColoredFormatter",
    "CommandResult",
    "get_component_logger",
    "get_logger",
    "init_logger",
    "CommandStatus",
    "ConfigManager",
    "DNSConfig",
    "Language",
    "LanguageError",
    "LanguageManager",
    "ShellExecutor",
    "SnapshotManager",
    "SplitWireLogger",
    "SystemSnapshot",
    "Theme",
    "WireGuardConfig",
    "ZapretConfig",
    "command_exists",
    "create_backup",
    "format_text",
    "get_backup_manager",
    "get_config",
    "get_config_manager",
    "get_current_language",
    "get_language_manager",
    "get_shell",
    "get_snapshot_manager",
    "get_text",
    "init_language_manager",
    "list_backups",
    "restore_backup",
    "run",
    "run_async",
    "save_config",
    "set_language",
    "setup_logging",
]


def __getattr__(name: str) -> object:
    """Lazily import core attributes on first access."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path, __package__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
