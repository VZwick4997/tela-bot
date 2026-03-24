# TELA Mietobjekt-Bot

Dieser Bot prüft regelmäßig die TELA-Seite für Mietimmobilien und schickt dir neue Objekte per Telegram.

## 1) Voraussetzungen
- Python 3.11+
- Linux / macOS / Windows
- Telegram-Konto

## 2) Installation
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## 3) Konfiguration
Umgebungsvariablen setzen:

### macOS / Linux
```bash
export TELEGRAM_BOT_TOKEN="DEIN_TOKEN"
export TELEGRAM_CHAT_ID="DEINE_CHAT_ID"
```

### Windows PowerShell
```powershell
$env:TELEGRAM_BOT_TOKEN="DEIN_TOKEN"
$env:TELEGRAM_CHAT_ID="DEINE_CHAT_ID"
```

## 4) Testlauf
```bash
python tela_mietbot.py
```

Wichtig:
- Beim ersten Lauf wird nur der aktuelle Stand gespeichert.
- Ab dem zweiten Lauf meldet der Bot nur neue Objekte.

## 5) Alle 5 Minuten automatisch laufen lassen

### Linux Crontab
```bash
*/5 * * * * cd /PFAD/ZUM/ORDNER && /usr/bin/python3 tela_mietbot.py >> bot.log 2>&1
```

### Windows Aufgabenplanung
- Programm: `python`
- Argumente: `tela_mietbot.py`
- Starten in: Ordner des Scripts
- Trigger: alle 5 Minuten

## 6) GitHub Actions (ohne eigenen Server)
Du kannst den Bot auch kostenlos über GitHub Actions alle 5 Minuten laufen lassen.
Dafür:
- Repository anlegen
- diese Dateien hochladen
- Secrets `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` anlegen
- Workflow aus `.github/workflows/tela-monitor.yml` verwenden

## 7) Hinweise
Die TELA-Seite scheint die Angebote nicht direkt als statisches HTML auszugeben. Deshalb nutzt der Bot Playwright und liest die gerenderte Seite aus.
Falls TELA die Struktur ändert, müssen die Selektoren im Script angepasst werden.
