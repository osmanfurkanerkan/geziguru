"""
Ajanların uçtan uca (gerçek Gemini ile) denemesi.

main.py'deki sohbet döngüsünün interaktif olmayan versiyonu: birkaç senaryo mesajı
gönderir, ajanların MCP araçlarını kullanıp doğru uzmana yönlendirdiğini gözle doğrular.

Çalıştırma:
    python -m tests.test_agents

NOT: Gerçek Gemini çağrısı yapar (API kotası kullanır).
"""

from __future__ import annotations

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import ensure_api_key  # .env yükler
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.orchestrator import root_agent
from app.data import db

APP_NAME = "geziguru-test"
USER_ID = "tester"

# Sırayla gönderilecek senaryo mesajları (gezi planı + bütçe = iki farklı uzman).
SCENARIO = [
    "Merhaba, neler yapabilirsin?",
    "Hangi gezilerim var?",
    "İstanbul gezimin 1. gününü göster",
    "Bu gezi için bütçemde ne kadar param kaldı?",
]


async def run() -> int:
    ensure_api_key()
    db.reset_db(seed=True)  # temiz, bilinen veriyle başla

    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    authors_seen: set[str] = set()

    for msg in SCENARIO:
        print(f"\n🧑 Sen: {msg}")
        message = types.Content(role="user", parts=[types.Part(text=msg)])
        final_text = ""
        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id, new_message=message
        ):
            author = getattr(event, "author", None)
            if author:
                authors_seen.add(author)
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(p.text or "" for p in event.content.parts).strip()
        print(f"🤖 GeziGuru: {final_text}")

    print("\n" + "=" * 60)
    print("Devreye giren ajanlar:", ", ".join(sorted(authors_seen)))
    ok = "itinerary_agent" in authors_seen and "booking_agent" in authors_seen
    if ok:
        print("✅ Her iki uzman ajan da yönlendirme ile devreye girdi (multi-agent çalışıyor).")
        return 0
    print("⚠️  Beklenen uzman ajanlardan biri devreye girmedi — yönlendirmeyi/talimatları gözden geçir.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
