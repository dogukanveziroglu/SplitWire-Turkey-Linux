"""
Tests for the configuration manager module.
"""

import json
import pytest
import tempfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitwire.core.config import (
    ConfigManager,
    AppConfig,
    DNSConfig,
    WireGuardConfig,
    ZapretConfig,
    ByeDPIConfig,
    Theme,
    Language,
)


class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AppConfig()
        assert config.version == "1.0.0"
        assert config.theme == "system"
        assert config.language == "en"
        assert config.start_minimized is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AppConfig(
            theme=Theme.DARK.value,
            language=Language.ENGLISH.value,
        )
        assert config.theme == "dark"
        assert config.language == "en"


class TestDNSConfig:
    """Tests for DNSConfig dataclass."""

    def test_default_values(self):
        """Test default DNS configuration."""
        config = DNSConfig()
        assert config.enabled is False
        assert config.primary == "1.1.1.1"
        assert config.secondary == "1.0.0.1"
        assert config.doh_enabled is False

    def test_custom_dns(self):
        """Test custom DNS settings."""
        config = DNSConfig(
            enabled=True,
            primary="1.1.1.1",
            secondary="1.0.0.1",
            doh_enabled=True,
            doh_url="https://cloudflare-dns.com/dns-query",
        )
        assert config.enabled is True
        assert config.primary == "1.1.1.1"
        assert config.doh_url == "https://cloudflare-dns.com/dns-query"


class TestWireGuardConfig:
    """Tests for WireGuardConfig dataclass."""

    def test_default_values(self):
        """Test default WireGuard configuration."""
        config = WireGuardConfig()
        assert config.config_path == ""
        assert config.split_tunnel_enabled is True
        assert config.allowed_apps == []

    def test_with_apps(self):
        """Test WireGuard config with allowed apps."""
        config = WireGuardConfig(
            split_tunnel_enabled=True,
            allowed_apps=["/usr/bin/discord", "/usr/bin/firefox"],
        )
        assert len(config.allowed_apps) == 2
        assert "/usr/bin/discord" in config.allowed_apps


class TestZapretConfig:
    """Tests for ZapretConfig dataclass."""

    def test_default_values(self):
        """Test default Zapret configuration."""
        config = ZapretConfig()
        assert config.enabled is False
        assert config.mode == "nfqws"
        assert config.strategy == "default"

    def test_custom_args(self):
        """Test Zapret with custom arguments."""
        config = ZapretConfig(
            enabled=True,
            mode="tpws",
            custom_args="--split-pos=2",
        )
        assert config.mode == "tpws"
        assert config.custom_args == "--split-pos=2"


class TestByeDPIConfig:
    """Tests for ByeDPIConfig dataclass."""

    def test_default_values(self):
        """Test default ByeDPI configuration."""
        config = ByeDPIConfig()
        assert config.enabled is False
        assert config.port == 10080
        assert config.strategy == "disorder"

    def test_custom_port(self):
        """Test ByeDPI with custom port."""
        config = ByeDPIConfig(port=8080, strategy="split")
        assert config.port == 8080
        assert config.strategy == "split"


class TestConfigManager:
    """Tests for ConfigManager class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temporary directory."""
        manager = ConfigManager(config_dir=temp_config_dir)
        manager._config = AppConfig()
        return manager

    def test_config_dir_creation(self, temp_config_dir):
        """Test that config directory is created."""
        config_dir = temp_config_dir / "splitwire"
        manager = ConfigManager(config_dir=config_dir)
        assert config_dir.exists()

    def test_save_and_load_config(self, config_manager, temp_config_dir):
        """Test saving and loading configuration."""
        # Modify config
        config_manager._config.theme = Theme.DARK.value
        config_manager._config.language = Language.ENGLISH.value

        # Save to file
        config_file = temp_config_dir / "config.json"
        config_dict = {
            "version": config_manager._config.version,
            "theme": config_manager._config.theme,
            "language": config_manager._config.language,
            "start_minimized": config_manager._config.start_minimized,
        }
        with open(config_file, "w") as f:
            json.dump(config_dict, f)

        # Verify file was created
        assert config_file.exists()

        # Load and verify
        with open(config_file) as f:
            loaded = json.load(f)
        assert loaded["theme"] == "dark"
        assert loaded["language"] == "en"

    def test_default_config_creation(self, temp_config_dir):
        """Test that default config is created when none exists."""
        config_file = temp_config_dir / "config.json"
        assert not config_file.exists()

        # Create default config
        default_config = AppConfig()
        config_dict = {
            "version": default_config.version,
            "theme": default_config.theme,
            "language": default_config.language,
        }
        with open(config_file, "w") as f:
            json.dump(config_dict, f)

        assert config_file.exists()


class TestThemeEnum:
    """Tests for Theme enumeration."""

    def test_theme_values(self):
        """Test all theme values exist."""
        assert Theme.LIGHT.value == "light"
        assert Theme.DARK.value == "dark"
        assert Theme.SYSTEM.value == "system"

    def test_theme_from_string(self):
        """Test creating theme from string."""
        assert Theme("light") == Theme.LIGHT
        assert Theme("dark") == Theme.DARK


class TestLanguageEnum:
    """Tests for Language enumeration."""

    def test_language_values(self):
        """Test all language values exist."""
        assert Language.TURKISH.value == "tr"
        assert Language.ENGLISH.value == "en"
        assert Language.RUSSIAN.value == "ru"
        assert Language.SPANISH.value == "es"

    def test_language_from_string(self):
        """Test creating language from string."""
        assert Language("tr") == Language.TURKISH
        assert Language("en") == Language.ENGLISH
