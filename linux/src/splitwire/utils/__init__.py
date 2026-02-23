"""
Utility modules for SplitWire-Turkey Linux.

This package contains:
- system: System detection and compatibility checking
- deps: Dependency checking and installation
- polkit: Privilege escalation helpers
"""

from .deps import (
    Dependency,
    DependencyChecker,
    DependencyStatus,
    check_dependencies,
    install_all_dependencies,
    print_dependency_status,
)
from .polkit import (
    ElevationMethod,
    ElevationResult,
    PolkitHelper,
    can_elevate,
    get_polkit_helper,
    is_root,
    run_elevated,
)
from .system import (
    DNSManager,
    FirewallBackend,
    InitSystem,
    SystemDetector,
    SystemInfo,
    UbuntuVersion,
    get_system_info,
    print_system_info,
)

__all__ = [
    # system
    "SystemDetector",
    "SystemInfo",
    "UbuntuVersion",
    "FirewallBackend",
    "InitSystem",
    "DNSManager",
    "get_system_info",
    "print_system_info",
    # deps
    "DependencyChecker",
    "Dependency",
    "DependencyStatus",
    "check_dependencies",
    "print_dependency_status",
    "install_all_dependencies",
    # polkit
    "PolkitHelper",
    "ElevationMethod",
    "ElevationResult",
    "get_polkit_helper",
    "run_elevated",
    "can_elevate",
    "is_root",
]
