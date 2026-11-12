# Standard Discord Bot

Ein einfacher Discord-Bot-Grundbaustein mit Python, `discord.py` und Slash-Commands.

## Voraussetzungen

- Python 3.10 oder neuer
- Ein Bot im [Discord Developer Portal](https://discord.com/developers/applications)

## Installation

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Kopiere `.env.example` nach `.env` und trage dort deinen Bot-Token ein:

```env
DISCORD_TOKEN=dein_bot_token_hier
SUPPORT_ROLE_ID=123456789012345678
TICKET_CATEGORY_ID=123456789012345678
```

`SUPPORT_ROLE_ID` und `TICKET_CATEGORY_ID` sind optional. Ohne Support-Rolle sehen nur der Ticket-Ersteller und der Bot den Ticket-Kanal. Die echte `.env` wird durch `.gitignore` ausgeschlossen. Teile deinen Token niemals und committe ihn nicht.

## Bot starten

```bash
python main.py
```

Der Bot synchronisiert beim Start die Slash-Commands. Verfügbare Befehle:

- `/ticket` erstellt ein privates Support-Ticket. Der Ersteller oder Support kann es über den Button schließen.
- `/buypanel` veröffentlicht das Kauf-Panel. Die Produktauswahl startet ein privates Ticket für das gewählte Produkt.
- `/buypanel-status` zeigt den Verfügbarkeitsstatus und erlaubt Server-Verwaltern, Produkte mit den Buttons ein- oder auszuschalten. Statusänderungen werden gespeichert und bestehende Kauf-Panels live aktualisiert.
- `/ping` antwortet mit `Pong!`.

Verfügbare Produkte: Project Neo, Project retrad, Project stellar, CSGO2 und Storm arc. Der Bot benötigt zum Erstellen und Verwalten der Tickets die Berechtigungen zum Verwalten von Kanälen sowie zum Senden und Anzeigen von Nachrichten. Beim Einladen müssen mindestens die Scopes `bot` und `applications.commands` ausgewählt sein.
