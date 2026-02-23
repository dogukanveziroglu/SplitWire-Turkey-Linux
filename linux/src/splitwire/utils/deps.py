"""
Dependency checking and installation module.

Checks for required system packages and Python dependencies,
and provides installation commands/automation.
"""

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """Status of a checked dependency.

    Attributes:
        INSTALLED: Dependency is present and working.
        MISSING: Dependency is not installed.
        OUTDATED: Dependency needs an update.
        UNKNOWN: Status could not be determined.
    """

    INSTALLED = "installed"
    MISSING = "missing"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"


class PackageManager(Enum):
    """Available system package managers.

    Attributes:
        APT: Debian/Ubuntu apt.
        SNAP: Snap package manager.
        FLATPAK: Flatpak package manager.
        PIP: Python pip.
    """

    APT = "apt"
    SNAP = "snap"
    FLATPAK = "flatpak"
    PIP = "pip"


@dataclass
class Dependency:
    """Represents a system or Python dependency.

    Attributes:
        name: Human-readable dependency name.
        package_name: Package manager package name.
        description: Short description of what it provides.
        required: Whether the app needs this to function.
        status: Current installation status.
        version: Detected version string (if known).
        check_command: Command to verify installation.
        install_command: Command to install the package.
    """

    name: str
    package_name: str
    description: str
    required: bool = True
    status: DependencyStatus = DependencyStatus.UNKNOWN
    version: str = ""
    check_command: list[str] = field(default_factory=list)
    install_command: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Return a formatted status string for display.

        Returns:
            Status icon, required flag, name, and description.
        """
        status_icon = {
            DependencyStatus.INSTALLED: "[OK]",
            DependencyStatus.MISSING: "[!!]",
            DependencyStatus.OUTDATED: "[UP]",
            DependencyStatus.UNKNOWN: "[??]",
        }
        req = "*" if self.required else " "
        return f"{status_icon[self.status]} {req} {self.name}: {self.description}"


# Required system packages for SplitWire-Turkey
SYSTEM_DEPENDENCIES: list[Dependency] = [
    # GTK4 and Libadwaita
    Dependency(
        name="python3-gi",
        package_name="python3-gi",
        description="Python GObject introspection",
        required=True,
        check_command=["python3", "-c", "import gi"],
    ),
    Dependency(
        name="python3-gi-cairo",
        package_name="python3-gi-cairo",
        description="Python GObject Cairo bindings",
        required=True,
        check_command=["python3", "-c", "import gi; gi.require_version('cairo', '1.0')"],
    ),
    Dependency(
        name="GTK4",
        package_name="gir1.2-gtk-4.0",
        description="GTK4 GObject introspection",
        required=True,
        check_command=[
            "python3",
            "-c",
            "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk",
        ],
    ),
    Dependency(
        name="Libadwaita",
        package_name="gir1.2-adw-1",
        description="Libadwaita for GNOME styling",
        required=True,
        check_command=[
            "python3",
            "-c",
            "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw",
        ],
    ),
    # WireGuard
    Dependency(
        name="wireguard-tools",
        package_name="wireguard-tools",
        description="WireGuard userspace tools (wg, wg-quick)",
        required=True,
        check_command=["which", "wg-quick"],
    ),
    # Zapret dependencies
    Dependency(
        name="libnetfilter-queue-dev",
        package_name="libnetfilter-queue-dev",
        description="Netfilter queue library (for Zapret nfqws)",
        required=True,
        check_command=["dpkg", "-s", "libnetfilter-queue-dev"],
    ),
    Dependency(
        name="iptables",
        package_name="iptables",
        description="IP packet filter administration",
        required=True,
        check_command=["which", "iptables"],
    ),
    # cgroups for app-based routing
    Dependency(
        name="cgroup-tools",
        package_name="cgroup-tools",
        description="Control group tools",
        required=False,  # Optional, for advanced features
        check_command=["which", "cgcreate"],
    ),
    # General utilities
    Dependency(
        name="curl",
        package_name="curl",
        description="Command line HTTP client",
        required=True,
        check_command=["which", "curl"],
    ),
    Dependency(
        name="wget",
        package_name="wget",
        description="Network downloader",
        required=False,
        check_command=["which", "wget"],
    ),
    Dependency(
        name="git",
        package_name="git",
        description="Version control (for Zapret clone)",
        required=True,
        check_command=["which", "git"],
    ),
    # Polkit for GUI privilege elevation
    Dependency(
        name="policykit-1",
        package_name="policykit-1",
        description="PolicyKit authentication agent",
        required=True,
        check_command=["which", "pkexec"],
    ),
]


# Python dependencies (from pip)
PYTHON_DEPENDENCIES: list[Dependency] = [
    Dependency(
        name="httpx",
        package_name="httpx",
        description="Modern HTTP client for API calls",
        required=True,
        check_command=["python3", "-c", "import httpx"],
    ),
    Dependency(
        name="pydantic",
        package_name="pydantic",
        description="Data validation library",
        required=True,
        check_command=["python3", "-c", "import pydantic"],
    ),
]


class DependencyChecker:
    """Checks and manages system and Python dependencies.

    Attributes:
        system_deps: List of system-level dependencies.
        python_deps: List of Python package dependencies.
    """

    def __init__(self) -> None:
        """Initialize checker with copies of dependency lists."""
        self.system_deps = [Dependency(**d.__dict__) for d in SYSTEM_DEPENDENCIES]
        self.python_deps = [Dependency(**d.__dict__) for d in PYTHON_DEPENDENCIES]
        self._apt_available: bool | None = None

    def _run_command(self, cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
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

    def _is_apt_available(self) -> bool:
        """Check if apt is available."""
        if self._apt_available is None:
            code, _, _ = self._run_command(["which", "apt"])
            self._apt_available = code == 0
        return self._apt_available

    def check_all(self) -> tuple[list[Dependency], list[Dependency]]:
        """Check all system and Python dependencies.

        Returns:
            Tuple of (system_deps, python_deps) with updated status.

        Example:
            >>> checker = DependencyChecker()
            >>> sys_deps, py_deps = checker.check_all()
            >>> isinstance(sys_deps, list)
            True
        """
        self.check_system_dependencies()
        self.check_python_dependencies()
        return self.system_deps, self.python_deps

    def check_system_dependencies(self) -> list[Dependency]:
        """Check all system dependencies and update their status.

        Returns:
            List of system dependencies with updated status.
        """
        logger.info("[DEPS] Checking system dependencies...")
        for dep in self.system_deps:
            if dep.check_command:
                code, _, _ = self._run_command(dep.check_command)
                dep.status = DependencyStatus.INSTALLED if code == 0 else DependencyStatus.MISSING
                status_str = "installed" if dep.status == DependencyStatus.INSTALLED else "missing"
                logger.debug(f"[DEPS] {dep.name}: {status_str}")
            else:
                dep.status = DependencyStatus.UNKNOWN

        missing = [d.name for d in self.system_deps if d.status == DependencyStatus.MISSING]
        if missing:
            logger.warning(f"[DEPS] Missing system packages: {', '.join(missing)}")
        else:
            logger.debug("[DEPS] All system dependencies satisfied")
        return self.system_deps

    def check_python_dependencies(self) -> list[Dependency]:
        """Check all Python dependencies and update their status.

        Returns:
            List of Python dependencies with updated status.
        """
        logger.info("[DEPS] Checking Python dependencies...")
        for dep in self.python_deps:
            if dep.check_command:
                code, _, _ = self._run_command(dep.check_command)
                dep.status = DependencyStatus.INSTALLED if code == 0 else DependencyStatus.MISSING
                status_str = "installed" if dep.status == DependencyStatus.INSTALLED else "missing"
                logger.debug(f"[DEPS] {dep.name}: {status_str}")
            else:
                dep.status = DependencyStatus.UNKNOWN

        missing = [d.name for d in self.python_deps if d.status == DependencyStatus.MISSING]
        if missing:
            logger.warning(f"[DEPS] Missing Python packages: {', '.join(missing)}")
        else:
            logger.debug("[DEPS] All Python dependencies satisfied")
        return self.python_deps

    def get_missing_system_deps(self) -> list[Dependency]:
        """Get list of missing system dependencies.

        Returns:
            Dependencies with MISSING status.
        """
        return [d for d in self.system_deps if d.status == DependencyStatus.MISSING]

    def get_missing_python_deps(self) -> list[Dependency]:
        """Get list of missing Python dependencies.

        Returns:
            Dependencies with MISSING status.
        """
        return [d for d in self.python_deps if d.status == DependencyStatus.MISSING]

    def get_missing_required_deps(self) -> list[Dependency]:
        """Get all missing required dependencies.

        Returns:
            Combined system and Python deps that are required
            but have MISSING status.
        """
        missing = []
        missing.extend(
            [d for d in self.system_deps if d.status == DependencyStatus.MISSING and d.required]
        )
        missing.extend(
            [d for d in self.python_deps if d.status == DependencyStatus.MISSING and d.required]
        )
        return missing

    def get_apt_install_command(self) -> list[str]:
        """Get the apt install command for missing system packages.

        Returns:
            Command list for ``sudo apt install``, or empty list.
        """
        missing = self.get_missing_system_deps()
        if not missing:
            return []

        packages = [d.package_name for d in missing]
        return ["sudo", "apt", "install", "-y", *packages]

    def get_pip_install_command(self) -> list[str]:
        """Get the pip install command for missing Python packages.

        Returns:
            Command list for ``pip install``, or empty list.
        """
        missing = self.get_missing_python_deps()
        if not missing:
            return []

        packages = [d.package_name for d in missing]
        return [sys.executable, "-m", "pip", "install", *packages]

    def install_system_dependencies(self, interactive: bool = True) -> bool:
        """
        Install missing system dependencies using apt.

        Args:
            interactive: If True, asks for confirmation

        Returns:
            True if installation succeeded or nothing to install
        """
        missing = self.get_missing_system_deps()
        if not missing:
            logger.debug("[DEPS] No missing system dependencies to install")
            return True

        if not self._is_apt_available():
            logger.error("[DEPS] apt package manager not available")
            return False

        packages = [d.package_name for d in missing]
        logger.info(
            "[DEPS] Installing system packages: %s",
            ", ".join(packages),
        )

        if interactive:
            response = input("Install missing packages? [Y/n]: ").strip().lower()
            if response and response != "y":
                logger.info("[DEPS] User cancelled installation")
                return False

        cmd = ["sudo", "apt", "update"]
        logger.debug("[DEPS] Running: %s", " ".join(cmd))
        code, _, _ = self._run_command(cmd, timeout=120)
        if code != 0:
            logger.warning("[DEPS] apt update failed, continuing anyway...")

        cmd = ["sudo", "apt", "install", "-y", *packages]
        logger.debug("[DEPS] Running: %s", " ".join(cmd))

        # For installation, we need to run interactively
        try:
            result = subprocess.run(cmd, timeout=300)
            if result.returncode == 0:
                logger.info("[DEPS] System packages installed successfully")
            else:
                logger.error(
                    "[DEPS] Package installation failed with code %s",
                    result.returncode,
                )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError) as e:
            logger.error("[DEPS] Error installing packages: %s", e)
            return False

    def install_python_dependencies(self, interactive: bool = True) -> bool:
        """
        Install missing Python dependencies using pip.

        Args:
            interactive: If True, asks for confirmation

        Returns:
            True if installation succeeded or nothing to install
        """
        missing = self.get_missing_python_deps()
        if not missing:
            return True

        packages = [d.package_name for d in missing]
        logger.info(
            "[DEPS] Missing Python packages: %s",
            ", ".join(packages),
        )

        if interactive:
            response = input("Install missing packages? [Y/n]: ").strip().lower()
            if response and response != "y":
                return False

        cmd = [sys.executable, "-m", "pip", "install", *packages]
        logger.info("[DEPS] Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(cmd, timeout=120)
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError) as e:
            logger.error("[DEPS] Error installing packages: %s", e)
            return False

    def check_python_version(self) -> tuple[bool, str]:
        """
        Check if Python version is compatible.

        Returns:
            Tuple of (is_compatible, message)
        """
        major, minor = sys.version_info[:2]
        version_str = f"{major}.{minor}.{sys.version_info.micro}"

        if major < 3 or (major == 3 and minor < 10):
            return False, f"Python {version_str} not supported. Requires Python 3.10+"
        return True, f"Python {version_str} is compatible"


def check_dependencies() -> tuple[list[Dependency], list[Dependency]]:
    """Check all dependencies and return their status.

    Returns:
        Tuple of (system_deps, python_deps) with updated status.
    """
    checker = DependencyChecker()
    return checker.check_all()


def print_dependency_status(
    system_deps: list[Dependency],
    python_deps: list[Dependency],
) -> None:
    """Log dependency status in a formatted table.

    Args:
        system_deps: System dependencies with checked status.
        python_deps: Python dependencies with checked status.
    """
    logger.info("=" * 50)
    logger.info("SplitWire-Turkey Dependency Check")
    logger.info("=" * 50)

    logger.info("System Dependencies:")
    logger.info("-" * 40)
    for dep in system_deps:
        logger.info("  %s", dep)

    logger.info("Python Dependencies:")
    logger.info("-" * 40)
    for dep in python_deps:
        logger.info("  %s", dep)

    # Summary
    missing_sys = [d for d in system_deps if d.status == DependencyStatus.MISSING]
    missing_py = [d for d in python_deps if d.status == DependencyStatus.MISSING]

    logger.info("=" * 50)
    if not missing_sys and not missing_py:
        logger.info("All dependencies are installed!")
    else:
        if missing_sys:
            logger.warning("Missing system packages: %s", len(missing_sys))
            logger.info(
                "  Install with: sudo apt install %s",
                " ".join(d.package_name for d in missing_sys),
            )
        if missing_py:
            logger.warning("Missing Python packages: %s", len(missing_py))
            logger.info(
                "  Install with: pip install %s",
                " ".join(d.package_name for d in missing_py),
            )
    logger.info("=" * 50)


def install_all_dependencies(interactive: bool = True) -> bool:
    """
    Check and install all missing dependencies.

    Args:
        interactive: If True, asks for confirmation before installing

    Returns:
        True if all dependencies are satisfied
    """
    checker = DependencyChecker()
    checker.check_all()

    # Check Python version first
    compatible, msg = checker.check_python_version()
    logger.info(msg)
    if not compatible:
        return False

    # Print current status
    print_dependency_status(checker.system_deps, checker.python_deps)

    # Install missing
    if checker.get_missing_system_deps():
        if not checker.install_system_dependencies(interactive):
            logger.error("Failed to install system dependencies")
            return False
        # Re-check
        checker.check_system_dependencies()

    if checker.get_missing_python_deps():
        if not checker.install_python_dependencies(interactive):
            logger.error("Failed to install Python dependencies")
            return False
        # Re-check
        checker.check_python_dependencies()

    # Final check
    missing = checker.get_missing_required_deps()
    if missing:
        logger.error(
            "Still missing required dependencies: %s",
            ", ".join(d.name for d in missing),
        )
        return False

    logger.info("All dependencies satisfied!")
    return True
