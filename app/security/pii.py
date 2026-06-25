"""
PII (Kişisel Tanımlanabilir Bilgi) tespiti ve maskelemesi.

Seyahat asistanı pasaport, kimlik, kart, telefon gibi hassas verilerle karşılaşır.
Bu modül bu verileri tespit eder ve loglara/dış servise giderken MASKELER, böylece
hassas bilgi düz metin olarak sızmaz.

Tasarım notu: Kasıtlı olarak basit ve okunaklı tutuldu (regex + birkaç kural). Üretim
sisteminde daha gelişmiş bir kütüphane kullanılırdı; ama buradaki amaç güvenlik
yaklaşımını net ve test edilebilir biçimde göstermek.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class PiiMatch(NamedTuple):
    type: str       # "email", "kredi_karti", "tc_kimlik", "pasaport", "telefon"
    value: str      # bulunan ham değer


# --------------------------------------------------------------------------- #
# Desenler (sıralama önemli: önce daha spesifik olanlar)
# --------------------------------------------------------------------------- #
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Kredi kartı: 13-19 hane, aralarında boşluk/tire olabilir.
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")

# TC kimlik: tam 11 hane (ilk hane 0 olamaz).
_TC = re.compile(r"\b[1-9]\d{10}\b")

# Türkiye pasaportu: 1-2 harf + 7-8 hane (örn. U12345678).
_PASSPORT = re.compile(r"\b[A-Za-z]{1,2}\d{7,8}\b")

# Telefon: +90 / 0 ile başlayan veya 10-11 haneli, ayraçlı numaralar.
_PHONE = re.compile(
    r"\b(?:\+90[ -]?)?0?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}\b"
)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _mask_email(v: str) -> str:
    name, _, domain = v.partition("@")
    shown = name[:2]
    return f"{shown}{'*' * max(1, len(name) - 2)}@{domain}"


def _mask_keep_last(v: str, keep: int = 4) -> str:
    """Sadece son `keep` haneyi gösterir, gerisini maskeler (kart/telefon için)."""
    d = _digits(v)
    if len(d) <= keep:
        return "*" * len(d)
    return "*" * (len(d) - keep) + d[-keep:]


def _mask_tc(v: str) -> str:
    d = _digits(v)
    return d[:2] + "*" * (len(d) - 4) + d[-2:]


def _mask_passport(v: str) -> str:
    return v[:2] + "*" * (len(v) - 4) + v[-2:]


def find_pii(text: str) -> list[PiiMatch]:
    """Metindeki PII'leri (tür, değer) olarak döndürür."""
    if not text:
        return []
    matches: list[PiiMatch] = []
    seen: set[str] = set()

    def add(kind: str, value: str) -> None:
        key = f"{kind}:{value}"
        if value and key not in seen:
            seen.add(key)
            matches.append(PiiMatch(kind, value))

    for m in _EMAIL.finditer(text):
        add("email", m.group())
    # Kart: en az 13 hane (TC ile karışmasın diye hane sayısına bak).
    for m in _CARD.finditer(text):
        if len(_digits(m.group())) >= 13:
            add("kredi_karti", m.group())
    for m in _TC.finditer(text):
        add("tc_kimlik", m.group())
    for m in _PASSPORT.finditer(text):
        add("pasaport", m.group())
    for m in _PHONE.finditer(text):
        if 10 <= len(_digits(m.group())) <= 11:
            add("telefon", m.group())
    return matches


def mask_pii(text: str) -> str:
    """Metindeki tüm PII'leri maskeleyerek döndürür (orijinali değiştirmez)."""
    if not text:
        return text

    # E-posta önce (içinde rakam olabilir, kartla karışmasın).
    text = _EMAIL.sub(lambda m: _mask_email(m.group()), text)

    def card_repl(m: re.Match) -> str:
        return _mask_keep_last(m.group(), 4) if len(_digits(m.group())) >= 13 else m.group()

    text = _CARD.sub(card_repl, text)
    text = _TC.sub(lambda m: _mask_tc(m.group()), text)
    text = _PASSPORT.sub(lambda m: _mask_passport(m.group()), text)

    def phone_repl(m: re.Match) -> str:
        return _mask_keep_last(m.group(), 2) if 10 <= len(_digits(m.group())) <= 11 else m.group()

    text = _PHONE.sub(phone_repl, text)
    return text


def has_pii(text: str) -> bool:
    return len(find_pii(text)) > 0
