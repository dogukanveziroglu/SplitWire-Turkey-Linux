"""
Pytest configuration and fixtures for SplitWire-Turkey integration tests.

This module provides pytest fixtures for:
- Kill switch management
- Network baseline capture/restore
- Connectivity verification
- Safe test cleanup
"""

import os
import sys
import pytest
import logging
from pathlib import Path
from typing import Generator, Optional

# Add source directory and tests directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from kill_switch import (
    KillSwitch,
    KillSwitchConfig,
    KillSwitchContext,
    force_cleanup_all,
    force_cleanup_zapret,
    force_cleanup_wireguard,
    force_cleanup_dns,
    force_cleanup_byedpi,
)
from fixtures import (
    PreTestChecklist,
    NetworkBaseline,
    PostTestRecovery,
    RecoveryResult,
)
from helpers import (
    verify_connectivity,
    wait_for_connectivity,
    is_root,
    tcp_connect_test,
)


# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TEST] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Pytest Hooks
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "phase0: Infrastructure setup tests (no risk)"
    )
    config.addinivalue_line(
        "markers", "phase1: Core functionality tests (no risk)"
    )
    config.addinivalue_line(
        "markers", "phase2: Backup/restore tests (low risk)"
    )
    config.addinivalue_line(
        "markers", "phase3: Read-only detection tests (no risk)"
    )
    config.addinivalue_line(
        "markers", "phase4: DNS tests (medium risk, requires kill switch)"
    )
    config.addinivalue_line(
        "markers", "phase5: ByeDPI tests (medium risk, requires kill switch)"
    )
    config.addinivalue_line(
        "markers", "phase6: WireGuard tests (medium-high risk, requires kill switch)"
    )
    config.addinivalue_line(
        "markers", "phase7: Zapret tests (HIGH risk, requires strict kill switch)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_root: Tests that require root privileges"
    )
    config.addinivalue_line(
        "markers", "requires_internet: Tests that require internet connectivity"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take a long time"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests based on conditions."""
    skip_root = pytest.mark.skip(reason="Test requires root privileges")
    skip_internet = pytest.mark.skip(reason="No internet connectivity")

    has_root = is_root()
    has_internet = tcp_connect_test("8.8.8.8", 53, timeout=5.0)

    for item in items:
        if "requires_root" in item.keywords and not has_root:
            item.add_marker(skip_root)
        if "requires_internet" in item.keywords and not has_internet:
            item.add_marker(skip_internet)


# =============================================================================
# Session-scoped Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def session_baseline() -> Generator[Optional[NetworkBaseline], None, None]:
    """
    Capture network baseline at session start.
    This baseline is used to verify system state throughout testing.
    """
    if not is_root():
        yield None
        return

    checklist = PreTestChecklist()
    if not checklist.run_checks():
        logger.warning(f"Pre-test checks failed: {checklist.get_issues()}")
        # Try to clean up
        force_cleanup_all()
        # Re-run checks
        if not checklist.run_checks():
            pytest.exit(
                f"System not in clean state: {checklist.get_issues()}\n"
                f"Run: sudo ./tests/emergency_restore.sh"
            )

    baseline = checklist.capture_baseline()
    logger.info("Session baseline captured")

    yield baseline

    # Session teardown - verify and restore
    logger.info("Session teardown - verifying state")
    recovery = PostTestRecovery(baseline)
    result = recovery.verify_and_recover(force_cleanup=True)

    if not result.connectivity_restored:
        logger.error("CRITICAL: Connectivity not restored after session!")
        logger.error("Run: sudo ./tests/emergency_restore.sh")


@pytest.fixture(scope="session")
def emergency_restore_path() -> Path:
    """Get path to emergency restore script."""
    return Path(__file__).parent / "emergency_restore.sh"


# =============================================================================
# Module-scoped Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def module_cleanup():
    """Ensure cleanup after each test module."""
    yield
    logger.info("Module cleanup - ensuring clean state")
    force_cleanup_all()
    wait_for_connectivity(timeout=10)


# =============================================================================
# Function-scoped Fixtures
# =============================================================================

@pytest.fixture
def kill_switch_standard() -> Generator[KillSwitch, None, None]:
    """
    Standard kill switch fixture (60s timeout, 10s threshold).
    Use for medium-risk operations like DNS and ByeDPI.
    """
    config = KillSwitchConfig(
        timeout=60,
        threshold=10,
        check_interval=1.0,
        nuclear_enabled=True
    )
    ks = KillSwitch(config)
    ks.start()

    yield ks

    ks.stop()
    if ks.was_triggered:
        logger.warning("Kill switch was triggered during test!")
        wait_for_connectivity(timeout=30)


@pytest.fixture
def kill_switch_wireguard() -> Generator[KillSwitch, None, None]:
    """
    WireGuard kill switch fixture (90s timeout, 15s threshold).
    Use for WireGuard operations that need longer handshake time.
    """
    config = KillSwitchConfig(
        timeout=90,
        threshold=15,
        check_interval=1.0,
        nuclear_enabled=True
    )
    ks = KillSwitch(config)
    ks.start()

    yield ks

    ks.stop()
    if ks.was_triggered:
        logger.warning("Kill switch was triggered during test!")
        force_cleanup_wireguard()
        wait_for_connectivity(timeout=30)


@pytest.fixture
def kill_switch_strict() -> Generator[KillSwitch, None, None]:
    """
    Strict kill switch fixture (45s timeout, 5s threshold).
    Use for HIGH-RISK operations like Zapret.
    """
    config = KillSwitchConfig(
        timeout=45,
        threshold=5,  # Trigger quickly on connectivity loss
        check_interval=0.5,  # Check more frequently
        nuclear_enabled=True
    )
    ks = KillSwitch(config)
    ks.start()

    yield ks

    ks.stop()
    if ks.was_triggered:
        logger.warning("STRICT kill switch was triggered!")
        force_cleanup_zapret()
        force_cleanup_all()
        wait_for_connectivity(timeout=30)


@pytest.fixture
def network_baseline(session_baseline) -> Generator[NetworkBaseline, None, None]:
    """
    Per-test network baseline fixture.
    Captures state before test and verifies restoration after.
    """
    if session_baseline is None:
        pytest.skip("Session baseline not available (not root?)")

    checklist = PreTestChecklist()
    baseline = checklist.capture_baseline()

    yield baseline

    # Verify state after test
    recovery = PostTestRecovery(baseline)
    result = recovery.verify_and_recover()

    if result.differences_found:
        logger.warning(f"State differences found: {result.differences_found}")

    if not result.connectivity_restored:
        logger.error("Connectivity not restored after test!")


@pytest.fixture
def ensure_connectivity():
    """
    Fixture that ensures connectivity before and after test.
    """
    # Before test
    if not tcp_connect_test("8.8.8.8", 53, timeout=5.0):
        pytest.skip("No initial connectivity")

    yield

    # After test
    if not wait_for_connectivity(timeout=30):
        force_cleanup_all()
        if not wait_for_connectivity(timeout=30):
            logger.error("Connectivity not restored!")


@pytest.fixture
def pre_test_checks():
    """
    Run pre-test checks and skip if system not clean.
    """
    checklist = PreTestChecklist()
    if not checklist.run_checks():
        issues = checklist.get_issues()
        pytest.skip(f"Pre-test checks failed: {issues}")

    yield checklist


# =============================================================================
# Cleanup Fixtures
# =============================================================================

@pytest.fixture
def cleanup_zapret():
    """Ensure zapret is cleaned up after test."""
    yield
    force_cleanup_zapret()


@pytest.fixture
def cleanup_wireguard():
    """Ensure wireguard is cleaned up after test."""
    yield
    force_cleanup_wireguard()


@pytest.fixture
def cleanup_dns():
    """Ensure DNS is cleaned up after test."""
    yield
    force_cleanup_dns()


@pytest.fixture
def cleanup_byedpi():
    """Ensure ByeDPI is cleaned up after test."""
    yield
    force_cleanup_byedpi()


@pytest.fixture
def cleanup_all():
    """Ensure everything is cleaned up after test."""
    yield
    force_cleanup_all()


# =============================================================================
# Context Manager Fixtures
# =============================================================================

@pytest.fixture
def kill_switch_context():
    """
    Factory fixture for creating kill switch contexts.

    Usage:
        def test_something(kill_switch_context):
            with kill_switch_context(timeout=60, threshold=10) as ks:
                # run risky operations
                pass
    """
    def _create_context(**kwargs) -> KillSwitchContext:
        return KillSwitchContext(**kwargs)

    return _create_context


# =============================================================================
# Service Fixtures
# =============================================================================

@pytest.fixture
def dns_service():
    """Get DNSService instance for testing."""
    from splitwire.services.dns import DNSService
    return DNSService()


@pytest.fixture
def zapret_service():
    """Get ZapretService instance for testing."""
    from splitwire.services.zapret import ZapretService
    return ZapretService()


@pytest.fixture
def wireguard_service():
    """Get WireGuardService instance for testing."""
    from splitwire.services.wireguard import WireGuardService
    return WireGuardService()


@pytest.fixture
def byedpi_service():
    """Get ByeDPIService instance for testing."""
    from splitwire.services.byedpi import ByeDPIService
    return ByeDPIService()


# =============================================================================
# Skip Markers
# =============================================================================

requires_root = pytest.mark.requires_root
requires_internet = pytest.mark.requires_internet
slow = pytest.mark.slow
integration = pytest.mark.integration

phase0 = pytest.mark.phase0
phase1 = pytest.mark.phase1
phase2 = pytest.mark.phase2
phase3 = pytest.mark.phase3
phase4 = pytest.mark.phase4
phase5 = pytest.mark.phase5
phase6 = pytest.mark.phase6
phase7 = pytest.mark.phase7
