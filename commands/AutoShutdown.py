# AutoShutdown.py
import os
import re
import asyncio
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from mcrcon import MCRcon


from .backup import run_backup_script, perform_post_backup_action

# ------------------------- Load environment variables -------------------------
load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_NAME = os.getenv("CHANNEL_NAME")

SSH_USER = os.getenv("MC_SERVER_USER", "minecraft")
SSH_HOST = os.getenv("SERVER_IP")
LOG_PATH = "/home/Minecraft/minecraft1/data/logs/latest.log"
SHUTDOWN_SCRIPT = "/home/Minecraft/minecraft1/backups/test.sh"

ROLE_ADMIN = os.getenv("ROLE_SERVER_CONTROL", "ServerAdmin")
ROLE_PLAYER = "mcPlayer"

RCON_PASSWORD = os.getenv("RCON_PASSWORD")
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))


# ------------------------- Cog -------------------------
class AutoShutdown(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.enabled = True
        self.shutdown_timer = 60
        self.countdown_task = None
        self.log_task = None
        self.online_players = set()

    # ------------------------- Helpers -------------------------
    def has_role(self, member: discord.Member, role_name: str):
        return any(role.name == role_name for role in member.roles)

    async def check_channel(self, interaction: discord.Interaction):
        if interaction.channel.name != CHANNEL_NAME:
            await interaction.response.send_message(
                f"Dieser Command darf nur im #{CHANNEL_NAME}-Kanal verwendet werden. ❌",
                ephemeral=True
            )
            return False
        return True

    # ------------------------- RCON Player Fetch -------------------------
    async def fetch_online_players_rcon(self):
        """Reads the current online players via RCON 'list' command."""
        try:
            with MCRcon(SSH_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
                response = mcr.command("list")

            # Expected: "There are 2 of a max of 20 players online: Steve, Alex"
            match = re.search(r"online:\s*(.*)", response)
            if not match:
                logging.warning(f"[AutoShutdown] Konnte Spieler aus RCON nicht parsen: '{response}'")
                return

            players_str = match.group(1).strip()
            if players_str == "":
                self.online_players = set()
            else:
                self.online_players = set(name.strip() for name in players_str.split(",") if name.strip())

            logging.info(f"[AutoShutdown] Initial RCON Players: {self.online_players}")

        except Exception as e:
            logging.error(f"[AutoShutdown] Fehler beim Abruf der Spieler über RCON: {e}")

    # ------------------------- Log follower -------------------------
    async def follow_log(self):
        cmd = ["ssh", f"{SSH_USER}@{SSH_HOST}", f"tail -F {LOG_PATH}"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        logging.info("[AutoShutdown] Verbunden mit Minecraft-Logs per SSH (tail -F).")

        while True:
            line = await process.stdout.readline()
            if not line:
                await asyncio.sleep(0.1)
                continue
            decoded = line.decode(errors="ignore").strip()
            await self.handle_log_line(decoded)

    async def handle_log_line(self, line: str):
        join_match = re.search(r"([A-Za-z0-9_]+) joined the game", line)
        leave_match = re.search(r"([A-Za-z0-9_]+) left the game", line)

        if join_match:
            player = join_match.group(1)
            if player not in self.online_players:
                self.online_players.add(player)
                logging.info(f"[AutoShutdown] Player JOIN: {player}")
                await self.cancel_shutdown(player)
            return

        if leave_match:
            player = leave_match.group(1)
            if player in self.online_players:
                self.online_players.remove(player)
                logging.info(f"[AutoShutdown] Player LEAVE: {player}")
                await self.check_after_leave()
            return

    async def check_after_leave(self):
        if not self.enabled:
            return
        if len(self.online_players) == 0:
            await self.start_shutdown_countdown()

    async def start_shutdown_countdown(self):
        if self.countdown_task:
            return
        channel = discord.utils.get(self.bot.get_all_channels(), name=CHANNEL_NAME)
        if channel:
            await channel.send(f"Server ist leer — AutoShutdown in `{self.shutdown_timer}` Minuten. ⏳")
        logging.info("[AutoShutdown] Countdown gestartet.")
        self.countdown_task = asyncio.create_task(self.countdown_coroutine())

    async def countdown_coroutine(self):
        remaining = self.shutdown_timer * 60
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            if len(self.online_players) > 0:
                logging.info("Countdown abgebrochen, Spieler wieder online. 🔄")
                self.countdown_task = None
                return
        await self.perform_shutdown()

    async def cancel_shutdown(self, player_name=None):
        if self.countdown_task:
            self.countdown_task.cancel()
            self.countdown_task = None
            channel = discord.utils.get(self.bot.get_all_channels(), name=CHANNEL_NAME)
            if channel:
                if player_name:
                    await channel.send(f"AutoShutdown durch das Joinen von `{player_name}` abgebrochen ❌")
                else:
                    await channel.send("AutoShutdown abgebrochen ❌")

    async def perform_shutdown(self):
        logging.info("[AutoShutdown] Starte Backup + ServerShutdown...")

        channel = discord.utils.get(self.bot.get_all_channels(), name=CHANNEL_NAME)
        if channel:
            await channel.send("Backup + Shutdown gestartet ⚙️")

        output, success = await run_backup_script()
        if not success:
            if channel:
                await channel.send(f"Backup fehlgeschlagen ❌\n```{output[:1000]}```")
            self.countdown_task = None
            return

        if channel:
            await channel.send(f"Backup erfolgreich ✅\n```{output[:1000]}```")

        await perform_post_backup_action("ServerShutdown")
        if channel:
            await channel.send("ServerShutdown durchgeführt. 🛑")

        self.countdown_task = None

    # ------------------------- Commands -------------------------
    @app_commands.command(name="autosd", description="Verwalte AutoShutdown")
    @app_commands.choices(action=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
        app_commands.Choice(name="Set Timer", value="set")
    ])
    @app_commands.describe(minutes="Nur für 'Set Timer', Minuten angeben")
    async def autosd(self, interaction: discord.Interaction, action: app_commands.Choice[str], minutes: int):
        if not await self.check_channel(interaction):
            return
        if not self.has_role(interaction.user, ROLE_ADMIN):
            return await interaction.response.send_message("Du benötigst die Admin-Rolle ❌", ephemeral=True)

        if action.value == "enable":
            self.enabled = True
            await interaction.response.send_message("AutoShutdown aktiviert ✅")

        elif action.value == "disable":
            self.enabled = False
            await interaction.response.send_message("AutoShutdown deaktiviert ❌")

        elif action.value == "set":
            if minutes is None or minutes <= 0:
                return await interaction.response.send_message("Bitte gültige Minuten angeben ❌", ephemeral=True)
            self.shutdown_timer = minutes
            await interaction.response.send_message(f"Shutdown-Timer auf **{minutes} Minuten** gesetzt ⏳")

    @app_commands.command(name="status", description="Zeige den AutoShutdown Status")
    async def status(self, interaction: discord.Interaction):
        if not self.has_role(interaction.user, ROLE_PLAYER):
            return await interaction.response.send_message("Du benötigst die Spieler-Rolle ❌", ephemeral=True)
        if not await self.check_channel(interaction):
            return
        if self.countdown_task:
            await interaction.response.send_message("Countdown läuft ⏳")
        else:
            await interaction.response.send_message("Kein aktiver Timer ⏹️")

    @app_commands.command(name="players", description="Zeige Online-Spieler")
    async def players(self, interaction: discord.Interaction):
        if not self.has_role(interaction.user, ROLE_PLAYER):
            return await interaction.response.send_message("Du benötigst die Spieler-Rolle ❌", ephemeral=True)
        if not await self.check_channel(interaction):
            return
        if not self.online_players:
            await interaction.response.send_message("Niemand online 👀")
        else:
            players = "\n• ".join(sorted(self.online_players))
            await interaction.response.send_message(f"Online Spieler ({len(self.online_players)}):\n• {players} 🎮")

    # ------------------------- On ready -------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        # 1) Detect currently online players BEFORE following logs
        await self.fetch_online_players_rcon()

        # 2) Start log follower
        if not self.log_task or self.log_task.done():
            self.log_task = asyncio.create_task(self.follow_log())


# ------------------------- Cog Setup -------------------------
async def setup(bot: commands.Bot):
    cog = AutoShutdown(bot)
    await bot.add_cog(cog)
    guild = discord.Object(id=GUILD_ID)

    bot.tree.add_command(cog.autosd, guild=guild)
    bot.tree.add_command(cog.status, guild=guild)
    bot.tree.add_command(cog.players, guild=guild)
