import asyncio
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

PRODUCTS = (
    "Project Neo",
    "Project retrac",
    "Project stellar",
    "CSGO2",
    "Storm arc",
)
TICKET_TYPES = (
    ("support", "Allgemeiner Support", "Fragen oder Hilfe zu einem Anliegen"),
    ("purchase", "Kaufanfrage", "Fragen zu einem Produkt oder einer Bestellung"),
    ("bug", "Problem melden", "Melde einen Fehler oder ein technisches Problem"),
)
STATE_FILE = Path(os.getenv("BOT_STATE_FILE", "bot_state.json"))


def load_state() -> dict:
    default = {
        "availability": {product: True for product in PRODUCTS},
        "prices": {product: None for product in PRODUCTS},
        "buy_panels": [],
    }
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        default["availability"].update(data.get("availability", {}))
        default["prices"].update(data.get("prices", {}))
        default["buy_panels"] = data.get("buy_panels", [])
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return default


state = load_state()


def save_state() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def format_price(value: object) -> str:
    if value is None or value == "":
        return "nicht festgelegt"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "nicht festgelegt"
    return f"{amount:.2f}".replace(".", ",") + " €"


def status_embed() -> discord.Embed:
    embed = discord.Embed(title="Verfügbarkeit & Preise", color=discord.Color.blurple())
    for product in PRODUCTS:
        available = state["availability"].get(product, False)
        embed.add_field(
            name=f"{'🟢' if available else '🔴'} {product} · Lifetime: {format_price(state['prices'].get(product))}",
            value="Verfügbar" if available else "Nicht verfügbar",
            inline=False,
        )
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
            name=f"{'🟢' if available else '🔴'} {product} · Lifetime: {format_price(state['prices'].get(product))}",
            value="Verfügbar" if available else "Derzeit nicht verfügbar",
            inline=True,
        )
    return embed


def ticket_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎫 Support-Tickets",
        description=(
            "Wähle im Menü unten aus, worum es geht. Ich erstelle dann einen privaten Kanal, "
            "in dem du mit dem Support-Team schreiben kannst.\n\n"
            "Bitte erstelle nur ein Ticket pro Anliegen."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Verfügbare Themen",
        value="🛟 Allgemeiner Support\n🛒 Kaufanfrage\n🛠️ Problem melden",
        inline=False,
    )
    embed.set_footer(text="Dein Ticket ist nur für dich und das Support-Team sichtbar.")
    return embed


async def create_ticket(
    interaction: discord.Interaction, *, ticket_type: str = "Allgemeiner Support"
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
        topic=f"ticket_owner:{interaction.user.id}; type:{ticket_type}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket geöffnet von {interaction.user}",
    )
    await channel.send(
        f"Hallo {interaction.user.mention}! Dein Ticket (**{ticket_type}**) wurde erstellt. "
        "Das Support-Team meldet sich hier.",
        view=TicketCloseView(),
    )
    return channel


async def refresh_buy_panels() -> None:
    # Bestehende Kauf-Panels werden nach Preis- oder Statusänderungen aktualisiert.
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
            await interaction.response.send_message(
                "Nur der Ticket-Ersteller oder Support kann schließen.", ephemeral=True
            )
            return
        await interaction.response.send_message("Ticket wird in 5 Sekunden geschlossen.", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket geschlossen von {interaction.user}")


class TicketPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Select(
                placeholder="Wähle ein Ticket-Thema …",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(label=label, value=value, description=description, emoji=emoji)
                    for value, label, description, emoji in (
                        ("support", "Allgemeiner Support", "Fragen oder Hilfe zu einem Anliegen", "🛟"),
                        ("purchase", "Kaufanfrage", "Fragen zu einem Produkt oder einer Bestellung", "🛒"),
                        ("bug", "Problem melden", "Melde einen Fehler oder ein technisches Problem", "🛠️"),
                    )
                ],
                custom_id="ticketpanel:type",
            )
        )
        self.children[0].callback = self.create_from_selection

    async def create_from_selection(self, interaction: discord.Interaction) -> None:
        selected_type = interaction.data["values"][0]
        labels = {value: label for value, label, _description in TICKET_TYPES}
        if selected_type not in labels:
            await interaction.response.send_message("Ungültige Ticket-Auswahl.", ephemeral=True)
            return
        try:
            channel = await create_ticket(interaction, ticket_type=labels[selected_type])
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            f"Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True
        )


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
            self.add_item(
                discord.ui.Button(
                    label="Aktuell keine Produkte verfügbar",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                    custom_id="buypanel:unavailable",
                )
            )

    async def select_product(self, interaction: discord.Interaction) -> None:
        product = interaction.data["values"][0]
        if product not in PRODUCTS or not state["availability"].get(product, False):
            await interaction.response.send_message(
                "Dieses Produkt ist aktuell nicht verfügbar.", ephemeral=True
            )
            return
        try:
            channel = await create_ticket(interaction, ticket_type=f"Kaufanfrage: {product}")
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            f"Dein Ticket für **{product}**: {channel.mention}", ephemeral=True
        )


class ProductPriceModal(discord.ui.Modal):
    def __init__(self, product: str, status_view: "StatusManagementView") -> None:
        super().__init__(title=f"Lifetime-Preis: {product}")
        self.product = product
        self.status_view = status_view
        current_price = state["prices"].get(product)
        self.price = discord.ui.TextInput(
            label="Preis in Euro",
            placeholder="z. B. 12,50",
            default=str(current_price).replace(".", ",") if current_price is not None else None,
            max_length=12,
            required=True,
        )
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_price = str(self.price.value).strip().replace(",", ".")
        try:
            amount = Decimal(raw_price)
        except InvalidOperation:
            await interaction.response.send_message(
                "Bitte gib einen gültigen Preis ein, zum Beispiel 12,50.", ephemeral=True
            )
            return
        if not amount.is_finite() or amount < 0 or amount > Decimal("999999.99"):
            await interaction.response.send_message(
                "Der Preis muss zwischen 0 und 999999,99 € liegen.", ephemeral=True
            )
            return

        state["prices"][self.product] = format(amount, "f")
        save_state()
        self.status_view.refresh_buttons()
        await refresh_buy_panels()
        if interaction.message is not None:
            await interaction.response.edit_message(embed=status_embed(), view=self.status_view)
        else:
            await interaction.response.send_message(
                f"Lifetime-Preis für **{self.product}** gespeichert: {format_price(amount)}",
                ephemeral=True,
            )


class StatusManagementView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        for index, product in enumerate(PRODUCTS):
            available = state["availability"].get(product, False)
            toggle = discord.ui.Button(
                label=product,
                style=discord.ButtonStyle.success if available else discord.ButtonStyle.danger,
                emoji="🟢" if available else "🔴",
                custom_id=f"buypanel-status:toggle:{index}",
                row=index,
            )
            toggle.callback = self.make_toggle(product)
            self.add_item(toggle)

            price_button = discord.ui.Button(
                label="Preis ändern",
                style=discord.ButtonStyle.secondary,
                emoji="💶",
                custom_id=f"buypanel-status:price:{index}",
                row=index,
            )
            price_button.callback = self.make_price_editor(product)
            self.add_item(price_button)

    def make_toggle(self, product: str):
        async def toggle(interaction: discord.Interaction) -> None:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "Dafür brauchst du die Berechtigung Server verwalten.", ephemeral=True
                )
                return
            state["availability"][product] = not state["availability"].get(product, False)
            save_state()
            self.refresh_buttons()
            await interaction.response.edit_message(embed=status_embed(), view=self)
            await refresh_buy_panels()

        return toggle

    def make_price_editor(self, product: str):
        async def edit_price(interaction: discord.Interaction) -> None:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "Dafür brauchst du die Berechtigung Server verwalten.", ephemeral=True
                )
                return
            await interaction.response.send_modal(ProductPriceModal(product, self))

        return edit_price

    def refresh_buttons(self) -> None:
        for item in self.children:
            if (
                isinstance(item, discord.ui.Button)
                and item.custom_id
                and item.custom_id.startswith("buypanel-status:toggle:")
            ):
                index = int(item.custom_id.rsplit(":", 1)[1])
                product = PRODUCTS[index]
                available = state["availability"].get(product, False)
                item.style = discord.ButtonStyle.success if available else discord.ButtonStyle.danger
                item.emoji = "🟢" if available else "🔴"


class StandardBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Persistent views halten Tickets und Panels nach Neustarts funktionsfähig.
        self.add_view(TicketCloseView())
        self.add_view(TicketPanelView())
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


@bot.tree.command(name="ticket", description="Erstellt direkt ein privates Support-Ticket.")
async def ticket(interaction: discord.Interaction) -> None:
    try:
        channel = await create_ticket(interaction)
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)
        return
    await interaction.response.send_message(
        f"Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True
    )


@bot.tree.command(name="ticket-panel", description="Veröffentlicht das Support-Ticket-Panel.")
async def ticket_panel(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "Das Ticket-Panel kann nur auf einem Server veröffentlicht werden.", ephemeral=True
        )
        return
    await interaction.response.send_message(embed=ticket_panel_embed(), view=TicketPanelView())


@bot.tree.command(name="buypanel", description="Veröffentlicht das Kauf-Panel mit verfügbaren Produkten.")
async def buypanel(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "Das Kauf-Panel kann nur auf einem Server veröffentlicht werden.", ephemeral=True
        )
        return
    await interaction.response.send_message(embed=buy_embed(), view=BuyPanelView())
    message = await interaction.original_response()
    state["buy_panels"].append(
        {
            "guild_id": str(interaction.guild.id),
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
        }
    )
    save_state()


@bot.tree.command(name="buypanel-status", description="Zeigt und verwaltet Produktstatus und Preise.")
async def buypanel_status(interaction: discord.Interaction) -> None:
    if interaction.guild is None or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "Dafür brauchst du auf einem Server die Berechtigung Server verwalten.", ephemeral=True
        )
        return
    await interaction.response.send_message(
        embed=status_embed(), view=StatusManagementView(), ephemeral=True
    )


async def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN fehlt. Lege eine .env-Datei an (siehe .env.example).")

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
