# GeziGuru — Güvenli Seyahat Planlama Concierge'i
### Google AI Agents Capstone — Yol Haritası

> **Track:** Concierge Agents
> **Teknoloji:** Google ADK (Python) + Gemini · Dil: Türkçe
> **Son teslim:** 6 Temmuz 2026, 23:59 PT (~12 gün)

---

## 1. Proje Özeti

Kullanıcının seyahatini gün gün planlayan, rezervasyon ve bütçesini takip eden, ve
**kişisel/hassas veriyi koruyan** çok-ajanlı (multi-agent) bir seyahat asistanı.
Asistan Türkçe konuşur, Gemini ile çalışır; pasaport/kart gibi hassas bilgileri bir
"Privacy Guard" ajanı ile zero-trust mantığında korur ve rezervasyon gibi yüksek etkili
işlemlerden önce kullanıcıdan onay ister.

### Tek cümlelik değer önerisi
> "Gezimi gün gün planlayan, bütçemi tutan, ama pasaport/kart bilgimi koruyup
> rezervasyon yapmadan önce bana soran akıllı seyahat asistanı."

### Örnek istek
> "3 günlüğüne İstanbul'a gidiyorum, bütçem 8000 TL. Tarihi yerler ağırlıklı bir plan yap,
> nerede kalacağımı öner ve harcamalarımı takip et."

---

## 2. Capstone Kriter Eşlemesi (en az 3 konsept şart — biz 4 veriyoruz)

| # | Konsept | Bu projede karşılığı | Durum |
|---|---------|----------------------|-------|
| 1 | **Multi-agent (ADK)** | Orchestrator + Itinerary + Booking/Bütçe + Keşif + Özet + Privacy Guard | ✅ Çekirdek |
| 2 | **MCP Server** | Gezi / itinerary / bütçe verisi için SQLite tabanlı kendi MCP server'ımız | ✅ Çekirdek |
| 3 | **Agent Skills** | "Gezi planı yap", "rota optimize et", "bütçe çıkar", "gezimi özetle" | ✅ Çekirdek |
| 4 | **Security Features** | Pasaport/kart PII maskeleme, prompt-injection filtresi, rezervasyon onayı (HITL) | ✅ Çekirdek |
| 5 | **Cloud Deployment** | (Opsiyonel) Cloud Run'a deploy + basit frontend | ⏳ Vakit kalırsa |

---

## 3. Mimari

```
                    ┌──────────────────────────────┐
   Kullanıcı  ───▶  │     Orchestrator Agent        │  Türkçe diyalog, niyet anlama,
                    │     (root_agent)              │  doğru alt-ajana yönlendirme
                    └───────────────┬───────────────┘
        ┌──────────────┬────────────┼────────────┬──────────────────┐
        ▼              ▼            ▼            ▼                  ▼
  ┌───────────┐  ┌───────────┐ ┌──────────┐ ┌──────────┐   ┌────────────────┐
  │ Itinerary │  │ Booking & │ │  Keşif   │ │  Özet    │   │ Privacy Guard  │
  │  Agent    │  │ Bütçe Ag. │ │  Agent   │ │  Agent   │   │     Agent      │
  └─────┬─────┘  └─────┬─────┘ └────┬─────┘ └────┬─────┘   └───────┬────────┘
        │              │            │            │                 │
        └──────────────┴────────────┴────────────┘                 │
                       │                                           │
                       ▼                                           ▼
              ┌─────────────────┐                       ┌────────────────────┐
              │   MCP Server     │                       │  Güvenlik Katmanı  │
              │ gezi+itinerary   │                       │ PII mask / inj.    │
              │ +bütçe (SQLite)  │                       │ filtresi / onay    │
              └─────────────────┘                       └────────────────────┘
```

### Ajanların görevleri
- **Orchestrator (root):** Kullanıcıyla Türkçe konuşur, niyeti anlar, alt-ajanlara dağıtır, cevapları birleştirir.
- **Itinerary Agent:** Gün gün gezi planı oluşturur, görülecek yerleri zamana/rotaya göre dağıtır, çakışmaları/yorgunluğu dengeler.
- **Booking & Bütçe Agent:** Konaklama/ulaşım/aktivite rezervasyon kayıtlarını tutar, bütçeyi hesaplar, harcamaları takip eder. Rezervasyon = onay gerektirir.
- **Keşif Agent:** Yer önerileri, etkinlik, hava durumu, mesafe/ulaşım bilgisi (dış kaynak) — *Privacy Guard onayından geçer*.
- **Özet Agent:** "Gezimi özetle", "2. günü göster", "kalan bütçem ne" gibi derleme yetenekleri.
- **Privacy Guard Agent:** Tüm dışa giden veriyi denetler — pasaport/kart/kimlik maskeler, enjeksiyon dener mi bakar, rezervasyon gibi yüksek etkili işlemde kullanıcıdan açık onay ister.

---

## 4. Klasör Yapısı (kurulduğunda)

```
kaggle_proje/
├── PLAN.md                      # bu dosya
├── README.md                    # jüriye anlatan ana doküman
├── requirements.txt
├── .env.example                 # GEMINI_API_KEY vb.
├── app/
│   ├── __init__.py
│   ├── main.py                  # giriş noktası / CLI sohbet döngüsü
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── itinerary.py
│   │   ├── booking.py
│   │   ├── discovery.py         # Keşif
│   │   ├── summary.py
│   │   └── privacy_guard.py
│   ├── skills/                  # agent skill tanımları
│   │   ├── plan_trip.py
│   │   ├── optimize_route.py
│   │   └── budget_report.py
│   ├── security/
│   │   ├── pii.py               # pasaport/kart/kimlik tespit + maskeleme
│   │   ├── injection.py         # prompt-injection filtresi
│   │   └── approval.py          # human-in-the-loop onay (rezervasyon)
│   └── data/
│       └── db.py                # SQLite şema + erişim
├── mcp_server/
│   └── server.py                # gezi+itinerary+bütçe MCP server (stdio)
├── tests/
│   └── test_security.py
└── demo/
    └── senaryo.md               # demo akışı / sunum notları
```

---

## 5. 12 Günlük Zaman Planı

| Gün | Aşama | Çıktı |
|-----|-------|-------|
| 1–2 | **İskelet + ortam** | Klasör yapısı, requirements, SQLite şema (gezi/itinerary/bütçe), Gemini bağlantısı çalışıyor |
| 3–4 | **MCP Server** | Gezi+itinerary+bütçe MCP server'ı stdio üzerinden çalışıyor, CRUD test edildi |
| 5–6 | **Çekirdek ajanlar** | Orchestrator + Itinerary + Booking/Bütçe ajanları konuşuyor, MCP'yi kullanıyor |
| 7   | **Keşif + Özet** | Yer/hava/mesafe bilgisi ve gezi özetleme yetenekleri |
| 8–9 | **Privacy Guard + Security** | Pasaport/kart maskeleme, injection filtresi, rezervasyon onay akışı + testler |
| 10  | **Skills cilası + uçtan uca demo** | Tüm senaryo akıyor (İstanbul 3 gün örneği), demo/senaryo.md yazıldı |
| 11  | **README + dokümantasyon** | Jüri için kriter eşlemesi, diyagram, kurulum, ekran kayıtları |
| 12  | **(Ops.) Cloud deploy / tampon** | Cloud Run veya hata düzeltme + son rötuş |

> Cloud deploy riskli/zaman alıcı olduğu için **tampon gün** olarak en sona koyduk.
> 10. günde elde **tamamen çalışan yerel bir proje** olması hedef.

---

## 6. Teknik Kararlar

- **LLM:** Gemini (ADK ile native). API key `.env`'de.
- **Veri:** SQLite (kurulum gerektirmez, repo'da taşınabilir, demo'da seed data ile gelir).
- **Dış kaynaklar:** Başlangıçta yer/etkinlik verisi **mock/sample** (gömülü örnek veri).
  Vakit kalırsa ücretsiz bir hava durumu API'si gerçek veriyle eklenir. (Uçuş/otel gerçek
  rezervasyon API'leri kapsam dışı — karmaşık ve key gerektiriyor; rezervasyon "kayıt + onay"
  olarak simüle edilir.)
- **MCP transport:** stdio (yerelde en basiti).
- **Güvenlik yaklaşımı:** Zero-trust — hiçbir dışa giden çağrı ve hiçbir rezervasyon Privacy Guard'dan geçmeden gerçekleşmez.
- **Dil:** Asistan Türkçe; kod/yorumlar Türkçe; README Türkçe (gerekirse İngilizce özet bölümü).

---

## 7. Güvenlik Tasarımı (puan kazandıran kısım — detay)

1. **PII Maskeleme:** Pasaport no, TC kimlik, kredi kartı, telefon, e-posta regex+heuristik ile
   tespit; loglara ve dış servise giderken maskelenir (`Pasaport: U12****56`, `Kart: **** **** **** 1234`).
2. **Prompt-Injection Filtresi:** Kullanıcı/araç girdisinde "önceki talimatları unut" türü kalıplar taranır,
   şüpheli girdi Orchestrator'a "güvenli moda al" sinyali verir.
3. **Human-in-the-Loop Onay:** Rezervasyon oluşturma, ödeme bilgisi gönderme gibi "yüksek etkili"
   işlemlerde kullanıcıdan açık onay istenir (zero-trust). Onay yoksa işlem kayıt altına alınmaz.
4. **Test:** `tests/test_security.py` — maskeleme ve injection senaryoları için birim testler.

---

## 8. Teslim Checklist'i (6 Temmuz öncesi)

- [ ] Çalışan yerel demo (İstanbul 3 günlük uçtan uca senaryo)
- [ ] README: capstone kriter eşleme tablosu + mimari diyagram
- [ ] Demo video / ekran kaydı (2–3 dk)
- [ ] Kaggle Writeup / repo linki
- [ ] Güvenlik testleri geçiyor
- [ ] (Ops.) Cloud Run linki + frontend

---

## 9. Sonraki Adım

Bu plan onaylandığında **Gün 1–2 iskeletini** kuruyoruz:
klasör yapısı, `requirements.txt`, SQLite şeması (gezi/itinerary/bütçe), `.env.example`
ve Gemini bağlantı testi.
