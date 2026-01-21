#!/usr/bin/env python3
"""
Kill Switch Watchdog Daemon for SplitWire-Turkey Integration Tests.

This module provides an independent connectivity watchdog that monitors network
connectivity during risky network operations. If connectivity is lost for a
configurable period, it automatically triggers cleanup procedures to restore
network connectivity.

Usage:
    # As standalone daemon
    python kill_switch.py --timeout 60 --threshold 10

    # Programmatically
    from kill_switch import KillSwitch, KillSwitchConfig

    config = KillSwitchConfig(timeout=60, threshold=10)
    ks = KillSwitch(config)
    ks.start()
    # ... run tests ...
    ks.stop()

Kill switch can be triggered manually via SIGUSR1.
"""

import os
import sys
import time
import signal
import socket
import subprocess
import threading
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [KILLSWITCH] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Connectivity check hosts
CHECK_HOSTS = [
    ("8.8.8.8", 53),      # Google DNS
    ("1.1.1.1", 53),      # Cloudflare DNS
    ("9.9.9.9", 53),      # Quad9 DNS
]

# Cleanup order - CRITICAL: Order matters!
CLEANUP_COMMANDS = [
    # 1. Kill bypass processes first
    (["pkill", "-9", "nfqws"], "Kill nfqws"),
    (["pkill", "-9", "tpws"], "Kill tpws"),
    (["pkill", "-9", "ciadpi"], "Kill ciadpi"),

    # 2. Remove iptables rules (order matters)
    (["iptables", "-t", "mangle", "-F", "POSTROUTING"], "Flush mangle POSTROUTING"),
    (["iptables", "-t", "nat", "-F", "OUTPUT"], "Flush nat OUTPUT"),

    # 3. Stop WireGuard
    (["wg-quick", "down", "splitwire"], "Stop WireGuard"),

    # 4. Clean up WireGuard interface if still exists
    (["ip", "link", "delete", "splitwire"], "Delete WireGuard interface"),

    # 5. Remove DNS config
    (["rm", "-f", "/etc/systemd/resolved.conf.d/splitwire.conf"], "Remove DNS config"),

    # 6. Restart DNS service
    (["systemctl", "restart", "systemd-resolved"], "Restart systemd-resolved"),
]

# Nuclear cleanup - last resort
NUCLEAR_CLEANUP = [
    (["iptables", "-F"], "Flush filter table"),
    (["iptables", "-t", "mangle", "-F"], "Flush mangle table"),
    (["iptables", "-t", "nat", "-F"], "Flush nat table"),
    (["iptables", "-t", "raw", "-F"], "Flush raw table"),
    (["systemctl", "restart", "NetworkManager"], "Restart NetworkManager"),
    (["systemctl", "restart", "systemd-resolved"], "Restart systemd-resolved"),
]


@dataclass
class KillSwitchConfig:
    """Configuration for kill switch behavior."""
    # Maximum time (seconds) before kill switch triggers
    timeout: int = 60
    # Connectivity loss threshold (seconds) before triggering
    threshold: int = 10
    # Check interval (seconds)
    check_interval: float = 1.0
    # Enable nuclear cleanup as last resort
    nuclear_enabled: bool = True
    # Log file path
    log_file: Optional[Path] = None
    # Callback after cleanup
    on_cleanup: Optional[Callable] = None
    # Custom cleanup commands to prepend
    extra_cleanup: List[List[str]] = field(default_factory=list)


@dataclass
class ConnectivityStatus:
    """Result of connectivity check."""
    is_connected: bool
    successful_hosts: List[str]
    failed_hosts: List[str]
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)


class KillSwitch:
    """
    Connectivity watchdog that monitors network and triggers cleanup on failure.

    The kill switch runs in a background thread, continuously checking connectivity
    to multiple hosts. If connectivity is lost for longer than the configured
    threshold, it executes cleanup commands to restore network connectivity.
    """

    def __init__(self, config: Optional[KillSwitchConfig] = None):
        self.config = config or KillSwitchConfig()
        self._running = False
        self._triggered = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._connectivity_lost_time: Optional[float] = None
        self._cleanup_performed = False

        # Set up file logging if configured
        if self.config.log_file:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s [KILLSWITCH] %(levelname)s: %(message)s'
            ))
            logger.addHandler(file_handler)

    def start(self) -> bool:
        """
        Start the kill switch watchdog.

        Returns:
            True if started successfully, False if already running
        """
        with self._lock:
            if self._running:
                logger.warning("Kill switch already running")
                return False

            self._running = True
            self._triggered = False
            self._cleanup_performed = False
            self._start_time = time.time()
            self._connectivity_lost_time = None

            # Set up signal handler for manual trigger
            signal.signal(signal.SIGUSR1, self._handle_manual_trigger)

            # Start monitor thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="KillSwitch-Monitor",
                daemon=True
            )
            self._monitor_thread.start()

            logger.info(
                f"Kill switch started (timeout={self.config.timeout}s, "
                f"threshold={self.config.threshold}s)"
            )
            return True

    def stop(self) -> bool:
        """
        Stop the kill switch watchdog.

        Returns:
            True if stopped successfully
        """
        with self._lock:
            if not self._running:
                return True

            self._running = False

            # Reset signal handler
            signal.signal(signal.SIGUSR1, signal.SIG_DFL)

            # Wait for monitor thread
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)

            logger.info("Kill switch stopped")
            return True

    def trigger(self, reason: str = "Manual trigger") -> bool:
        """
        Manually trigger the kill switch.

        Args:
            reason: Reason for triggering

        Returns:
            True if cleanup was performed
        """
        with self._lock:
            if self._triggered:
                logger.warning("Kill switch already triggered")
                return False

            self._triggered = True

        logger.warning(f"KILL SWITCH TRIGGERED: {reason}")
        return self._perform_cleanup()

    def check_connectivity(self) -> ConnectivityStatus:
        """
        Check connectivity to multiple hosts.

        Returns:
            ConnectivityStatus with results
        """
        successful = []
        failed = []
        total_latency = 0.0

        for host, port in CHECK_HOSTS:
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((host, port))
                sock.close()
                latency = (time.time() - start) * 1000
                total_latency += latency
                successful.append(host)
            except (socket.timeout, socket.error, OSError):
                failed.append(host)

        is_connected = len(successful) > 0
        avg_latency = total_latency / len(successful) if successful else 0.0

        return ConnectivityStatus(
            is_connected=is_connected,
            successful_hosts=successful,
            failed_hosts=failed,
            latency_ms=avg_latency
        )

    @property
    def is_running(self) -> bool:
        """Check if kill switch is running."""
        return self._running

    @property
    def was_triggered(self) -> bool:
        """Check if kill switch was triggered."""
        return self._triggered

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since start."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def _handle_manual_trigger(self, signum: int, frame) -> None:
        """Signal handler for manual trigger via SIGUSR1."""
        self.trigger("SIGUSR1 signal received")

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        logger.info("Monitor loop started")

        while self._running:
            # Check timeout
            if self.elapsed_time > self.config.timeout:
                self.trigger(f"Timeout exceeded ({self.config.timeout}s)")
                break

            # Check connectivity
            status = self.check_connectivity()

            if status.is_connected:
                # Reset connectivity lost timer
                if self._connectivity_lost_time is not None:
                    logger.info(
                        f"Connectivity restored after "
                        f"{time.time() - self._connectivity_lost_time:.1f}s"
                    )
                self._connectivity_lost_time = None
            else:
                # Track connectivity loss
                if self._connectivity_lost_time is None:
                    self._connectivity_lost_time = time.time()
                    logger.warning("Connectivity lost, starting threshold timer")
                else:
                    loss_duration = time.time() - self._connectivity_lost_time
                    logger.warning(
                        f"Connectivity lost for {loss_duration:.1f}s "
                        f"(threshold: {self.config.threshold}s)"
                    )

                    if loss_duration >= self.config.threshold:
                        self.trigger(
                            f"Connectivity lost for {loss_duration:.1f}s "
                            f"(threshold: {self.config.threshold}s)"
                        )
                        break

            time.sleep(self.config.check_interval)

        logger.info("Monitor loop ended")

    def _perform_cleanup(self) -> bool:
        """
        Execute cleanup commands to restore connectivity.

        Returns:
            True if cleanup was successful
        """
        if self._cleanup_performed:
            logger.warning("Cleanup already performed")
            return True

        logger.info("=" * 60)
        logger.info("PERFORMING EMERGENCY CLEANUP")
        logger.info("=" * 60)

        success_count = 0
        fail_count = 0

        # Execute extra cleanup commands first
        for cmd in self.config.extra_cleanup:
            self._run_cleanup_command(cmd, f"Custom: {' '.join(cmd)}")

        # Execute standard cleanup commands
        for cmd, description in CLEANUP_COMMANDS:
            if self._run_cleanup_command(cmd, description):
                success_count += 1
            else:
                fail_count += 1

        # Check if connectivity restored
        time.sleep(2)  # Wait for network to stabilize
        status = self.check_connectivity()

        if not status.is_connected and self.config.nuclear_enabled:
            logger.warning("Standard cleanup failed, executing NUCLEAR cleanup")
            for cmd, description in NUCLEAR_CLEANUP:
                self._run_cleanup_command(cmd, f"[NUCLEAR] {description}")

            time.sleep(3)
            status = self.check_connectivity()

        self._cleanup_performed = True

        if status.is_connected:
            logger.info("=" * 60)
            logger.info(f"CLEANUP SUCCESSFUL - Connectivity restored")
            logger.info(f"Successful hosts: {status.successful_hosts}")
            logger.info("=" * 60)
        else:
            logger.error("=" * 60)
            logger.error("CLEANUP FAILED - Manual intervention required!")
            logger.error("Run: sudo ./tests/emergency_restore.sh")
            logger.error("=" * 60)

        # Execute callback if configured
        if self.config.on_cleanup:
            try:
                self.config.on_cleanup()
            except Exception as e:
                logger.error(f"Cleanup callback failed: {e}")

        return status.is_connected

    def _run_cleanup_command(self, cmd: List[str], description: str) -> bool:
        """
        Run a cleanup command with sudo if needed.

        Args:
            cmd: Command to run
            description: Description for logging

        Returns:
            True if command succeeded
        """
        try:
            # Check if we need sudo
            if os.geteuid() != 0:
                cmd = ["sudo"] + cmd

            logger.info(f"Executing: {description}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info(f"  -> Success")
                return True
            else:
                # Some commands fail gracefully (e.g., interface doesn't exist)
                logger.debug(f"  -> Exit code {result.returncode}: {result.stderr.strip()}")
                return False

        except subprocess.TimeoutExpired:
            logger.warning(f"  -> Timeout")
            return False
        except Exception as e:
            logger.error(f"  -> Error: {e}")
            return False


class KillSwitchContext:
    """
    Context manager for kill switch usage in tests.

    Usage:
        with KillSwitchContext(timeout=60, threshold=10) as ks:
            # run risky network operations
            pass
        # Kill switch automatically stops on exit
    """

    def __init__(self, **kwargs):
        self.config = KillSwitchConfig(**kwargs)
        self.kill_switch: Optional[KillSwitch] = None

    def __enter__(self) -> KillSwitch:
        self.kill_switch = KillSwitch(self.config)
        self.kill_switch.start()
        return self.kill_switch

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.kill_switch:
            self.kill_switch.stop()
        return False  # Don't suppress exceptions


def force_cleanup_all() -> bool:
    """
    Force cleanup without kill switch - use for test teardown.

    Returns:
        True if connectivity is restored
    """
    ks = KillSwitch(KillSwitchConfig(nuclear_enabled=True))
    ks._triggered = True  # Skip monitoring
    return ks._perform_cleanup()


def force_cleanup_zapret() -> bool:
    """
    Force cleanup specifically for zapret - kills processes and clears iptables.

    Returns:
        True if successful
    """
    cleanup_cmds = [
        (["pkill", "-9", "nfqws"], "Kill nfqws"),
        (["pkill", "-9", "tpws"], "Kill tpws"),
        (["iptables", "-t", "mangle", "-F", "POSTROUTING"], "Flush mangle POSTROUTING"),
        (["iptables", "-t", "nat", "-F", "OUTPUT"], "Flush nat OUTPUT"),
    ]

    success = True
    for cmd, desc in cleanup_cmds:
        try:
            if os.geteuid() != 0:
                cmd = ["sudo"] + cmd
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception as e:
            logger.warning(f"Zapret cleanup command failed: {desc} - {e}")
            success = False

    return success


def force_cleanup_wireguard() -> bool:
    """
    Force cleanup specifically for WireGuard.

    Returns:
        True if successful
    """
    cleanup_cmds = [
        (["wg-quick", "down", "splitwire"], "Stop WireGuard"),
        (["ip", "link", "delete", "splitwire"], "Delete interface"),
    ]

    for cmd, desc in cleanup_cmds:
        try:
            if os.geteuid() != 0:
                cmd = ["sudo"] + cmd
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception:
            pass  # Interface might not exist

    return True


def force_cleanup_dns() -> bool:
    """
    Force cleanup specifically for DNS settings.

    Returns:
        True if successful
    """
    cleanup_cmds = [
        (["rm", "-f", "/etc/systemd/resolved.conf.d/splitwire.conf"], "Remove DNS config"),
        (["systemctl", "restart", "systemd-resolved"], "Restart systemd-resolved"),
    ]

    success = True
    for cmd, desc in cleanup_cmds:
        try:
            if os.geteuid() != 0:
                cmd = ["sudo"] + cmd
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode != 0:
                success = False
        except Exception:
            success = False

    return success


def force_cleanup_byedpi() -> bool:
    """
    Force cleanup specifically for ByeDPI.

    Returns:
        True if successful
    """
    try:
        cmd = ["pkill", "-9", "ciadpi"]
        if os.geteuid() != 0:
            cmd = ["sudo"] + cmd
        subprocess.run(cmd, capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def main():
    """Run kill switch as standalone daemon."""
    import argparse

    parser = argparse.ArgumentParser(description="Kill Switch Watchdog Daemon")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Maximum time before kill switch triggers (seconds)")
    parser.add_argument("--threshold", type=int, default=10,
                        help="Connectivity loss threshold before trigger (seconds)")
    parser.add_argument("--log-file", type=str,
                        help="Log file path")
    parser.add_argument("--nuclear", action="store_true",
                        help="Enable nuclear cleanup as last resort")
    args = parser.parse_args()

    config = KillSwitchConfig(
        timeout=args.timeout,
        threshold=args.threshold,
        nuclear_enabled=args.nuclear,
        log_file=Path(args.log_file) if args.log_file else None
    )

    ks = KillSwitch(config)

    print(f"Starting kill switch watchdog")
    print(f"  Timeout: {args.timeout}s")
    print(f"  Threshold: {args.threshold}s")
    print(f"  Nuclear: {args.nuclear}")
    print(f"  PID: {os.getpid()}")
    print(f"  Send SIGUSR1 to trigger manually: kill -USR1 {os.getpid()}")
    print()

    ks.start()

    try:
        while ks.is_running and not ks.was_triggered:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        ks.stop()

    if ks.was_triggered:
        print("Kill switch was triggered!")
        sys.exit(1)
    else:
        print("Kill switch completed normally")
        sys.exit(0)


if __name__ == "__main__":
    main()
