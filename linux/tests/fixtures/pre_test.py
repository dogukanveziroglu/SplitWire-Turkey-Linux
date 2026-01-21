"""
Pre-test checklist and baseline capture for SplitWire-Turkey integration tests.

This module provides utilities for capturing the system state before
running risky network tests, enabling proper restoration on failure.
"""

import subprocess
import socket
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class NetworkBaseline:
    """Captured network baseline state."""
    timestamp: datetime
    interfaces: List[str]
    routing_table: str
    iptables_filter: str
    iptables_nat: str
    iptables_mangle: str
    dns_servers: List[str]
    resolv_conf: str
    running_processes: List[str]
    connectivity_hosts: Dict[str, bool]
    wireguard_interfaces: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "interfaces": self.interfaces,
            "routing_table": self.routing_table,
            "iptables_filter": self.iptables_filter,
            "iptables_nat": self.iptables_nat,
            "iptables_mangle": self.iptables_mangle,
            "dns_servers": self.dns_servers,
            "resolv_conf": self.resolv_conf,
            "running_processes": self.running_processes,
            "connectivity_hosts": self.connectivity_hosts,
            "wireguard_interfaces": self.wireguard_interfaces,
        }

    def save(self, path: Path) -> None:
        """Save baseline to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "NetworkBaseline":
        """Load baseline from JSON file."""
        data = json.loads(path.read_text())
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class PreTestChecklist:
    """
    Pre-test checklist that verifies system state and captures baseline.

    This class should be used before running any risky network tests to:
    1. Verify the system is in a clean state
    2. Capture baseline state for later comparison
    3. Ensure no conflicting services are running
    """

    # Processes that indicate previous test failure
    CONFLICT_PROCESSES = ["nfqws", "tpws", "ciadpi", "goodbyedpi"]

    # Expected iptables state (should be empty in these chains)
    EXPECTED_EMPTY_CHAINS = [
        ("mangle", "POSTROUTING"),
        ("nat", "OUTPUT"),
    ]

    def __init__(self):
        self.baseline: Optional[NetworkBaseline] = None
        self.issues: List[str] = []

    def run_checks(self) -> bool:
        """
        Run all pre-test checks.

        Returns:
            True if all checks pass, False otherwise
        """
        self.issues = []

        # Check for root privileges
        self._check_root()

        # Check connectivity
        self._check_connectivity()

        # Check for conflicting processes
        self._check_processes()

        # Check iptables state
        self._check_iptables()

        # Check WireGuard state
        self._check_wireguard()

        # Check DNS state
        self._check_dns()

        return len(self.issues) == 0

    def capture_baseline(self) -> NetworkBaseline:
        """
        Capture current network state as baseline.

        Returns:
            NetworkBaseline with current state
        """
        self.baseline = NetworkBaseline(
            timestamp=datetime.now(),
            interfaces=self._get_interfaces(),
            routing_table=self._get_routing_table(),
            iptables_filter=self._get_iptables("filter"),
            iptables_nat=self._get_iptables("nat"),
            iptables_mangle=self._get_iptables("mangle"),
            dns_servers=self._get_dns_servers(),
            resolv_conf=self._get_resolv_conf(),
            running_processes=self._get_running_processes(),
            connectivity_hosts=self._check_hosts_connectivity(),
            wireguard_interfaces=self._get_wireguard_interfaces(),
        )
        return self.baseline

    def get_issues(self) -> List[str]:
        """Get list of issues found during checks."""
        return self.issues.copy()

    def _check_root(self) -> None:
        """Check for root privileges."""
        import os
        if os.geteuid() != 0:
            self.issues.append("Tests require root privileges (run with sudo)")

    def _check_connectivity(self) -> None:
        """Check basic network connectivity."""
        hosts = [("8.8.8.8", 53), ("1.1.1.1", 53)]
        connected = False

        for host, port in hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((host, port))
                sock.close()
                connected = True
                break
            except (socket.timeout, socket.error):
                continue

        if not connected:
            self.issues.append(
                "No network connectivity - cannot proceed with tests"
            )

    def _check_processes(self) -> None:
        """Check for conflicting processes."""
        for process in self.CONFLICT_PROCESSES:
            result = subprocess.run(
                ["pgrep", "-x", process],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.issues.append(
                    f"Conflicting process '{process}' is running. "
                    f"Run emergency_restore.sh first."
                )

    def _check_iptables(self) -> None:
        """Check iptables for leftover rules."""
        for table, chain in self.EXPECTED_EMPTY_CHAINS:
            result = subprocess.run(
                ["sudo", "iptables", "-t", table, "-L", chain, "-n"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Check if chain has non-default rules
                lines = result.stdout.strip().split("\n")
                # First 2 lines are headers, rest are rules
                if len(lines) > 2:
                    rule_count = len(lines) - 2
                    self.issues.append(
                        f"iptables {table}/{chain} has {rule_count} rules. "
                        f"Run emergency_restore.sh first."
                    )

    def _check_wireguard(self) -> None:
        """Check for existing WireGuard interfaces."""
        result = subprocess.run(
            ["ip", "link", "show", "splitwire"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            self.issues.append(
                "WireGuard interface 'splitwire' exists. "
                "Run emergency_restore.sh first."
            )

    def _check_dns(self) -> None:
        """Check for SplitWire DNS configuration."""
        dns_config = Path("/etc/systemd/resolved.conf.d/splitwire.conf")
        if dns_config.exists():
            self.issues.append(
                "SplitWire DNS config exists. Run emergency_restore.sh first."
            )

    def _get_interfaces(self) -> List[str]:
        """Get list of network interfaces."""
        result = subprocess.run(
            ["ip", "-o", "link", "show"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return []

        interfaces = []
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    interfaces.append(parts[1].strip().split("@")[0])
        return interfaces

    def _get_routing_table(self) -> str:
        """Get current routing table."""
        result = subprocess.run(
            ["ip", "route", "show"],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else ""

    def _get_iptables(self, table: str) -> str:
        """Get iptables rules for specified table."""
        result = subprocess.run(
            ["sudo", "iptables", "-t", table, "-L", "-n", "-v"],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else ""

    def _get_dns_servers(self) -> List[str]:
        """Get current DNS servers."""
        servers = []

        # Try resolvectl first
        result = subprocess.run(
            ["resolvectl", "status"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            import re
            for line in result.stdout.split("\n"):
                if "DNS Servers:" in line or "Current DNS Server:" in line:
                    ips = re.findall(r'\d+\.\d+\.\d+\.\d+', line)
                    servers.extend(ips)

        # Fallback to resolv.conf
        if not servers:
            try:
                content = Path("/etc/resolv.conf").read_text()
                for line in content.split("\n"):
                    if line.startswith("nameserver"):
                        servers.append(line.split()[1])
            except Exception:
                pass

        return list(dict.fromkeys(servers))

    def _get_resolv_conf(self) -> str:
        """Get contents of resolv.conf."""
        try:
            return Path("/etc/resolv.conf").read_text()
        except Exception:
            return ""

    def _get_running_processes(self) -> List[str]:
        """Get list of relevant running processes."""
        processes = []
        check_list = self.CONFLICT_PROCESSES + ["wireguard", "wg-quick"]

        for proc in check_list:
            result = subprocess.run(
                ["pgrep", "-a", proc],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                processes.append(result.stdout.strip())

        return processes

    def _check_hosts_connectivity(self) -> Dict[str, bool]:
        """Check connectivity to multiple hosts."""
        hosts = {
            "8.8.8.8": False,
            "1.1.1.1": False,
            "9.9.9.9": False,
        }

        for host in hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((host, 53))
                sock.close()
                hosts[host] = True
            except (socket.timeout, socket.error):
                pass

        return hosts

    def _get_wireguard_interfaces(self) -> List[str]:
        """Get list of WireGuard interfaces."""
        result = subprocess.run(
            ["wg", "show", "interfaces"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split()
        return []


def verify_baseline(current: NetworkBaseline, original: NetworkBaseline) -> List[str]:
    """
    Compare current state to original baseline.

    Args:
        current: Current network state
        original: Original baseline state

    Returns:
        List of differences found
    """
    differences = []

    # Check interfaces
    new_interfaces = set(current.interfaces) - set(original.interfaces)
    if new_interfaces:
        differences.append(f"New interfaces: {new_interfaces}")

    removed_interfaces = set(original.interfaces) - set(current.interfaces)
    # Filter out loopback which might appear differently
    removed_interfaces = {i for i in removed_interfaces if i != "lo"}
    if removed_interfaces:
        differences.append(f"Missing interfaces: {removed_interfaces}")

    # Check WireGuard interfaces
    if current.wireguard_interfaces != original.wireguard_interfaces:
        differences.append(
            f"WireGuard interfaces changed: "
            f"{original.wireguard_interfaces} -> {current.wireguard_interfaces}"
        )

    # Check DNS
    if set(current.dns_servers) != set(original.dns_servers):
        differences.append(
            f"DNS servers changed: {original.dns_servers} -> {current.dns_servers}"
        )

    # Check connectivity
    for host, was_connected in original.connectivity_hosts.items():
        is_connected = current.connectivity_hosts.get(host, False)
        if was_connected and not is_connected:
            differences.append(f"Lost connectivity to {host}")

    # Check running processes
    new_procs = set(current.running_processes) - set(original.running_processes)
    if new_procs:
        differences.append(f"New bypass processes: {new_procs}")

    return differences
