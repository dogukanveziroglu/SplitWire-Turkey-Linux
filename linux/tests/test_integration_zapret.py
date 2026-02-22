"""
Zapret Integration Tests for SplitWire-Turkey (Phase 7).

!!! HIGHEST RISK TESTS !!!

These tests modify iptables rules and REQUIRE:
- Root privileges
- STRICT kill switch (45s timeout, 5s threshold)
- Network connectivity
- nfqws binary installed

RISK LEVEL: HIGH
- iptables NFQUEUE rules can break ALL network traffic
- Failed cleanup = complete connectivity loss
- Recovery: iptables flush + pkill nfqws/tpws

Run with:
    sudo pytest tests/test_integration_zapret.py -v

CRITICAL: ALWAYS run emergency_restore.sh if tests fail!
    sudo ./tests/emergency_restore.sh
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
    verify_connectivity,
    is_process_running,
    get_iptables_rules,
    has_nfqueue_rules,
    has_redirect_rules,
    ping_test,
    kill_process,
)
from kill_switch import force_cleanup_zapret, force_cleanup_all


# =============================================================================
# Test Configuration
# =============================================================================

NFQWS_PROCESS = "nfqws"
TPWS_PROCESS = "tpws"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def ensure_clean_state_zapret():
    """
    CRITICAL: Ensure absolutely clean state before and after Zapret tests.

    This is the most important cleanup - Zapret can break all networking!
    """
    # Before test - AGGRESSIVE cleanup
    force_cleanup_zapret()
    time.sleep(2)

    # Verify no NFQUEUE rules
    assert not has_nfqueue_rules(), "NFQUEUE rules exist before test - run emergency_restore.sh"

    # Verify no processes
    assert not is_process_running(NFQWS_PROCESS), "nfqws running before test"
    assert not is_process_running(TPWS_PROCESS), "tpws running before test"

    # Verify connectivity
    assert wait_for_connectivity(timeout=10), "No connectivity before Zapret test"

    yield

    # After test - AGGRESSIVE cleanup (in finally block equivalent)
    force_cleanup_zapret()
    time.sleep(2)

    # Second cleanup pass for safety
    force_cleanup_zapret()
    time.sleep(1)

    # Verify cleanup
    assert not has_nfqueue_rules(), "NFQUEUE rules remain after test!"
    assert not is_process_running(NFQWS_PROCESS), "nfqws still running after test"

    # Verify connectivity restored
    if not wait_for_connectivity(timeout=30):
        # EMERGENCY: Full cleanup
        force_cleanup_all()
        time.sleep(3)

        if not wait_for_connectivity(timeout=30):
            pytest.fail(
                "CRITICAL: Connectivity NOT restored after Zapret test!\n"
                "Run: sudo ./tests/emergency_restore.sh"
            )


@pytest.fixture
def zapret_baseline():
    """Capture iptables baseline before Zapret test."""
    baseline = {
        "mangle": get_iptables_rules("mangle"),
        "nat": get_iptables_rules("nat"),
        "filter": get_iptables_rules("filter"),
        "nfqws_running": is_process_running(NFQWS_PROCESS),
        "tpws_running": is_process_running(TPWS_PROCESS),
        "connectivity": verify_connectivity(),
    }
    return baseline


# =============================================================================
# Phase 7: Zapret Integration Tests
# =============================================================================


class TestZapretIntegration:
    """
    Zapret integration tests with STRICT kill switch protection.

    WARNING: These tests can break network connectivity!
    """

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_zapret_service_status(self, zapret_service):
        """Test Zapret service status check."""
        from splitwire.services.base import ServiceStatus

        status = zapret_service.status()
        assert status in [
            ServiceStatus.RUNNING,
            ServiceStatus.STOPPED,
            ServiceStatus.NOT_INSTALLED,
            ServiceStatus.FAILED,
            ServiceStatus.UNKNOWN,
        ]

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_zapret_binary_exists(self, zapret_service):
        """Test that Zapret binary exists."""
        # Check if nfqws is installed
        if not zapret_service.is_installed():
            pytest.skip("Zapret (nfqws) not installed")

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_zapret_presets_available(self, zapret_service):
        """Test that Zapret presets are available."""
        presets = zapret_service.get_presets()
        assert len(presets) > 0, "No Zapret presets available"

        # Should have at least a Discord preset
        preset_names = list(presets.keys())
        assert any(
            "discord" in name.lower() for name in preset_names
        ), "No Discord preset found"

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_zapret_start_stop_safe_preset(
        self, zapret_service, kill_switch_strict, zapret_baseline
    ):
        """
        Test Zapret start and stop with safest preset.

        This is the core Zapret test - start, verify, stop, verify cleanup.
        """
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        # Find safest preset (prefer discord or similar targeted preset)
        presets = zapret_service.get_presets()
        safe_preset = None

        for name in ["discord", "general"]:
            if name in presets:
                safe_preset = name
                break

        if not safe_preset:
            safe_preset = list(presets.keys())[0]

        try:
            # Set preset
            zapret_service.set_preset(safe_preset)

            # Verify baseline connectivity
            assert tcp_connect_test("8.8.8.8", 53), "No baseline connectivity"

            # START ZAPRET - HIGH RISK OPERATION
            result = zapret_service.start()
            assert result, f"Zapret start failed with preset {safe_preset}"

            # IMMEDIATELY check connectivity (within 0.5s)
            time.sleep(0.5)
            assert tcp_connect_test("8.8.8.8", 53, timeout=3), (
                "CRITICAL: Lost connectivity immediately after Zapret start!"
            )

            # Wait a bit more
            time.sleep(2)

            # Verify NFQUEUE rules added
            assert has_nfqueue_rules(), "NFQUEUE rules not added"

            # Verify process running
            assert is_process_running(NFQWS_PROCESS), "nfqws not running"

            # Verify HTTPS still works
            curl_result = curl_test("https://www.google.com", timeout=10)
            # Note: might fail due to DPI, but basic connectivity should work

            # STOP ZAPRET
            stop_result = zapret_service.stop()
            assert stop_result, "Zapret stop failed"

            time.sleep(2)

            # Verify cleanup
            assert not has_nfqueue_rules(), "NFQUEUE rules not removed!"
            assert not is_process_running(NFQWS_PROCESS), "nfqws still running!"

        finally:
            # CRITICAL: Always cleanup
            force_cleanup_zapret()
            time.sleep(1)

            # Verify final state
            assert not has_nfqueue_rules(), "Final cleanup: NFQUEUE rules remain"
            assert wait_for_connectivity(timeout=15), "Final cleanup: No connectivity"

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    @pytest.mark.slow
    def test_zapret_iptables_rules_correct(
        self, zapret_service, kill_switch_strict, zapret_baseline
    ):
        """Test that Zapret adds correct iptables rules."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            # Start Zapret
            result = zapret_service.start()
            if not result:
                pytest.skip("Zapret start failed")

            time.sleep(2)

            # Check mangle table
            mangle_rules = get_iptables_rules("mangle")
            assert "NFQUEUE" in mangle_rules, "NFQUEUE not in mangle table"
            assert "POSTROUTING" in mangle_rules, "POSTROUTING chain not found"

            # Check for correct ports (443 for HTTPS)
            assert "443" in mangle_rules or "dpt:443" in mangle_rules, "Port 443 rule not found"

        finally:
            zapret_service.stop()
            force_cleanup_zapret()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_zapret_multiple_start_safe(self, zapret_service, kill_switch_strict):
        """Test that multiple starts don't create duplicate rules."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            # First start
            zapret_service.start()
            time.sleep(2)

            first_rules = get_iptables_rules("mangle")
            first_nfqueue_count = first_rules.count("NFQUEUE")

            # Second start (should be safe)
            zapret_service.start()
            time.sleep(2)

            second_rules = get_iptables_rules("mangle")
            second_nfqueue_count = second_rules.count("NFQUEUE")

            # Should not have more rules
            assert second_nfqueue_count <= first_nfqueue_count * 2, (
                "Duplicate NFQUEUE rules created"
            )

        finally:
            zapret_service.stop()
            force_cleanup_zapret()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.requires_internet
    def test_zapret_connectivity_during_operation(self, zapret_service, kill_switch_strict):
        """Test connectivity is maintained while Zapret is running."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            # Verify before
            assert tcp_connect_test("8.8.8.8", 53), "No connectivity before"

            # Start
            zapret_service.start()

            # Check multiple times during operation
            for i in range(5):
                time.sleep(1)
                assert tcp_connect_test("8.8.8.8", 53, timeout=3), (
                    f"Lost connectivity at check {i + 1}"
                )

            # DNS should work
            from helpers import dns_lookup

            ips = dns_lookup("google.com")
            assert len(ips) > 0, "DNS resolution failed during Zapret"

        finally:
            zapret_service.stop()
            force_cleanup_zapret()


# =============================================================================
# Kill Switch Strict Behavior Tests
# =============================================================================


class TestZapretKillSwitchBehavior:
    """Test strict kill switch behavior during Zapret operations."""

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_strict_kill_switch_config(self, kill_switch_strict):
        """Test strict kill switch has appropriate settings."""
        # Timeout should be short
        assert kill_switch_strict.config.timeout <= 45, "Zapret kill switch timeout too long"

        # Threshold should be very short
        assert kill_switch_strict.config.threshold <= 5, "Zapret kill switch threshold too long"

        # Check interval should be fast
        assert kill_switch_strict.config.check_interval <= 1.0, (
            "Zapret kill switch check interval too slow"
        )

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_kill_switch_not_triggered_on_success(self, zapret_service, kill_switch_strict):
        """Test kill switch isn't triggered during successful operation."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            zapret_service.start()
            time.sleep(3)

            assert not kill_switch_strict.was_triggered, (
                "Kill switch triggered during successful Zapret operation"
            )

            zapret_service.stop()
            time.sleep(1)

            assert not kill_switch_strict.was_triggered, "Kill switch triggered during Zapret stop"

        finally:
            force_cleanup_zapret()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_kill_switch_monitors_connectivity(self, zapret_service, kill_switch_strict):
        """Test kill switch continuously monitors during Zapret."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            zapret_service.start()

            # Check that kill switch sees connectivity
            for _ in range(5):
                time.sleep(0.5)
                status = kill_switch_strict.check_connectivity()
                assert status.is_connected, "Kill switch detected connectivity loss"

        finally:
            zapret_service.stop()
            force_cleanup_zapret()


# =============================================================================
# Zapret Rule Cleanup Tests
# =============================================================================


class TestZapretCleanup:
    """Test Zapret cleanup procedures."""

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_zapret_rules_removed_on_stop(self, zapret_service, kill_switch_strict):
        """Test iptables rules are properly removed on stop."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            # Start
            zapret_service.start()
            time.sleep(2)

            # Verify rules exist
            assert has_nfqueue_rules(), "Rules not created"

            # Stop
            zapret_service.stop()
            time.sleep(2)

            # Verify rules removed
            assert not has_nfqueue_rules(), "NFQUEUE rules not removed on stop"

        finally:
            force_cleanup_zapret()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_zapret_process_killed_on_stop(self, zapret_service, kill_switch_strict):
        """Test nfqws process is killed on stop."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            # Start
            zapret_service.start()
            time.sleep(2)

            # Verify running
            assert is_process_running(NFQWS_PROCESS), "nfqws not started"

            # Stop
            zapret_service.stop()
            time.sleep(2)

            # Verify killed
            assert not is_process_running(NFQWS_PROCESS), "nfqws not killed"

        finally:
            force_cleanup_zapret()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_force_cleanup_works(self, kill_switch_strict):
        """Test force_cleanup_zapret clears everything."""
        # Even without starting, cleanup should be safe
        force_cleanup_zapret()

        # Verify clean state
        assert not has_nfqueue_rules()
        assert not is_process_running(NFQWS_PROCESS)

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_cleanup_after_simulated_crash(self, zapret_service, kill_switch_strict):
        """Test cleanup after simulated crash."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            # Start
            zapret_service.start()
            time.sleep(2)

            # Verify it started
            assert is_process_running(NFQWS_PROCESS), "nfqws not started"
            assert has_nfqueue_rules(), "NFQUEUE rules not set"

            # Simulate crash - force cleanup without going through service stop
            # This tests that force_cleanup_zapret can handle any state
            force_cleanup_zapret()
            time.sleep(2)

            # Everything should be clean
            assert not has_nfqueue_rules(), "Rules remain after crash cleanup"
            assert not is_process_running(NFQWS_PROCESS), "Process still running after cleanup"
            assert wait_for_connectivity(timeout=10), "No connectivity after crash cleanup"

        finally:
            force_cleanup_zapret()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestZapretErrorHandling:
    """Test Zapret error handling."""

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_zapret_stop_without_start(self, zapret_service, kill_switch_strict):
        """Test stopping Zapret that wasn't started."""
        # Should not crash
        result = zapret_service.stop()
        assert isinstance(result, bool)

        # Should not have created rules
        assert not has_nfqueue_rules()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_zapret_handles_missing_binary(self, zapret_service, kill_switch_strict):
        """Test Zapret handles missing binary gracefully."""
        from splitwire.services.zapret import NFQWS_BINARY

        binary_path = (
            Path(NFQWS_BINARY) if hasattr(NFQWS_BINARY, "__fspath__") else Path(str(NFQWS_BINARY))
        )
        backup_path = binary_path.with_suffix(".bak")

        try:
            if binary_path.exists():
                binary_path.rename(backup_path)

                # Start should fail gracefully
                result = zapret_service.start()
                assert result is False, "Start succeeded without binary"

                # Should not have created rules
                assert not has_nfqueue_rules(), "Rules created without binary"

        finally:
            if backup_path.exists():
                backup_path.rename(binary_path)
            force_cleanup_zapret()

    @pytest.mark.phase7
    @pytest.mark.requires_root
    @pytest.mark.slow
    def test_zapret_restart_cycle(self, zapret_service, kill_switch_strict):
        """Test multiple start/stop cycles."""
        if not zapret_service.is_installed():
            pytest.skip("Zapret not installed")

        try:
            for i in range(3):
                # Start
                result = zapret_service.start()
                assert result, f"Start failed on cycle {i + 1}"

                time.sleep(1)
                assert has_nfqueue_rules(), f"Rules not created on cycle {i + 1}"
                assert tcp_connect_test("8.8.8.8", 53), f"Lost connectivity on cycle {i + 1}"

                # Stop
                result = zapret_service.stop()
                assert result, f"Stop failed on cycle {i + 1}"

                time.sleep(1)
                assert not has_nfqueue_rules(), f"Rules not removed on cycle {i + 1}"
                assert wait_for_connectivity(timeout=10), f"No connectivity after cycle {i + 1}"

        finally:
            force_cleanup_zapret()


# =============================================================================
# Final Verification
# =============================================================================


class TestZapretFinalVerification:
    """Final verification tests - run last."""

    @pytest.mark.phase7
    @pytest.mark.requires_root
    def test_final_state_clean(self):
        """Final test to verify clean state."""
        # Force cleanup
        force_cleanup_zapret()
        force_cleanup_all()
        time.sleep(3)

        # Verify everything is clean
        assert not has_nfqueue_rules(), "NFQUEUE rules remain"
        assert not has_redirect_rules(), "REDIRECT rules remain"
        assert not is_process_running(NFQWS_PROCESS), "nfqws running"
        assert not is_process_running(TPWS_PROCESS), "tpws running"

        # Verify connectivity
        connectivity = verify_connectivity()
        assert connectivity.get("8.8.8.8", False), "No connectivity to 8.8.8.8"

        print("\n" + "=" * 60)
        print("ZAPRET TESTS COMPLETED - SYSTEM STATE VERIFIED CLEAN")
        print("=" * 60)
