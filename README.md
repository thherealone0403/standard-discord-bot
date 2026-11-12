# Standard Discord Bot

Ein einfacher, sauberer Discord-Bot-Grundbaustein mit Python, `discord.py` und Slash-Commands.

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
```

Die echte `.env` wird durch `.gitignore` ausgeschlossen. Teile deinen Token niemals und committe ihn nicht.

## Bot starten

```bash
python main.py
```

Der Bot synchronisiert beim Start die Slash-Commands. Der Beispiel-Command `/ping` antwortet mit `Pong!`.

Beim Einladen des Bots müssen mindestens die Scopes `bot` und `applications.commands` ausgewählt sein. Für den Beispiel-Command sind keine privilegierten Intents erforderlich.
