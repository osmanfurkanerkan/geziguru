"""
GeziGuru MCP Server — gezi / itinerary / bütçe / rezervasyon araçları.

Bu, kendi yazdığımız Model Context Protocol (MCP) server'ıdır. Ajanlar (ADK)
seyahat verisine doğrudan SQLite'a değil, bu MCP server üzerinden erişir.
Bu sayede veri erişimi tek bir denetlenebilir arayüzde toplanır.

Çalıştırma (stdio):
    python -m mcp_server.server

Sunulan araçlar:
    Gezi      : list_trips, get_trip, create_trip
    Plan      : get_itinerary, add_itinerary_item
    Bütçe     : add_expense, list_expenses, budget_summary
    Rezervasyon: list_bookings, create_booking, confirm_booking

Not: create_booking rezervasyonu 'pending' (onay bekliyor) olarak oluşturur.
Onay (confirm_booking) yalnızca kullanıcı onayından sonra çağrılmalıdır —
human-in-the-loop / zero-trust yaklaşımı (bkz. app/security/approval.py).
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

# Demo çıktısını temiz tutmak için server'ın INFO request loglarını tamamen kapat.
# (MCP kütüphanesi kendi handler'ını kurduğu için setLevel yetmiyor; disable global ve kesin.)
logging.disable(logging.INFO)

# Paket içe aktarımının "python -m mcp_server.server" ile çalışması için kök dizini ekle.
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.data import db  # noqa: E402

# Server başlarken yalnızca şemanın var olduğundan emin ol — demo veriyi BURADA YÜKLEME.
# (Aksi halde web sitesi temiz başlasa bile MCP alt süreci demo gezisini geri ekler ve
# ajan, kullanıcının vermediği demo bütçesini onun sanır.) Demo tohumlama; CLI (main.py),
# testler ve demo betiği tarafından açıkça yapılır.
db.init_db(seed=False)

mcp = FastMCP(
    "geziguru-data",
    instructions=(
        "GeziGuru seyahat verisi MCP server'ı. Geziler, gün gün planlar, "
        "bütçe/harcamalar ve rezervasyonlar için CRUD araçları sunar. "
        "Rezervasyonlar 'pending' oluşturulur ve yalnızca kullanıcı onayından "
        "sonra confirm_booking ile onaylanmalıdır."
    ),
)


# --------------------------------------------------------------------------- #
# Gezi (trips)
# --------------------------------------------------------------------------- #
@mcp.tool()
def list_trips() -> list[dict[str, Any]]:
    """Kayıtlı tüm gezileri listeler."""
    return db.list_trips()


@mcp.tool()
def get_trip(trip_id: int) -> dict[str, Any]:
    """Belirli bir geziyi id ile getirir."""
    trip = db.get_trip(trip_id)
    return trip or {"error": f"Gezi bulunamadı: {trip_id}"}


@mcp.tool()
def create_trip(
    destination: str,
    start_date: str,
    end_date: str,
    budget_total: float = 0,
    currency: str = "TRY",
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Yeni bir gezi oluşturur.

    Args:
        destination: Varış yeri (örn. "İstanbul").
        start_date: Başlangıç tarihi, YYYY-MM-DD.
        end_date: Bitiş tarihi, YYYY-MM-DD.
        budget_total: Toplam bütçe (varsayılan 0).
        currency: Para birimi (varsayılan "TRY").
        notes: Opsiyonel not.
    """
    return db.create_trip(destination, start_date, end_date, budget_total, currency, notes)


# --------------------------------------------------------------------------- #
# Plan (itinerary)
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_itinerary(trip_id: int, day_number: Optional[int] = None) -> list[dict[str, Any]]:
    """Gezinin gün gün planını verir. day_number verilirse yalnızca o günü döndürür."""
    return db.get_itinerary(trip_id, day_number)


@mcp.tool()
def add_itinerary_item(
    trip_id: int,
    day_number: int,
    title: str,
    time: Optional[str] = None,
    place: Optional[str] = None,
    category: Optional[str] = None,
    est_cost: float = 0,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Plana yeni bir kalem (gezilecek yer / aktivite) ekler.

    Args:
        trip_id: Gezi id'si.
        day_number: Gün numarası (1, 2, 3...).
        title: Kalem başlığı (örn. "Ayasofya gezisi").
        time: Saat "HH:MM" (opsiyonel).
        place: Semt/yer (opsiyonel).
        category: Kategori (tarihi/müze/yemek/aktivite...).
        est_cost: Tahmini maliyet.
        notes: Opsiyonel not.
    """
    return db.add_itinerary_item(
        trip_id, day_number, title, time, place, category, est_cost, notes
    )


# --------------------------------------------------------------------------- #
# Bütçe (expenses)
# --------------------------------------------------------------------------- #
@mcp.tool()
def add_expense(
    trip_id: int,
    item: str,
    amount: float,
    category: Optional[str] = None,
    day_number: Optional[int] = None,
) -> dict[str, Any]:
    """Geziye bir harcama kaydı ekler."""
    return db.add_expense(trip_id, item, amount, category, day_number)


@mcp.tool()
def list_expenses(trip_id: int) -> list[dict[str, Any]]:
    """Gezinin tüm harcamalarını listeler."""
    return db.list_expenses(trip_id)


@mcp.tool()
def budget_summary(trip_id: int) -> dict[str, Any]:
    """Bütçe özeti: toplam, harcanan, kalan ve kategori dağılımı."""
    return db.budget_summary(trip_id)


# --------------------------------------------------------------------------- #
# Rezervasyon (bookings) — onay akışı
# --------------------------------------------------------------------------- #
@mcp.tool()
def list_bookings(trip_id: int) -> list[dict[str, Any]]:
    """Gezinin rezervasyonlarını (onay durumlarıyla) listeler."""
    return db.list_bookings(trip_id)


@mcp.tool()
def create_booking(
    trip_id: int,
    type: str,
    name: str,
    date: Optional[str] = None,
    cost: float = 0,
) -> dict[str, Any]:
    """Yeni rezervasyon oluşturur — 'pending' (onay bekliyor) durumunda.

    ÖNEMLİ: Bu işlem rezervasyonu kesinleştirmez. Kesinleştirmek için kullanıcı
    onayı alınıp confirm_booking çağrılmalıdır (human-in-the-loop).

    Args:
        trip_id: Gezi id'si.
        type: Rezervasyon türü (konaklama/ulaşim/aktivite).
        name: Rezervasyon adı (örn. "Sultanahmet Butik Otel").
        date: Tarih YYYY-MM-DD (opsiyonel).
        cost: Maliyet.
    """
    return db.create_booking(trip_id, type, name, date, cost)


@mcp.tool()
def confirm_booking(booking_id: int) -> dict[str, Any]:
    """Bekleyen bir rezervasyonu onaylar.

    Yalnızca kullanıcı açıkça onayladıktan sonra çağrılmalıdır (zero-trust).
    """
    result = db.confirm_booking(booking_id)
    return result or {"error": f"Rezervasyon bulunamadı: {booking_id}"}


def main() -> None:
    """MCP server'ı stdio üzerinden çalıştırır."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
