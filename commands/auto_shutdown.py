import os
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import paramiko
from mcstatus.server import JavaServer

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("AutoShutdown")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

@dataclass
class EnvConfig:
    guild_id: int
    channel_name: str
    rcon_host: str
    rcon_port: int
    rcon_password: str
    server_ip: str
    ssh_user: str
    empty_timeout_seconds: int = 900
    check_interval_seconds: int = 10


def load_env_config() -> EnvConfig:
    return EnvConfig(
        guild_id=int(os.getenv("GUILD_ID", "0")),
        channel_name=os.getenv("CHANNEL_NAME", "general"),
        rcon_host=os.getenv("RCON_HOST", "127.0.0.1"),
        rcon_port=int(os.getenv("RCON_PORT", "25575")),
        rcon_password=os.getenv("RCON_PASSWORD", ""),
        server_ip=os.getenv("SERVER_IP", "127.0.0.1"),
        ssh_user=os.getenv("MC_SERVER_USER", "minecraft"),
        empty_timeout_seconds=int(os.getenv("EMPTY_TIMEOUT", "1800")),
        check_interval_seconds=int(os.getenv("CHECK_INTERVAL", "10")),
    )


class AutoShutdownCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: EnvConfig):
        self.bot = bot
        self.cfg = cfg
        self.enabled = True
        self.empty_timeout_seconds = cfg.empty_timeout_seconds
        self._shutdown_deadline: Optional[float] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_known_player_count: Optional[int] = None
        self._shutdown_in_progress = False
        self.mc = JavaServer.lookup(f"{cfg.rcon_host}:25565")
        bot.loop.create_task(self._start_bg())

    async def _start_bg(self):
        await self.bot.wait_until_ready()
        if not self._monitor_task or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _send_channel_message(self, message: str):
        guild = self.bot.get_guild(self.cfg.guild_id)
        if not guild:
            return
        channel = discord.utils.get(guild.text_channels, name=self.cfg.channel_name)
        if channel:
            await channel.send(message)

    @app_commands.command(name="autosd", description="Auto-Shutdown verwalten.")
    @app_commands.describe(action="Aktion wählen")
    @app_commands.choices(action=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Set", value="set")
    ])
    async def autosd(self, interaction: discord.Interaction, action: app_commands.Choice[str], seconds: Optional[int] = None):
        action_value = action.value.lower()

        if action_value == "enable":
            self.enabled = True
            await interaction.response.send_message("AutoShutdown aktiviert. 🟩")
            return

        if action_value == "disable":
            self.enabled = False
            self._shutdown_deadline = None
            await interaction.response.send_message("AutoShutdown deaktiviert. 🟥")
            return

        if action_value == "status":
            if not self.enabled:
                await interaction.response.send_message("AutoShutdown deaktiviert.")
                return
            if self._shutdown_deadline is None:
                await interaction.response.send_message(f"Aktiv, kein Timer. Timer Zeit: `{self.empty_timeout_seconds}`s ⏱️")
                return
            remaining = max(0, int(self._shutdown_deadline - time.time()))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            await interaction.response.send_message(f"Timer läuft: `{hours:02d}:{minutes:02d}:{seconds:02d} `⌛")
            return

        if action_value == "set":
            if seconds is None or seconds < 0:
                await interaction.response.send_message("Ungültige Zeit.")
                return
            self.empty_timeout_seconds = seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            sec = seconds % 60
            await interaction.response.send_message(f"Timeout gesetzt: {hours:02d}:{minutes:02d}:{sec:02d}")
            return

        await interaction.response.send_message("Ungültige Aktion.")

    async def _monitor_loop(self):
        backoff = 5
        while True:
            try:
                if self._shutdown_in_progress:
                    # Server ist gerade heruntergefahren, ping loop bis wieder online
                    while True:
                        try:
                            await asyncio.sleep(30)
                            status = await asyncio.get_running_loop().run_in_executor(None, self.mc.status)
                            if status.players is not None:
                                self._shutdown_in_progress = False
                                remaining = self.empty_timeout_seconds
                                hours = remaining // 3600
                                minutes = (remaining % 3600) // 60
                                seconds = remaining % 60
                                await self._send_channel_message(f"Shutdown-Timer gestartet: `{hours:02d}:{minutes:02d}:{seconds:02d}` bis Server-Shutdown ⌛")
                                break
                        except:
                            continue
                else:
                    await self._cycle()
                backoff = 5
            except Exception as e:
                logger.exception(e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)

            await asyncio.sleep(self.cfg.check_interval_seconds)

    async def _cycle(self):
        loop = asyncio.get_running_loop()
        player_count = None
        try:
            status = await loop.run_in_executor(None, self.mc.status)
            player_count = status.players.online
        except:
            try:
                q = await loop.run_in_executor(None, self.mc.query)
                player_count = len(q.players)
            except:
                logger.warning("Minecraft unreachable.")
                return

        if self.enabled:
            if player_count == 0:
                if self._shutdown_deadline is None:
                    self._shutdown_deadline = time.time() + self.empty_timeout_seconds
                    remaining = self.empty_timeout_seconds
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    seconds = remaining % 60
                    await self._send_channel_message(f"Shutdown-Timer gestartet: `{hours:02d}:{minutes:02d}:{seconds:02d}` bis Server-Shutdown")
                else:
                    if time.time() >= self._shutdown_deadline:
                        self._shutdown_in_progress = True
                        await self._shutdown_server()
                        self._shutdown_deadline = None
            else:
                if self._shutdown_deadline is not None:
                    await self._send_channel_message(f"Shutdown-Timer gestoppt durch Spielerbeigetritt (`{player_count}` Spieler online)")
                self._shutdown_deadline = None

        self._last_known_player_count = player_count

    async def _shutdown_server(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._ssh_shutdown)

    def _ssh_shutdown(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=self.cfg.server_ip, username=self.cfg.ssh_user, timeout=10)
            stdin, stdout, stderr = client.exec_command("sudo shutdown -h now")
            stdout.channel.recv_exit_status()
        finally:
            client.close()


async def setup(bot: commands.Bot):
    cfg = load_env_config()
    cog = AutoShutdownCog(bot, cfg)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.autosd, guild=discord.Object(id=cfg.guild_id))
