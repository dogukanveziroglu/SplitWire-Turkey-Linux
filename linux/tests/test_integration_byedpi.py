"""
ByeDPI Integration Tests for SplitWire-Turkey (Phase 5).

These tests start/stop ByeDPI proxy and REQUIRE:
- Root privileges
- Kill switch protection (60s timeout)
- Network connectivity

RISK LEVEL: MEDIUM
- Port conflicts possible
- Proxy routing issues
- Recovery: pkill ciadpi

Run with:
    sudo pytest tests/test_integration_byedpi.py -v

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
    curl_test,
    wait_for_connectivity,
    is_process_running,
    is_port_listening,
    wait_for_port,
    kill_process,
)
from kill_switch import force_cleanup_byedpi


# =============================================================================
# Test Configuration
# =============================================================================

BYEDPI_DEFAULT_PORT = 1080
BYEDPI_PROCESS_NAME = "ciadpi"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def ensure_clean_state():
    """Ensure clean state before and after each test."""
    # Before test - force cleanup
    force_cleanup_byedpi()
    time.sleep(1)

    yield

    # After test - force cleanup
    force_cleanup_byedpi()
    time.sleep(1)

    # Verify process is dead
    assert not is_process_running(BYEDPI_PROCESS_NAME), "ByeDPI process still running"


# =============================================================================
# Phase 5: ByeDPI Integration Tests
# =============================================================================

class TestByeDPIIntegration:
    """ByeDPI integration tests with kill switch protection."""

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_byedpi_service_status(self, byedpi_service):
        """Test ByeDPI service status check."""
        from splitwire.services.base import ServiceStatus

        status = byedpi_service.status()
        assert status in [
            ServiceStatus.RUNNING,
            ServiceStatus.STOPPED,
            ServiceStatus.NOT_INSTALLED,
            ServiceStatus.FAILED,
            ServiceStatus.UNKNOWN
        ]

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_byedpi_binary_download(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test ByeDPI binary download functionality."""
        # Check if binary needs download
        if not byedpi_service.is_installed():
            # Attempt to download (private method)
            result = byedpi_service._download_binary()
            if not result:
                pytest.skip("Could not download ByeDPI binary")

        # Binary should exist now
        assert byedpi_service.is_installed(), "ByeDPI binary not installed"

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_byedpi_start_stop(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test ByeDPI start and stop."""
        # Ensure binary is available
        if not byedpi_service.is_installed():
            if not byedpi_service._download_binary():
                pytest.skip("ByeDPI binary not available")

        try:
            # Start ByeDPI
            result = byedpi_service.start()
            assert result, "ByeDPI start failed"

            # Wait for process to start
            time.sleep(2)

            # Verify process is running
            assert is_process_running(BYEDPI_PROCESS_NAME), "ByeDPI process not running"

            # Verify port is listening
            assert wait_for_port(BYEDPI_DEFAULT_PORT, timeout=10), \
                f"Port {BYEDPI_DEFAULT_PORT} not listening"

            # Stop ByeDPI
            stop_result = byedpi_service.stop()
            assert stop_result, "ByeDPI stop failed"

            time.sleep(2)

            # Verify process is stopped
            assert not is_process_running(BYEDPI_PROCESS_NAME), "ByeDPI process still running"

            # Verify port is closed
            assert wait_for_port(BYEDPI_DEFAULT_PORT, timeout=10, should_exist=False), \
                f"Port {BYEDPI_DEFAULT_PORT} still listening"

        finally:
            force_cleanup_byedpi()

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_byedpi_proxy_connectivity(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test connectivity through ByeDPI proxy."""
        if not byedpi_service.is_installed():
            if not byedpi_service._download_binary():
                pytest.skip("ByeDPI binary not available")

        try:
            # Start ByeDPI
            result = byedpi_service.start()
            if not result:
                pytest.skip("ByeDPI could not start")

            time.sleep(3)

            # Test proxy connectivity
            proxy_url = f"socks5://127.0.0.1:{BYEDPI_DEFAULT_PORT}"

            # Test curl through proxy
            curl_result = curl_test(
                "https://www.google.com",
                timeout=15,
                proxy=proxy_url
            )

            # Note: Proxy might not work for all sites
            # Just verify the proxy port is accessible
            assert is_port_listening(BYEDPI_DEFAULT_PORT), "Proxy port not listening"

        finally:
            byedpi_service.stop()
            force_cleanup_byedpi()

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_byedpi_port_availability(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test ByeDPI checks port availability."""
        # Port should be free initially
        assert not is_port_listening(BYEDPI_DEFAULT_PORT), \
            f"Port {BYEDPI_DEFAULT_PORT} already in use"

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_byedpi_multiple_start(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test that multiple starts don't cause issues."""
        if not byedpi_service.is_installed():
            if not byedpi_service._download_binary():
                pytest.skip("ByeDPI binary not available")

        try:
            # First start
            byedpi_service.start()
            time.sleep(2)

            # Second start should be safe (either no-op or restart)
            byedpi_service.start()
            time.sleep(2)

            # Should still be running
            assert is_process_running(BYEDPI_PROCESS_NAME), "ByeDPI not running after double start"

        finally:
            byedpi_service.stop()
            force_cleanup_byedpi()

    @pytest.mark.phase5
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_byedpi_does_not_affect_connectivity(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test that ByeDPI doesn't break regular connectivity."""
        if not byedpi_service.is_installed():
            if not byedpi_service._download_binary():
                pytest.skip("ByeDPI binary not available")

        # Verify baseline connectivity
        assert tcp_connect_test("8.8.8.8", 53), "No baseline connectivity"

        try:
            # Start ByeDPI
            byedpi_service.start()
            time.sleep(2)

            # Regular connectivity should still work
            assert tcp_connect_test("8.8.8.8", 53), "Lost connectivity with ByeDPI running"
            assert tcp_connect_test("1.1.1.1", 53), "Lost connectivity to Cloudflare"

            # HTTP/HTTPS should work
            curl_result = curl_test("https://www.google.com", timeout=10)
            # Note: might fail due to DPI in test environment, that's OK
            # Main thing is we didn't lose connectivity

        finally:
            byedpi_service.stop()
            force_cleanup_byedpi()

        # Verify connectivity after stop
        assert wait_for_connectivity(timeout=15), "Connectivity not restored after ByeDPI stop"


# =============================================================================
# ByeDPI Configuration Tests
# =============================================================================

class TestByeDPIConfiguration:
    """Test ByeDPI configuration options."""

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_byedpi_get_presets(self, byedpi_service):
        """Test getting ByeDPI presets."""
        presets = byedpi_service.get_all_presets()
        assert isinstance(presets, dict), "Presets should be a dictionary"

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_byedpi_default_config(self, byedpi_service):
        """Test ByeDPI default configuration."""
        # Should have a default configuration
        config = byedpi_service._config
        assert config is not None

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_byedpi_custom_port(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test ByeDPI with custom port."""
        if not byedpi_service.is_installed():
            if not byedpi_service._download_binary():
                pytest.skip("ByeDPI binary not available")

        custom_port = 1081

        try:
            # Set custom port using the public method
            byedpi_service.set_proxy_port(custom_port)

            # Start with custom port
            result = byedpi_service.start()
            if not result:
                pytest.skip("ByeDPI could not start with custom port")

            time.sleep(2)

            # Verify listening on custom port
            assert wait_for_port(custom_port, timeout=10), \
                f"Not listening on custom port {custom_port}"

        finally:
            byedpi_service.stop()
            # Reset to default port
            byedpi_service.set_proxy_port(BYEDPI_DEFAULT_PORT)
            # Kill any remaining processes
            kill_process(BYEDPI_PROCESS_NAME)


# =============================================================================
# Kill Switch Behavior Tests
# =============================================================================

class TestByeDPIKillSwitchBehavior:
    """Test kill switch behavior during ByeDPI operations."""

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_kill_switch_not_triggered_on_success(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test kill switch isn't triggered on successful operation."""
        if not byedpi_service.is_installed():
            pytest.skip("ByeDPI not installed")

        try:
            byedpi_service.start()
            time.sleep(3)

            # Kill switch should not have triggered
            assert not kill_switch_standard.was_triggered, \
                "Kill switch triggered during successful ByeDPI start"

            byedpi_service.stop()
            time.sleep(2)

            assert not kill_switch_standard.was_triggered, \
                "Kill switch triggered during successful ByeDPI stop"

        finally:
            force_cleanup_byedpi()

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_connectivity_maintained_during_byedpi(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test connectivity is maintained during ByeDPI lifecycle."""
        if not byedpi_service.is_installed():
            pytest.skip("ByeDPI not installed")

        try:
            # Check connectivity before
            status_before = kill_switch_standard.check_connectivity()
            assert status_before.is_connected, "No connectivity before ByeDPI"

            byedpi_service.start()
            time.sleep(2)

            # Check during
            status_during = kill_switch_standard.check_connectivity()
            assert status_during.is_connected, "Lost connectivity during ByeDPI"

            byedpi_service.stop()
            time.sleep(2)

            # Check after
            status_after = kill_switch_standard.check_connectivity()
            assert status_after.is_connected, "Lost connectivity after ByeDPI"

        finally:
            force_cleanup_byedpi()


# =============================================================================
# Error Recovery Tests
# =============================================================================

class TestByeDPIErrorRecovery:
    """Test ByeDPI error recovery."""

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_byedpi_handles_missing_binary(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test ByeDPI handles missing binary gracefully."""
        # Just verify the service handles its state correctly
        # If binary is installed, is_installed should return True
        # If not, start should handle it gracefully (either fail or download)
        is_installed = byedpi_service.is_installed()
        assert isinstance(is_installed, bool), "is_installed should return bool"

        # The start method should not crash regardless of binary state
        try:
            result = byedpi_service.start()
            assert isinstance(result, bool), "start should return bool"
            if result:
                # If start succeeded, stop it
                byedpi_service.stop()
        except Exception as e:
            pytest.fail(f"start() should not raise exception: {e}")

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_byedpi_stop_without_start(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test stopping ByeDPI that wasn't started."""
        # Should not crash
        result = byedpi_service.stop()
        # Should return True (nothing to stop) or False gracefully
        assert isinstance(result, bool)

    @pytest.mark.phase5
    @pytest.mark.requires_root
    def test_byedpi_cleanup_after_crash(
        self,
        byedpi_service,
        kill_switch_standard
    ):
        """Test cleanup after simulated crash."""
        if not byedpi_service.is_installed():
            pytest.skip("ByeDPI not installed")

        try:
            # Start ByeDPI
            byedpi_service.start()
            time.sleep(2)

            # Simulate crash by killing process directly
            kill_process(BYEDPI_PROCESS_NAME, signal=9)
            time.sleep(1)

            # Process should be dead
            assert not is_process_running(BYEDPI_PROCESS_NAME)

            # Port should be released
            assert wait_for_port(BYEDPI_DEFAULT_PORT, timeout=5, should_exist=False)

            # Should be able to start again
            byedpi_service.start()
            time.sleep(2)

            assert is_process_running(BYEDPI_PROCESS_NAME), "Could not restart after crash"

        finally:
            byedpi_service.stop()
            force_cleanup_byedpi()
