"""
Privacy Guard — güvenlik callback katmanı.

Bu, projenin "güvenlik bekçisi"dir. ADK callback'leri sayesinde ajan akışının
KRİTİK noktalarına müdahale eder (zero-trust, defense-in-depth):

1) before_model_callback (modele gitmeden ÖNCE):
   - Prompt-injection tespit edilirse model çağrısını ENGELLER, güvenli cevap döner.
   - Kullanıcı mesajındaki PII'yi tespit edip loglarda MASKELER (düz metin sızmaz).
   - Kullanıcının onay ifadelerini ("evet/onaylıyorum") yakalayıp oturum durumuna yazar.

2) before_tool_callback (bir araç çalışmadan ÖNCE):
   - confirm_booking gibi YÜKSEK ETKİLİ (para harcayan) işlemleri, kullanıcı açıkça
     onaylamadıysa ENGELLER. Yani onay sadece prompt'a güvenle değil, KOD seviyesinde
     zorlanır (human-in-the-loop).

Bu callback'ler ajanlara orchestrator.py / booking.py içinde bağlanır.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.security.injection import detect_injection
from app.security.pii import find_pii, mask_pii

# Güvenlik olay defteri: hem terminale yazılır hem de buraya eklenir. Web arayüzü
# (app/web.py) bu listeyi okuyup "Güvenlik Olayları" panelinde gösterir.
SECURITY_EVENTS: list[str] = []


def log_security(msg: str) -> None:
    """Bir güvenlik olayını hem terminale yazar hem de UI defterine ekler."""
    print(msg)
    SECURITY_EVENTS.append(msg)


# Oturum durumunda onay bayrağının anahtarı.
APPROVAL_KEY = "booking_approval"

# Yüksek etkili (kod seviyesinde onay gerektiren) araçlar.
HIGH_IMPACT_TOOLS = {"confirm_booking"}

# Onay / iptal ifadeleri (kullanıcı mesajında aranır).
_APPROVE = re.compile(r"\b(evet|onaylıyorum|onayla|onayluyorum|kabul|tamam onayla|okey onayla)\b", re.I)
_CANCEL = re.compile(r"\b(hayır|iptal|vazgeç|istemiyorum|onaylamıyorum)\b", re.I)


def _user_text(callback_context: CallbackContext) -> str:
    """Bu turdaki kullanıcı mesajının düz metnini çıkarır."""
    uc = getattr(callback_context, "user_content", None)
    if not uc or not getattr(uc, "parts", None):
        return ""
    return " ".join(p.text for p in uc.parts if getattr(p, "text", None))


def _refusal(text: str) -> LlmResponse:
    """Model çağrısını kesip güvenli bir cevap döndüren LlmResponse üretir."""
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)])
    )


# --------------------------------------------------------------------------- #
# 1) Modele gitmeden önce: injection engelle + PII maskeli log + onay tespiti
# --------------------------------------------------------------------------- #
def guard_before_model(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    user_text = _user_text(callback_context)
    if not user_text:
        return None

    # (a) Prompt-injection: şüpheliyse modeli HİÇ çağırma, güvenli cevap dön.
    findings = detect_injection(user_text)
    if findings:
        kinds = ", ".join(sorted({f.pattern for f in findings}))
        log_security(f"🛡️ Şüpheli istek engellendi (injection: {kinds}).")
        return _refusal(
            "Güvenlik nedeniyle bu isteği yerine getiremem. Talimatlarımı değiştirme, "
            "sistem bilgilerini ifşa etme veya güvenlik adımlarını atlama girişimleri "
            "engellenir. Seyahat planlaman için sana memnuniyetle yardımcı olurum. 🙂"
        )

    # (b) PII: tespit edilirse loglarda MASKELE (düz metin sızdırma).
    pii = find_pii(user_text)
    if pii:
        kinds = ", ".join(sorted({m.type for m in pii}))
        log_security(f"🔒 Hassas veri ({kinds}) tespit edildi ve maskelendi: {mask_pii(user_text)}")

    # (c) Onay tespiti: kullanıcı açıkça onayladıysa/iptal ettiyse duruma yaz.
    if _APPROVE.search(user_text):
        callback_context.state[APPROVAL_KEY] = True
    elif _CANCEL.search(user_text):
        callback_context.state[APPROVAL_KEY] = False

    return None  # None = devam et, modeli normal çağır


# --------------------------------------------------------------------------- #
# 2) Araç çalışmadan önce: yüksek etkili işlemlerde onay zorla
# --------------------------------------------------------------------------- #
def guard_before_tool(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    if tool.name in HIGH_IMPACT_TOOLS:
        approved = bool(tool_context.state.get(APPROVAL_KEY, False))
        if not approved:
            log_security(f"🛡️ '{tool.name}' onaysız çağrıldı — ENGELLENDİ.")
            # Dict döndürmek aracı çalıştırmadan bu sonucu kullandırır.
            return {
                "blocked": True,
                "reason": (
                    "Bu işlem para harcayan/geri alınması zor bir işlemdir ve kullanıcının "
                    "AÇIK onayı olmadan gerçekleştirilemez. Lütfen kullanıcıya rezervasyonun "
                    "adını, tarihini ve tutarını gösterip 'onaylıyor musunuz?' diye sor. "
                    "Kullanıcı 'evet' derse işlem tekrar denenebilir."
                ),
            }
        # Onay tek kullanımlık: kullanıldıktan sonra sıfırla (tekrar onaysız geçmesin).
        tool_context.state[APPROVAL_KEY] = False
        log_security(f"✅ '{tool.name}' kullanıcı onayıyla yürütülüyor.")
    return None  # None = aracı normal çalıştır
