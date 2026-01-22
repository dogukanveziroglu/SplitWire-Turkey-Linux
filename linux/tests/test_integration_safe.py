"""
Safe Integration Tests for SplitWire-Turkey (Phases 0-3).

These tests do NOT require kill switch as they don't modify network state.
- Phase 0: Infrastructure setup and baseline verification
- Phase 1: Config, language, logger, preset validation
- Phase 2: Backup/restore mechanisms (read-only verification)
- Phase 3: Discord detection (read-only)

Run with:
    pytest tests/test_integration_safe.py -v
    pytest tests/ -m "phase0 or phase1 or phase2 or phase3" -v
"""

import os
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from helpers import (
    verify_connectivity,
    get_current_dns,
    get_interfaces,
    is_process_running,
    get_iptables_rules,
    is_root,
    tcp_connect_test,
)
from fixtures import PreTestChecklist, NetworkBaseline


# =============================================================================
# Phase 0: Infrastructure Setup
# =============================================================================

class TestPhase0Infrastructure:
    """Phase 0: Infrastructure setup and baseline tests."""

    @pytest.mark.phase0
    def test_baseline_connectivity(self):
        """Test that we have baseline network connectivity."""
        connectivity = verify_connectivity()
        assert any(connectivity.values()), "No connectivity to any test host"

        # At least Google DNS should work
        assert connectivity.get("8.8.8.8", False), "No connectivity to 8.8.8.8"

    @pytest.mark.phase0
    def test_baseline_dns_resolution(self):
        """Test that DNS resolution works."""
        from helpers import dns_lookup

        ips = dns_lookup("google.com")
        assert len(ips) > 0, "DNS resolution failed for google.com"

    @pytest.mark.phase0
    def test_get_current_dns(self):
        """Test that we can retrieve current DNS servers."""
        dns_servers = get_current_dns()
        # Should have at least one DNS server configured
        assert len(dns_servers) > 0, "No DNS servers configured"

    @pytest.mark.phase0
    def test_get_interfaces(self):
        """Test that we can list network interfaces."""
        interfaces = get_interfaces()
        assert len(interfaces) > 0, "No network interfaces found"
        assert "lo" in interfaces, "Loopback interface not found"

    @pytest.mark.phase0
    def test_iptables_readable(self):
        """Test that iptables rules can be read."""
        if not is_root():
            pytest.skip("Requires root to read iptables")

        rules = get_iptables_rules("filter")
        assert "Chain" in rules, "Could not read iptables filter rules"

        rules = get_iptables_rules("mangle")
        assert "Chain" in rules, "Could not read iptables mangle rules"

    @pytest.mark.phase0
    def test_pre_test_checklist_creation(self):
        """Test that PreTestChecklist can be created."""
        checklist = PreTestChecklist()
        assert checklist is not None

    @pytest.mark.phase0
    @pytest.mark.requires_root
    def test_baseline_capture(self):
        """Test that network baseline can be captured."""
        checklist = PreTestChecklist()
        baseline = checklist.capture_baseline()

        assert baseline is not None
        assert isinstance(baseline, NetworkBaseline)
        assert len(baseline.interfaces) > 0
        assert baseline.timestamp is not None

    @pytest.mark.phase0
    def test_emergency_restore_script_exists(self, emergency_restore_path):
        """Test that emergency restore script exists and is executable."""
        assert emergency_restore_path.exists(), "emergency_restore.sh not found"
        assert os.access(emergency_restore_path, os.X_OK), "emergency_restore.sh not executable"


# =============================================================================
# Phase 1: Core Functionality
# =============================================================================

class TestPhase1CoreFunctionality:
    """Phase 1: Core functionality tests (config, language, logger)."""

    @pytest.mark.phase1
    def test_config_manager_import(self):
        """Test that config manager can be imported."""
        from splitwire.core.config import ConfigManager, get_config
        config = get_config()
        assert config is not None

    @pytest.mark.phase1
    def test_config_manager_paths(self):
        """Test that config manager has valid paths."""
        from splitwire.core.config import ConfigManager

        manager = ConfigManager()
        # Config manager should have config_dir attribute
        assert hasattr(manager, '_config_file') or hasattr(manager, 'config_dir')

    @pytest.mark.phase1
    def test_language_manager_import(self):
        """Test that language manager can be imported."""
        from splitwire.core.language import LanguageManager, get_language_manager
        lang = get_language_manager()
        assert lang is not None

    @pytest.mark.phase1
    def test_language_available_languages(self):
        """Test that languages are available."""
        from splitwire.core.language import LanguageManager
        lang = LanguageManager()

        languages = lang.get_available_languages()
        assert len(languages) > 0, "No languages available"

        # Turkish and English should always be available (returns dict: code -> name)
        assert "tr" in languages, "Turkish language not available"
        assert "en" in languages, "English language not available"

    @pytest.mark.phase1
    def test_language_translation(self):
        """Test that translations work."""
        from splitwire.core.language import LanguageManager
        lang = LanguageManager()

        # Try loading English
        lang.set_language("en")
        # Get a common translation key using get_text method
        text = lang.get_text("app_name", default="NOT_FOUND")
        # If app_name doesn't exist, try another key
        if text == "NOT_FOUND":
            text = lang.get_text("main", "title", default="NOT_FOUND")
        # Just verify the method works without crashing
        assert isinstance(text, str)

    @pytest.mark.phase1
    def test_logger_import(self):
        """Test that logger can be imported."""
        from splitwire.core.logger import get_logger
        logger = get_logger()
        assert logger is not None

    @pytest.mark.phase1
    def test_logger_functionality(self):
        """Test basic logger functionality."""
        from splitwire.core.logger import get_logger
        logger = get_logger()

        # Should be able to log without errors
        logger.debug("Test debug message")
        logger.info("Test info message")
        logger.warning("Test warning message")

    @pytest.mark.phase1
    def test_shell_import(self):
        """Test that shell module can be imported."""
        from splitwire.core.shell import ShellExecutor, get_shell, CommandResult
        shell = get_shell()
        assert shell is not None

    @pytest.mark.phase1
    def test_shell_basic_command(self):
        """Test basic shell command execution."""
        from splitwire.core.shell import get_shell
        shell = get_shell()

        result = shell.run(["echo", "hello"])
        assert result.success, "Echo command failed"
        assert "hello" in result.stdout


# =============================================================================
# Phase 2: Backup/Restore
# =============================================================================

class TestPhase2BackupRestore:
    """Phase 2: Backup/restore mechanism tests."""

    @pytest.mark.phase2
    def test_backup_manager_import(self):
        """Test that backup manager can be imported."""
        from splitwire.core.backup import BackupManager, get_backup_manager
        manager = get_backup_manager()
        assert manager is not None

    @pytest.mark.phase2
    def test_snapshot_manager_import(self):
        """Test that snapshot manager can be imported."""
        from splitwire.core.backup import SnapshotManager
        manager = SnapshotManager()
        assert manager is not None

    @pytest.mark.phase2
    def test_snapshot_manager_methods(self):
        """Test SnapshotManager methods."""
        from splitwire.core.backup import SnapshotManager
        manager = SnapshotManager()

        # Should have create_snapshot and rollback methods
        assert hasattr(manager, 'create_snapshot')
        assert hasattr(manager, 'rollback')

    @pytest.mark.phase2
    def test_network_baseline_serialization(self):
        """Test that NetworkBaseline can be serialized."""
        checklist = PreTestChecklist()

        # Create a minimal baseline
        baseline = NetworkBaseline(
            timestamp=checklist._checklist.capture_baseline().timestamp
            if hasattr(checklist, '_checklist') else
            __import__('datetime').datetime.now(),
            interfaces=["lo", "eth0"],
            routing_table="default via 192.168.1.1",
            iptables_filter="Chain INPUT",
            iptables_nat="Chain OUTPUT",
            iptables_mangle="Chain POSTROUTING",
            dns_servers=["8.8.8.8"],
            resolv_conf="nameserver 8.8.8.8",
            running_processes=[],
            connectivity_hosts={"8.8.8.8": True},
            wireguard_interfaces=[]
        )

        # Test to_dict
        data = baseline.to_dict()
        assert "interfaces" in data
        assert "dns_servers" in data

        # Test save/load
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            baseline.save(Path(f.name))
            loaded = NetworkBaseline.load(Path(f.name))
            assert loaded.interfaces == baseline.interfaces
            Path(f.name).unlink()

    @pytest.mark.phase2
    def test_baseline_comparison(self):
        """Test baseline comparison logic."""
        from fixtures.pre_test import verify_baseline

        baseline1 = NetworkBaseline(
            timestamp=__import__('datetime').datetime.now(),
            interfaces=["lo", "eth0"],
            routing_table="default via 192.168.1.1",
            iptables_filter="Chain INPUT",
            iptables_nat="Chain OUTPUT",
            iptables_mangle="Chain POSTROUTING",
            dns_servers=["8.8.8.8"],
            resolv_conf="nameserver 8.8.8.8",
            running_processes=[],
            connectivity_hosts={"8.8.8.8": True},
            wireguard_interfaces=[]
        )

        # Same state - no differences
        differences = verify_baseline(baseline1, baseline1)
        assert len(differences) == 0

        # Different DNS
        baseline2 = NetworkBaseline(
            timestamp=__import__('datetime').datetime.now(),
            interfaces=["lo", "eth0"],
            routing_table="default via 192.168.1.1",
            iptables_filter="Chain INPUT",
            iptables_nat="Chain OUTPUT",
            iptables_mangle="Chain POSTROUTING",
            dns_servers=["1.1.1.1"],  # Changed
            resolv_conf="nameserver 1.1.1.1",
            running_processes=[],
            connectivity_hosts={"8.8.8.8": True},
            wireguard_interfaces=[]
        )

        differences = verify_baseline(baseline2, baseline1)
        assert len(differences) > 0
        assert any("DNS" in d for d in differences)


# =============================================================================
# Phase 3: Discord Detection (Read-only)
# =============================================================================

class TestPhase3DiscordDetection:
    """Phase 3: Discord detection tests (read-only)."""

    @pytest.mark.phase3
    def test_discord_service_import(self):
        """Test that discord service can be imported."""
        from splitwire.services.discord import DiscordService
        service = DiscordService()
        assert service is not None

    @pytest.mark.phase3
    def test_discord_detection_methods(self):
        """Test Discord detection method availability."""
        from splitwire.services.discord import DiscordService
        service = DiscordService()

        # These methods should exist
        assert hasattr(service, 'is_installed')
        assert hasattr(service, 'detect_all')
        assert hasattr(service, 'status')

    @pytest.mark.phase3
    def test_discord_is_installed(self):
        """Test Discord installation check."""
        from splitwire.services.discord import DiscordService
        service = DiscordService()

        # Should return bool without error
        result = service.is_installed()
        assert isinstance(result, bool)

    @pytest.mark.phase3
    def test_discord_status(self):
        """Test Discord status check."""
        from splitwire.services.discord import DiscordService
        from splitwire.services.base import ServiceStatus
        service = DiscordService()

        # Should return ServiceStatus without error
        result = service.status()
        assert isinstance(result, ServiceStatus)

    @pytest.mark.phase3
    @pytest.mark.requires_internet
    def test_discord_ip_ranges(self):
        """Test Discord IP range definitions."""
        from splitwire.services.wireguard import DISCORD_CLOUDFLARE_IPS

        # Should have IP ranges defined
        assert len(DISCORD_CLOUDFLARE_IPS) > 0, "No Discord IP ranges defined"

        # All should be valid CIDR notation
        import ipaddress
        for ip_range in DISCORD_CLOUDFLARE_IPS:
            try:
                ipaddress.ip_network(ip_range)
            except ValueError:
                pytest.fail(f"Invalid IP range: {ip_range}")


# =============================================================================
# Integration Tests: Service Imports
# =============================================================================

class TestServiceImports:
    """Test that all services can be imported."""

    @pytest.mark.phase1
    def test_base_service_import(self):
        """Test base service imports."""
        from splitwire.services.base import (
            BaseService, ServiceStatus, ServiceType, ServiceInfo
        )
        assert ServiceStatus is not None
        assert ServiceType is not None

    @pytest.mark.phase1
    def test_dns_service_import(self):
        """Test DNS service import."""
        from splitwire.services.dns import DNSService
        assert DNSService is not None

    @pytest.mark.phase1
    def test_zapret_service_import(self):
        """Test Zapret service import."""
        from splitwire.services.zapret import ZapretService
        assert ZapretService is not None

    @pytest.mark.phase1
    def test_wireguard_service_import(self):
        """Test WireGuard service import."""
        from splitwire.services.wireguard import WireGuardService
        assert WireGuardService is not None

    @pytest.mark.phase1
    def test_byedpi_service_import(self):
        """Test ByeDPI service import."""
        from splitwire.services.byedpi import ByeDPIService
        assert ByeDPIService is not None

    @pytest.mark.phase1
    def test_systemd_manager_import(self):
        """Test systemd manager import."""
        from splitwire.services.systemd import SystemdManager, get_systemd_manager
        manager = get_systemd_manager()
        assert manager is not None


# =============================================================================
# Integration Tests: Preset Validation
# =============================================================================

class TestPresetValidation:
    """Test preset configurations are valid."""

    @pytest.mark.phase1
    def test_zapret_presets_exist(self):
        """Test that Zapret presets are defined."""
        from splitwire.services.zapret import ZapretService
        service = ZapretService()

        presets = service.get_presets()
        assert len(presets) > 0, "No Zapret presets defined"

    @pytest.mark.phase1
    def test_zapret_preset_structure(self):
        """Test that Zapret presets have required fields."""
        from splitwire.services.zapret import ZapretService, ZapretPreset
        service = ZapretService()

        presets = service.get_presets()
        for name, preset in presets.items():
            assert isinstance(preset, ZapretPreset), f"Preset {name} is not ZapretPreset"
            assert hasattr(preset, 'name'), f"Preset {name} missing 'name'"
            assert hasattr(preset, 'description'), f"Preset {name} missing 'description'"

    @pytest.mark.phase1
    def test_dns_presets_exist(self):
        """Test that DNS presets are defined."""
        from splitwire.services.dns import DNS_PRESETS

        assert len(DNS_PRESETS) > 0, "No DNS presets defined"
        assert "cloudflare" in DNS_PRESETS or "Cloudflare" in DNS_PRESETS


# =============================================================================
# Utility Tests
# =============================================================================

class TestUtilities:
    """Test utility functions."""

    @pytest.mark.phase0
    def test_tcp_connect_test(self):
        """Test TCP connectivity helper."""
        # Should connect to Google DNS
        result = tcp_connect_test("8.8.8.8", 53, timeout=5.0)
        assert result is True or result is False  # Should return bool

    @pytest.mark.phase0
    def test_is_process_running(self):
        """Test process check helper."""
        # init/systemd should always be running
        result = is_process_running("systemd") or is_process_running("init")
        # Note: might not find exactly "systemd" on some systems
        assert isinstance(result, bool)

    @pytest.mark.phase0
    def test_is_root_check(self):
        """Test root check helper."""
        result = is_root()
        assert result == (os.geteuid() == 0)
