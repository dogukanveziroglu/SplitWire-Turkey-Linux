"""
ByeDPI service data models.

Enums, dataclasses, and preset definitions for the ByeDPI proxy service.
"""

from dataclasses import dataclass, field
from enum import Enum

from .constants import DEFAULT_PROXY_HOST, DEFAULT_PROXY_PORT


class ByeDPIMode(Enum):
    """ByeDPI operation mode."""

    DISORDER = "disorder"  # Packet reordering
    SPLIT = "split"  # Packet splitting
    FAKE = "fake"  # Fake packets
    OOB = "oob"  # Out-of-band data
    DISOOB = "disoob"  # Disorder + OOB
    COMBINED = "combined"  # Multiple methods


@dataclass
class ByeDPIPreset:
    """Configuration preset for ByeDPI."""

    name: str
    description: str
    args: str
    mode: ByeDPIMode = ByeDPIMode.DISORDER
    is_custom: bool = False


@dataclass
class ByeDPIConfig:
    """ByeDPI service configuration."""

    enabled: bool = False
    preset_name: str = "default"
    custom_args: str = ""
    proxy_host: str = DEFAULT_PROXY_HOST
    proxy_port: int = DEFAULT_PROXY_PORT
    include_browsers: bool = False
    tunneled_apps: list[str] = field(default_factory=list)


# ========================================================================
# Default presets
# ========================================================================

DEFAULT_PRESETS: dict[str, ByeDPIPreset] = {
    "default": ByeDPIPreset(
        name="Default",
        description="Default optimized settings",
        args="--disorder 1 --auto=torst --tlsrec 1+s",
        mode=ByeDPIMode.DISORDER,
    ),
    "discord": ByeDPIPreset(
        name="Discord",
        description="Optimized settings for Discord traffic",
        args=("--disorder 3 --auto=torst --tlsrec 1+s --fake -1 --ttl 8"),
        mode=ByeDPIMode.COMBINED,
    ),
    "preset_disorder": ByeDPIPreset(
        name="Disorder Mode",
        description="Packet order disruption",
        args="--disorder 1",
        mode=ByeDPIMode.DISORDER,
    ),
    "preset_disorder2": ByeDPIPreset(
        name="Disorder Mode 2",
        description="Advanced packet order disruption",
        args="--disorder 3",
        mode=ByeDPIMode.DISORDER,
    ),
    "preset_split": ByeDPIPreset(
        name="Split Mode",
        description="Packet splitting",
        args="--split 1",
        mode=ByeDPIMode.SPLIT,
    ),
    "preset_split_tlsrec": ByeDPIPreset(
        name="Split + TLS Record",
        description="Packet splitting with TLS record splitting",
        args="--split 1 --tlsrec 1+s",
        mode=ByeDPIMode.SPLIT,
    ),
    "preset_fake": ByeDPIPreset(
        name="Fake Mode",
        description="Sahte paket gönderme",
        args="--fake -1 --ttl 8",
        mode=ByeDPIMode.FAKE,
    ),
    "preset_oob": ByeDPIPreset(
        name="OOB Mode",
        description="Out-of-band veri",
        args="--oob 1",
        mode=ByeDPIMode.OOB,
    ),
    "preset_disoob": ByeDPIPreset(
        name="Disorder + OOB",
        description="Disorder ve OOB kombinasyonu",
        args="--disoob 1",
        mode=ByeDPIMode.DISOOB,
    ),
    "preset_auto": ByeDPIPreset(
        name="Auto Mode",
        description="Automatic detection and processing",
        args="--auto=torst",
        mode=ByeDPIMode.COMBINED,
    ),
}
