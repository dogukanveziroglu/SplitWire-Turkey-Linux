"""
Dependency installation and status display helpers.

Extracted from deps.py to keep file sizes under 500 lines.
"""

import logging
import subprocess
import sys

from .deps import Dependency, DependencyChecker, DependencyStatus

logger = logging.getLogger(__name__)


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

    _log_dependency_group("System Dependencies", system_deps)
    _log_dependency_group("Python Dependencies", python_deps)
    _log_dependency_summary(system_deps, python_deps)


def _log_dependency_group(title: str, deps: list[Dependency]) -> None:
    """Log a single dependency group with header."""
    logger.info("%s:", title)
    logger.info("-" * 40)
    for dep in deps:
        logger.info("  %s", dep)


def _log_dependency_summary(
    system_deps: list[Dependency],
    python_deps: list[Dependency],
) -> None:
    """Log summary of missing dependencies with install hints."""
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
    """Check and install all missing dependencies.

    Args:
        interactive: If True, asks for confirmation before installing.

    Returns:
        True if all dependencies are satisfied.
    """
    checker = DependencyChecker()
    checker.check_all()

    compatible, msg = checker.check_python_version()
    logger.info(msg)
    if not compatible:
        return False

    print_dependency_status(checker.system_deps, checker.python_deps)

    if not _install_missing_system(checker, interactive):
        return False
    if not _install_missing_python(checker, interactive):
        return False

    return _verify_all_satisfied(checker)


def _install_missing_system(checker: DependencyChecker, interactive: bool) -> bool:
    """Install missing system deps if any, returning False on failure."""
    if checker.get_missing_system_deps():
        if not checker.install_system_dependencies(interactive):
            logger.error("Failed to install system dependencies")
            return False
        checker.check_system_dependencies()
    return True


def _install_missing_python(checker: DependencyChecker, interactive: bool) -> bool:
    """Install missing Python deps if any, returning False on failure."""
    if checker.get_missing_python_deps():
        if not checker.install_python_dependencies(interactive):
            logger.error("Failed to install Python dependencies")
            return False
        checker.check_python_dependencies()
    return True


def _verify_all_satisfied(checker: DependencyChecker) -> bool:
    """Check that no required deps remain missing."""
    missing = checker.get_missing_required_deps()
    if missing:
        logger.error(
            "Still missing required dependencies: %s",
            ", ".join(d.name for d in missing),
        )
        return False
    logger.info("All dependencies satisfied!")
    return True


def _run_apt_install(packages: list[str], timeout: int) -> bool:
    """Run apt install for the given packages.

    Args:
        packages: Package names to install.
        timeout: Timeout in seconds.

    Returns:
        True if installation succeeded.
    """
    cmd = ["sudo", "apt", "install", "-y", *packages]
    logger.debug("[DEPS] Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, timeout=timeout)
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


def _run_pip_install(packages: list[str], timeout: int) -> bool:
    """Run pip install for the given packages.

    Args:
        packages: Package names to install.
        timeout: Timeout in seconds.

    Returns:
        True if installation succeeded.
    """
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    logger.info("[DEPS] Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, timeout=timeout)
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError) as e:
        logger.error("[DEPS] Error installing packages: %s", e)
        return False
