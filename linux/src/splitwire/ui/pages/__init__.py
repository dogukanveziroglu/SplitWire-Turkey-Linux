"""
SplitWire-Turkey UI Pages.

Contains all application pages:
- MainPage: WireGuard/WireSock setup
- ByeDPIPage: ByeDPI proxy setup
- RepairPage: Discord repair tools
- AdvancedPage: Advanced service management
- SettingsPage: Application settings

Disabled pages (don't work against Turkish ISP):
- ZapretPage: Zapret DPI bypass
- GoodbyeDPIPage: GoodbyeDPI (nfqws on Linux)
"""

from .main_page import MainPage
from .byedpi_page import ByeDPIPage
# Disabled - Zapret doesn't work against Turkish ISP deep packet inspection
# from .zapret_page import ZapretPage
# from .goodbyedpi_page import GoodbyeDPIPage
from .repair_page import RepairPage
from .advanced_page import AdvancedPage
from .settings_page import SettingsPage

__all__ = [
    "MainPage",
    "ByeDPIPage",
    # "ZapretPage",     # Disabled
    # "GoodbyeDPIPage", # Disabled
    "RepairPage",
    "AdvancedPage",
    "SettingsPage",
]
