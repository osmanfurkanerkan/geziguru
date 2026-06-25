"""
GeziGuru ortak yapılandırma.

.env dosyasını yükler, model adını verir ve ADK'nın beklediği anahtar adını ayarlar.

Neden bu dosya var? Ortam okumayı tek bir yerde toplamak için. Birçok dosya "model adı
ne?" veya "API anahtarı nerede?" diye sormak yerine buradan alır (tek doğru kaynak).
"""

from __future__ import annotations

import logging
import os
import sys
import warnings

# .env'i yükle (varsa).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def quiet_noise() -> None:
    """Demo çıktısını temiz tutmak için ADK/kütüphane gürültüsünü kıs.

    - Deneysel özellik UserWarning'lerini gizle.
    - ADK / google-genai / MCP INFO loglarını WARNING seviyesine çek
      (örn. "Processing request of type ListToolsRequest" satırları).
    """
    warnings.filterwarnings("ignore", category=UserWarning)
    for noisy in ("google_adk", "google.adk", "google_genai", "google.genai",
                  "mcp", "mcp.server", "httpx", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


quiet_noise()

# ADK / google-genai, AI Studio modunda GOOGLE_API_KEY arar. Biz .env'de
# GEMINI_API_KEY tutuyoruz; onu GOOGLE_API_KEY'e taşıyıp GEMINI_API_KEY'i kaldırıyoruz.
# (İkisi birden set olursa ADK "ikisi de set" uyarısı basıyor — tek anahtar bırakalım.)
_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if _api_key:
    os.environ["GOOGLE_API_KEY"] = _api_key
    os.environ.pop("GEMINI_API_KEY", None)

# Vertex değil, AI Studio anahtarı kullan.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

# Kullanılacak Gemini modeli (günlük istek limiti yüksek lite model).
MODEL = os.environ.get("GEZIGURU_MODEL", "gemini-3.1-flash-lite")

# Proje kök dizini (MCP server'ı alt süreç olarak başlatırken lazım).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

API_KEY = _api_key


def ensure_api_key() -> None:
    """Anahtar yoksa kullanıcıyı net biçimde yönlendirip programı durdurur."""
    if not API_KEY or API_KEY == "buraya_anahtarinizi_yapistirin":
        print("❌ GEMINI_API_KEY bulunamadı.")
        print("   .env.example'ı .env olarak kopyalayıp anahtarınızı girin,")
        print("   sonra tekrar deneyin. (https://aistudio.google.com/apikey)")
        sys.exit(1)
