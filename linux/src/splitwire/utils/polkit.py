"""
Polkit (PolicyKit) helper module for privilege escalation.

Provides wrappers around pkexec for running commands with elevated
privileges from a GUI application.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ElevationMethod(Enum):
    """Method for privilege elevation.

    Attributes:
        PKEXEC: Polkit GUI dialog.
        SUDO: Terminal sudo.
        GKSUDO: Legacy GTK sudo dialog.
        KDESUDO: KDE sudo dialog.
        ROOT: Already running as root.
        NONE: No elevation method available.
    """

    PKEXEC = "pkexec"  # Polkit (GUI dialog)
    SUDO = "sudo"  # sudo (terminal)
    GKSUDO = "gksudo"  # Legacy GTK sudo
    KDESUDO = "kdesudo"  # KDE sudo
    ROOT = "root"  # Already root
    NONE = "none"  # No elevation available


@dataclass
class ElevationResult:
    """Result of an elevated command execution.

    Attributes:
        success: Whether the command exited with code 0.
        returncode: Process exit code.
        stdout: Captured standard output.
        stderr: Captured standard error.
        cancelled: True if user cancelled the auth dialog.
        method: Elevation method that was used.
    """

    success: bool
    returncode: int
    stdout: str
    stderr: str
    cancelled: bool = False
    method: ElevationMethod = ElevationMethod.NONE


class PolkitError(Exception):
    """Exception raised for polkit-related errors."""


class PolkitHelper:
    """Runs commands with elevated privileges via Polkit.

    Uses pkexec for GUI applications, with fallbacks to sudo,
    gksudo, and kdesudo.

    Attributes:
        ACTION_WIREGUARD: Polkit action ID for WireGuard ops.
        ACTION_ZAPRET: Polkit action ID for Zapret ops.
        ACTION_DNS: Polkit action ID for DNS ops.
        ACTION_SYSTEM: Polkit action ID for system ops.
        POLICY_PATH: Filesystem path to the polkit policy file.
        is_root: Whether the process runs as root.
        elevation_method: Detected best elevation method.
    """

    ACTION_WIREGUARD = "com.splitwire.turkey.wireguard"
    ACTION_ZAPRET = "com.splitwire.turkey.zapret"
    ACTION_DNS = "com.splitwire.turkey.dns"
    ACTION_SYSTEM = "com.splitwire.turkey.system"

    POLICY_PATH = Path("/usr/share/polkit-1/actions/com.splitwire.turkey.policy")

    # Timeout constants (seconds)
    TIMEOUT_ELEVATED_DEFAULT = 60  # run_elevated default
    TIMEOUT_WG_QUICK = 30  # wg-quick up/down
    TIMEOUT_SYSTEMCTL = 30  # systemctl action
    TIMEOUT_IPTABLES = 10  # iptables rule changes
    TIMEOUT_FILE_COPY = 10  # cp to root-owned locations
    TIMEOUT_FILE_WRITE = 30  # tee to root-owned files

    def __init__(self) -> None:
        """Initialize PolkitHelper and detect elevation method."""
        self._elevation_method: ElevationMethod | None = None
        self._is_root = os.geteuid() == 0

    @property
    def is_root(self) -> bool:
        """Check if running as root."""
        return self._is_root

    @property
    def elevation_method(self) -> ElevationMethod:
        """Get the available elevation method."""
        if self._elevation_method is None:
            self._elevation_method = self._detect_elevation_method()
        return self._elevation_method

    def _detect_elevation_method(self) -> ElevationMethod:
        """Detect the best available elevation method."""
        if self._is_root:
            logger.debug("[POLKIT] Running as root, no elevation needed")
            return ElevationMethod.ROOT

        # Check pkexec (preferred for GUI)
        if shutil.which("pkexec"):
            logger.debug("[POLKIT] Elevation method: pkexec")
            return ElevationMethod.PKEXEC

        # Check sudo
        if shutil.which("sudo"):
            logger.debug("[POLKIT] Elevation method: sudo")
            return ElevationMethod.SUDO

        # Legacy options
        if shutil.which("gksudo"):
            logger.debug("[POLKIT] Elevation method: gksudo")
            return ElevationMethod.GKSUDO

        if shutil.which("kdesudo"):
            logger.debug("[POLKIT] Elevation method: kdesudo")
            return ElevationMethod.KDESUDO

        logger.warning("[POLKIT] No elevation method available")
        return ElevationMethod.NONE

    def can_elevate(self) -> bool:
        """Check if privilege elevation is available.

        Returns:
            True if at least one elevation method is detected.
        """
        return self.elevation_method != ElevationMethod.NONE

    def is_policy_installed(self) -> bool:
        """Check if the SplitWire polkit policy file exists.

        Returns:
            True if the policy file is present on disk.
        """
        return self.POLICY_PATH.exists()

    def run_elevated(
        self,
        command: list[str],
        action_id: str | None = None,
        timeout: int = TIMEOUT_ELEVATED_DEFAULT,
        capture_output: bool = True,
    ) -> ElevationResult:
        """Run a command with elevated privileges.

        Args:
            command: Command and arguments to run.
            action_id: Polkit action ID (for pkexec).
            timeout: Command timeout in seconds.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            ElevationResult with output and status.

        Example:
            >>> helper = PolkitHelper()
            >>> result = helper.run_elevated(["whoami"])
            >>> isinstance(result, ElevationResult)
            True
        """
        method = self.elevation_method
        cmd_str = " ".join(command)
        cmd_preview = cmd_str[:80] + "..." if len(cmd_str) > 80 else cmd_str
        logger.debug(f"[POLKIT] Running elevated ({method.value}): {cmd_preview}")

        if method == ElevationMethod.ROOT:
            # Already root, run directly
            result = self._run_direct(command, timeout, capture_output)
        elif method == ElevationMethod.PKEXEC:
            result = self._run_pkexec(command, action_id, timeout, capture_output)
        elif method == ElevationMethod.SUDO:
            result = self._run_sudo(command, timeout, capture_output)
        elif method in (ElevationMethod.GKSUDO, ElevationMethod.KDESUDO):
            result = self._run_legacy_sudo(command, method, timeout, capture_output)
        else:
            logger.error("[POLKIT] No elevation method available")
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="No elevation method available",
                method=ElevationMethod.NONE,
            )

        # Log result
        if result.success:
            logger.info(f"[POLKIT] Elevation successful: {cmd_preview}")
        elif result.cancelled:
            logger.warning("[POLKIT] User cancelled elevation")
        else:
            logger.error(f"[POLKIT] Elevation failed (exit={result.returncode}): {cmd_preview}")
            if result.stderr:
                stderr_preview = (
                    result.stderr[:200] + "..." if len(result.stderr) > 200 else result.stderr
                )
                logger.error(f"[POLKIT] stderr: {stderr_preview}")

        return result

    def _run_direct(
        self, command: list[str], timeout: int, capture_output: bool
    ) -> ElevationResult:
        """Run command directly (when already root)."""
        try:
            if capture_output:
                result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                return ElevationResult(
                    success=result.returncode == 0,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    method=ElevationMethod.ROOT,
                )
            result = subprocess.run(command, timeout=timeout)
            return ElevationResult(
                success=result.returncode == 0,
                returncode=result.returncode,
                stdout="",
                stderr="",
                method=ElevationMethod.ROOT,
            )
        except subprocess.TimeoutExpired:
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Command timed out",
                method=ElevationMethod.ROOT,
            )
        except Exception as e:
            return ElevationResult(
                success=False, returncode=-1, stdout="", stderr=str(e), method=ElevationMethod.ROOT
            )

    def _run_pkexec(
        self, command: list[str], action_id: str | None, timeout: int, capture_output: bool
    ) -> ElevationResult:
        """Run command with pkexec."""
        # Build pkexec command
        pkexec_cmd = ["pkexec"]

        # Note: pkexec doesn't support --action directly for arbitrary commands
        # The action ID is determined by the policy file based on the command
        pkexec_cmd.extend(command)

        try:
            if capture_output:
                result = subprocess.run(
                    pkexec_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=self._get_pkexec_env(),
                )
            else:
                result = subprocess.run(pkexec_cmd, timeout=timeout, env=self._get_pkexec_env())
                return ElevationResult(
                    success=result.returncode == 0,
                    returncode=result.returncode,
                    stdout="",
                    stderr="",
                    method=ElevationMethod.PKEXEC,
                )

            # Check for user cancellation (pkexec returns 126 when cancelled)
            cancelled = result.returncode == 126

            return ElevationResult(
                success=result.returncode == 0,
                returncode=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                cancelled=cancelled,
                method=ElevationMethod.PKEXEC,
            )

        except subprocess.TimeoutExpired:
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Command timed out",
                method=ElevationMethod.PKEXEC,
            )
        except Exception as e:
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=str(e),
                method=ElevationMethod.PKEXEC,
            )

    def _run_sudo(self, command: list[str], timeout: int, capture_output: bool) -> ElevationResult:
        """Run command with sudo."""
        sudo_cmd = ["sudo", *command]

        try:
            if capture_output:
                result = subprocess.run(sudo_cmd, capture_output=True, text=True, timeout=timeout)
            else:
                result = subprocess.run(sudo_cmd, timeout=timeout)
                return ElevationResult(
                    success=result.returncode == 0,
                    returncode=result.returncode,
                    stdout="",
                    stderr="",
                    method=ElevationMethod.SUDO,
                )

            return ElevationResult(
                success=result.returncode == 0,
                returncode=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                method=ElevationMethod.SUDO,
            )

        except subprocess.TimeoutExpired:
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Command timed out",
                method=ElevationMethod.SUDO,
            )
        except Exception as e:
            return ElevationResult(
                success=False, returncode=-1, stdout="", stderr=str(e), method=ElevationMethod.SUDO
            )

    def _run_legacy_sudo(
        self, command: list[str], method: ElevationMethod, timeout: int, capture_output: bool
    ) -> ElevationResult:
        """Run command with gksudo or kdesudo."""
        if method == ElevationMethod.GKSUDO:
            sudo_cmd = ["gksudo", "--", *command]
        else:
            sudo_cmd = ["kdesudo", "--", *command]

        try:
            if capture_output:
                result = subprocess.run(sudo_cmd, capture_output=True, text=True, timeout=timeout)
            else:
                result = subprocess.run(sudo_cmd, timeout=timeout)
                return ElevationResult(
                    success=result.returncode == 0,
                    returncode=result.returncode,
                    stdout="",
                    stderr="",
                    method=method,
                )

            return ElevationResult(
                success=result.returncode == 0,
                returncode=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                method=method,
            )

        except subprocess.TimeoutExpired:
            return ElevationResult(
                success=False, returncode=-1, stdout="", stderr="Command timed out", method=method
            )
        except Exception as e:
            return ElevationResult(
                success=False, returncode=-1, stdout="", stderr=str(e), method=method
            )

    def _get_pkexec_env(self) -> dict:
        """Get environment variables for pkexec."""
        env = os.environ.copy()
        # pkexec needs DISPLAY for GUI dialogs
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        return env

    # Convenience methods for common operations

    def run_wg_quick(self, action: str, interface: str) -> ElevationResult:
        """Run wg-quick up/down with elevated privileges.

        Args:
            action: "up" or "down".
            interface: WireGuard interface name.

        Returns:
            ElevationResult from the wg-quick command.
        """
        return self.run_elevated(
            ["wg-quick", action, interface],
            action_id=self.ACTION_WIREGUARD,
            timeout=self.TIMEOUT_WG_QUICK,
        )

    def run_systemctl(self, action: str, service: str) -> ElevationResult:
        """Run systemctl action on a service with elevation.

        Args:
            action: systemctl verb (start, stop, restart, etc.).
            service: Unit name of the service.

        Returns:
            ElevationResult from the systemctl command.
        """
        return self.run_elevated(
            ["systemctl", action, service],
            action_id=self.ACTION_SYSTEM,
            timeout=self.TIMEOUT_SYSTEMCTL,
        )

    def run_iptables(self, args: list[str]) -> ElevationResult:
        """Run iptables command with elevated privileges.

        Args:
            args: iptables arguments (e.g. ["-A", "INPUT", ...]).

        Returns:
            ElevationResult from the iptables command.
        """
        return self.run_elevated(
            ["iptables", *args],
            action_id=self.ACTION_ZAPRET,
            timeout=self.TIMEOUT_IPTABLES,
        )

    def copy_file_as_root(self, src: str, dst: str) -> ElevationResult:
        """Copy a file to a root-owned location.

        Args:
            src: Source file path.
            dst: Destination file path.

        Returns:
            ElevationResult from the cp command.
        """
        return self.run_elevated(
            ["cp", src, dst],
            action_id=self.ACTION_SYSTEM,
            timeout=self.TIMEOUT_FILE_COPY,
        )

    def write_file_as_root(self, content: str, path: str) -> ElevationResult:
        """Write content to a root-owned file using pkexec tee.

        Args:
            content: Text content to write.
            path: Destination file path.

        Returns:
            ElevationResult from the tee command.
        """
        # Use tee to write to file
        proc = None
        try:
            proc = subprocess.Popen(
                ["pkexec", "tee", path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._get_pkexec_env(),
            )
            stdout, stderr = proc.communicate(input=content, timeout=self.TIMEOUT_FILE_WRITE)

            return ElevationResult(
                success=proc.returncode == 0,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                cancelled=proc.returncode == 126,
                method=ElevationMethod.PKEXEC,
            )
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
                proc.communicate()  # Clean up
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Command timed out",
                method=ElevationMethod.PKEXEC,
            )
        except Exception as e:
            if proc and proc.poll() is None:
                proc.kill()
            return ElevationResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=str(e),
                method=ElevationMethod.PKEXEC,
            )


# Global instance for convenience
_polkit_helper: PolkitHelper | None = None


def get_polkit_helper() -> PolkitHelper:
    """Get the global PolkitHelper singleton.

    Returns:
        The shared PolkitHelper instance.
    """
    global _polkit_helper
    if _polkit_helper is None:
        _polkit_helper = PolkitHelper()
    return _polkit_helper


def run_elevated(command: list[str], **kwargs: object) -> ElevationResult:
    """Run a command with elevated privileges.

    Args:
        command: Command and arguments to run.
        **kwargs: Passed to PolkitHelper.run_elevated().

    Returns:
        ElevationResult with output and status.
    """
    return get_polkit_helper().run_elevated(command, **kwargs)


def can_elevate() -> bool:
    """Check if privilege elevation is available.

    Returns:
        True if an elevation method is detected.
    """
    return get_polkit_helper().can_elevate()


def is_root() -> bool:
    """Check if the current process is running as root.

    Returns:
        True if effective UID is 0.
    """
    return get_polkit_helper().is_root
