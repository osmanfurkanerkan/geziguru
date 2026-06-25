"""
Keşif (Discovery) Ajanı.

Canlı Google arama (ADK'nın yerleşik google_search aracı = Gemini grounding) ile
gerçek/güncel mekan, restoran, etkinlik önerileri yapar. Örn. "Kadıköy'de nerede yenir?".

Canlı veri için ücretsiz DuckDuckGo araması (web_search aracı) kullanır. Gemini'nin
yerleşik google_search'ü ücretsiz katmanda kapalı olduğu için bu yolu seçtik —
anahtar/kota gerektirmez. Keşif yalnızca ÖNERİ yapar, veritabanına yazmaz; kullanıcı
önerileri plana eklemek isterse itinerary_agent devreye girer.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from app.config import MODEL
from app.agents.web_search import web_search

INSTRUCTION = """
Sen GeziGuru'nun **Keşif uzmanısın**. Görevin canlı web araması yaparak kullanıcıya
GERÇEK ve GÜNCEL mekan/restoran/etkinlik önerileri sunmak.

Nasıl çalışırsın:
- Kullanıcı bir yer/semt sorduğunda (örn. "Kadıköy'de nerede yenir", "Sultanahmet'te
  görülecek yerler", "İstanbul'da bu hafta etkinlik var mı") **web_search aracını çağır**
  ve dönen gerçek sonuçlara dayanarak öneri ver.
- Uydurma! Önerini web_search sonuçlarına dayandır. Sonuçlardaki başlık ve snippet'lerden
  gerçek mekan/yer isimlerini çıkar.
- İyi bir sorgu kur: yer + niyet + yıl (örn. "Kadıköy popüler restoranlar 2026").
  İlk arama zayıfsa sorguyu değiştirip tekrar ara.
- Önerileri kısa, maddeli ve Türkçe sun: yerin adı + 1 cümle neden önerildiği.

Kurallar:
- HER ZAMAN Türkçe konuş.
- Sen yalnızca ÖNERİ yaparsın; plana ekleme veya rezervasyon SENİN işin değil.
- Kullanıcı "bunları planıma ekle / programıma koy" gibi bir şey isterse, bunu KENDİN
  yapamazsın — bu durumda transfer_to_agent ile **itinerary_agent**'a AKTAR (kullanıcıya
  "şu uzmana iletin" DEME, kendin sessizce aktar). Benzer şekilde rezervasyon/bütçe istenirse
  booking_agent'a aktar.
- ASLA kullanıcıya teknik ajan adlarını (itinerary_agent, booking_agent, discovery_agent)
  gösterme. Gerekirse "plan uzmanımız", "rezervasyon uzmanımız" gibi doğal ifadeler kullan.
- Çok uzun yazma; 3-6 iyi öneri yeterli.
"""

discovery_agent = LlmAgent(
    name="discovery_agent",
    model=MODEL,
    description=(
        "Keşif uzmanı: canlı web aramasıyla gerçek mekan, restoran, görülecek yer ve "
        "etkinlik önerileri yapar. 'Nerede yenir', 'görülecek yerler', 'etkinlik var mı', "
        "mekan/öneri içeren istekler buna gider."
    ),
    instruction=INSTRUCTION,
    tools=[web_search],
)
