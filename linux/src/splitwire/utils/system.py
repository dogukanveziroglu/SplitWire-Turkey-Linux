"""
System detection and compatibility checking module.

Detects Ubuntu version, systemd, firewall backend, WireGuard support,
and other system capabilities needed for SplitWire-Turkey.
"""

import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class FirewallBackend(Enum):
    """Detected firewall backend on the system.

    Attributes:
        IPTABLES: Legacy iptables.
        NFTABLES: nftables (modern replacement).
        FIREWALLD: firewalld service.
        UNKNOWN: Could not be determined.
    """

    IPTABLES = "iptables"
    NFTABLES = "nftables"
    FIREWALLD = "firewalld"
    UNKNOWN = "unknown"


class InitSystem(Enum):
    """Detected init system.

    Attributes:
        SYSTEMD: systemd init.
        OPENRC: OpenRC init.
        SYSVINIT: Traditional SysV init.
        UNKNOWN: Could not be determined.
    """

    SYSTEMD = "systemd"
    OPENRC = "openrc"
    SYSVINIT = "sysvinit"
    UNKNOWN = "unknown"


class DetectedDNSBackend(Enum):
    """Detected DNS resolution backend on the system.

    Attributes:
        SYSTEMD_RESOLVED: systemd-resolved service.
        NETWORK_MANAGER: NetworkManager DNS plugin.
        RESOLVCONF: resolvconf utility.
        MANUAL: Direct /etc/resolv.conf editing.
        UNKNOWN: Could not be determined.
    """

    SYSTEMD_RESOLVED = "systemd-resolved"
    NETWORK_MANAGER = "NetworkManager"
    RESOLVCONF = "resolvconf"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass
class UbuntuVersion:
    """Ubuntu version information parsed from /etc/os-release.

    Attributes:
        version: Full version string (e.g. "22.04").
        codename: Release codename (e.g. "jammy").
        major: Major version number.
        minor: Minor version number.
        is_ubuntu: True if distro is Ubuntu.
        is_supported: True if version is 22.04+.
    """

    version: str = ""
    codename: str = ""
    major: int = 0
    minor: int = 0
    is_ubuntu: bool = False
    is_supported: bool = False

    def __str__(self) -> str:
        """Return human-readable version string.

        Returns:
            "Ubuntu X.Y (codename)" or "Not Ubuntu".
        """
        if self.is_ubuntu:
            return f"Ubuntu {self.version} ({self.codename})"
        return "Not Ubuntu"


@dataclass
class SystemInfo:
    """Complete system information for compatibility checking.

    Attributes:
        ubuntu: Ubuntu version details.
        kernel_version: Running kernel version string.
        architecture: CPU architecture (e.g. "x86_64").
        init_system: Detected init system type.
        firewall_backend: Detected firewall backend.
        iptables_available: Whether iptables binary exists.
        nftables_available: Whether nft binary exists.
        wireguard_module_loaded: Whether wireguard kernel module is loaded.
        wireguard_tools_installed: Whether wg binary exists.
        wg_quick_available: Whether wg-quick binary exists.
        nfqueue_available: Whether NFQUEUE target works.
        libnetfilter_queue_installed: Whether the library file exists.
        dns_manager: Detected DNS management backend.
        resolvectl_available: Whether resolvectl binary exists.
        cgroups_v2: Whether cgroups v2 is active.
        cgproxy_available: Whether cgproxy binary exists.
        python_version: Running Python version string.
        python_major: Python major version number.
        python_minor: Python minor version number.
        is_root: Whether running as root.
        can_sudo: Whether passwordless sudo is available.
    """

    # OS info
    ubuntu: UbuntuVersion = field(default_factory=UbuntuVersion)
    kernel_version: str = ""
    architecture: str = ""

    # Init system
    init_system: InitSystem = InitSystem.UNKNOWN

    # Firewall
    firewall_backend: FirewallBackend = FirewallBackend.UNKNOWN
    iptables_available: bool = False
    nftables_available: bool = False

    # WireGuard
    wireguard_module_loaded: bool = False
    wireguard_tools_installed: bool = False
    wg_quick_available: bool = False

    # NFQUEUE (for zapret)
    nfqueue_available: bool = False
    libnetfilter_queue_installed: bool = False

    # DNS
    dns_manager: DetectedDNSBackend = DetectedDNSBackend.UNKNOWN
    resolvectl_available: bool = False

    # cgroups (for app-based routing)
    cgroups_v2: bool = False
    cgproxy_available: bool = False

    # Python
    python_version: str = ""
    python_major: int = 0
    python_minor: int = 0

    # User
    is_root: bool = False
    can_sudo: bool = False

    def is_compatible(self) -> bool:
        """Check if system meets SplitWire minimum requirements.

        Returns:
            True if Ubuntu 22.04+, systemd, and Python 3.10+.
        """
        return (
            self.ubuntu.is_supported
            and self.init_system == InitSystem.SYSTEMD
            and self.python_major >= 3
            and self.python_minor >= 10
        )

    def get_compatibility_issues(self) -> list[str]:
        """Get list of detected compatibility issues.

        Returns:
            Human-readable issue description strings.
        """
        issues = []

        if not self.ubuntu.is_ubuntu:
            issues.append("Not running Ubuntu (other distros not yet supported)")
        elif not self.ubuntu.is_supported:
            issues.append(f"Ubuntu {self.ubuntu.version} not supported (requires 22.04+)")

        if self.init_system != InitSystem.SYSTEMD:
            issues.append("systemd not detected (required for service management)")

        if self.python_major < 3 or (self.python_major == 3 and self.python_minor < 10):
            issues.append(f"Python {self.python_version} not supported (requires 3.10+)")

        if not self.wireguard_tools_installed:
            issues.append("WireGuard tools not installed")

        if not self.nfqueue_available:
            issues.append("NFQUEUE not available (required for Zapret)")

        return issues


class SystemDetector:
    """Detects system capabilities and compatibility.

    Probes the OS, kernel, firewall, WireGuard, DNS, cgroups,
    and Python environment to build a SystemInfo report.
    """

    # Timeout constants (seconds)
    TIMEOUT_COMMAND_CHECK = 5  # general command execution
    TIMEOUT_NFQUEUE_CHECK = 3  # iptables -m nfqueue --help

    def __init__(self) -> None:
        """Initialize system detector."""
        self._info: SystemInfo | None = None

    def detect(self) -> SystemInfo:
        """Run full system detection and return results.

        Returns:
            Populated SystemInfo with all detected capabilities.

        Example:
            >>> detector = SystemDetector()
            >>> info = detector.detect()
            >>> isinstance(info, SystemInfo)
            True
        """
        logger.info("[SYSTEM] Detecting system capabilities...")
        self._info = SystemInfo()

        self._detect_ubuntu_version()
        self._detect_kernel()
        self._detect_architecture()
        self._detect_init_system()
        self._detect_firewall()
        self._detect_wireguard()
        self._detect_nfqueue()
        self._detect_dns_manager()
        self._detect_cgroups()
        self._detect_python()
        self._detect_user_privileges()

        # Log detected information
        logger.debug(f"[SYSTEM] OS: {self._info.ubuntu}")
        logger.debug(f"[SYSTEM] Kernel: {self._info.kernel_version}")
        logger.debug(f"[SYSTEM] Init: {self._info.init_system.value}")
        logger.debug(f"[SYSTEM] Firewall: {self._info.firewall_backend.value}")
        logger.debug(
            "[SYSTEM] WireGuard: tools=%s, module=%s",
            self._info.wireguard_tools_installed,
            self._info.wireguard_module_loaded,
        )
        logger.debug(f"[SYSTEM] NFQUEUE: {self._info.nfqueue_available}")
        logger.debug(f"[SYSTEM] Cgroups v2: {self._info.cgroups_v2}")
        logger.debug(f"[SYSTEM] DNS Manager: {self._info.dns_manager.value}")
        logger.info("[SYSTEM] System detection completed")

        return self._info

    def _run_command(
        self,
        cmd: list[str],
        timeout: int = TIMEOUT_COMMAND_CHECK,
    ) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", "Command not found"
        except OSError as e:
            return -1, "", str(e)

    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists in PATH."""
        code, _, _ = self._run_command(["which", cmd])
        return code == 0

    def _detect_ubuntu_version(self) -> None:
        """Detect Ubuntu version from /etc/os-release."""
        os_release = Path("/etc/os-release")

        if not os_release.exists():
            return

        try:
            content = os_release.read_text()
            info = {}
            for line in content.splitlines():
                if "=" in line:
                    key, _, value = line.partition("=")
                    info[key] = value.strip('"')

            distro_id = info.get("ID", "").lower()

            if distro_id == "ubuntu":
                self._info.ubuntu.is_ubuntu = True
                self._info.ubuntu.version = info.get("VERSION_ID", "")
                self._info.ubuntu.codename = info.get("VERSION_CODENAME", "")

                # Parse version
                if self._info.ubuntu.version:
                    parts = self._info.ubuntu.version.split(".")
                    if len(parts) >= 1:
                        self._info.ubuntu.major = int(parts[0])
                    if len(parts) >= 2:
                        self._info.ubuntu.minor = int(parts[1])

                # Check if supported (22.04+)
                _min_major = 22
                _min_minor = 4
                major = self._info.ubuntu.major
                minor = self._info.ubuntu.minor
                if major > _min_major or (major == _min_major and minor >= _min_minor):
                    self._info.ubuntu.is_supported = True
        except (OSError, ValueError, KeyError):
            pass

    def _detect_kernel(self) -> None:
        """Detect kernel version."""
        code, stdout, _ = self._run_command(["uname", "-r"])
        if code == 0:
            self._info.kernel_version = stdout

    def _detect_architecture(self) -> None:
        """Detect system architecture."""
        code, stdout, _ = self._run_command(["uname", "-m"])
        if code == 0:
            self._info.architecture = stdout

    def _detect_init_system(self) -> None:
        """Detect init system (systemd, openrc, etc.)."""
        # Check for systemd
        if Path("/run/systemd/system").exists():
            self._info.init_system = InitSystem.SYSTEMD
            return

        # Check for OpenRC
        if Path("/run/openrc").exists():
            self._info.init_system = InitSystem.OPENRC
            return

        # Check PID 1
        try:
            pid1 = Path("/proc/1/comm").read_text().strip()
            if pid1 == "systemd":
                self._info.init_system = InitSystem.SYSTEMD
            elif pid1 == "init":
                self._info.init_system = InitSystem.SYSVINIT
        except OSError:
            pass

    def _detect_firewall(self) -> None:
        """Detect firewall backend."""
        # Check iptables
        self._info.iptables_available = self._command_exists("iptables")

        # Check nftables
        self._info.nftables_available = self._command_exists("nft")

        # Check firewalld
        if self._command_exists("firewall-cmd"):
            code, _, _ = self._run_command(["systemctl", "is-active", "firewalld"])
            if code == 0:
                self._info.firewall_backend = FirewallBackend.FIREWALLD
                return

        # Determine primary backend
        # On Ubuntu, iptables is usually the default
        if self._info.iptables_available:
            # Check if iptables is actually nftables backend
            code, stdout, _ = self._run_command(["iptables", "--version"])
            if code == 0 and "nf_tables" in stdout:
                self._info.firewall_backend = FirewallBackend.NFTABLES
            else:
                self._info.firewall_backend = FirewallBackend.IPTABLES
        elif self._info.nftables_available:
            self._info.firewall_backend = FirewallBackend.NFTABLES

    def _detect_wireguard(self) -> None:
        """Detect WireGuard support."""
        # Check if module is loaded
        code, stdout, _ = self._run_command(["lsmod"])
        if code == 0:
            self._info.wireguard_module_loaded = "wireguard" in stdout

        # Also check /sys/module
        if Path("/sys/module/wireguard").exists():
            self._info.wireguard_module_loaded = True

        # Check wireguard-tools
        self._info.wg_quick_available = self._command_exists("wg-quick")
        self._info.wireguard_tools_installed = self._command_exists("wg")

    def _detect_nfqueue(self) -> None:
        """Detect NFQUEUE support for Zapret."""
        # Check if NFQUEUE target is available
        # Try to list iptables extensions
        code, stdout, _ = self._run_command(
            ["iptables", "-m", "nfqueue", "--help"],
            timeout=self.TIMEOUT_NFQUEUE_CHECK,
        )
        # If help text is shown, NFQUEUE is available
        self._info.nfqueue_available = code == 0 or "NFQUEUE" in stdout

        # Check for libnetfilter-queue
        # Look for the library file
        lib_paths = [
            "/usr/lib/x86_64-linux-gnu/libnetfilter_queue.so",
            "/usr/lib/libnetfilter_queue.so",
            "/lib/x86_64-linux-gnu/libnetfilter_queue.so",
        ]
        self._info.libnetfilter_queue_installed = any(
            Path(p).exists() or Path(p + ".1").exists() for p in lib_paths
        )

    def _detect_dns_manager(self) -> None:
        """Detect DNS manager."""
        # Check for systemd-resolved
        code, _, _ = self._run_command(["systemctl", "is-active", "systemd-resolved"])
        if code == 0:
            self._info.dns_manager = DetectedDNSBackend.SYSTEMD_RESOLVED
            self._info.resolvectl_available = self._command_exists("resolvectl")
            return

        # Check for NetworkManager
        code, _, _ = self._run_command(["systemctl", "is-active", "NetworkManager"])
        if code == 0:
            self._info.dns_manager = DetectedDNSBackend.NETWORK_MANAGER
            return

        # Check for resolvconf
        if self._command_exists("resolvconf"):
            self._info.dns_manager = DetectedDNSBackend.RESOLVCONF
            return

        # Manual (direct /etc/resolv.conf editing)
        if Path("/etc/resolv.conf").exists():
            self._info.dns_manager = DetectedDNSBackend.MANUAL

    def _detect_cgroups(self) -> None:
        """Detect cgroups version and cgproxy availability."""
        # Check cgroups v2
        if Path("/sys/fs/cgroup/cgroup.controllers").exists():
            self._info.cgroups_v2 = True

        # Check cgproxy
        self._info.cgproxy_available = self._command_exists("cgproxy")

    def _detect_python(self) -> None:
        """Detect Python version."""
        import sys

        self._info.python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        self._info.python_major = sys.version_info.major
        self._info.python_minor = sys.version_info.minor

    def _detect_user_privileges(self) -> None:
        """Detect user privileges."""
        self._info.is_root = os.geteuid() == 0

        # Check if user can sudo
        if not self._info.is_root:
            code, _, _ = self._run_command(["sudo", "-n", "true"])
            self._info.can_sudo = code == 0


def get_system_info() -> SystemInfo:
    """Detect and return system information.

    Returns:
        Populated SystemInfo for the current machine.
    """
    detector = SystemDetector()
    return detector.detect()


def print_system_info(info: SystemInfo) -> None:
    """Log system information in a formatted table.

    Delegates to system_info module.

    Args:
        info: SystemInfo to display.
    """
    from .system_info import print_system_info as _print_info

    _print_info(info)
