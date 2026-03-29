"""Zapret packet processing service manager."""

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path

from splitwire.services.base import BaseService, ServiceStatus, ServiceType

from .config_mgr import (
    get_blacklist,
    load_config,
    load_presets,
    save_config,
    save_presets,
    set_blacklist,
)
from .constants import (
    BLACKLIST_FILE,
    LOCAL_CONFIG_DIR,
    NFQUEUE_NUM,
    NFQWS_BINARY,
    NFQWS_PID_FILE,
    PID_DIR,
    TPWS_BINARY,
    TPWS_PID_FILE,
    TPWS_PORT,
    ZAPRET_INSTALL_DIR,
)
from .install import (
    build_zapret,
    clone_zapret,
    install_dependencies,
    install_systemd_service,
    remove_systemd_service,
    setup_config_dirs,
)
from .iptables import add_iptables_rules, remove_iptables_rules
from .models import (
    ZapretConfig,
    ZapretMode,
    ZapretPreset,
)


class ZapretService(BaseService):
    """
    Zapret packet processing service manager.

    Manages nfqws/tpws packet manipulation, iptables rules,
    presets, and custom configurations.
    """

    # Zapret-specific timeouts (seconds)
    TIMEOUT_REMOVE_DIR = 60
    TIMEOUT_PROCESS_KILL = 5
    TIMEOUT_PROCESS_CHECK = 5

    def __init__(self) -> None:
        """Initialize Zapret service and load saved configuration."""
        super().__init__(
            name="zapret",
            display_name="Zapret",
            description="Traffic processing using nfqws/tpws packet manipulation",
            service_type=ServiceType.PACKET_PROCESSING,
        )
        self._config = ZapretConfig()
        self._presets: dict[str, ZapretPreset] = {}
        self._nfqws_process: subprocess.Popen | None = None
        self._tpws_process: subprocess.Popen | None = None

        load_presets(self)
        load_config(self)
        LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def install(self, **kwargs: object) -> bool:
        """Install Zapret from source."""
        self._logger.info("Installing Zapret...")
        self._notify_status_change(ServiceStatus.INSTALLING)
        try:
            if not install_dependencies(self):
                self._logger.error("Failed to install dependencies")
                return False
            if not clone_zapret(self):
                self._logger.error("Failed to clone Zapret repository")
                return False
            if not build_zapret(self):
                self._logger.error("Failed to build Zapret binaries")
                return False
            setup_config_dirs(self)
            install_systemd_service(self)
            save_presets(self)
            self._logger.info("Zapret installed successfully")
            self._notify_status_change(ServiceStatus.STOPPED)
            return True
        except Exception as e:
            self._logger.error("Installation failed: %s", e)
            self._notify_status_change(ServiceStatus.FAILED)
            return False

    def remove(self) -> bool:
        """Remove Zapret installation."""
        self._logger.info("Removing Zapret...")
        self._notify_status_change(ServiceStatus.REMOVING)
        try:
            if self.is_running():
                self.stop()
            remove_systemd_service(self)
            if ZAPRET_INSTALL_DIR.exists():
                result = self._run_privileged(
                    ["rm", "-rf", str(ZAPRET_INSTALL_DIR)],
                    timeout=self.TIMEOUT_REMOVE_DIR,
                )
                if not result.success:
                    self._logger.warning("Failed to remove %s", ZAPRET_INSTALL_DIR)
            self._logger.info("Zapret removed successfully")
            self._notify_status_change(ServiceStatus.NOT_INSTALLED)
            return True
        except Exception as e:
            self._logger.error("Removal failed: %s", e)
            return False

    def is_installed(self) -> bool:
        """Check if Zapret is installed."""
        nfqws_exists = NFQWS_BINARY.exists()
        tpws_exists = TPWS_BINARY.exists()
        installed = nfqws_exists or tpws_exists
        self._logger.debug(
            "[ZAPRET] Installation check: nfqws=%s, tpws=%s, installed=%s",
            nfqws_exists,
            tpws_exists,
            installed,
        )
        return installed

    def start(self, one_shot: bool = False) -> bool:
        """Start Zapret service."""
        if not self.is_installed():
            self._logger.error("Zapret is not installed")
            return False
        if self.is_running():
            self._logger.warning("Zapret is already running")
            return True
        self._logger.info("Starting Zapret in %s mode", self._config.mode.value)
        try:
            preset = self._get_current_preset()
            if not add_iptables_rules(self):
                self._logger.error("Failed to add iptables rules")
                return False
            return self._start_processes(preset, one_shot)
        except Exception as e:
            self._logger.error("Failed to start Zapret: %s", e)
            self.stop()
            return False

    def _start_processes(self, preset: ZapretPreset | None, one_shot: bool) -> bool:
        """Start nfqws and/or tpws based on current mode."""
        mode = preset.mode if preset else self._config.mode
        if mode in [ZapretMode.NFQWS, ZapretMode.COMBINED] and not self._start_nfqws(
            preset, one_shot
        ):
            remove_iptables_rules(self)
            return False
        if mode in [ZapretMode.TPWS, ZapretMode.COMBINED] and not self._start_tpws(
            preset, one_shot
        ):
            self._stop_nfqws()
            remove_iptables_rules(self)
            return False
        self._config.enabled = True
        save_config(self)
        self._notify_status_change(ServiceStatus.RUNNING)
        self._logger.info("Zapret started successfully")
        return True

    def stop(self) -> bool:
        """Stop Zapret service."""
        self._logger.info("Stopping Zapret...")
        try:
            self._stop_nfqws()
            self._stop_tpws()
            remove_iptables_rules(self)
            self._config.enabled = False
            save_config(self)
            self._notify_status_change(ServiceStatus.STOPPED)
            self._logger.info("Zapret stopped")
            return True
        except Exception as e:
            self._logger.error("Failed to stop Zapret: %s", e)
            return False

    def status(self) -> ServiceStatus:
        """Get Zapret service status."""
        if not self.is_installed():
            return ServiceStatus.NOT_INSTALLED
        if self._is_nfqws_running() or self._is_tpws_running():
            return ServiceStatus.RUNNING
        return ServiceStatus.STOPPED

    def _start_nfqws(self, preset: ZapretPreset | None, one_shot: bool = False) -> bool:
        """Start nfqws process."""
        if not NFQWS_BINARY.exists():
            self._logger.error("nfqws binary not found at %s", NFQWS_BINARY)
            return False
        args = self._build_nfqws_args(preset)
        cmd = [str(NFQWS_BINARY), *args]
        self._logger.debug("Starting nfqws: %s", " ".join(cmd))
        try:
            PID_DIR.mkdir(parents=True, exist_ok=True)
            self._nfqws_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            NFQWS_PID_FILE.write_text(str(self._nfqws_process.pid))
            time.sleep(0.5)
            if self._nfqws_process.poll() is not None:
                self._logger.error("nfqws process terminated immediately")
                return False
            self._logger.info("nfqws started with PID %s", self._nfqws_process.pid)
            return True
        except Exception as e:
            self._logger.error("Failed to start nfqws: %s", e)
            return False

    def _stop_nfqws(self) -> bool:
        """Stop nfqws process."""
        self._logger.debug("[ZAPRET] Stopping nfqws process...")
        try:
            pid = self._read_pid_file(NFQWS_PID_FILE)
            if self._nfqws_process and self._nfqws_process.poll() is None:
                pid = self._nfqws_process.pid
            if pid:
                self._kill_pid(pid)
            self._shell.run(["pkill", "-9", "nfqws"], timeout=self.TIMEOUT_PROCESS_KILL)
            if NFQWS_PID_FILE.exists():
                NFQWS_PID_FILE.unlink()
            self._nfqws_process = None
            return True
        except Exception as e:
            self._logger.error("Error stopping nfqws: %s", e)
            return False

    def _is_nfqws_running(self) -> bool:
        """Check if nfqws is running."""
        result = self._shell.run(["pgrep", "-x", "nfqws"], timeout=self.TIMEOUT_PROCESS_CHECK)
        self._logger.debug("[ZAPRET] nfqws process running: %s", result.success)
        return result.success

    def _build_nfqws_args(self, preset: ZapretPreset | None) -> list[str]:
        """Build nfqws command line arguments."""
        args = ["--qnum", str(NFQUEUE_NUM)]
        if preset and preset.nfqws_args:
            args.extend(preset.nfqws_args.split())
        elif self._config.custom_nfqws_args:
            args.extend(self._config.custom_nfqws_args.split())
        else:
            args.extend(
                ["--dpi-desync=fake,split2", "--dpi-desync-ttl=5", "--dpi-desync-fooling=md5sig"]
            )
        use_bl = (preset and preset.use_blacklist) or self._config.use_blacklist
        if use_bl and BLACKLIST_FILE.exists():
            args.extend(["--hostlist", str(BLACKLIST_FILE)])
        return args

    def _start_tpws(self, preset: ZapretPreset | None, one_shot: bool = False) -> bool:
        """Start tpws process."""
        if not TPWS_BINARY.exists():
            self._logger.error("tpws binary not found at %s", TPWS_BINARY)
            return False
        args = self._build_tpws_args(preset)
        cmd = [str(TPWS_BINARY), *args]
        self._logger.debug("Starting tpws: %s", " ".join(cmd))
        try:
            PID_DIR.mkdir(parents=True, exist_ok=True)
            self._tpws_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            TPWS_PID_FILE.write_text(str(self._tpws_process.pid))
            time.sleep(0.5)
            if self._tpws_process.poll() is not None:
                self._logger.error("tpws process terminated immediately")
                return False
            self._logger.info("tpws started with PID %s", self._tpws_process.pid)
            return True
        except Exception as e:
            self._logger.error("Failed to start tpws: %s", e)
            return False

    def _stop_tpws(self) -> bool:
        """Stop tpws process."""
        self._logger.debug("[ZAPRET] Stopping tpws process...")
        try:
            pid = self._read_pid_file(TPWS_PID_FILE)
            if self._tpws_process and self._tpws_process.poll() is None:
                pid = self._tpws_process.pid
            if pid:
                self._kill_pid(pid)
            self._shell.run(["pkill", "-9", "tpws"], timeout=self.TIMEOUT_PROCESS_KILL)
            if TPWS_PID_FILE.exists():
                TPWS_PID_FILE.unlink()
            self._tpws_process = None
            return True
        except Exception as e:
            self._logger.error("Error stopping tpws: %s", e)
            return False

    def _is_tpws_running(self) -> bool:
        """Check if tpws is running."""
        result = self._shell.run(["pgrep", "-x", "tpws"], timeout=self.TIMEOUT_PROCESS_CHECK)
        self._logger.debug("[ZAPRET] tpws process running: %s", result.success)
        return result.success

    def _build_tpws_args(self, preset: ZapretPreset | None) -> list[str]:
        """Build tpws command line arguments."""
        args = ["--port", str(TPWS_PORT), "--bind-addr=127.0.0.1"]
        if preset and preset.tpws_args:
            args.extend(preset.tpws_args.split())
        elif self._config.custom_tpws_args:
            args.extend(self._config.custom_tpws_args.split())
        else:
            args.extend(["--split-pos=3", "--disorder"])
        use_bl = (preset and preset.use_blacklist) or self._config.use_blacklist
        if use_bl and BLACKLIST_FILE.exists():
            args.extend(["--hostlist", str(BLACKLIST_FILE)])
        return args

    def _read_pid_file(self, pid_file: Path) -> int | None:
        """Read a PID from a PID file, returning None on failure."""
        if not pid_file.exists():
            return None
        try:
            pid = int(pid_file.read_text().strip())
            self._logger.debug("[ZAPRET] Read PID from %s: %s", pid_file, pid)
            return pid
        except (ValueError, OSError) as e:
            self._logger.warning("[ZAPRET] Failed to read PID file %s: %s", pid_file, e)
            return None

    def _kill_pid(self, pid: int) -> None:
        """Send SIGTERM then SIGKILL to a process."""
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Already dead

    def get_presets(self) -> dict[str, ZapretPreset]:
        """Get all available presets."""
        return self._presets.copy()

    def get_preset(self, name: str) -> ZapretPreset | None:
        """Get a specific preset by name."""
        return self._presets.get(name)

    def set_preset(self, name: str) -> bool:
        """Set active preset."""
        if name not in self._presets:
            self._logger.error("Preset '%s' not found", name)
            return False
        self._config.preset_name = name
        save_config(self)
        return self.restart() if self.is_running() else True

    def add_custom_preset(self, name: str, preset: ZapretPreset) -> bool:
        """Add a custom preset."""
        preset.is_custom = True
        self._presets[name] = preset
        save_presets(self)
        return True

    def remove_custom_preset(self, name: str) -> bool:
        """Remove a custom preset."""
        if name not in self._presets:
            return False
        if not self._presets[name].is_custom:
            self._logger.error("Cannot remove built-in preset")
            return False
        del self._presets[name]
        save_presets(self)
        return True

    def _get_current_preset(self) -> ZapretPreset | None:
        """Get currently active preset."""
        return self._presets.get(self._config.preset_name)

    def _get_current_mode(self) -> ZapretMode:
        """Get current operation mode."""
        preset = self._get_current_preset()
        return preset.mode if preset else self._config.mode

    def get_blacklist(self) -> list[str]:
        """Get current blacklist domains."""
        return get_blacklist()

    def set_blacklist(self, domains: list[str]) -> bool:
        """Set blacklist domains."""
        return set_blacklist(domains)

    def add_to_blacklist(self, domain: str) -> bool:
        """Add domain to blacklist."""
        domains = self.get_blacklist()
        if domain not in domains:
            domains.append(domain)
            return self.set_blacklist(domains)
        return True

    def remove_from_blacklist(self, domain: str) -> bool:
        """Remove domain from blacklist."""
        domains = self.get_blacklist()
        if domain in domains:
            domains.remove(domain)
            return self.set_blacklist(domains)
        return True

    def set_use_blacklist(self, enabled: bool) -> bool:
        """Enable or disable blacklist filtering."""
        self._config.use_blacklist = enabled
        save_config(self)
        return self.restart() if self.is_running() else True

    def set_custom_nfqws_args(self, args: str) -> bool:
        """Set custom nfqws arguments."""
        self._config.custom_nfqws_args = args
        save_config(self)
        return True

    def set_custom_tpws_args(self, args: str) -> bool:
        """Set custom tpws arguments."""
        self._config.custom_tpws_args = args
        save_config(self)
        return True

    def set_mode(self, mode: ZapretMode) -> bool:
        """Set operation mode."""
        self._config.mode = mode
        save_config(self)
        return self.restart() if self.is_running() else True

    def get_config(self) -> ZapretConfig:
        """Get current configuration."""
        return self._config

    def configure(
        self,
        params: str | None = None,
        preset: str | None = None,
        mode: ZapretMode | None = None,
    ) -> bool:
        """Configure Zapret with specified parameters."""
        if preset:
            self._config.preset_name = preset
        if params:
            current_mode = mode or self._config.mode
            if current_mode == ZapretMode.TPWS:
                self._config.custom_tpws_args = params
            else:
                self._config.custom_nfqws_args = params
        if mode:
            self._config.mode = mode
        save_config(self)
        self._logger.info(
            "Zapret configured with preset=%s, mode=%s",
            preset,
            self._config.mode.value,
        )
        return True

    def run_once(self, params: str | None = None, preset: str | None = None) -> bool:
        """Run Zapret once without installing as a service."""
        self._logger.info("Running Zapret once (one-shot mode)...")
        if params or preset:
            self.configure(params=params, preset=preset)
        return self.start(one_shot=True)


# ============================================================================
# Module-level singleton
# ============================================================================

_zapret_service: ZapretService | None = None


def get_zapret_service() -> ZapretService:
    """Get the singleton Zapret service instance."""
    global _zapret_service
    if _zapret_service is None:
        _zapret_service = ZapretService()
    return _zapret_service
