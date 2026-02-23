"""
Logging module for SplitWire Linux.

Provides centralized logging setup with file rotation and colored console output.
Logs are stored in ~/.cache/splitwire/logs/

Usage:
    # In __main__.py (once, before app startup):
    from splitwire.core.logger import setup_logging
    setup_logging(debug=args.debug)

    # In every other module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("message %s", value)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import ClassVar

# Log formats
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Rotation settings
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 3

APP_NAME = "splitwire"


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""

    # ANSI color codes
    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with color codes on levelname."""
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        result = super().format(record)

        # Restore original levelname
        record.levelname = levelname
        return result


def setup_logging(
    debug: bool = False,
    log_dir: Path | None = None,
) -> None:
    """
    Configure the root 'splitwire' logger with file and console handlers.

    Must be called once early in application startup (after argument parsing,
    before any other module work). All modules using ``logging.getLogger(__name__)``
    under the ``splitwire`` namespace will inherit this configuration.

    Args:
        debug: Enable DEBUG level logging (default: INFO)
        log_dir: Override log directory (default: ~/.cache/splitwire/logs)
    """
    if log_dir is None:
        log_dir = Path.home() / ".cache" / APP_NAME / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger(APP_NAME)
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear any existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()

    # File handler -- rotates at 5 MB, keeps 3 backups
    file_handler = RotatingFileHandler(
        log_dir / "splitwire.log",
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # Console handler -- colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(ColoredFormatter(CONSOLE_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)


class SplitWireLogger:
    """
    Utility class for log management operations.

    Provides helpers to read, clear, and measure log files.
    Does NOT proxy logging calls -- modules use stdlib
    ``logging.getLogger(__name__)`` directly.

    Args:
        log_dir: Log directory (default: ~/.cache/splitwire/logs)
    """

    def __init__(self, log_dir: Path | None = None):
        if log_dir is None:
            log_dir = Path.home() / ".cache" / APP_NAME / "logs"
        self._log_dir = log_dir

    @property
    def log_dir(self) -> Path:
        """Get log directory path."""
        return self._log_dir

    @property
    def log_file(self) -> Path:
        """Get main log file path."""
        return self._log_dir / "splitwire.log"

    def get_recent_logs(self, lines: int = 100) -> list[str]:
        """
        Get recent log entries.

        Args:
            lines: Number of lines to retrieve

        Returns:
            List of log lines
        """
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, encoding="utf-8") as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except OSError:
            return []

    def clear_logs(self) -> bool:
        """
        Clear all log files.

        Returns:
            True if successful
        """
        try:
            for log_file in self._log_dir.glob("*.log*"):
                log_file.unlink()
            return True
        except OSError:
            return False

    def get_log_size(self) -> int:
        """
        Get total size of log files in bytes.

        Returns:
            Total size in bytes
        """
        total = 0
        for log_file in self._log_dir.glob("*.log*"):
            total += log_file.stat().st_size
        return total
