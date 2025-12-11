import os
import asyncio
import textwrap

import discord
from discord.ext import commands
from discord import app_commands
from mcrcon import MCRcon
from dotenv import load_dotenv

# Lade .env, falls vorhanden
load_dotenv()

class MCCommands(commands.Cog):
    """Cog zum Ausführen von Minecraft-RCON-Befehlen über Discord Slash-Commands.

    - liest RCON-Konfiguration aus der Umgebung
    - prüft Rollenberechtigung (ROLE_SERVER_CONTROL)
    - führt Blocking-RCON-Aufrufe im Threadpool aus, damit der Bot-Loop nicht blockiert
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Konfiguration aus Umgebung
        self.RCON_HOST = os.getenv("RCON_HOST", "127.0.0.1")
        self.RCON_PORT = int(os.getenv("RCON_PORT", 25575))
        self.RCON_PASSWORD = os.getenv("RCON_PASSWORD", "changeme")

        # Rolle, die Zugriff auf Server-Kommandos hat
        self.ROLE_SERVER_CONTROL = os.getenv("ROLE_SERVER_CONTROL", "ServerAdmin")

    async def _run_rcon_blocking(self, command: str) -> str:
        """Blocking RCON-Aufruf — führt MCRcon in executor aus."""
        def blocking():
            try:
                with MCRcon(self.RCON_HOST, self.RCON_PASSWORD, port=self.RCON_PORT) as rcon:
                    return rcon.command(command)
            except Exception as e:
                return f"RCON-Fehler: {e}"

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, blocking)

    def _member_has_role(self, member: discord.Member) -> bool:
        if not isinstance(member, discord.Member):
            return False
        for r in member.roles:
            if r.name == self.ROLE_SERVER_CONTROL:
                return True
        return False

    @app_commands.command(name="mcd", description="Führe einen Minecraft-Befehl über RCON aus")
    @app_commands.describe(cmd="Der auszuführende Minecraft-Server-Befehl (z. B. 'say Hallo')")
    async def mcd(self, interaction: discord.Interaction, cmd: str):
        # Permissions: nur Mitglieder mit Rolle ROLE_SERVER_CONTROL dürfen Befehle ausführen
        member = interaction.user
        if not self._member_has_role(member):
            await interaction.response.send_message("Du hast keine Berechtigung, Minecraft-Befehle auszuführen.", ephemeral=True)
            return

        # Ack immediate to avoid interaction timeout
        await interaction.response.defer(ephemeral=True)

        # Run RCON in executor
        try:
            result = await asyncio.wait_for(self._run_rcon_blocking(cmd), timeout=20)
        except asyncio.TimeoutError:
            await interaction.followup.send("RCON-Antwort zu langsam (Timeout).", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"Fehler beim Ausführen des Befehls: {e}", ephemeral=True)
            return

        if not result:
            result = "(kein Output)"

        # Limit length to Discord message limits and format nicely
        max_len = 1900
        if len(result) > max_len:
            result = result[:max_len] + "\n... (gekürzt)"

        await interaction.followup.send(f"**RCON Output:**\n```\n{result}\n```", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cog = MCCommands(bot)
    await bot.add_cog(cog)
    # App-Command explizit zur Guild hinzufügen (wie in deinem Stil)
    try:
        bot.tree.add_command(cog.mcd, guild=bot.guild)
    except Exception:
        # Falls bot.guild nicht gesetzt ist (z. B. beim Unit-Test), ignoriere
        pass
