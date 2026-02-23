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
    "DNSManager",
    "Dependency",
    "DependencyChecker",
    "DependencyStatus",
    "ElevationMethod",
    "ElevationResult",
    "FirewallBackend",
    "InitSystem",
    "PolkitHelper",
    "SystemDetector",
    "SystemInfo",
    "UbuntuVersion",
    "can_elevate",
    "check_dependencies",
    "get_polkit_helper",
    "get_system_info",
    "install_all_dependencies",
    "is_root",
    "print_dependency_status",
    "print_system_info",
    "run_elevated",
]
