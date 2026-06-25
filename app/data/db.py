"""
GeziGuru veri katmanı — SQLite.

Tüm gezi/itinerary/bütçe/rezervasyon verisi burada tutulur. Hem MCP server
(mcp_server/server.py) hem de ajanlar bu modüldeki fonksiyonları kullanır.

Tablolar:
  - trips            : geziler (varış, tarih, bütçe)
  - itinerary_items  : gün gün gezi planı kalemleri
  - expenses         : harcama/bütçe takibi kayıtları
  - bookings         : rezervasyonlar (onay durumu ile — human-in-the-loop)

Kullanım:
  from app.data import db
  db.init_db(seed=True)   # şemayı kur + örnek İstanbul gezisini ekle
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator, Optional

# Veritabanı yolu .env'den (GEZIGURU_DB) override edilebilir.
DEFAULT_DB_PATH = os.environ.get(
    "GEZIGURU_DB",
    os.path.join(os.path.dirname(__file__), "geziguru.db"),
)


# --------------------------------------------------------------------------- #
# Bağlantı yönetimi
# --------------------------------------------------------------------------- #
@contextmanager
def get_conn(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Satırları sözlük gibi döndüren bir SQLite bağlantısı verir."""
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Şema
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    destination  TEXT    NOT NULL,
    start_date   TEXT    NOT NULL,          -- YYYY-MM-DD
    end_date     TEXT    NOT NULL,          -- YYYY-MM-DD
    budget_total REAL    NOT NULL DEFAULT 0,
    currency     TEXT    NOT NULL DEFAULT 'TRY',
    notes        TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS itinerary_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id     INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number  INTEGER NOT NULL,           -- 1, 2, 3...
    time        TEXT,                        -- "09:30" gibi (opsiyonel)
    title       TEXT    NOT NULL,
    place       TEXT,
    category    TEXT,                        -- tarihi/yemek/müze/ulaşim...
    est_cost    REAL    NOT NULL DEFAULT 0,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id     INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    item        TEXT    NOT NULL,
    category    TEXT,
    amount      REAL    NOT NULL DEFAULT 0,
    day_number  INTEGER,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id      INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    type         TEXT    NOT NULL,          -- konaklama/ulaşim/aktivite
    name         TEXT    NOT NULL,
    date         TEXT,                       -- YYYY-MM-DD
    cost         REAL    NOT NULL DEFAULT 0,
    status       TEXT    NOT NULL DEFAULT 'pending',  -- pending/confirmed/cancelled
    confirmed_at TEXT
);
"""


def init_db(db_path: str | None = None, seed: bool = False) -> None:
    """Şemayı oluşturur. seed=True ise (ve tablo boşsa) örnek gezi ekler."""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
    if seed:
        seed_demo_data(db_path)


def reset_db(db_path: str | None = None, seed: bool = True) -> None:
    """Tüm tabloları sıfırlar (demo/test için)."""
    with get_conn(db_path) as conn:
        for table in ("bookings", "expenses", "itinerary_items", "trips"):
            conn.execute(f"DELETE FROM {table};")
    if seed:
        seed_demo_data(db_path)


# --------------------------------------------------------------------------- #
# Trips (gezi) CRUD
# --------------------------------------------------------------------------- #
def create_trip(
    destination: str,
    start_date: str,
    end_date: str,
    budget_total: float = 0,
    currency: str = "TRY",
    notes: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO trips (destination, start_date, end_date, budget_total, currency, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (destination, start_date, end_date, budget_total, currency, notes),
        )
        trip_id = cur.lastrowid
    return get_trip(trip_id, db_path)  # type: ignore[return-value]


def get_trip(trip_id: int, db_path: str | None = None) -> Optional[dict[str, Any]]:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    return _row_to_dict(row)


def list_trips(db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM trips ORDER BY start_date").fetchall()
    return _rows_to_list(rows)


def delete_trip(trip_id: int, db_path: str | None = None) -> bool:
    with get_conn(db_path) as conn:
        cur = conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Itinerary (gün gün plan) CRUD
# --------------------------------------------------------------------------- #
def add_itinerary_item(
    trip_id: int,
    day_number: int,
    title: str,
    time: str | None = None,
    place: str | None = None,
    category: str | None = None,
    est_cost: float = 0,
    notes: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO itinerary_items
               (trip_id, day_number, time, title, place, category, est_cost, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (trip_id, day_number, time, title, place, category, est_cost, notes),
        )
        item_id = cur.lastrowid
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM itinerary_items WHERE id = ?", (item_id,)
        ).fetchone()
    return _row_to_dict(row)  # type: ignore[return-value]


def get_itinerary(
    trip_id: int, day_number: int | None = None, db_path: str | None = None
) -> list[dict[str, Any]]:
    """Gezinin tüm planını ya da tek bir gününü, gün ve saate göre sıralı verir."""
    with get_conn(db_path) as conn:
        if day_number is None:
            rows = conn.execute(
                """SELECT * FROM itinerary_items WHERE trip_id = ?
                   ORDER BY day_number, time""",
                (trip_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM itinerary_items WHERE trip_id = ? AND day_number = ?
                   ORDER BY time""",
                (trip_id, day_number),
            ).fetchall()
    return _rows_to_list(rows)


def delete_itinerary_item(item_id: int, db_path: str | None = None) -> bool:
    with get_conn(db_path) as conn:
        cur = conn.execute("DELETE FROM itinerary_items WHERE id = ?", (item_id,))
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Expenses (harcama/bütçe) CRUD
# --------------------------------------------------------------------------- #
def add_expense(
    trip_id: int,
    item: str,
    amount: float,
    category: str | None = None,
    day_number: int | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO expenses (trip_id, item, category, amount, day_number)
               VALUES (?, ?, ?, ?, ?)""",
            (trip_id, item, category, amount, day_number),
        )
        exp_id = cur.lastrowid
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (exp_id,)).fetchone()
    return _row_to_dict(row)  # type: ignore[return-value]


def list_expenses(trip_id: int, db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE trip_id = ? ORDER BY created_at", (trip_id,)
        ).fetchall()
    return _rows_to_list(rows)


def budget_summary(trip_id: int, db_path: str | None = None) -> dict[str, Any]:
    """Bütçe özeti: toplam bütçe, harcanan, kalan, kategori dağılımı."""
    trip = get_trip(trip_id, db_path)
    if trip is None:
        return {"error": f"Gezi bulunamadı: {trip_id}"}
    with get_conn(db_path) as conn:
        spent_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS spent FROM expenses WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()
        by_cat_rows = conn.execute(
            """SELECT COALESCE(category, 'diğer') AS category, SUM(amount) AS total
               FROM expenses WHERE trip_id = ? GROUP BY category ORDER BY total DESC""",
            (trip_id,),
        ).fetchall()
    spent = spent_row["spent"]
    total = trip["budget_total"]
    return {
        "trip_id": trip_id,
        "destination": trip["destination"],
        "currency": trip["currency"],
        "budget_total": total,
        "spent": spent,
        "remaining": total - spent,
        "by_category": _rows_to_list(by_cat_rows),
    }


# --------------------------------------------------------------------------- #
# Bookings (rezervasyon) — onay akışı için
# --------------------------------------------------------------------------- #
def create_booking(
    trip_id: int,
    type: str,
    name: str,
    date: str | None = None,
    cost: float = 0,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Rezervasyonu 'pending' (onay bekliyor) durumunda oluşturur.

    Privacy Guard / onay akışı confirm_booking ile onaylar — zero-trust.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bookings (trip_id, type, name, date, cost, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (trip_id, type, name, date, cost),
        )
        bid = cur.lastrowid
    return get_booking(bid, db_path)  # type: ignore[return-value]


def confirm_booking(booking_id: int, db_path: str | None = None) -> Optional[dict[str, Any]]:
    """Bekleyen bir rezervasyonu onaylar (kullanıcı onayından SONRA çağrılmalı)."""
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bookings SET status = 'confirmed', confirmed_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), booking_id),
        )
    return get_booking(booking_id, db_path)


def get_booking(booking_id: int, db_path: str | None = None) -> Optional[dict[str, Any]]:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    return _row_to_dict(row)


def list_bookings(trip_id: int, db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE trip_id = ? ORDER BY date", (trip_id,)
        ).fetchall()
    return _rows_to_list(rows)


# --------------------------------------------------------------------------- #
# Seed (örnek İstanbul gezisi)
# --------------------------------------------------------------------------- #
def seed_demo_data(db_path: str | None = None) -> int:
    """Örnek 3 günlük İstanbul gezisini ekler (zaten varsa tekrar eklemez).

    Demo senaryosunun çalışması için temel veri. trip_id döndürür.
    """
    existing = list_trips(db_path)
    for t in existing:
        if t["destination"] == "İstanbul" and t["notes"] == "demo":
            return t["id"]  # zaten eklenmiş

    trip = create_trip(
        destination="İstanbul",
        start_date="2026-07-10",
        end_date="2026-07-12",
        budget_total=8000,
        currency="TRY",
        notes="demo",
        db_path=db_path,
    )
    tid = trip["id"]

    # 1. gün — Tarihi Yarımada
    add_itinerary_item(tid, 1, "Ayasofya gezisi", time="09:30", place="Sultanahmet",
                       category="tarihi", est_cost=600, db_path=db_path)
    add_itinerary_item(tid, 1, "Sultanahmet Camii", time="11:30", place="Sultanahmet",
                       category="tarihi", est_cost=0, db_path=db_path)
    add_itinerary_item(tid, 1, "Öğle yemeği", time="13:00", place="Sultanahmet",
                       category="yemek", est_cost=400, db_path=db_path)
    add_itinerary_item(tid, 1, "Topkapı Sarayı", time="14:30", place="Sultanahmet",
                       category="müze", est_cost=750, db_path=db_path)

    # 2. gün — Boğaz & Karaköy
    add_itinerary_item(tid, 2, "Boğaz turu", time="10:00", place="Eminönü",
                       category="aktivite", est_cost=500, db_path=db_path)
    add_itinerary_item(tid, 2, "Karaköy'de öğle yemeği", time="13:00", place="Karaköy",
                       category="yemek", est_cost=450, db_path=db_path)
    add_itinerary_item(tid, 2, "İstanbul Modern", time="15:00", place="Karaköy",
                       category="müze", est_cost=400, db_path=db_path)

    # 3. gün — Kapalıçarşı & Balat
    add_itinerary_item(tid, 3, "Kapalıçarşı", time="10:00", place="Beyazıt",
                       category="alışveriş", est_cost=300, db_path=db_path)
    add_itinerary_item(tid, 3, "Balat gezisi", time="14:00", place="Balat",
                       category="gezi", est_cost=150, db_path=db_path)

    # Örnek rezervasyon (onay bekliyor) + birkaç harcama
    create_booking(tid, type="konaklama", name="Sultanahmet Butik Otel",
                   date="2026-07-10", cost=3000, db_path=db_path)
    add_expense(tid, "Ayasofya bileti", 600, category="tarihi", day_number=1, db_path=db_path)
    add_expense(tid, "Öğle yemeği", 400, category="yemek", day_number=1, db_path=db_path)

    return tid


if __name__ == "__main__":
    # Windows konsolunda Türkçe/ok karakterleri için UTF-8 çıktıyı zorla.
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Doğrudan çalıştırınca: şemayı kur, seed et, özet yazdır.
    init_db(seed=True)
    trips = list_trips()
    print(f"Toplam gezi: {len(trips)}")
    for t in trips:
        print(f"  #{t['id']} {t['destination']} ({t['start_date']} → {t['end_date']}), "
              f"bütçe {t['budget_total']} {t['currency']}")
        summary = budget_summary(t["id"])
        print(f"     harcanan: {summary['spent']}, kalan: {summary['remaining']}")
        print(f"     plan kalemi: {len(get_itinerary(t['id']))}, "
              f"rezervasyon: {len(list_bookings(t['id']))}")
