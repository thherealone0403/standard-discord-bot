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

`SUPPORT_ROLE_ID` und `TICKET_CATEGORY_ID` sind optional. Ohne Support-Rolle sehen nur der Ticket-Ersteller und der Bot den Ticket-Kanal. Die echte `.env` wird durch `.gitignore` ausgeschlossen. `BOT_STATE_FILE` kann optional den Speicherort der Statusdatei festlegen.

## Bot starten

```bash
python main.py
```

Der Bot synchronisiert beim Start die Slash-Commands. Verfügbare Befehle:

- `/ticket` erstellt sofort ein privates Support-Ticket.
- `/ticket-panel` veröffentlicht ein Ticket-Panel mit Auswahl für allgemeinen Support, Kaufanfragen und gemeldete Probleme. Die Auswahl erstellt einen privaten Ticket-Kanal; ein Ticket kann über den Schließen-Button beendet werden.
- `/buypanel` veröffentlicht das Kauf-Panel. Dafür ist keine Berechtigung „Server verwalten“ erforderlich; der Bot muss im aktuellen Kanal Nachrichten senden und Embeds einbetten dürfen.
- `/buypanel-status` zeigt den Verfügbarkeitsstatus und erlaubt Server-Verwaltern, Produkte ein- oder auszuschalten.
- `/ping` antwortet mit `Pong!`.

Verfügbare Produkte: Project Neo, Project retrad, Project stellar, CSGO2 und Storm arc. Der Bot benötigt zum Erstellen und Verwalten der Tickets die Berechtigung „Kanäle verwalten“. Benutzer benötigen diese Bot-Berechtigung nicht. Zum Ändern der Produktverfügbarkeit bleibt „Server verwalten“ erforderlich, damit nicht beliebige Mitglieder den Status ändern können.
