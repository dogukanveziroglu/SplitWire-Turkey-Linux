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
    """Formatter that adds ANSI color codes to console log output.

    Attributes:
        COLORS: Mapping of log level names to ANSI color codes.
        RESET: ANSI reset escape sequence.
    """

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
        """Format the log record with ANSI color on levelname.

        Args:
            record: Log record to format.

        Returns:
            Formatted log string with color escapes.
        """
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
    """Configure the root 'splitwire' logger.

    Must be called once early in application startup. All modules
    using ``logging.getLogger(__name__)`` under the ``splitwire``
    namespace inherit this configuration.

    Args:
        debug: Enable DEBUG level logging (default INFO).
        log_dir: Override log directory
            (default: ~/.cache/splitwire/logs).

    Example:
        >>> setup_logging(debug=True)
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
    """Utility class for log file management operations.

    Provides helpers to read, clear, and measure log files.
    Does NOT proxy logging calls -- modules use stdlib
    ``logging.getLogger(__name__)`` directly.

    Attributes:
        log_dir: Directory containing log files.
        log_file: Path to the main log file.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        """Initialize logger utility.

        Args:
            log_dir: Override log directory
                (default: ~/.cache/splitwire/logs).
        """
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
        """Get the most recent log entries from the main log.

        Args:
            lines: Maximum number of lines to retrieve.

        Returns:
            List of log line strings (may be fewer than requested).

        Example:
            >>> logger_util = SplitWireLogger()
            >>> recent = logger_util.get_recent_logs(10)
            >>> isinstance(recent, list)
            True
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
        """Clear all log files from the log directory.

        Returns:
            True if all files removed, False on error.
        """
        try:
            for log_file in self._log_dir.glob("*.log*"):
                log_file.unlink()
            return True
        except OSError:
            return False

    def get_log_size(self) -> int:
        """Get total size of all log files in bytes.

        Returns:
            Combined size of all *.log* files in bytes.
        """
        total = 0
        for log_file in self._log_dir.glob("*.log*"):
            total += log_file.stat().st_size
        return total
