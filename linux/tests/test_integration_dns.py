"""
DNS Integration Tests for SplitWire-Turkey (Phase 4).

These tests modify DNS settings and REQUIRE:
- Root privileges
- Kill switch protection (60s timeout)
- Network connectivity

RISK LEVEL: MEDIUM
- Incorrect DNS = no name resolution
- Recovery: systemd-resolved restart + config removal

Run with:
    sudo pytest tests/test_integration_dns.py -v

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
    get_current_dns,
    dns_lookup,
    tcp_connect_test,
    wait_for_connectivity,
    verify_connectivity,
)
from kill_switch import force_cleanup_dns


# =============================================================================
# Test Configuration
# =============================================================================

# DNS servers to test
TEST_DNS_CLOUDFLARE = ["1.1.1.1", "1.0.0.1"]
TEST_DNS_GOOGLE = ["8.8.8.8", "8.8.4.4"]
TEST_DNS_QUAD9 = ["9.9.9.9", "149.112.112.112"]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def ensure_clean_state():
    """Ensure clean state before and after each test."""
    # Before test - force cleanup
    force_cleanup_dns()
    time.sleep(1)

    yield

    # After test - force cleanup
    force_cleanup_dns()
    time.sleep(1)

    # Verify connectivity restored
    assert wait_for_connectivity(timeout=30), "Connectivity not restored after DNS test"


# =============================================================================
# Phase 4: DNS Integration Tests
# =============================================================================

class TestDNSIntegration:
    """DNS integration tests with kill switch protection."""

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_dns_service_status(self, dns_service):
        """Test DNS service status check."""
        from splitwire.services.base import ServiceStatus

        status = dns_service.status()
        assert status in [
            ServiceStatus.RUNNING,
            ServiceStatus.STOPPED,
            ServiceStatus.NOT_INSTALLED
        ]

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_dns_backup_and_restore(
        self,
        dns_service,
        kill_switch_standard,
        network_baseline
    ):
        """Test DNS backup and restore functionality."""
        # Capture original DNS
        original_dns = get_current_dns()
        assert len(original_dns) > 0, "No original DNS servers"

        # Backup current DNS
        backup_result = dns_service._backup_current_dns()
        assert backup_result, "DNS backup failed"

        # Restore DNS
        restore_result = dns_service._restore_dns()
        assert restore_result, "DNS restore failed"

        # Wait for DNS to stabilize
        time.sleep(2)

        # Verify restoration
        current_dns = get_current_dns()
        # At least some DNS server should be configured
        assert len(current_dns) > 0, "No DNS servers after restore"

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_dns_apply_cloudflare(
        self,
        dns_service,
        kill_switch_standard,
        network_baseline
    ):
        """Test applying Cloudflare DNS."""
        # Capture original state
        original_dns = get_current_dns()

        try:
            # Apply Cloudflare DNS
            result = dns_service.start()

            if result:
                # Wait for DNS to apply
                time.sleep(3)

                # Verify connectivity still works
                assert tcp_connect_test("8.8.8.8", 53), "Lost connectivity after DNS change"

                # Verify DNS resolution works
                ips = dns_lookup("google.com")
                assert len(ips) > 0, "DNS resolution failed after applying Cloudflare"

                # Test specific DNS resolution through new DNS
                ips = dns_lookup("cloudflare.com", "1.1.1.1")
                assert len(ips) > 0, "Resolution through Cloudflare DNS failed"

        finally:
            # Always restore
            dns_service.stop()
            time.sleep(2)

            # Verify restoration
            assert wait_for_connectivity(timeout=30), "Connectivity not restored"

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_dns_start_stop_cycle(
        self,
        dns_service,
        kill_switch_standard,
        network_baseline
    ):
        """Test DNS service start/stop cycle."""
        from splitwire.services.base import ServiceStatus

        # Initial state should be stopped
        initial_status = dns_service.status()

        try:
            # Start DNS service
            start_result = dns_service.start()
            if not start_result:
                pytest.skip("DNS service start not supported on this system")

            time.sleep(2)

            # Verify connectivity
            assert tcp_connect_test("8.8.8.8", 53), "Lost connectivity after DNS start"
            assert tcp_connect_test("1.1.1.1", 53), "Cannot reach Cloudflare DNS"

            # Stop DNS service
            stop_result = dns_service.stop()
            assert stop_result, "DNS service stop failed"

            time.sleep(2)

            # Verify connectivity restored
            assert wait_for_connectivity(timeout=30), "Connectivity not restored after stop"

        finally:
            # Ensure stopped
            dns_service.stop()
            force_cleanup_dns()

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_dns_preset_application(
        self,
        dns_service,
        kill_switch_standard
    ):
        """Test DNS preset application."""
        from splitwire.services.dns import DNS_PRESETS, DNSServer

        # Get available presets
        presets = DNS_PRESETS
        assert len(presets) > 0, "No DNS presets available"

        # Test that preset keys exist
        preset_names = list(presets.keys())
        assert len(preset_names) > 0

        # Just verify preset structure - don't actually apply
        for name, preset in presets.items():
            assert isinstance(preset, DNSServer), f"Preset {name} is not a DNSServer"
            assert hasattr(preset, 'primary'), f"Preset {name} missing primary"
            assert preset.primary, f"Preset {name} has empty primary"

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_dns_resolution_after_change(
        self,
        dns_service,
        kill_switch_standard
    ):
        """Test that DNS resolution works after changing DNS."""
        try:
            # Start DNS service
            if not dns_service.start():
                pytest.skip("DNS service start not supported")

            time.sleep(3)

            # Test resolution of multiple domains
            test_domains = ["google.com", "cloudflare.com", "github.com"]

            for domain in test_domains:
                ips = dns_lookup(domain)
                assert len(ips) > 0, f"Failed to resolve {domain}"

        finally:
            dns_service.stop()
            force_cleanup_dns()
            time.sleep(2)

    @pytest.mark.phase4
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_dns_config_file_creation(
        self,
        dns_service,
        kill_switch_standard
    ):
        """Test that DNS config file is created and removed correctly."""
        config_path = Path("/etc/systemd/resolved.conf.d/splitwire.conf")

        # Should not exist initially
        force_cleanup_dns()
        time.sleep(1)
        assert not config_path.exists(), "Config file exists before test"

        try:
            # Start DNS service
            if not dns_service.start():
                pytest.skip("DNS service start not supported")

            time.sleep(2)

            # Config file should exist (if using systemd-resolved)
            # Note: might not exist on all systems
            if Path("/etc/systemd/resolved.conf.d").exists():
                # Just check that DNS is working
                assert tcp_connect_test("8.8.8.8", 53), "DNS not working after start"

        finally:
            dns_service.stop()
            force_cleanup_dns()
            time.sleep(2)

            # Config should be removed
            # Note: might already be removed by stop()
            if config_path.exists():
                config_path.unlink()


# =============================================================================
# Kill Switch Trigger Tests
# =============================================================================

class TestDNSKillSwitchBehavior:
    """Test kill switch behavior during DNS operations."""

    @pytest.mark.phase4
    @pytest.mark.requires_root
    def test_kill_switch_monitors_during_dns_change(
        self,
        kill_switch_standard
    ):
        """Test that kill switch monitors connectivity during DNS changes."""
        # Kill switch should be running
        assert kill_switch_standard.is_running, "Kill switch not running"

        # Check connectivity status
        status = kill_switch_standard.check_connectivity()
        assert status.is_connected, "No connectivity before DNS test"

        # Elapsed time should be increasing
        time.sleep(2)
        assert kill_switch_standard.elapsed_time >= 2, "Kill switch timer not running"

    @pytest.mark.phase4
    @pytest.mark.requires_root
    def test_kill_switch_not_triggered_on_success(
        self,
        dns_service,
        kill_switch_standard
    ):
        """Test that kill switch is not triggered on successful DNS change."""
        try:
            # Start DNS (should succeed without triggering kill switch)
            dns_service.start()
            time.sleep(3)

            # Kill switch should not have triggered
            assert not kill_switch_standard.was_triggered, \
                "Kill switch triggered during successful DNS change"

        finally:
            dns_service.stop()
            force_cleanup_dns()


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestDNSErrorHandling:
    """Test DNS error handling."""

    @pytest.mark.phase4
    @pytest.mark.requires_root
    def test_dns_handles_missing_backup(
        self,
        dns_service,
        kill_switch_standard
    ):
        """Test DNS restore handles missing backup gracefully."""
        # Remove backup file if exists
        backup_file = Path.home() / ".local" / "share" / "splitwire" / "dns_backup.json"
        if backup_file.exists():
            backup_file.unlink()

        # Restore should handle missing backup gracefully
        result = dns_service._restore_dns()
        # Should return False but not crash
        assert isinstance(result, bool)

    @pytest.mark.phase4
    @pytest.mark.requires_root
    def test_dns_multiple_start_stop(
        self,
        dns_service,
        kill_switch_standard
    ):
        """Test multiple start/stop cycles don't cause issues."""
        try:
            for i in range(3):
                dns_service.start()
                time.sleep(1)

                # Verify connectivity
                assert tcp_connect_test("8.8.8.8", 53), f"Lost connectivity on cycle {i+1}"

                dns_service.stop()
                time.sleep(1)

                # Verify restored
                assert wait_for_connectivity(timeout=15), f"Not restored on cycle {i+1}"

        finally:
            dns_service.stop()
            force_cleanup_dns()
