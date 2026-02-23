"""
Core modules for SplitWire-Turkey Linux.

This package contains:
- config: Configuration management (XDG paths, JSON storage)
- language: Localization and translation
- logger: Logging system
- shell: Shell command execution
- backup: Backup and rollback system
"""

from .backup import (
    BackupError,
    BackupManager,
    BackupMetadata,
    BackupType,
    SnapshotManager,
    SystemSnapshot,
    create_backup,
    get_backup_manager,
    get_snapshot_manager,
    list_backups,
    restore_backup,
)
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
    setup_logging,
)
from .shell import (
    CommandResult,
    CommandStatus,
    ShellExecutor,
    command_exists,
    get_shell,
    run,
    run_async,
)

__all__ = [
    "AppConfig",
    "BackupError",
    "BackupManager",
    "BackupMetadata",
    "BackupType",
    "ByeDPIConfig",
    "ColoredFormatter",
    "CommandResult",
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
