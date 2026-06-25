"""
GeziGuru MCP server'ı için uçtan uca CRUD testi.

MCP server'ı bir alt süreç olarak (stdio) başlatır, gerçek bir MCP client ile
araçları çağırır ve sonuçları doğrular. Çalıştırma:

    python -m tests.test_mcp_client
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _payload(result) -> object:
    """call_tool sonucundan JSON içeriğini çıkarır."""
    # FastMCP yapılandırılmış çıktıyı structuredContent içinde de döndürür.
    if getattr(result, "structuredContent", None):
        sc = result.structuredContent
        # FastMCP liste/skaler dönüşleri {"result": ...} altına sarar.
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    # Aksi halde ilk metin içeriğini JSON olarak çöz.
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    return None


async def run() -> int:
    # MCP server artık demo veriyi otomatik yüklemiyor; test kendi verisini tohumlasın.
    from app.data import db
    db.reset_db(seed=True)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    failures = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        mark = "✅" if condition else "❌"
        print(f"  {mark} {name}" + (f" — {detail}" if detail and not condition else ""))
        if not condition:
            failures += 1

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) Araç listesi
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            print(f"Sunulan araç sayısı: {len(tool_names)}")
            print("  " + ", ".join(sorted(tool_names)))
            for expected in ("list_trips", "create_trip", "add_itinerary_item",
                             "budget_summary", "create_booking", "confirm_booking"):
                check(f"araç mevcut: {expected}", expected in tool_names)

            # 2) Seed gezisini oku
            trips = _payload(await session.call_tool("list_trips", {}))
            check("list_trips en az 1 gezi döndürdü", len(trips) >= 1)
            demo = next((t for t in trips if t["destination"] == "İstanbul"), trips[0])
            tid = demo["id"]
            print(f"Demo gezi id: {tid} ({demo['destination']})")

            # 3) Itinerary oku
            itinerary = _payload(await session.call_tool("get_itinerary", {"trip_id": tid}))
            check("itinerary kalemleri var", len(itinerary) >= 1,
                  f"dönen kalem: {len(itinerary)}")

            # 4) Yeni gezi oluştur (CREATE)
            new_trip = _payload(await session.call_tool("create_trip", {
                "destination": "İzmir",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "budget_total": 5000,
            }))
            check("create_trip yeni gezi döndürdü", new_trip.get("destination") == "İzmir")
            new_id = new_trip["id"]

            # 5) Plana kalem ekle
            item = _payload(await session.call_tool("add_itinerary_item", {
                "trip_id": new_id, "day_number": 1, "title": "Saat Kulesi",
                "time": "10:00", "place": "Konak", "category": "tarihi", "est_cost": 0,
            }))
            check("add_itinerary_item kalem ekledi", item.get("title") == "Saat Kulesi")

            # 6) Harcama ekle + bütçe özeti
            await session.call_tool("add_expense", {
                "trip_id": new_id, "item": "Otobüs bileti", "amount": 750,
                "category": "ulaşim", "day_number": 1,
            })
            summary = _payload(await session.call_tool("budget_summary", {"trip_id": new_id}))
            check("budget_summary harcanan=750", summary.get("spent") == 750,
                  f"spent={summary.get('spent')}")
            check("budget_summary kalan=4250", summary.get("remaining") == 4250,
                  f"remaining={summary.get('remaining')}")

            # 7) Rezervasyon oluştur (pending) + onayla (confirmed)
            booking = _payload(await session.call_tool("create_booking", {
                "trip_id": new_id, "type": "konaklama", "name": "Konak Otel",
                "date": "2026-08-01", "cost": 2000,
            }))
            check("create_booking 'pending' döndürdü", booking.get("status") == "pending",
                  f"status={booking.get('status')}")
            confirmed = _payload(await session.call_tool("confirm_booking", {
                "booking_id": booking["id"],
            }))
            check("confirm_booking 'confirmed' yaptı", confirmed.get("status") == "confirmed",
                  f"status={confirmed.get('status')}")

    print()
    if failures == 0:
        print("🎉 Tüm MCP server testleri geçti.")
        return 0
    print(f"⚠️  {failures} test başarısız.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
