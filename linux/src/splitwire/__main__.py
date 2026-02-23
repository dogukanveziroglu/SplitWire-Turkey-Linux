#!/usr/bin/env python3
"""
SplitWire Linux - Main entry point.

This module serves as the entry point for the application.
It initializes core systems and launches the GUI.
"""

import sys
import argparse
from pathlib import Path

# Ensure the package can be found when run directly
_package_dir = Path(__file__).parent.parent
if str(_package_dir) not in sys.path:
    sys.path.insert(0, str(_package_dir))


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        print(f"Error: Python 3.10+ required, found {major}.{minor}")
        return False
    return True


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="splitwire",
        description="SplitWire - A privacy-focused network routing tool for Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  splitwire                    Launch GUI application
  splitwire --check-deps       Check system dependencies
  splitwire --version          Show version information
  splitwire --debug            Enable debug logging

For more information, visit: https://github.com/cagritaskn/SplitWire-Turkey
        """,
    )

    parser.add_argument(
        "--version", "-v", action="store_true", help="Show version information and exit"
    )

    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")

    parser.add_argument(
        "--check-deps", action="store_true", help="Check system dependencies and exit"
    )

    parser.add_argument(
        "--check-system", action="store_true", help="Show system information and exit"
    )

    parser.add_argument("--install-deps", action="store_true", help="Install missing dependencies")

    parser.add_argument(
        "--language",
        "-l",
        choices=["tr", "en", "ru", "es"],
        default=None,
        help="Set application language",
    )

    parser.add_argument("--config-dir", type=Path, default=None, help="Override config directory")

    return parser.parse_args()


def show_version() -> None:
    """Display version information."""
    from splitwire.core import get_config

    config = get_config()
    print(f"SplitWire Linux v{config.version}")
    print("A privacy-focused network routing tool for Linux")
    print("")
    print("GitHub: https://github.com/cagritaskn/SplitWire-Turkey")
    print("License: MIT")


def check_dependencies() -> bool:
    """Check and display dependency status."""
    from splitwire.utils import check_dependencies, print_dependency_status

    system_deps, python_deps = check_dependencies()
    print_dependency_status(system_deps, python_deps)

    # Return True if all required deps are installed
    missing_required = [
        d for d in system_deps + python_deps if d.required and d.status.value == "missing"
    ]
    return len(missing_required) == 0


def check_system() -> None:
    """Display system information."""
    from splitwire.utils import get_system_info, print_system_info

    info = get_system_info()
    print_system_info(info)


def install_dependencies() -> bool:
    """Install missing dependencies."""
    from splitwire.utils import install_all_dependencies

    return install_all_dependencies(interactive=True)


def run_gui(args: argparse.Namespace) -> int:
    """
    Launch the GTK4 GUI application.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    from splitwire.core import (
        init_logger,
        init_language_manager,
        get_config_manager,
    )

    # Initialize logger
    logger = init_logger(debug=args.debug)
    logger.info("Starting SplitWire Linux")

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.config

    # Initialize language manager
    language = args.language or config.language
    init_language_manager(language)

    logger.info(f"Language: {language}")
    logger.info(f"Debug mode: {args.debug}")

    # Check if GTK is available
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw  # noqa: F401
    except (ImportError, ValueError) as e:
        logger.error(f"GTK4/Libadwaita not available: {e}")
        print("Error: GTK4 and Libadwaita are required for GUI mode.")
        print("Install with: sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1 python3-gi")
        return 1

    # Import and run the GTK4 application
    from splitwire.application import SplitWireApp

    logger.info("Launching GTK4 GUI")
    app = SplitWireApp()
    return app.run(sys.argv[:1])


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    # Check Python version first
    if not check_python_version():
        return 1

    # Parse arguments
    args = parse_args()

    # Handle simple commands that don't need full initialization
    if args.version:
        show_version()
        return 0

    if args.check_deps:
        success = check_dependencies()
        return 0 if success else 1

    if args.check_system:
        check_system()
        return 0

    if args.install_deps:
        success = install_dependencies()
        return 0 if success else 1

    # Launch GUI
    return run_gui(args)


if __name__ == "__main__":
    sys.exit(main())
