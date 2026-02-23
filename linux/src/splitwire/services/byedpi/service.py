"""ByeDPI (ciadpi) proxy service for SplitWire Linux."""

import json
import subprocess
import tempfile
import time
from pathlib import Path

from ..base import BaseService, ServiceStatus, ServiceType
from .constants import (
    BYEDPI_BINARY,
    CONFIG_FILE,
    LOCAL_CONFIG_DIR,
    PRESETS_FILE,
    SYSTEMD_SERVICE,
)
from .download import download_binary, is_binary_installed
from .models import (
    DEFAULT_PRESETS,
    ByeDPIConfig,
    ByeDPIMode,
    ByeDPIPreset,
)
from .process import (
    create_pid_dir,
    is_process_running,
    kill_by_pid,
    save_pid,
    terminate_process,
)


class ByeDPIService(BaseService):
    """
    ByeDPI proxy service for traffic processing.

    Runs ciadpi as a SOCKS5 proxy for traffic processing.
    """

    # ByeDPI-specific timeouts (seconds)
    TIMEOUT_SYSTEMCTL_ACTION = 30
    TIMEOUT_SYSTEMCTL_QUERY = 10

    def __init__(self):
        """Initialize ByeDPI service."""
        super().__init__(
            name="byedpi",
            display_name="ByeDPI Proxy",
            description="SOCKS5 proxy with traffic processing",
            service_type=ServiceType.PROXY,
        )
        self._config = ByeDPIConfig()
        self._process: subprocess.Popen | None = None
        self._custom_presets: dict[str, ByeDPIPreset] = {}
        self._ensure_directories()
        self._load_config()
        self._load_custom_presets()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text())
            self._config = ByeDPIConfig(
                enabled=data.get("enabled", False),
                preset_name=data.get("preset_name", "default"),
                custom_args=data.get("custom_args", ""),
                proxy_host=data.get("proxy_host", "127.0.0.1"),
                proxy_port=data.get("proxy_port", 1080),
                include_browsers=data.get("include_browsers", False),
                tunneled_apps=data.get("tunneled_apps", []),
            )
        except Exception as e:
            self._logger.warning(f"Failed to load config: {e}")

    def _save_config(self) -> None:
        """Save configuration to file."""
        data = {
            "enabled": self._config.enabled,
            "preset_name": self._config.preset_name,
            "custom_args": self._config.custom_args,
            "proxy_host": self._config.proxy_host,
            "proxy_port": self._config.proxy_port,
            "include_browsers": self._config.include_browsers,
            "tunneled_apps": self._config.tunneled_apps,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    def _load_custom_presets(self) -> None:
        """Load custom presets from file."""
        if not PRESETS_FILE.exists():
            return
        try:
            data = json.loads(PRESETS_FILE.read_text())
            for name, pd in data.items():
                self._custom_presets[name] = ByeDPIPreset(
                    name=pd.get("name", name),
                    description=pd.get("description", ""),
                    args=pd.get("args", ""),
                    mode=ByeDPIMode(pd.get("mode", "disorder")),
                    is_custom=True,
                )
        except Exception as e:
            self._logger.warning(f"[BYEDPI] Failed to load custom presets: {e}")

    def _save_custom_presets(self) -> None:
        """Save custom presets to file."""
        data = {}
        for name, preset in self._custom_presets.items():
            data[name] = {
                "name": preset.name,
                "description": preset.description,
                "args": preset.args,
                "mode": preset.mode.value,
            }
        PRESETS_FILE.write_text(json.dumps(data, indent=2))

    def install(
        self,
        preset: str | None = None,
        include_browsers: bool = False,
        one_shot: bool = False,
        as_service: bool = True,
        **kwargs,
    ) -> bool:
        """Install and start ByeDPI."""
        self._logger.info("Installing ByeDPI")
        self._notify_status_change(ServiceStatus.INSTALLING)

        try:
            if not self._ensure_binary():
                return False

            preset_name = preset or "default"
            if preset_name not in self.get_all_presets():
                self._logger.error(f"Unknown preset: {preset_name}")
                return False

            self._config.preset_name = preset_name
            self._config.include_browsers = include_browsers

            if not self._start_with_mode(one_shot, as_service):
                return False

            self._config.enabled = True
            self._save_config()
            self._logger.info(f"ByeDPI installed with preset: {preset_name}")
            return True

        except Exception as e:
            self._logger.exception(f"Installation failed: {e}")
            self._notify_status_change(ServiceStatus.FAILED)
            return False

    def _ensure_binary(self) -> bool:
        """Download ciadpi binary if not present."""
        if not is_binary_installed():
            self._logger.info("Downloading ciadpi binary...")
            if not download_binary(self._run_privileged, self._logger):
                self._logger.error("Failed to download ciadpi")
                return False
        return True

    def _start_with_mode(self, one_shot: bool, as_service: bool) -> bool:
        """Start ByeDPI using the appropriate mode."""
        if one_shot:
            return self._start_process()
        if as_service:
            if not self._install_systemd_service():
                return False
            return self.start()
        return self._start_process()

    def remove(self) -> bool:
        """Remove ByeDPI service."""
        self._logger.info("Removing ByeDPI")
        try:
            self.stop()
            self._remove_systemd_service()
            self._config.enabled = False
            self._save_config()
            self._notify_status_change(ServiceStatus.NOT_INSTALLED)
            return True
        except Exception as e:
            self._logger.exception(f"Removal failed: {e}")
            return False

    def start(self) -> bool:
        """Start ByeDPI service."""
        self._logger.info("Starting ByeDPI")

        if self._is_service_installed():
            result = self._run_privileged(
                ["systemctl", "start", SYSTEMD_SERVICE], timeout=self.TIMEOUT_SYSTEMCTL_ACTION
            )
            if result.success:
                self._logger.info("ByeDPI started via systemd")
                self._notify_status_change(ServiceStatus.RUNNING)
                return True
            self._logger.error(f"Failed to start service: {result.stderr}")
        return self._start_process()

    def stop(self) -> bool:
        """Stop ByeDPI."""
        self._logger.info("Stopping ByeDPI")

        if self._is_service_installed():
            result = self._run_privileged(
                ["systemctl", "stop", SYSTEMD_SERVICE], timeout=self.TIMEOUT_SYSTEMCTL_ACTION
            )
            if result.success:
                self._logger.info("ByeDPI stopped via systemd")
                self._notify_status_change(ServiceStatus.STOPPED)
                return True
        return self._stop_process()

    def status(self) -> ServiceStatus:
        """Get ByeDPI status."""
        if not self.is_installed():
            return ServiceStatus.NOT_INSTALLED

        if self._is_service_installed():
            result = self._shell.run(
                ["systemctl", "is-active", SYSTEMD_SERVICE],
                timeout=self.TIMEOUT_SYSTEMCTL_QUERY,
            )
            stdout = result.stdout.strip().lower()
            if stdout == "active":
                return ServiceStatus.RUNNING
            if stdout == "failed":
                return ServiceStatus.FAILED

        if is_process_running(self._run_privileged, self._logger):
            return ServiceStatus.RUNNING
        return ServiceStatus.STOPPED

    def is_installed(self) -> bool:
        """Check if ByeDPI is installed."""
        return is_binary_installed()

    def get_config(self) -> ByeDPIConfig:
        """Get current configuration."""
        return self._config

    def get_all_presets(self) -> dict[str, ByeDPIPreset]:
        """Get all available presets (default + custom)."""
        presets = DEFAULT_PRESETS.copy()
        presets.update(self._custom_presets)
        return presets

    def get_preset(self, name: str) -> ByeDPIPreset | None:
        """Get a specific preset by name."""
        return self.get_all_presets().get(name)

    def get_current_preset(self) -> ByeDPIPreset | None:
        """Get the currently selected preset."""
        return self.get_preset(self._config.preset_name)

    def add_custom_preset(self, key: str, preset: ByeDPIPreset) -> bool:
        """Add a custom preset."""
        if key in DEFAULT_PRESETS:
            self._logger.error(f"Cannot override default preset: {key}")
            return False
        preset.is_custom = True
        self._custom_presets[key] = preset
        self._save_custom_presets()
        return True

    def remove_custom_preset(self, key: str) -> bool:
        """Remove a custom preset."""
        if key in self._custom_presets:
            del self._custom_presets[key]
            self._save_custom_presets()
            return True
        return False

    def set_preset(self, name: str) -> bool:
        """Set the active preset."""
        if name not in self.get_all_presets():
            self._logger.error(f"Unknown preset: {name}")
            return False
        self._config.preset_name = name
        self._save_config()
        return True

    def set_custom_args(self, args: str) -> None:
        """Set custom command line arguments."""
        self._config.custom_args = args
        self._save_config()

    def set_proxy_port(self, port: int) -> None:
        """Set the SOCKS5 proxy port."""
        self._config.proxy_port = port
        self._save_config()

    def get_proxy_address(self) -> str:
        """Get the SOCKS5 proxy address."""
        return f"socks5://{self._config.proxy_host}:{self._config.proxy_port}"

    def set_include_browsers(self, include: bool) -> None:
        """Set whether to include browsers in tunneling."""
        self._config.include_browsers = include
        self._save_config()

    def add_tunneled_app(self, app: str) -> None:
        """Add an app to tunnel through the proxy."""
        if app not in self._config.tunneled_apps:
            self._config.tunneled_apps.append(app)
            self._save_config()

    def remove_tunneled_app(self, app: str) -> None:
        """Remove an app from tunnel list."""
        if app in self._config.tunneled_apps:
            self._config.tunneled_apps.remove(app)
            self._save_config()

    def get_tunneled_apps(self) -> list[str]:
        """Get list of apps tunneled through proxy."""
        return self._config.tunneled_apps.copy()

    def configure(
        self,
        preset: str | None = None,
        custom_params: str | None = None,
        include_browsers: bool = False,
    ) -> bool:
        """Configure ByeDPI with preset or custom params."""
        if preset:
            self._config.preset_name = preset
        if custom_params:
            self._config.custom_args = custom_params
        self._config.include_browsers = include_browsers
        self._save_config()
        return True

    def _build_command(self) -> list[str]:
        """Build ciadpi command with arguments."""
        cmd = [str(BYEDPI_BINARY)]
        cmd.extend(["-i", self._config.proxy_host])
        cmd.extend(["-p", str(self._config.proxy_port)])

        if self._config.custom_args:
            args = self._config.custom_args.split()
        else:
            preset = self.get_current_preset()
            args = preset.args.split() if preset else []

        cmd.extend(args)
        return cmd

    def _start_process(self) -> bool:
        """Start ciadpi process directly."""
        if is_process_running(self._run_privileged, self._logger):
            self._logger.info("ByeDPI already running")
            return True

        try:
            cmd = self._build_command()
            self._logger.info(f"Starting: {' '.join(cmd)}")
            create_pid_dir(self._run_privileged)

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            time.sleep(0.5)
            if self._process.poll() is not None:
                _stdout, stderr = self._process.communicate()
                self._logger.error(f"Process exited: {stderr.decode()}")
                return False

            save_pid(
                self._process.pid,
                self._run_privileged,
                self._logger,
            )
            self._logger.info(f"ByeDPI started with PID {self._process.pid}")
            self._notify_status_change(ServiceStatus.RUNNING)
            return True
        except Exception as e:
            self._logger.exception(f"Failed to start process: {e}")
            return False

    def _stop_process(self) -> bool:
        """Stop ciadpi process."""
        try:
            kill_by_pid(self._run_privileged, self._logger)
            terminate_process(self._process)
            self._process = None
            self._notify_status_change(ServiceStatus.STOPPED)
            return True
        except Exception as e:
            self._logger.exception(f"Failed to stop process: {e}")
            return False

    def _is_service_installed(self) -> bool:
        """Check if systemd service is installed."""
        result = self._shell.run(
            ["systemctl", "list-unit-files", SYSTEMD_SERVICE],
            timeout=self.TIMEOUT_SYSTEMCTL_QUERY,
        )
        return SYSTEMD_SERVICE in result.stdout

    def _install_systemd_service(self) -> bool:
        """Install systemd service file."""
        preset = self.get_current_preset()
        args = self._config.custom_args or (preset.args if preset else "")

        content = f"""[Unit]
Description=SplitWire ByeDPI Proxy Service
Documentation=https://github.com/hufrea/byedpi
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={BYEDPI_BINARY} -i {self._config.proxy_host} \
-p {self._config.proxy_port} {args}
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes

[Install]
WantedBy=multi-user.target
"""

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as f:
                f.write(content)
                tmp_path = f.name

            path = f"/etc/systemd/system/{SYSTEMD_SERVICE}"
            result = self._run_privileged(["cp", tmp_path, path])
            Path(tmp_path).unlink(missing_ok=True)

            if not result.success:
                return False

            self._run_privileged(["systemctl", "daemon-reload"])
            self._run_privileged(["systemctl", "enable", SYSTEMD_SERVICE])
            return True
        except Exception as e:
            self._logger.exception(f"Failed to install service: {e}")
            return False

    def _remove_systemd_service(self) -> bool:
        """Remove systemd service file."""
        try:
            self._run_privileged(["systemctl", "stop", SYSTEMD_SERVICE])
            self._run_privileged(["systemctl", "disable", SYSTEMD_SERVICE])
            self._run_privileged(
                [
                    "rm",
                    "-f",
                    f"/etc/systemd/system/{SYSTEMD_SERVICE}",
                ]
            )
            self._run_privileged(["systemctl", "daemon-reload"])
            return True
        except Exception as e:
            self._logger.warning(f"Failed to remove service: {e}")
            return False


# Convenience functions
_byedpi_service: ByeDPIService | None = None


def get_byedpi_service() -> ByeDPIService:
    """Get the global ByeDPI service instance."""
    global _byedpi_service
    if _byedpi_service is None:
        _byedpi_service = ByeDPIService()
    return _byedpi_service
