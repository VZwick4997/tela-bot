#!/usr/bin/env python3
"""
TELA Mietobjekt-Bot

Prüft die Seite
https://www.tela-immobilien.de/angebote-mietimmobilien
auf neue Mietobjekte und sendet bei Änderungen eine Telegram-Nachricht.

Warum Browser-Automation?
Die TELA-Seite selbst enthält im statischen HTML keine Objektliste.
Die Seite verweist darauf, dass die Immobilien über immobilie1 angeboten werden.
Daher wird die Seite mit Playwright geladen und danach nach Objektlinks/Objektkarten
im gerenderten DOM gesucht.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


TELA_URL = "https://www.tela-immobilien.de/angebote-mietimmobilien"
STATE_FILE = Path("seen_tela_objects.json")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def make_key(item: Dict[str, str]) -> str:
    raw = f"{item.get('url','')}|{item.get('title','')}|{item.get('meta','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_rendered_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            # bisschen scrollen, falls lazy-loaded
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)
            html = page.content()
            return html
        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"Playwright timeout while loading {url}") from e
        finally:
            browser.close()


def extract_items_from_html(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, str]] = []

    # Strategie 1: Links zu immobilie1 / exposés
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        text = normalize_text(a.get_text(" ", strip=True))
        if not href:
            continue

        full_url = urljoin(TELA_URL, href)

        looks_like_offer = any([
            "immobilie1" in full_url.lower(),
            "/expose/" in full_url.lower(),
            "/immobilien/" in full_url.lower(),
            "/angebote/" in full_url.lower(),
        ])
        if not looks_like_offer:
            continue

        # Kontext aus Elternkarte zusammensuchen
        card = a
        for _ in range(4):
            card = card.parent
            if card is None:
                break
        context_text = normalize_text(card.get_text(" ", strip=True)) if card else text

        title = text or context_text[:120]
        meta = context_text[:300]

        item = {
            "title": title,
            "url": full_url,
            "meta": meta,
        }
        item["key"] = make_key(item)
        items.append(item)

    # deduplizieren
    dedup = {}
    for item in items:
        dedup[item["key"]] = item

    # Fallback Strategie 2: strukturierte Karten suchen, falls keine brauchbaren Links da sind
    if not dedup:
        possible_cards = soup.select("[class*='estate'], [class*='property'], [class*='offer'], article, .object, .card")
        for card in possible_cards:
            text = normalize_text(card.get_text(" ", strip=True))
            if len(text) < 30:
                continue
            a = card.select_one("a[href]")
            href = a.get("href", "").strip() if a else TELA_URL
            full_url = urljoin(TELA_URL, href)
            title = normalize_text(a.get_text(" ", strip=True)) if a else text[:120]
            item = {"title": title, "url": full_url, "meta": text[:300]}
            item["key"] = make_key(item)
            dedup[item["key"]] = item

    return list(dedup.values())


def load_seen_keys() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen_keys", []))
    except Exception:
        return set()


def save_seen_keys(keys: set[str]) -> None:
    payload = {
        "seen_keys": sorted(keys),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def format_message(new_items: List[Dict[str, str]]) -> str:
    lines = [f"🏠 Neue TELA-Mietobjekte gefunden: {len(new_items)}", ""]
    for item in new_items[:10]:
        lines.append(f"• {item['title']}")
        if item.get("meta"):
            lines.append(f"  {item['meta'][:200]}")
        lines.append(f"  {item['url']}")
        lines.append("")
    if len(new_items) > 10:
        lines.append(f"... und {len(new_items) - 10} weitere")
    return "\n".join(lines).strip()


def send_telegram(text: str) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=30)
    resp.raise_for_status()


def main() -> int:
    log("Lade TELA-Seite...")
    html = fetch_rendered_html(TELA_URL)
    items = extract_items_from_html(html)
    log(f"{len(items)} potenzielle Objekte erkannt.")

    if not items:
        log("Keine Objekte erkannt. Prüfe Selektoren oder Website-Struktur.")
        return 2

    seen = load_seen_keys()
    current = {item["key"] for item in items}
    new_items = [item for item in items if item["key"] not in seen]

    if not seen:
        # erster Lauf: nur initialisieren, nichts senden
        save_seen_keys(current)
        log("Erstlauf erkannt. Zustand gespeichert, keine Benachrichtigung versendet.")
        return 0

    if new_items:
        msg = format_message(new_items)
        send_telegram(msg)
        log(f"Benachrichtigung versendet für {len(new_items)} neue Objekte.")
    else:
        log("Keine neuen Objekte.")

    save_seen_keys(current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
