"""
Post-test recovery and verification for SplitWire-Turkey integration tests.

This module provides utilities for verifying system state after tests
and performing recovery operations if needed.
"""

import subprocess
import socket
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

from .pre_test import NetworkBaseline, PreTestChecklist, verify_baseline


class RecoveryStatus(Enum):
    """Status of recovery operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_NEEDED = "not_needed"


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    status: RecoveryStatus
    connectivity_restored: bool
    differences_found: List[str]
    actions_taken: List[str]
    errors: List[str]


class PostTestRecovery:
    """
    Post-test recovery utility that verifies state and restores if needed.

    This class should be used after running network tests to:
    1. Verify the system is back to baseline state
    2. Perform cleanup if needed
    3. Report any issues found
    """

    def __init__(self, baseline: Optional[NetworkBaseline] = None):
        self.baseline = baseline
        self._checklist = PreTestChecklist()

    def verify_and_recover(self, force_cleanup: bool = False) -> RecoveryResult:
        """
        Verify system state and recover if needed.

        Args:
            force_cleanup: Always perform cleanup even if state looks good

        Returns:
            RecoveryResult with details
        """
        actions = []
        errors = []

        # First check connectivity
        connectivity = self._check_connectivity()

        # Capture current state
        current_state = self._checklist.capture_baseline()

        # Compare to baseline if available
        differences = []
        if self.baseline:
            differences = verify_baseline(current_state, self.baseline)

        # Determine if recovery is needed
        needs_recovery = (
            force_cleanup or
            not connectivity or
            len(differences) > 0 or
            len(self._checklist.get_issues()) > 0
        )

        if not needs_recovery:
            return RecoveryResult(
                status=RecoveryStatus.NOT_NEEDED,
                connectivity_restored=True,
                differences_found=[],
                actions_taken=[],
                errors=[]
            )

        # Perform recovery
        if self._cleanup_processes():
            actions.append("Killed bypass processes")

        if self._cleanup_iptables():
            actions.append("Cleaned iptables rules")

        if self._cleanup_wireguard():
            actions.append("Stopped WireGuard")

        if self._cleanup_dns():
            actions.append("Restored DNS settings")

        # Wait for network to stabilize
        time.sleep(2)

        # Verify recovery
        final_connectivity = self._check_connectivity()

        if final_connectivity:
            return RecoveryResult(
                status=RecoveryStatus.SUCCESS,
                connectivity_restored=True,
                differences_found=differences,
                actions_taken=actions,
                errors=errors
            )
        else:
            errors.append("Connectivity not restored after cleanup")
            return RecoveryResult(
                status=RecoveryStatus.FAILED,
                connectivity_restored=False,
                differences_found=differences,
                actions_taken=actions,
                errors=errors
            )

    def verify_only(self) -> Dict[str, bool]:
        """
        Verify system state without performing recovery.

        Returns:
            Dictionary with verification results
        """
        return {
            "connectivity": self._check_connectivity(),
            "no_bypass_processes": self._verify_no_bypass_processes(),
            "iptables_clean": self._verify_iptables_clean(),
            "wireguard_stopped": self._verify_wireguard_stopped(),
            "dns_restored": self._verify_dns_restored(),
        }

    def _check_connectivity(self) -> bool:
        """Check network connectivity."""
        hosts = [("8.8.8.8", 53), ("1.1.1.1", 53)]

        for host, port in hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((host, port))
                sock.close()
                return True
            except (socket.timeout, socket.error):
                continue

        return False

    def _verify_no_bypass_processes(self) -> bool:
        """Verify no bypass processes are running."""
        processes = ["nfqws", "tpws", "ciadpi"]

        for proc in processes:
            result = subprocess.run(
                ["pgrep", "-x", proc],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return False

        return True

    def _verify_iptables_clean(self) -> bool:
        """Verify iptables has no SplitWire rules."""
        # Check mangle POSTROUTING for NFQUEUE
        result = subprocess.run(
            ["sudo", "iptables", "-t", "mangle", "-L", "POSTROUTING", "-n"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            if "NFQUEUE" in result.stdout:
                return False

        # Check nat OUTPUT for REDIRECT
        result = subprocess.run(
            ["sudo", "iptables", "-t", "nat", "-L", "OUTPUT", "-n"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            if "REDIRECT" in result.stdout:
                return False

        return True

    def _verify_wireguard_stopped(self) -> bool:
        """Verify WireGuard interface is down."""
        result = subprocess.run(
            ["ip", "link", "show", "splitwire"],
            capture_output=True,
            text=True
        )
        return result.returncode != 0

    def _verify_dns_restored(self) -> bool:
        """Verify DNS configuration is restored."""
        config_path = "/etc/systemd/resolved.conf.d/splitwire.conf"
        try:
            from pathlib import Path
            return not Path(config_path).exists()
        except Exception:
            return True

    def _cleanup_processes(self) -> bool:
        """Kill bypass processes."""
        processes = ["nfqws", "tpws", "ciadpi"]
        killed_any = False

        for proc in processes:
            result = subprocess.run(
                ["sudo", "pkill", "-9", proc],
                capture_output=True
            )
            if result.returncode == 0:
                killed_any = True

        return killed_any

    def _cleanup_iptables(self) -> bool:
        """Clean up iptables rules."""
        cleaned = False

        # Flush mangle POSTROUTING
        result = subprocess.run(
            ["sudo", "iptables", "-t", "mangle", "-F", "POSTROUTING"],
            capture_output=True
        )
        if result.returncode == 0:
            cleaned = True

        # Flush nat OUTPUT
        result = subprocess.run(
            ["sudo", "iptables", "-t", "nat", "-F", "OUTPUT"],
            capture_output=True
        )
        if result.returncode == 0:
            cleaned = True

        return cleaned

    def _cleanup_wireguard(self) -> bool:
        """Stop WireGuard interface."""
        # Try wg-quick down
        result = subprocess.run(
            ["sudo", "wg-quick", "down", "splitwire"],
            capture_output=True
        )
        if result.returncode == 0:
            return True

        # Try ip link delete
        result = subprocess.run(
            ["sudo", "ip", "link", "delete", "splitwire"],
            capture_output=True
        )

        return result.returncode == 0

    def _cleanup_dns(self) -> bool:
        """Restore DNS settings."""
        from pathlib import Path

        config_path = Path("/etc/systemd/resolved.conf.d/splitwire.conf")
        cleaned = False

        if config_path.exists():
            result = subprocess.run(
                ["sudo", "rm", "-f", str(config_path)],
                capture_output=True
            )
            if result.returncode == 0:
                cleaned = True

        # Restart systemd-resolved
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "systemd-resolved"],
            capture_output=True
        )

        return cleaned or result.returncode == 0


def assert_clean_state() -> None:
    """
    Assert that the system is in a clean state.

    Raises:
        AssertionError: If system is not clean
    """
    recovery = PostTestRecovery()
    results = recovery.verify_only()

    failures = [key for key, value in results.items() if not value]
    if failures:
        raise AssertionError(
            f"System not in clean state. Failed checks: {failures}"
        )


def assert_connectivity() -> None:
    """
    Assert that network connectivity is available.

    Raises:
        AssertionError: If no connectivity
    """
    recovery = PostTestRecovery()
    if not recovery._check_connectivity():
        raise AssertionError("Network connectivity not available")


def ensure_clean_state() -> RecoveryResult:
    """
    Ensure system is in clean state, performing cleanup if needed.

    Returns:
        RecoveryResult with details
    """
    recovery = PostTestRecovery()
    return recovery.verify_and_recover(force_cleanup=False)
