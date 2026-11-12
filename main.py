import asyncio
import json
import os
import re
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

PRODUCTS = (
    "Project Neo",
    "Project retrad",
    "Project stellar",
    "CSGO2",
    "Storm arc",
)
STATE_FILE = Path(os.getenv("BOT_STATE_FILE", "bot_state.json"))


def load_state() -> dict:
    default = {"availability": {product: True for product in PRODUCTS}, "buy_panels": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        default["availability"].update(data.get("availability", {}))
        default["buy_panels"] = data.get("buy_panels", [])
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return default


state = load_state()


def save_state() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def status_embed() -> discord.Embed:
    embed = discord.Embed(title="Verfügbarkeit", color=discord.Color.blurple())
    for product in PRODUCTS:
        emoji = "🟢" if state["availability"].get(product, False) else "🔴"
        label = "Verfügbar" if state["availability"].get(product, False) else "Nicht verfügbar"
        embed.add_field(name=f"{emoji} {product}", value=label, inline=False)
    return embed


def buy_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Kauf-Panel",
        description="Wähle ein verfügbares Produkt aus dem Dropdown-Menü. Dadurch wird ein privates Ticket für deine Anfrage erstellt.",
        color=discord.Color.green(),
    )
    for product in PRODUCTS:
        available = state["availability"].get(product, False)
        embed.add_field(
            name=f"{'🟢' if available else '🔴'} {product}",
            value="Verfügbar" if available else "Derzeit nicht verfügbar",
            inline=True,
        )
    return embed


async def create_ticket(
    interaction: discord.Interaction, *, product: str | None = None
) -> discord.TextChannel:
    guild = interaction.guild
    if guild is None:
        raise ValueError("Tickets können nur auf einem Server erstellt werden.")

    for channel in guild.text_channels:
        if channel.topic and channel.topic.startswith(f"ticket_owner:{interaction.user.id}"):
            raise ValueError(f"Du hast bereits ein offenes Ticket: {channel.mention}")

    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True
        ),
    }
    if guild.me is not None:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
        )

    support_role_id = os.getenv("SUPPORT_ROLE_ID")
    if support_role_id and support_role_id.isdigit():
        support_role = guild.get_role(int(support_role_id))
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

    category = None
    category_id = os.getenv("TICKET_CATEGORY_ID")
    if category_id and category_id.isdigit():
        possible_category = guild.get_channel(int(category_id))
        if isinstance(possible_category, discord.CategoryChannel):
            category = possible_category

    slug = re.sub(r"[^a-z0-9-]", "", interaction.user.name.lower().replace(" ", "-"))[:40]
    channel = await guild.create_text_channel(
        name=f"ticket-{slug or interaction.user.id}",
        topic=f"ticket_owner:{interaction.user.id}; product:{product or 'support'}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket geöffnet von {interaction.user}",
    )
    details = f" für **{product}**" if product else ""
    await channel.send(
        f"Hallo {interaction.user.mention}! Dein Ticket{details} wurde erstellt. Das Support-Team meldet sich hier."
        ,
        view=TicketCloseView(),
    )
    return channel


async def refresh_buy_panels() -> None:
    # Bestehende Kauf-Panels werden nach einer Statusänderung ebenfalls aktualisiert.
    valid_panels = []
    for panel in state["buy_panels"]:
        try:
            guild = bot.get_guild(int(panel["guild_id"]))
            channel = guild.get_channel(int(panel["channel_id"])) if guild else None
            message = await channel.fetch_message(int(panel["message_id"])) if channel else None
            if message:
                await message.edit(embed=buy_embed(), view=BuyPanelView())
                valid_panels.append(panel)
        except (discord.HTTPException, KeyError, ValueError, TypeError):
            continue
    if len(valid_panels) != len(state["buy_panels"]):
        state["buy_panels"] = valid_panels
        save_state()


class TicketCloseView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ticket schließen", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket:close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not (
            channel.topic and channel.topic.startswith("ticket_owner:")
        ):
            await interaction.response.send_message("Das ist kein Ticket-Kanal.", ephemeral=True)
            return
        owner_id = channel.topic.split(";", 1)[0].split(":", 1)[1]
        is_owner = str(interaction.user.id) == owner_id
        is_staff = interaction.user.guild_permissions.manage_channels
        role_id = os.getenv("SUPPORT_ROLE_ID")
        if role_id and role_id.isdigit():
            role = interaction.guild.get_role(int(role_id)) if interaction.guild else None
            is_staff = is_staff or (role is not None and role in getattr(interaction.user, "roles", []))
        if not (is_owner or is_staff):
            await interaction.response.send_message("Nur der Ticket-Ersteller oder Support kann schließen.", ephemeral=True)
            return
        await interaction.response.send_message("Ticket wird in 5 Sekunden geschlossen.", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket geschlossen von {interaction.user}")


class BuyPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        available = [product for product in PRODUCTS if state["availability"].get(product, False)]
        if available:
            select = discord.ui.Select(
                placeholder="Verfügbares Produkt auswählen…",
                min_values=1,
                max_values=1,
                options=[discord.SelectOption(label=product, value=product) for product in available],
                custom_id="buypanel:product",
            )
            select.callback = self.select_product
            self.add_item(select)
        else:
            self.add_item(discord.ui.Button(
                label="Aktuell keine Produkte verfügbar", style=discord.ButtonStyle.secondary,
                disabled=True, custom_id="buypanel:unavailable",
            ))

    async def select_product(self, interaction: discord.Interaction) -> None:
        product = interaction.data["values"][0]
        if product not in PRODUCTS or not state["availability"].get(product, False):
            await interaction.response.send_message("Dieses Produkt ist aktuell nicht verfügbar.", ephemeral=True)
            return
        try:
            channel = await create_ticket(interaction, product=product)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Dein Ticket für **{product}**: {channel.mention}", ephemeral=True)


class StatusManagementView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        for index, product in enumerate(PRODUCTS):
            button = discord.ui.Button(
                label=product,
                style=discord.ButtonStyle.success if state["availability"].get(product, False) else discord.ButtonStyle.danger,
                emoji="🟢" if state["availability"].get(product, False) else "🔴",
                custom_id=f"buypanel-status:toggle:{index}",
                row=index // 3,
            )
            button.callback = self.make_toggle(product)
            self.add_item(button)

    def make_toggle(self, product: str):
        async def toggle(interaction: discord.Interaction) -> None:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("Dafür brauchst du die Berechtigung Server verwalten.", ephemeral=True)
                return
            state["availability"][product] = not state["availability"].get(product, False)
            save_state()
            self.refresh_buttons()
            await interaction.response.edit_message(embed=status_embed(), view=self)
            await refresh_buy_panels()
        return toggle

    def refresh_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("buypanel-status:toggle:"):
                index = int(item.custom_id.rsplit(":", 1)[1])
                product = PRODUCTS[index]
                available = state["availability"].get(product, False)
                item.style = discord.ButtonStyle.success if available else discord.ButtonStyle.danger
                item.emoji = "🟢" if available else "🔴"


class StandardBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Persistent views halten Ticket-Buttons und Panels nach Neustarts funktionsfähig.
        self.add_view(TicketCloseView())
        self.add_view(BuyPanelView())
        self.add_view(StatusManagementView())
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


@bot.tree.command(name="ticket", description="Erstellt ein privates Support-Ticket.")
async def ticket(interaction: discord.Interaction) -> None:
    try:
        channel = await create_ticket(interaction)
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)
        return
    await interaction.response.send_message(f"Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True)


@bot.tree.command(name="buypanel", description="Zeigt das Kauf-Panel mit verfügbaren Produkten.")
async def buypanel(interaction: discord.Interaction) -> None:
    if interaction.guild is None or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Dafür brauchst du auf einem Server die Berechtigung Server verwalten.", ephemeral=True)
        return
    await interaction.response.send_message(embed=buy_embed(), view=BuyPanelView())
    message = await interaction.original_response()
    state["buy_panels"].append({
        "guild_id": str(interaction.guild.id),
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
    })
    save_state()


@bot.tree.command(name="buypanel-status", description="Zeigt und verwaltet die Verfügbarkeit der Produkte.")
async def buypanel_status(interaction: discord.Interaction) -> None:
    if interaction.guild is None or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Dafür brauchst du auf einem Server die Berechtigung Server verwalten.", ephemeral=True)
        return
    await interaction.response.send_message(
        embed=status_embed(), view=StatusManagementView(),
        ephemeral=True,
    )


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
