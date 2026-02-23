"""
Journal log access for systemd units.

Provides methods for reading, parsing, and following journal logs.
"""

import json
import logging
import subprocess
from collections.abc import Callable

from .models import JournalEntry

logger = logging.getLogger(__name__)

# Journal query timeout (seconds)
TIMEOUT_JOURNAL_QUERY = 30


def get_logs(
    shell,
    unit_name: str,
    lines: int = 100,
    since: str | None = None,
    until: str | None = None,
    priority: int | None = None,
) -> list[str]:
    """
    Get journal logs for a unit.

    Args:
        shell: Shell executor instance
        unit_name: Name of the unit
        lines: Maximum number of lines to return
        since: Start time (e.g., '1 hour ago', '2024-01-01')
        until: End time
        priority: Maximum priority level (0-7)

    Returns:
        List of log lines
    """
    cmd = [
        "journalctl",
        "-u",
        unit_name,
        "-n",
        str(lines),
        "--no-pager",
    ]

    if since:
        cmd.extend(["--since", since])
    if until:
        cmd.extend(["--until", until])
    if priority is not None:
        cmd.extend(["-p", str(priority)])

    result = shell.run(cmd, timeout=TIMEOUT_JOURNAL_QUERY)

    if result.success:
        return result.stdout.strip().split("\n")
    return []


def get_logs_json(shell, unit_name: str, lines: int = 100) -> list[JournalEntry]:
    """
    Get journal logs as structured entries.

    Args:
        shell: Shell executor instance
        unit_name: Name of the unit
        lines: Maximum number of entries

    Returns:
        List of JournalEntry objects
    """
    result = shell.run(
        [
            "journalctl",
            "-u",
            unit_name,
            "-n",
            str(lines),
            "--no-pager",
            "-o",
            "json",
        ],
        timeout=TIMEOUT_JOURNAL_QUERY,
    )

    entries = []
    if result.success:
        for line in result.stdout.strip().split("\n"):
            entry = _parse_journal_json_line(line, unit_name)
            if entry:
                entries.append(entry)

    logger.debug(
        "[SYSTEMD] Retrieved %d journal entries for %s",
        len(entries),
        unit_name,
    )
    return entries


def _parse_journal_json_line(line: str, unit_name: str) -> JournalEntry | None:
    """Parse a single JSON journal line into a JournalEntry."""
    if not line:
        return None
    try:
        data = json.loads(line)
        return JournalEntry(
            timestamp=data.get("__REALTIME_TIMESTAMP", ""),
            unit=data.get("_SYSTEMD_UNIT", unit_name),
            priority=int(data.get("PRIORITY", 6)),
            message=data.get("MESSAGE", ""),
            pid=int(data.get("_PID", 0)) or None,
            hostname=data.get("_HOSTNAME"),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.debug("[SYSTEMD] Failed to parse journal JSON line: %s", e)
        return None


def follow_logs(unit_name: str, callback: Callable[[str], None]) -> None:
    """
    Follow journal logs in real-time (blocking).

    Args:
        unit_name: Name of the unit
        callback: Function to call with each log line
    """
    proc = subprocess.Popen(
        ["journalctl", "-u", unit_name, "-f", "--no-pager"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        for line in proc.stdout:
            callback(line.rstrip())
    except KeyboardInterrupt:
        proc.terminate()


def clear_logs(shell, _unit_name: str) -> bool:
    """Clear journal logs for a unit (requires root)."""
    result = shell.run(["sudo", "journalctl", "--rotate"], timeout=TIMEOUT_JOURNAL_QUERY)
    return result.success
