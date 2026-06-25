"""
Gemini bağlantı smoke test'i.

.env içindeki GEMINI_API_KEY ile küçük bir Gemini çağrısı yapar ve cevabı yazdırır.
Kurulumun doğru olduğunu doğrulamak için:

    python check_gemini.py

API anahtarı yoksa ne yapılması gerektiğini açıkça söyler (kod çökmek yerine
yönlendirir).
"""

from __future__ import annotations

import os
import sys

# Windows konsolunda Türkçe karakter için UTF-8 çıktı.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv yoksa ortam değişkenleri yine de okunur


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "buraya_anahtarinizi_yapistirin":
        print("❌ GEMINI_API_KEY bulunamadı.")
        print()
        print("Yapmanız gerekenler:")
        print("  1. https://aistudio.google.com/apikey adresinden ücretsiz anahtar alın")
        print("  2. .env.example dosyasını .env olarak kopyalayın")
        print("  3. .env içine GEMINI_API_KEY=... satırına anahtarınızı yapıştırın")
        print("  4. Bu testi tekrar çalıştırın: python check_gemini.py")
        return 1

    model = os.environ.get("GEZIGURU_MODEL", "gemini-2.0-flash")
    print(f"🔌 Gemini'ye bağlanılıyor (model: {model}) ...")

    try:
        from google import genai
    except ImportError:
        print("❌ google-genai kurulu değil. Çalıştırın: pip install -r requirements.txt")
        return 1

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents="Tek cümleyle kendini bir seyahat asistanı olarak Türkçe tanıt.",
        )
        print("✅ Bağlantı başarılı! Gemini'nin cevabı:")
        print()
        print("   " + (resp.text or "").strip())
        return 0
    except Exception as exc:  # noqa: BLE001 — kullanıcıya net hata göster
        print(f"❌ Gemini çağrısı başarısız: {exc}")
        print("   Anahtarınızı, internet bağlantınızı ve model adını kontrol edin.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
