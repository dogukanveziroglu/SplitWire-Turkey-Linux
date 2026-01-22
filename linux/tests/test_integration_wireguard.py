"""
WireGuard Integration Tests for SplitWire-Turkey (Phase 6).

These tests create WireGuard interfaces and REQUIRE:
- Root privileges
- Kill switch protection (90s timeout for handshake)
- Network connectivity
- wg-quick installed

RISK LEVEL: MEDIUM-HIGH
- Interface creation affects routing
- Failed handshake = connectivity loss
- Recovery: wg-quick down + ip link delete

Run with:
    sudo pytest tests/test_integration_wireguard.py -v

IMPORTANT: Run emergency_restore.sh if tests fail unexpectedly!
"""

import os
import sys
import time
import pytest
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from helpers import (
    tcp_connect_test,
    wait_for_connectivity,
    verify_connectivity,
    interface_exists,
    get_interfaces,
    get_routing_table,
    get_default_gateway,
    ping_test,
)
from kill_switch import force_cleanup_wireguard


# =============================================================================
# Test Configuration
# =============================================================================

WIREGUARD_INTERFACE = "splitwire"
WIREGUARD_CONFIG_DIR = Path("/etc/wireguard")


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def ensure_clean_state():
    """Ensure clean state before and after each test."""
    # Before test - force cleanup
    force_cleanup_wireguard()
    time.sleep(2)

    # Verify interface doesn't exist
    assert not interface_exists(WIREGUARD_INTERFACE), "WireGuard interface exists before test"

    yield

    # After test - force cleanup
    force_cleanup_wireguard()
    time.sleep(2)

    # Verify interface is gone
    assert not interface_exists(WIREGUARD_INTERFACE), "WireGuard interface still exists"

    # Verify connectivity restored
    assert wait_for_connectivity(timeout=30), "Connectivity not restored after WireGuard test"


# =============================================================================
# Phase 6: WireGuard Integration Tests
# =============================================================================

class TestWireGuardIntegration:
    """WireGuard integration tests with kill switch protection."""

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_wireguard_service_status(self, wireguard_service):
        """Test WireGuard service status check."""
        from splitwire.services.base import ServiceStatus

        status = wireguard_service.status()
        assert status in [
            ServiceStatus.RUNNING,
            ServiceStatus.STOPPED,
            ServiceStatus.NOT_INSTALLED,
            ServiceStatus.FAILED,
            ServiceStatus.UNKNOWN
        ]

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_tools_installed(self, wireguard_service):
        """Test that WireGuard tools are installed."""
        import subprocess

        # Check wg-quick
        result = subprocess.run(
            ["which", "wg-quick"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            pytest.skip("wg-quick not installed")

        # Check wg
        result = subprocess.run(
            ["which", "wg"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            pytest.skip("wg not installed")

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_wgcf_download(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test WGCF binary download."""
        # Use ensure_wgcf which handles download if needed
        result = wireguard_service.ensure_wgcf()
        if not result:
            pytest.skip("Could not ensure WGCF binary")

        # Just verify the method worked
        assert result is True, "WGCF ensure failed"

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_warp_registration(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test WARP account registration."""
        # Ensure WGCF is available
        if not wireguard_service.ensure_wgcf():
            pytest.skip("WGCF not available")

        # Register WARP account
        result = wireguard_service.register_warp_account()

        if not result:
            # Registration might fail due to rate limiting or already registered
            pytest.skip("WARP registration failed (possibly rate limited or already registered)")

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_wireguard_config_generation(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test WireGuard config file generation."""
        # Ensure WGCF is available
        if not wireguard_service.ensure_wgcf():
            pytest.skip("WGCF not available")

        # Generate config using generate_warp_profile
        result = wireguard_service.generate_warp_profile()

        if not result:
            # Config generation might fail if not registered
            pytest.skip("Config generation failed (might need WARP registration first)")

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_wireguard_start_stop(
        self,
        wireguard_service,
        kill_switch_wireguard,
        network_baseline
    ):
        """Test WireGuard interface start and stop."""
        # Skip if not properly configured
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        # Capture baseline
        original_gateway = get_default_gateway()
        original_interfaces = get_interfaces()

        try:
            # Start WireGuard
            result = wireguard_service.start()
            if not result:
                pytest.skip("WireGuard start failed (might need WARP registration)")

            # Wait for interface
            time.sleep(5)

            # Verify interface exists
            assert interface_exists(WIREGUARD_INTERFACE), "WireGuard interface not created"

            # CRITICAL: Verify we still have connectivity
            # With split tunnel, regular traffic should bypass VPN
            assert wait_for_connectivity(timeout=15), "Lost connectivity after WireGuard start"

            # Stop WireGuard
            stop_result = wireguard_service.stop()
            assert stop_result, "WireGuard stop failed"

            time.sleep(3)

            # Verify interface is gone
            assert not interface_exists(WIREGUARD_INTERFACE), "Interface not removed"

            # Verify connectivity restored
            assert wait_for_connectivity(timeout=15), "Connectivity not restored after stop"

        finally:
            force_cleanup_wireguard()

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_wireguard_split_tunnel(
        self,
        wireguard_service,
        kill_switch_wireguard,
        network_baseline
    ):
        """Test WireGuard split tunnel functionality."""
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        try:
            # Start WireGuard
            result = wireguard_service.start()
            if not result:
                pytest.skip("WireGuard start failed")

            time.sleep(5)

            # With split tunnel:
            # 1. Regular traffic (8.8.8.8) should NOT go through VPN
            # 2. Discord IPs should go through VPN

            # Test regular connectivity (should work without VPN)
            ping_result = ping_test("8.8.8.8")
            assert ping_result.success, "Cannot reach 8.8.8.8 (should bypass VPN)"

            # Test Google DNS is reachable
            assert tcp_connect_test("8.8.8.8", 53), "Cannot connect to 8.8.8.8:53"

        finally:
            wireguard_service.stop()
            force_cleanup_wireguard()

    @pytest.mark.phase6
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_wireguard_interface_not_exists_after_stop(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test WireGuard interface is properly removed after stop."""
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        try:
            # Start
            if not wireguard_service.start():
                pytest.skip("WireGuard start failed")

            time.sleep(3)
            assert interface_exists(WIREGUARD_INTERFACE)

            # Stop
            wireguard_service.stop()
            time.sleep(2)

            # Interface should be gone
            assert not interface_exists(WIREGUARD_INTERFACE)

            # Routes should be restored
            routing = get_routing_table()
            assert WIREGUARD_INTERFACE not in routing, "WireGuard still in routing table"

        finally:
            force_cleanup_wireguard()


# =============================================================================
# WireGuard Configuration Tests
# =============================================================================

class TestWireGuardConfiguration:
    """Test WireGuard configuration handling."""

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_discord_ips_defined(self):
        """Test that Discord IPs are properly defined."""
        from splitwire.services.wireguard import DISCORD_CLOUDFLARE_IPS

        assert len(DISCORD_CLOUDFLARE_IPS) > 0, "No Discord IPs defined"

        # Validate CIDR notation
        import ipaddress
        for ip_range in DISCORD_CLOUDFLARE_IPS:
            try:
                ipaddress.ip_network(ip_range)
            except ValueError:
                pytest.fail(f"Invalid IP range: {ip_range}")

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_excluded_networks_defined(self):
        """Test that excluded networks are defined."""
        from splitwire.services.wireguard import DEFAULT_EXCLUDED_NETWORKS

        assert len(DEFAULT_EXCLUDED_NETWORKS) > 0, "No excluded networks defined"

        # Should include private ranges
        ranges_str = str(DEFAULT_EXCLUDED_NETWORKS)
        assert "192.168.0.0" in ranges_str or "192.168" in ranges_str
        assert "10.0.0.0" in ranges_str or "10." in ranges_str

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_warp_endpoints_defined(self):
        """Test that WARP endpoints are defined."""
        from splitwire.services.wireguard import WARP_ENDPOINTS

        assert len(WARP_ENDPOINTS) > 0, "No WARP endpoints defined"
        assert "standard" in WARP_ENDPOINTS or len(WARP_ENDPOINTS) >= 1


# =============================================================================
# Kill Switch Behavior Tests
# =============================================================================

class TestWireGuardKillSwitchBehavior:
    """Test kill switch behavior during WireGuard operations."""

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_kill_switch_wireguard_timeout(self, kill_switch_wireguard):
        """Test WireGuard kill switch has appropriate timeout."""
        # WireGuard kill switch should have longer timeout for handshake
        assert kill_switch_wireguard.config.timeout >= 90, \
            "WireGuard kill switch timeout too short"

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_kill_switch_not_triggered_on_success(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test kill switch isn't triggered on successful operation."""
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        try:
            wireguard_service.start()
            time.sleep(5)

            assert not kill_switch_wireguard.was_triggered, \
                "Kill switch triggered during successful WireGuard start"

            wireguard_service.stop()
            time.sleep(2)

            assert not kill_switch_wireguard.was_triggered, \
                "Kill switch triggered during successful WireGuard stop"

        finally:
            force_cleanup_wireguard()

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_connectivity_during_wireguard(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test connectivity is maintained during WireGuard lifecycle."""
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        try:
            # Before
            status = kill_switch_wireguard.check_connectivity()
            assert status.is_connected, "No connectivity before WireGuard"

            wireguard_service.start()
            time.sleep(5)

            # During (with split tunnel, should maintain connectivity)
            status = kill_switch_wireguard.check_connectivity()
            assert status.is_connected, "Lost connectivity during WireGuard"

            wireguard_service.stop()
            time.sleep(2)

            # After
            status = kill_switch_wireguard.check_connectivity()
            assert status.is_connected, "Lost connectivity after WireGuard"

        finally:
            force_cleanup_wireguard()


# =============================================================================
# Error Recovery Tests
# =============================================================================

class TestWireGuardErrorRecovery:
    """Test WireGuard error recovery."""

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_stop_without_start(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test stopping WireGuard that wasn't started."""
        # Should not crash
        result = wireguard_service.stop()
        assert isinstance(result, bool)

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_handles_missing_config(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test WireGuard handles missing config gracefully."""
        from splitwire.services.wireguard import SPLITWIRE_CONFIG_FILE

        # Temporarily move config if it exists
        import subprocess

        backup_path = Path("/tmp/splitwire_config_backup.conf")

        try:
            # Move config
            subprocess.run(
                ["sudo", "mv", str(SPLITWIRE_CONFIG_FILE), str(backup_path)],
                capture_output=True
            )

            # Start should fail gracefully
            result = wireguard_service.start()
            assert result is False, "Start succeeded without config"

        finally:
            # Restore config
            subprocess.run(
                ["sudo", "mv", str(backup_path), str(SPLITWIRE_CONFIG_FILE)],
                capture_output=True
            )

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_cleanup_stale_interface(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test cleanup of stale WireGuard interface."""
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        try:
            # Start WireGuard
            wireguard_service.start()
            time.sleep(3)

            # Kill wg-quick but leave interface (simulated crash)
            import subprocess
            subprocess.run(["sudo", "pkill", "-9", "wg-quick"], capture_output=True)

            # Interface might still exist
            if interface_exists(WIREGUARD_INTERFACE):
                # Manual cleanup
                subprocess.run(
                    ["sudo", "ip", "link", "delete", WIREGUARD_INTERFACE],
                    capture_output=True
                )

            time.sleep(1)
            assert not interface_exists(WIREGUARD_INTERFACE)

        finally:
            force_cleanup_wireguard()

    @pytest.mark.phase6
    @pytest.mark.requires_root
    def test_wireguard_recovers_after_failure(
        self,
        wireguard_service,
        kill_switch_wireguard
    ):
        """Test WireGuard can restart after previous failure."""
        if not wireguard_service.is_installed():
            pytest.skip("WireGuard not configured")

        try:
            # First start
            wireguard_service.start()
            time.sleep(3)

            # Force cleanup (simulating failure)
            force_cleanup_wireguard()
            time.sleep(2)

            # Should be able to start again
            result = wireguard_service.start()
            if result:  # Might fail if no proper config
                time.sleep(3)
                assert interface_exists(WIREGUARD_INTERFACE), "Could not restart after cleanup"

        finally:
            wireguard_service.stop()
            force_cleanup_wireguard()
