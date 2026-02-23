"""
Strategy generation for blockcheck scans.

Contains DPI bypass strategy definitions for different scan modes.
"""

from .models import ScanMode

# Basic strategies for all modes
_BASIC_STRATEGIES = [
    {
        "name": "fake+split2 TTL5",
        "mode": "nfqws",
        "args": ("--dpi-desync=fake,split2 --dpi-desync-ttl=5 --dpi-desync-fooling=md5sig"),
    },
    {
        "name": "fake+disorder2 TTL8",
        "mode": "nfqws",
        "args": ("--dpi-desync=fake,disorder2 --dpi-desync-ttl=8 --dpi-desync-fooling=md5sig"),
    },
    {
        "name": "split2 only",
        "mode": "nfqws",
        "args": "--dpi-desync=split2 --dpi-desync-split-pos=3",
    },
]

# Additional strategies for standard/full modes
_EXTENDED_STRATEGIES = [
    {
        "name": "fake TTL6",
        "mode": "nfqws",
        "args": "--dpi-desync=fake --dpi-desync-ttl=6",
    },
    {
        "name": "fake+split2 badseq",
        "mode": "nfqws",
        "args": ("--dpi-desync=fake,split2 --dpi-desync-ttl=4 --dpi-desync-fooling=badseq"),
    },
    {
        "name": "disorder2 TTL10",
        "mode": "nfqws",
        "args": "--dpi-desync=disorder2 --dpi-desync-ttl=10",
    },
    {
        "name": "TPWS split",
        "mode": "tpws",
        "args": "--split-pos=3 --disorder",
    },
]

# Comprehensive strategies for full mode
_FULL_STRATEGIES = [
    {
        "name": "fake+split TTL3",
        "mode": "nfqws",
        "args": ("--dpi-desync=fake,split --dpi-desync-ttl=3 --dpi-desync-fooling=md5sig"),
    },
    {
        "name": "fake+split2 TTL2 badsum",
        "mode": "nfqws",
        "args": ("--dpi-desync=fake,split2 --dpi-desync-ttl=2 --dpi-desync-fooling=badsum"),
    },
    {
        "name": "multisplit",
        "mode": "nfqws",
        "args": "--dpi-desync=multisplit --dpi-desync-split-pos=3,5",
    },
    {
        "name": "TPWS split+disorder",
        "mode": "tpws",
        "args": "--split-pos=3 --disorder --oob",
    },
    {
        "name": "fake+fakedsplit",
        "mode": "nfqws",
        "args": ("--dpi-desync=fake,fakedsplit --dpi-desync-ttl=4"),
    },
]


def generate_strategies(mode: ScanMode) -> list[dict]:
    """Generate list of strategies to test based on scan mode."""
    strategies = list(_BASIC_STRATEGIES)

    if mode in (ScanMode.STANDARD, ScanMode.FULL):
        strategies.extend(_EXTENDED_STRATEGIES)

    if mode == ScanMode.FULL:
        strategies.extend(_FULL_STRATEGIES)

    return strategies
