"""
Data models and enums for the proxy route service.
"""

from dataclasses import dataclass, field
from enum import Enum

from .constants import DEFAULT_PROXY_HOST, DEFAULT_PROXY_PORT


class ProxyMethod(Enum):
    """Method for routing apps through proxy."""

    CGPROXY = "cgproxy"  # cgroup-based (recommended)
    REDSOCKS = "redsocks"  # iptables-based redirect
    ENV = "env"  # Environment variables (per-app only)


@dataclass
class ProxiedApp:
    """Information about an app configured for proxy routing."""

    name: str
    path: str
    enabled: bool = True
    is_custom: bool = False


@dataclass
class ProxyRouteConfig:
    """Proxy routing configuration."""

    enabled: bool = False
    method: ProxyMethod = ProxyMethod.CGPROXY
    proxy_host: str = DEFAULT_PROXY_HOST
    proxy_port: int = DEFAULT_PROXY_PORT
    include_browsers: bool = False
    apps: list[ProxiedApp] = field(default_factory=list)
    custom_paths: list[str] = field(default_factory=list)
