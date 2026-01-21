"""
Helper functions for SplitWire-Turkey integration tests.

This module provides utility functions used across integration tests
for network verification, process management, and system state checks.
"""

import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class PingResult:
    """Result of a ping test."""
    success: bool
    host: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class CurlResult:
    """Result of a curl test."""
    success: bool
    url: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


def ping_test(host: str, count: int = 1, timeout: int = 5) -> PingResult:
    """
    Perform a ping test to a host.

    Args:
        host: Host to ping (IP or hostname)
        count: Number of pings
        timeout: Timeout in seconds

    Returns:
        PingResult with success status and latency
    """
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )

        if result.returncode == 0:
            # Extract latency from output
            latency = None
            for line in result.stdout.split("\n"):
                if "time=" in line:
                    match = re.search(r'time=(\d+\.?\d*)', line)
                    if match:
                        latency = float(match.group(1))
                        break

            return PingResult(success=True, host=host, latency_ms=latency)
        else:
            return PingResult(
                success=False,
                host=host,
                error=result.stderr.strip() or "Ping failed"
            )

    except subprocess.TimeoutExpired:
        return PingResult(success=False, host=host, error="Timeout")
    except Exception as e:
        return PingResult(success=False, host=host, error=str(e))


def tcp_connect_test(host: str, port: int, timeout: float = 5.0) -> bool:
    """
    Test TCP connectivity to a host:port.

    Args:
        host: Host to connect to
        port: Port number
        timeout: Connection timeout

    Returns:
        True if connection succeeded
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def curl_test(
    url: str,
    timeout: int = 10,
    proxy: Optional[str] = None,
    follow_redirects: bool = True
) -> CurlResult:
    """
    Perform a curl test to a URL.

    Args:
        url: URL to fetch
        timeout: Timeout in seconds
        proxy: Optional proxy URL (e.g., "socks5://127.0.0.1:1080")
        follow_redirects: Whether to follow redirects

    Returns:
        CurlResult with status and timing
    """
    try:
        cmd = [
            "curl",
            "-s",
            "-o", "/dev/null",
            "-w", "%{http_code},%{time_total}",
            "--max-time", str(timeout),
        ]

        if follow_redirects:
            cmd.append("-L")

        if proxy:
            cmd.extend(["--proxy", proxy])

        cmd.append(url)

        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        elapsed = (time.time() - start_time) * 1000

        if result.returncode == 0 and result.stdout:
            parts = result.stdout.strip().split(",")
            if len(parts) >= 2:
                status_code = int(parts[0])
                response_time = float(parts[1]) * 1000

                return CurlResult(
                    success=200 <= status_code < 400,
                    url=url,
                    status_code=status_code,
                    response_time_ms=response_time
                )

        return CurlResult(
            success=False,
            url=url,
            error=result.stderr.strip() or "Curl failed"
        )

    except subprocess.TimeoutExpired:
        return CurlResult(success=False, url=url, error="Timeout")
    except Exception as e:
        return CurlResult(success=False, url=url, error=str(e))


def dns_lookup(hostname: str, server: Optional[str] = None) -> List[str]:
    """
    Perform DNS lookup for a hostname.

    Args:
        hostname: Hostname to resolve
        server: Optional DNS server to use

    Returns:
        List of resolved IP addresses
    """
    try:
        cmd = ["nslookup", hostname]
        if server:
            cmd.append(server)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        # Parse IP addresses from output
        ips = []
        in_answer = False
        for line in result.stdout.split("\n"):
            if "Name:" in line:
                in_answer = True
            if in_answer and "Address:" in line:
                ip = line.split("Address:")[-1].strip()
                if ip and not ip.startswith("::"):  # Skip IPv6 for now
                    ips.append(ip)

        return ips

    except Exception:
        return []


def get_current_dns() -> List[str]:
    """
    Get currently configured DNS servers.

    Returns:
        List of DNS server IPs
    """
    servers = []

    # Try resolvectl
    try:
        result = subprocess.run(
            ["resolvectl", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "DNS Servers:" in line or "Current DNS Server:" in line:
                    ips = re.findall(r'\d+\.\d+\.\d+\.\d+', line)
                    servers.extend(ips)
    except Exception:
        pass

    # Fallback to resolv.conf
    if not servers:
        try:
            content = Path("/etc/resolv.conf").read_text()
            for line in content.split("\n"):
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
        except Exception:
            pass

    return list(dict.fromkeys(servers))


def get_iptables_rules(table: str = "filter") -> str:
    """
    Get iptables rules for a table.

    Args:
        table: Table name (filter, nat, mangle, raw)

    Returns:
        iptables output as string
    """
    try:
        cmd = ["iptables", "-t", table, "-L", "-n", "-v"]
        if os.geteuid() != 0:
            cmd = ["sudo"] + cmd

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def has_nfqueue_rules() -> bool:
    """Check if iptables has NFQUEUE rules."""
    mangle_rules = get_iptables_rules("mangle")
    return "NFQUEUE" in mangle_rules


def has_redirect_rules() -> bool:
    """Check if iptables has REDIRECT rules."""
    nat_rules = get_iptables_rules("nat")
    return "REDIRECT" in nat_rules


def get_interfaces() -> List[str]:
    """
    Get list of network interfaces.

    Returns:
        List of interface names
    """
    try:
        result = subprocess.run(
            ["ip", "-o", "link", "show"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []

        interfaces = []
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    iface = parts[1].strip().split("@")[0]
                    interfaces.append(iface)
        return interfaces
    except Exception:
        return []


def interface_exists(name: str) -> bool:
    """
    Check if a network interface exists.

    Args:
        name: Interface name

    Returns:
        True if interface exists
    """
    try:
        result = subprocess.run(
            ["ip", "link", "show", name],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def is_process_running(name: str) -> bool:
    """
    Check if a process is running by name.

    Excludes zombie processes (state 'Z') which are technically still in
    the process table but are not running.

    Args:
        name: Process name

    Returns:
        True if process is running (not zombie)
    """
    try:
        # Get PIDs of processes with this name
        pids = os.popen(f"pgrep -x {name} 2>/dev/null").read().strip()
        if not pids:
            return False

        # Check if any of them are NOT zombies
        for pid in pids.split('\n'):
            pid = pid.strip()
            if pid:
                # Check process state - exclude zombies
                state_output = os.popen(f"ps -o state= -p {pid} 2>/dev/null").read().strip()
                if state_output and state_output[0] != 'Z':
                    return True
        return False
    except Exception:
        return False


def get_process_pids(name: str) -> List[int]:
    """
    Get PIDs of processes by name.

    Args:
        name: Process name

    Returns:
        List of PIDs
    """
    try:
        result = subprocess.run(
            ["pgrep", "-x", name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return [int(pid) for pid in result.stdout.strip().split("\n")]
        return []
    except Exception:
        return []


def kill_process(name: str, signal: int = 9) -> bool:
    """
    Kill a process by name.

    Args:
        name: Process name
        signal: Signal number (default: SIGKILL)

    Returns:
        True if process was killed or didn't exist
    """
    try:
        cmd = ["pkill", f"-{signal}", name]
        if os.geteuid() != 0:
            cmd = ["sudo"] + cmd

        subprocess.run(cmd, capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def is_port_listening(port: int, protocol: str = "tcp") -> bool:
    """
    Check if a port is being listened on.

    Args:
        port: Port number
        protocol: Protocol (tcp or udp)

    Returns:
        True if port is listening
    """
    try:
        result = subprocess.run(
            ["ss", "-ln", f"-{protocol[0]}", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # Check if any lines after header contain LISTEN
        lines = result.stdout.strip().split("\n")
        return len(lines) > 1 and "LISTEN" in result.stdout
    except Exception:
        return False


def wait_for_port(
    port: int,
    timeout: float = 30.0,
    interval: float = 0.5,
    should_exist: bool = True
) -> bool:
    """
    Wait for a port to start or stop listening.

    Args:
        port: Port number
        timeout: Maximum wait time
        interval: Check interval
        should_exist: True to wait for port to open, False to wait for close

    Returns:
        True if condition was met within timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        listening = is_port_listening(port)
        if listening == should_exist:
            return True
        time.sleep(interval)
    return False


def get_routing_table() -> str:
    """Get current routing table."""
    try:
        result = subprocess.run(
            ["ip", "route", "show"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def route_exists(destination: str) -> bool:
    """
    Check if a route exists.

    Args:
        destination: Destination network/host

    Returns:
        True if route exists
    """
    try:
        result = subprocess.run(
            ["ip", "route", "get", destination],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_default_gateway() -> Optional[str]:
    """Get the default gateway IP."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            match = re.search(r'via\s+(\d+\.\d+\.\d+\.\d+)', result.stdout)
            if match:
                return match.group(1)
        return None
    except Exception:
        return None


def force_cleanup_all() -> None:
    """
    Force cleanup of all SplitWire components.
    Use this in test teardown to ensure clean state.
    """
    from .kill_switch import (
        force_cleanup_zapret,
        force_cleanup_wireguard,
        force_cleanup_dns,
        force_cleanup_byedpi
    )

    force_cleanup_zapret()
    force_cleanup_byedpi()
    force_cleanup_wireguard()
    force_cleanup_dns()


def wait_for_connectivity(timeout: float = 30.0, interval: float = 1.0) -> bool:
    """
    Wait for network connectivity to be established.

    Args:
        timeout: Maximum wait time
        interval: Check interval

    Returns:
        True if connectivity established within timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        if tcp_connect_test("8.8.8.8", 53, timeout=3.0):
            return True
        time.sleep(interval)
    return False


def verify_connectivity() -> Dict[str, bool]:
    """
    Verify connectivity to multiple hosts.

    Returns:
        Dictionary mapping host to connectivity status
    """
    hosts = [
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
        ("9.9.9.9", 53),
    ]

    results = {}
    for host, port in hosts:
        results[host] = tcp_connect_test(host, port, timeout=3.0)

    return results


def is_root() -> bool:
    """Check if running as root."""
    return os.geteuid() == 0


def require_root() -> None:
    """
    Raise an error if not running as root.

    Raises:
        PermissionError: If not root
    """
    if not is_root():
        raise PermissionError("This test requires root privileges")


def skip_if_no_internet() -> None:
    """
    Raise SkipTest if no internet connectivity.

    Raises:
        pytest.skip: If no connectivity
    """
    import pytest
    if not tcp_connect_test("8.8.8.8", 53, timeout=5.0):
        pytest.skip("No internet connectivity available")
