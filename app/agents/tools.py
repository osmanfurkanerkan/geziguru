"""
ADK ajanlarını kendi MCP server'ımıza bağlayan toolset fabrikası.

Ajanlar veriye doğrudan SQLite ile değil, mcp_server/server.py üzerinden erişir.
Burada her ajan için, yalnızca işine yarayan araçları içeren bir McpToolset üretiriz
(tool_filter). Böylece her ajan sadece kendi sorumluluğundaki araçları görür —
"en az yetki" (least privilege) ilkesi.
"""

from __future__ import annotations

import sys
from typing import List

from mcp import StdioServerParameters
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams

from app.config import PROJECT_ROOT


def _server_params() -> StdioServerParameters:
    """MCP server'ı alt süreç olarak başlatan stdio parametreleri."""
    return StdioServerParameters(
        command=sys.executable,                 # mevcut Python yorumlayıcısı
        args=["-m", "mcp_server.server"],        # python -m mcp_server.server
        cwd=PROJECT_ROOT,
        env={"PYTHONIOENCODING": "utf-8", **_os_environ()},
    )


def _os_environ() -> dict:
    import os
    return dict(os.environ)


def make_toolset(tool_filter: List[str]) -> McpToolset:
    """Verilen araç adlarıyla sınırlı bir MCP toolset üretir.

    Args:
        tool_filter: Bu toolset'in göstereceği MCP araç adları
                     (örn. ["get_itinerary", "add_itinerary_item"]).
    """
    return McpToolset(
        connection_params=StdioConnectionParams(server_params=_server_params()),
        tool_filter=tool_filter,
    )


# Hangi ajan hangi araçları görür (sorumluluk dağılımı tek yerde, okunaklı).
ITINERARY_TOOLS = [
    "list_trips",
    "get_trip",
    "create_trip",
    "get_itinerary",
    "add_itinerary_item",
]

BOOKING_TOOLS = [
    "list_trips",
    "get_trip",
    "budget_summary",
    "add_expense",
    "list_expenses",
    "list_bookings",
    "create_booking",
    "confirm_booking",
]
