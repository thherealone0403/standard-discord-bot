import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


class StandardBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Registriert Slash-Commands global bei Discord.
        await self.tree.sync()


intents = discord.Intents.default()
bot = StandardBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    if bot.user is not None:
        print(f"Eingeloggt als {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="ping", description="Prüft, ob der Bot erreichbar ist.")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Pong! 🏓")


async def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN fehlt. Lege eine .env-Datei an (siehe .env.example)."
        )

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
