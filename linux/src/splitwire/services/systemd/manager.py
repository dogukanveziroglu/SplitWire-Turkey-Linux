"""
SystemdManager - comprehensive systemd integration for SplitWire.

Provides unit file management, service lifecycle, status monitoring,
and journal log access.
"""

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from splitwire.core import get_shell

from . import journal
from .constants import SPLITWIRE_SERVICES, SYSTEM_UNIT_DIR
from .models import (
    JournalEntry,
    SystemdActiveState,
    SystemdEnabledState,
    SystemdUnitStatus,
    SystemdUnitType,
)

# Mapping from systemctl show property names to SystemdUnitStatus fields.
# Values are (attr_name, converter) tuples.
_SHOW_PROPERTY_MAP: dict[str, tuple[str, type]] = {
    "Description": ("description", str),
    "LoadState": ("load_state", str),
    "SubState": ("sub_state", str),
    "MainPID": ("main_pid", int),
    "MemoryCurrent": ("memory_current", int),
    "TasksCurrent": ("tasks_current", int),
    "CPUUsageNSec": ("cpu_usage_nsec", int),
    "InvocationID": ("invocation_id", str),
    "ActiveEnterTimestamp": ("active_enter_timestamp", str),
    "InactiveEnterTimestamp": ("inactive_enter_timestamp", str),
}


class SystemdManager:
    """
    Manager for systemd services.

    Provides comprehensive systemd integration including:
    - Unit file management (install, remove, reload)
    - Service lifecycle (start, stop, restart, reload)
    - Status monitoring
    - Journal log access
    """

    # Timeout constants (seconds)
    TIMEOUT_UNIT_ACTION = 60  # start/stop/restart
    TIMEOUT_UNIT_QUICK = 30  # enable/disable/reload/mask/daemon-reload/cp/rm
    TIMEOUT_UNIT_QUERY = 10  # is-active/is-enabled/is-failed/show/chmod

    # System paths
    SYSTEM_UNIT_DIR = SYSTEM_UNIT_DIR
    USER_UNIT_DIR = Path.home() / ".config/systemd/user"

    # SplitWire service unit names
    SPLITWIRE_SERVICES: ClassVar[dict[str, str]] = SPLITWIRE_SERVICES

    def __init__(self):
        """Initialize systemd manager."""
        self._logger = logging.getLogger(__name__)
        self._shell = get_shell()
        self._unit_files_dir = Path(__file__).parent.parent.parent.parent / "systemd"

    def install_unit(
        self,
        unit_name: str,
        content: str | None = None,
        enable: bool = True,
        start: bool = False,
    ) -> bool:
        """
        Install a systemd unit file.

        Args:
            unit_name: Name of the unit (e.g., 'splitwire-wg.service')
            content: Unit file content (if None, reads from bundled files)
            enable: Whether to enable the unit
            start: Whether to start the unit after installation

        Returns:
            True if installation successful
        """
        self._logger.info(f"Installing systemd unit: {unit_name}")

        if content is None:
            content = self._get_bundled_unit_content(unit_name)
            if content is None:
                self._logger.error(f"No bundled unit file found for: {unit_name}")
                return False

        return self._write_and_activate_unit(unit_name, content, enable, start)

    def _write_and_activate_unit(
        self,
        unit_name: str,
        content: str,
        enable: bool,
        start: bool,
    ) -> bool:
        """Write unit file to system directory and optionally activate."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as f:
                f.write(content)
                temp_path = f.name

            target_path = self.SYSTEM_UNIT_DIR / unit_name
            result = self._shell.run(
                ["sudo", "cp", temp_path, str(target_path)], timeout=self.TIMEOUT_UNIT_QUICK
            )
            os.unlink(temp_path)

            if not result.success:
                self._logger.error(f"Failed to copy unit file: {result.stderr}")
                return False

            self._shell.run(
                ["sudo", "chmod", "644", str(target_path)], timeout=self.TIMEOUT_UNIT_QUERY
            )
            self.daemon_reload()

            if enable:
                self.enable(unit_name)
            if start:
                self.start(unit_name)

            self._logger.info(f"Successfully installed: {unit_name}")
            return True

        except Exception as e:
            self._logger.error(f"Error installing unit: {e}")
            return False

    def remove_unit(self, unit_name: str, stop_first: bool = True) -> bool:
        """
        Remove a systemd unit file.

        Args:
            unit_name: Name of the unit to remove
            stop_first: Whether to stop the service first

        Returns:
            True if removal successful
        """
        self._logger.info(f"Removing systemd unit: {unit_name}")

        if stop_first:
            self.stop(unit_name)
            self.disable(unit_name)

        target_path = self.SYSTEM_UNIT_DIR / unit_name
        if target_path.exists():
            result = self._shell.run(
                ["sudo", "rm", "-f", str(target_path)], timeout=self.TIMEOUT_UNIT_QUICK
            )
            if not result.success:
                self._logger.error(f"Failed to remove unit file: {result.stderr}")
                return False

        self.daemon_reload()
        self._shell.run(
            ["sudo", "systemctl", "reset-failed", unit_name], timeout=self.TIMEOUT_UNIT_QUERY
        )

        self._logger.info(f"Successfully removed: {unit_name}")
        return True

    def unit_exists(self, unit_name: str) -> bool:
        """Check if a unit file exists."""
        target_path = self.SYSTEM_UNIT_DIR / unit_name
        return target_path.exists()

    def daemon_reload(self) -> bool:
        """Reload systemd daemon to pick up unit file changes."""
        self._logger.debug("[SYSTEMD] Running daemon-reload...")
        result = self._shell.run(
            ["sudo", "systemctl", "daemon-reload"], timeout=self.TIMEOUT_UNIT_QUICK
        )
        if result.success:
            self._logger.debug("[SYSTEMD] daemon-reload completed successfully")
        else:
            self._logger.error(f"[SYSTEMD] daemon-reload failed: {result.stderr}")
        return result.success

    def _get_bundled_unit_content(self, unit_name: str) -> str | None:
        """Get content of bundled unit file."""
        unit_path = self._unit_files_dir / unit_name
        if unit_path.exists():
            return unit_path.read_text()
        return None

    def start(self, unit_name: str) -> bool:
        """Start a systemd unit."""
        self._logger.info(f"Starting: {unit_name}")
        result = self._shell.run(
            ["sudo", "systemctl", "start", unit_name], timeout=self.TIMEOUT_UNIT_ACTION
        )
        if not result.success:
            self._logger.error(f"Failed to start {unit_name}: {result.stderr}")
        return result.success

    def stop(self, unit_name: str) -> bool:
        """Stop a systemd unit."""
        self._logger.info(f"Stopping: {unit_name}")
        result = self._shell.run(
            ["sudo", "systemctl", "stop", unit_name], timeout=self.TIMEOUT_UNIT_ACTION
        )
        if not result.success and "not loaded" not in result.stderr.lower():
            self._logger.error(f"Failed to stop {unit_name}: {result.stderr}")
        return result.success

    def restart(self, unit_name: str) -> bool:
        """Restart a systemd unit."""
        self._logger.info(f"Restarting: {unit_name}")
        result = self._shell.run(
            ["sudo", "systemctl", "restart", unit_name], timeout=self.TIMEOUT_UNIT_ACTION
        )
        if not result.success:
            self._logger.error(f"Failed to restart {unit_name}: {result.stderr}")
        return result.success

    def reload(self, unit_name: str) -> bool:
        """Reload a systemd unit (send SIGHUP)."""
        self._logger.info(f"Reloading: {unit_name}")
        result = self._shell.run(
            ["sudo", "systemctl", "reload", unit_name], timeout=self.TIMEOUT_UNIT_QUICK
        )
        if not result.success:
            self._logger.error(f"Failed to reload {unit_name}: {result.stderr}")
        return result.success

    def enable(self, unit_name: str) -> bool:
        """Enable a systemd unit (start on boot)."""
        self._logger.info(f"Enabling: {unit_name}")
        result = self._shell.run(
            ["sudo", "systemctl", "enable", unit_name], timeout=self.TIMEOUT_UNIT_QUICK
        )
        if not result.success:
            self._logger.error(f"Failed to enable {unit_name}: {result.stderr}")
        return result.success

    def disable(self, unit_name: str) -> bool:
        """Disable a systemd unit (don't start on boot)."""
        self._logger.info(f"Disabling: {unit_name}")
        result = self._shell.run(
            ["sudo", "systemctl", "disable", unit_name], timeout=self.TIMEOUT_UNIT_QUICK
        )
        if not result.success and "does not exist" not in result.stderr.lower():
            self._logger.error(f"Failed to disable {unit_name}: {result.stderr}")
        return result.success

    def mask(self, unit_name: str) -> bool:
        """Mask a systemd unit (prevent starting)."""
        result = self._shell.run(
            ["sudo", "systemctl", "mask", unit_name], timeout=self.TIMEOUT_UNIT_QUICK
        )
        return result.success

    def unmask(self, unit_name: str) -> bool:
        """Unmask a systemd unit."""
        result = self._shell.run(
            ["sudo", "systemctl", "unmask", unit_name], timeout=self.TIMEOUT_UNIT_QUICK
        )
        return result.success

    def get_status(self, unit_name: str) -> SystemdUnitStatus:
        """
        Get detailed status of a systemd unit.

        Args:
            unit_name: Name of the unit

        Returns:
            SystemdUnitStatus with current state
        """
        unit_type = self._determine_unit_type(unit_name)
        active_state = self._get_active_state(unit_name)
        enabled_state = self._get_enabled_state(unit_name)

        status = SystemdUnitStatus(
            name=unit_name,
            unit_type=unit_type,
            active_state=active_state,
            enabled_state=enabled_state,
        )

        self._populate_show_properties(unit_name, status)
        return status

    @staticmethod
    def _determine_unit_type(unit_name: str) -> SystemdUnitType:
        """Determine systemd unit type from its name suffix."""
        if unit_name.endswith(".timer"):
            return SystemdUnitType.TIMER
        if unit_name.endswith(".socket"):
            return SystemdUnitType.SOCKET
        if unit_name.endswith(".path"):
            return SystemdUnitType.PATH
        return SystemdUnitType.SERVICE

    def _get_active_state(self, unit_name: str) -> SystemdActiveState:
        """Query systemctl for the active state of a unit."""
        result = self._shell.run(
            ["systemctl", "is-active", unit_name], timeout=self.TIMEOUT_UNIT_QUERY
        )
        active_str = result.stdout.strip().lower()
        try:
            return SystemdActiveState(active_str)
        except ValueError:
            return SystemdActiveState.UNKNOWN

    def _get_enabled_state(self, unit_name: str) -> SystemdEnabledState:
        """Query systemctl for the enabled state of a unit."""
        result = self._shell.run(
            ["systemctl", "is-enabled", unit_name], timeout=self.TIMEOUT_UNIT_QUERY
        )
        enabled_str = result.stdout.strip().lower()
        try:
            return SystemdEnabledState(enabled_str)
        except ValueError:
            return SystemdEnabledState.UNKNOWN

    def _populate_show_properties(self, unit_name: str, status: SystemdUnitStatus) -> None:
        """Populate status from systemctl show properties."""
        show_result = self._shell.run(
            [
                "systemctl",
                "show",
                unit_name,
                "--property=Description,LoadState,SubState,MainPID,"
                "MemoryCurrent,TasksCurrent,CPUUsageNSec,InvocationID,"
                "ActiveEnterTimestamp,InactiveEnterTimestamp",
            ],
            timeout=self.TIMEOUT_UNIT_QUERY,
        )
        if show_result.success:
            _parse_show_output(show_result.stdout, status)

    def is_active(self, unit_name: str) -> bool:
        """Check if a unit is active (running)."""
        result = self._shell.run(
            ["systemctl", "is-active", "--quiet", unit_name], timeout=self.TIMEOUT_UNIT_QUERY
        )
        return result.returncode == 0

    def is_enabled(self, unit_name: str) -> bool:
        """Check if a unit is enabled."""
        result = self._shell.run(
            ["systemctl", "is-enabled", "--quiet", unit_name], timeout=self.TIMEOUT_UNIT_QUERY
        )
        return result.returncode == 0

    def is_failed(self, unit_name: str) -> bool:
        """Check if a unit is in failed state."""
        result = self._shell.run(
            ["systemctl", "is-failed", "--quiet", unit_name], timeout=self.TIMEOUT_UNIT_QUERY
        )
        return result.returncode == 0

    def get_logs(
        self,
        unit_name: str,
        lines: int = 100,
        since: str | None = None,
        until: str | None = None,
        priority: int | None = None,
    ) -> list[str]:
        """Get journal logs for a unit."""
        return journal.get_logs(self._shell, unit_name, lines, since, until, priority)

    def get_logs_json(self, unit_name: str, lines: int = 100) -> list[JournalEntry]:
        """Get journal logs as structured entries."""
        return journal.get_logs_json(self._shell, unit_name, lines)

    def follow_logs(self, unit_name: str, callback: Callable[[str], None]) -> None:
        """Follow journal logs in real-time (blocking)."""
        journal.follow_logs(unit_name, callback)

    def clear_logs(self, unit_name: str) -> bool:
        """Clear journal logs for a unit (requires root)."""
        return journal.clear_logs(self._shell, unit_name)

    def get_splitwire_services_status(
        self,
    ) -> dict[str, SystemdUnitStatus]:
        """Get status of all SplitWire services."""
        self._logger.debug("[SYSTEMD] Getting status of all SplitWire services...")
        status_dict = {}
        for key, unit_name in self.SPLITWIRE_SERVICES.items():
            status_dict[key] = self.get_status(unit_name)
            unit_status = status_dict[key]
            self._logger.debug(
                "[SYSTEMD] %s: active=%s, enabled=%s",
                key,
                unit_status.active_state.value,
                unit_status.enabled_state.value,
            )
        return status_dict

    def install_splitwire_service(self, service_key: str, config: dict | None = None) -> bool:
        """
        Install a SplitWire service.

        Args:
            service_key: Key from SPLITWIRE_SERVICES
            config: Optional configuration to substitute in unit file

        Returns:
            True if successful
        """
        unit_name = self.SPLITWIRE_SERVICES.get(service_key)
        if not unit_name:
            self._logger.error(f"Unknown service key: {service_key}")
            return False
        return self.install_unit(unit_name, enable=True)

    def remove_splitwire_service(self, service_key: str) -> bool:
        """Remove a SplitWire service."""
        unit_name = self.SPLITWIRE_SERVICES.get(service_key)
        if not unit_name:
            return False
        return self.remove_unit(unit_name)

    def stop_all_splitwire_services(self) -> bool:
        """Stop all SplitWire services."""
        success = True
        for unit_name in self.SPLITWIRE_SERVICES.values():
            if self.is_active(unit_name) and not self.stop(unit_name):
                success = False
        return success

    def remove_all_splitwire_services(self) -> bool:
        """Remove all SplitWire services."""
        success = True
        for unit_name in self.SPLITWIRE_SERVICES.values():
            if self.unit_exists(unit_name) and not self.remove_unit(unit_name):
                success = False
        return success


def _parse_show_output(output: str, status: SystemdUnitStatus) -> None:
    """Parse key=value output from systemctl show into status fields."""
    for line in output.strip().split("\n"):
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        mapping = _SHOW_PROPERTY_MAP.get(key)
        if mapping is None:
            continue
        attr_name, converter = mapping
        if converter is int:
            if value.isdigit():
                setattr(status, attr_name, int(value))
        elif value:
            setattr(status, attr_name, value)
