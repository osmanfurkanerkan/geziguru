"""
GeziGuru — Web sitesi arka ucu (FastAPI).

Modern bir ön yüz (web/index.html) ile çok-ajanlı asistanı birleştirir.
Ön yüz JSON ile /api/chat'e mesaj gönderir; burada ADK runner çalışır ve cevap döner.

Çalıştırma:
    python -m app.api
    # veya: uvicorn app.api:app --reload
Sonra tarayıcıda:  http://localhost:8000
"""

from __future__ import annotations

import os
import sys
import uuid

# Windows konsolunda emoji/Türkçe çıktı için UTF-8 zorla.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import API_KEY
from app.agents.orchestrator import root_agent
from app.data import db

from google.adk.runners import InMemoryRunner
from google.genai import types

APP_NAME = "geziguru-site"
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

# İç ajan adlarını kullanıcı dostu Türkçe etiketlere çevir (ön yüzde rozet olarak gösterilir).
FRIENDLY_AGENT = {
    "itinerary_agent": "🗺️ Plan Uzmanı",
    "booking_agent": "💳 Rezervasyon & Bütçe",
    "discovery_agent": "🔎 Keşif",
}

app = FastAPI(title="GeziGuru")

_runner: InMemoryRunner | None = None
_sessions: set[str] = set()


def _get_runner() -> InMemoryRunner:
    global _runner
    if _runner is None:
        # Web sitesi TEMİZ başlar: şemayı kur ama demo örnek gezisini YÜKLEME.
        # (Aksi halde ajan, kullanıcının vermediği demo bütçesini "kullanıcının" sanır.)
        db.init_db(seed=False)
        for t in db.list_trips():
            if t.get("notes") == "demo":
                db.delete_trip(t["id"])
        _runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    return _runner


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "api_key": bool(API_KEY)}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> JSONResponse:
    if not API_KEY:
        return JSONResponse(
            {"answer": "Sunucuda GEMINI_API_KEY tanımlı değil. .env dosyasını kontrol edin.",
             "agent": None, "session_id": req.session_id or ""},
            status_code=200,
        )

    runner = _get_runner()
    sid = req.session_id or uuid.uuid4().hex

    # Bu tarayıcı oturumu için ADK oturumunu bir kez oluştur.
    if sid not in _sessions:
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id=sid, session_id=sid
        )
        _sessions.add(sid)

    message = types.Content(role="user", parts=[types.Part(text=req.message)])
    final, agents = "", []
    try:
        async for ev in runner.run_async(user_id=sid, session_id=sid, new_message=message):
            author = getattr(ev, "author", None)
            if author and author != root_agent.name and author not in agents:
                agents.append(author)
            if ev.is_final_response() and ev.content and ev.content.parts:
                final = "".join(p.text or "" for p in ev.content.parts).strip()
    except Exception as exc:  # noqa: BLE001 — site çökmesin, kibar mesaj dön
        if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
            final = "⏳ Şu an çok yoğunum (dakikalık kota doldu). Lütfen ~1 dakika sonra tekrar deneyin."
        else:
            final = f"⚠️ Bir sorun oluştu ({type(exc).__name__}). Tekrar dener misiniz?"

    # Cevap boş kaldıysa (ör. anlık dakika kotası akışı sessizce bitirdi) boş baloncuk
    # yerine kibar bir mesaj dön.
    if not final.strip():
        final = ("⏳ Şu an cevabı üretemedim — büyük olasılıkla anlık istek yoğunluğu "
                 "(dakikalık kota). Lütfen ~1 dakika sonra tekrar dener misiniz?")

    # En son devreye giren uzmanı kullanıcı dostu etikete çevir.
    friendly = None
    for a in reversed(agents):
        if a in FRIENDLY_AGENT:
            friendly = FRIENDLY_AGENT[a]
            break

    return JSONResponse({"answer": final, "agent": friendly, "session_id": sid})


# Statik dosyalar (varsa) — şimdilik tek index.html yeterli.
if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def main() -> None:
    import uvicorn
    print("🌐 GeziGuru sitesi: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
