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
    # config
    "ConfigManager",
    "AppConfig",
    "DNSConfig",
    "WireGuardConfig",
    "ZapretConfig",
    "ByeDPIConfig",
    "Theme",
    "Language",
    "get_config_manager",
    "get_config",
    "save_config",
    # language
    "LanguageManager",
    "LanguageError",
    "get_language_manager",
    "init_language_manager",
    "get_text",
    "format_text",
    "set_language",
    "get_current_language",
    # logger
    "SplitWireLogger",
    "ColoredFormatter",
    "setup_logging",
    # shell
    "ShellExecutor",
    "CommandResult",
    "CommandStatus",
    "get_shell",
    "run",
    "run_async",
    "command_exists",
    # backup
    "BackupManager",
    "BackupMetadata",
    "BackupType",
    "BackupError",
    "SnapshotManager",
    "SystemSnapshot",
    "get_backup_manager",
    "get_snapshot_manager",
    "create_backup",
    "restore_backup",
    "list_backups",
]
