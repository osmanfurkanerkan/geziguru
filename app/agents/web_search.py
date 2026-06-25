"""
Ücretsiz canlı web arama aracı (DuckDuckGo).

Keşif ajanının kullandığı fonksiyon-araç. Gemini'nin yerleşik google_search'ü ücretsiz
katmanda kapalı olduğu için, anahtar/kota gerektirmeyen DuckDuckGo araması kullanıyoruz.
Bu sayede canlı/gerçek veri elde ederiz ve ekstra ücret ödemeyiz.

ADK, tip ipuçlu ve docstring'li sıradan bir Python fonksiyonunu doğrudan araç olarak
kullanabilir — bu yüzden burada özel bir sınıf gerekmez.
"""

from __future__ import annotations

import asyncio
from typing import Any


def _search_sync(query: str, max_results: int) -> dict[str, Any]:
    """Bloklayan DuckDuckGo araması (ayrı thread'de çalıştırılır)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return {"error": "ddgs paketi kurulu değil. 'pip install ddgs' çalıştırın."}

    try:
        raw = DDGS().text(query, region="tr-tr", max_results=max_results)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw
        ]
        if not results:
            return {"results": [], "note": "Sonuç bulunamadı; sorguyu sadeleştirmeyi deneyin."}
        return {"results": results}
    except Exception as exc:  # noqa: BLE001 — araç çökmesin, ajana hata bildir
        return {"error": f"Web araması başarısız: {exc}"}


async def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Canlı web araması yapar ve sonuçları döndürür (DuckDuckGo, Türkçe bölge).

    Mekan, restoran, görülecek yer, etkinlik gibi GÜNCEL bilgileri internetten arar.

    ASYNC: DuckDuckGo çağrısı bloklayıcı olduğundan, çalışan event loop'u (web sunucusu)
    kilitlememek için ayrı bir thread'de çalıştırılır.

    Args:
        query: Arama sorgusu (örn. "Kadıköy popüler restoranlar 2026").
        max_results: Döndürülecek azami sonuç sayısı (varsayılan 5).

    Returns:
        {"results": [{"title", "url", "snippet"}, ...]} biçiminde sözlük.
        Hata olursa {"error": "..."} döner.
    """
    return await asyncio.to_thread(_search_sync, query, max_results)
