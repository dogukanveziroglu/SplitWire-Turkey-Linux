"""
Data models for the split tunnel service.
"""

from dataclasses import dataclass, field


@dataclass
class TunneledApp:
    """Information about an app configured for tunneling."""

    name: str
    path: str
    enabled: bool = True
    is_custom: bool = False


@dataclass
class SplitTunnelConfig:
    """Split tunnel configuration."""

    enabled: bool = False
    include_browsers: bool = False
    apps: list[TunneledApp] = field(default_factory=list)
    custom_paths: list[str] = field(default_factory=list)
