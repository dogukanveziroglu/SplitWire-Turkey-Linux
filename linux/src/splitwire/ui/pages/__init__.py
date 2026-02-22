"""
SplitWire UI Pages.

Contains all application pages:
- MainPage: WireGuard/WireSock setup
- ByeDPIPage: ByeDPI proxy setup
- RepairPage: Discord repair tools
- AdvancedPage: Advanced service management
- SettingsPage: Application settings

Disabled pages:
- ZapretPage: Zapret packet processing
- GoodbyeDPIPage: GoodbyeDPI (nfqws on Linux)
"""

from .main_page import MainPage
from .byedpi_page import ByeDPIPage

# Disabled
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
