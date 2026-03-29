"""Data models and enums for the Zapret service."""

from dataclasses import dataclass, field
from enum import Enum


class ZapretMode(Enum):
    """Zapret operation mode."""

    NFQWS = "nfqws"  # Netfilter queue (packet modification)
    TPWS = "tpws"  # Transparent proxy
    COMBINED = "combined"  # Both modes


class ScanMode(Enum):
    """Blockcheck scan mode."""

    QUICK = "quick"  # basic scan
    STANDARD = "standard"  # moderate scan
    FULL = "full"  # comprehensive scan


@dataclass
class ZapretPreset:
    """Configuration preset for Zapret."""

    name: str
    description: str
    nfqws_args: str = ""
    tpws_args: str = ""
    mode: ZapretMode = ZapretMode.NFQWS
    use_blacklist: bool = False
    is_custom: bool = False


@dataclass
class ZapretConfig:
    """Zapret service configuration."""

    enabled: bool = False
    mode: ZapretMode = ZapretMode.NFQWS
    preset_name: str = "discord"
    custom_nfqws_args: str = ""
    custom_tpws_args: str = ""
    use_blacklist: bool = False
    http_ports: list[int] = field(default_factory=lambda: [80])
    https_ports: list[int] = field(default_factory=lambda: [443])
    quic_enabled: bool = False


DEFAULT_PRESETS: dict[str, ZapretPreset] = {
    "discord": ZapretPreset(
        name="Discord",
        description="Optimized settings for Discord traffic",
        nfqws_args=("--dpi-desync=fake,split2 --dpi-desync-ttl=5 --dpi-desync-fooling=md5sig"),
        mode=ZapretMode.NFQWS,
    ),
    "general": ZapretPreset(
        name="General",
        description="General purpose settings",
        nfqws_args=("--dpi-desync=fake,disorder2 --dpi-desync-ttl=8 --dpi-desync-fooling=md5sig"),
        mode=ZapretMode.NFQWS,
    ),
    "youtube": ZapretPreset(
        name="YouTube",
        description="Optimized settings for YouTube traffic",
        nfqws_args=(
            "--dpi-desync=fake,split2 --dpi-desync-ttl=4 --dpi-desync-fooling=md5sig,badseq"
        ),
        mode=ZapretMode.NFQWS,
    ),
    "preset_split": ZapretPreset(
        name="Split Mode",
        description="Packet splitting method",
        nfqws_args="--dpi-desync=split2 --dpi-desync-split-pos=3",
        mode=ZapretMode.NFQWS,
    ),
    "preset_fake": ZapretPreset(
        name="Fake Mode",
        description="Fake packet method",
        nfqws_args="--dpi-desync=fake --dpi-desync-ttl=6",
        mode=ZapretMode.NFQWS,
    ),
    "preset_disorder": ZapretPreset(
        name="Disorder Mode",
        description="Packet order disruption",
        nfqws_args="--dpi-desync=disorder2 --dpi-desync-ttl=8",
        mode=ZapretMode.NFQWS,
    ),
    "preset_tpws": ZapretPreset(
        name="TPWS Mode",
        description="Transparent proxy method",
        tpws_args="--split-pos=3 --disorder",
        mode=ZapretMode.TPWS,
    ),
    "preset_combined": ZapretPreset(
        name="Combined Mode",
        description="nfqws + tpws birlikte",
        nfqws_args="--dpi-desync=fake,split2 --dpi-desync-ttl=5",
        tpws_args="--split-pos=3",
        mode=ZapretMode.COMBINED,
    ),
}
