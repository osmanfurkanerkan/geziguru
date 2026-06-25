"""
GeziGuru — terminal sohbet arayüzü.

Kök ajanı (orchestrator) bir ADK Runner ile çalıştırır ve kullanıcıyla terminal
üzerinden Türkçe sohbet ettirir. Hangi uzman ajanın devreye girdiğini de gösterir
(multi-agent akışını görebilmek için).

Çalıştırma:
    python -m app.main

Çıkmak için: 'çık', 'quit' ya da Ctrl+C.
"""

from __future__ import annotations

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# config en başta import edilmeli: .env'i yükler ve API anahtarını ayarlar.
from app.config import ensure_api_key, MODEL  # noqa: E402

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from app.agents.orchestrator import root_agent  # noqa: E402
from app.data import db  # noqa: E402

APP_NAME = "geziguru"
USER_ID = "demo-user"


BANNER = f"""
╔══════════════════════════════════════════════════════════╗
║   ✈️  GeziGuru — Güvenli Kişisel Seyahat Asistanı         ║
╠══════════════════════════════════════════════════════════╣
║  Model: {MODEL:<48} ║
║  Çıkmak için: 'çık' yazın ya da Ctrl+C                     ║
╚══════════════════════════════════════════════════════════╝

Örnek sorular:
  • "Hangi gezilerim var?"
  • "İstanbul gezimin 1. gününü göster"
  • "Bütçemde ne kadar param kaldı?"
  • "Topkapı için 14:30'a bir gezi ekle"
"""


async def chat() -> None:
    ensure_api_key()

    # Şema + demo verisinin hazır olduğundan emin ol.
    db.init_db(seed=True)

    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    print(BANNER)

    loop = asyncio.get_event_loop()
    while True:
        try:
            # input() bloklayıcı; event loop'u kilitlememek için executor'da çalıştır.
            user_text = (await loop.run_in_executor(None, lambda: input("\n🧑 Sen: "))).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Görüşürüz, iyi yolculuklar!")
            return

        if not user_text:
            continue
        if user_text.lower() in {"çık", "cik", "quit", "exit", "q"}:
            print("👋 Görüşürüz, iyi yolculuklar!")
            return

        message = types.Content(role="user", parts=[types.Part(text=user_text)])

        last_author = None
        printed_final = False
        try:
            async for event in runner.run_async(
                user_id=USER_ID, session_id=session.id, new_message=message
            ):
                # Hangi uzman ajanın konuştuğunu göster (multi-agent akışı görünür olsun).
                author = getattr(event, "author", None)
                if author and author != last_author and author != root_agent.name:
                    print(f"   ↳ [{author} devrede]")
                    last_author = author

                if event.is_final_response() and event.content and event.content.parts:
                    text = "".join(p.text or "" for p in event.content.parts).strip()
                    if text:
                        print(f"\n🤖 GeziGuru: {text}")
                        printed_final = True
        except Exception as exc:  # noqa: BLE001 — demo'da çökmek yerine kibar mesaj
            if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
                print("\n⏳ GeziGuru: Şu an çok hızlı istek attık, dakikalık kota doldu. "
                      "Lütfen ~1 dakika bekleyip tekrar deneyin.")
            else:
                print(f"\n⚠️ GeziGuru: Bir sorun oluştu ({type(exc).__name__}). "
                      "Tekrar dener misiniz?")
            continue

        if not printed_final:
            print("\n🤖 GeziGuru: (cevap üretilemedi — tekrar dener misiniz?)")


def main() -> None:
    try:
        asyncio.run(chat())
    except KeyboardInterrupt:
        print("\n👋 Görüşürüz, iyi yolculuklar!")


if __name__ == "__main__":
    main()
