"""
SplitWire proxy route service package.

Re-exports all public names so that existing imports like
``from splitwire.services.proxy_route import ProxyRouteService`` continue to work.
"""

from .constants import DEFAULT_PROXY_HOST, DEFAULT_PROXY_PORT
from .models import ProxiedApp, ProxyMethod, ProxyRouteConfig
from .service import ProxyRouteService

# Singleton instance
_proxy_route_service: ProxyRouteService | None = None


def get_proxy_route_service() -> ProxyRouteService:
    """Get the global proxy route service instance."""
    global _proxy_route_service
    if _proxy_route_service is None:
        _proxy_route_service = ProxyRouteService()
    return _proxy_route_service


__all__ = [
    "DEFAULT_PROXY_HOST",
    "DEFAULT_PROXY_PORT",
    "ProxiedApp",
    "ProxyMethod",
    "ProxyRouteConfig",
    "ProxyRouteService",
    "get_proxy_route_service",
]
