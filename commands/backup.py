# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import asyncssh
import os
from dotenv import load_dotenv
import logging
import tempfile
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)

MC_SERVER_HOST = os.getenv("MC_SERVER_HOST", "192.168.188.150")
MC_SERVER_USER = os.getenv("MC_SERVER_USER", "minecraft")
MC_SERVER_WORLD = "/home/Minecraft/minecraft1/data"
BACKUP_ROOT = "/home/Minecraft/minecraft1/backups"

DOCKER_CONTAINERS = os.getenv("DOCKER_CONTAINERS", "minecraft1").split(",")

# Lock file (cross-platform)
LOCK_DIR = os.path.join(tempfile.gettempdir(), "minecraft_backup")
os.makedirs(LOCK_DIR, exist_ok=True)
LOCK_FILE = os.path.join(LOCK_DIR, "backup.lock")

# Map backup type → required role
BACKUP_ROLES = {
    "ServerRestart": os.getenv("ROLE_SERVER_RESTART", "mcAdmin"),
    "ServerShutdown": os.getenv("ROLE_SERVER_SHUTDOWN", "mcAdmin"),
    "McHot": os.getenv("ROLE_MCHOT", "mcPlayer"),
    "McRestart": os.getenv("ROLE_MCRESTART", "mcAdmin"),
    "McShutdown": os.getenv("ROLE_MCSHUTDOWN", "mcAdmin"),
}


async def run_backup_script() -> tuple[str, bool]:
    """SSH into the server and run backup.sh"""
    if os.path.exists(LOCK_FILE):
        return ("Ein Backup läuft gerade, bitte warten…", False)

    # create lock
    with open(LOCK_FILE, "w") as f:
        f.write("locked")

    try:
        async with asyncssh.connect(MC_SERVER_HOST, username=MC_SERVER_USER) as conn:
            # Execute the backup.sh script
            cmd = "/home/Minecraft/minecraft1/backups/backup.sh"
            result = await conn.run(cmd, check=False)

            output = result.stdout or ""
            if result.stderr:
                output += "\nError:\n" + result.stderr

            if result.exit_status != 0:
                return (f"Backup-Script failed with exit code {result.exit_status}:\n{output}", False)

            logger.info("Backup script executed successfully.")
            return (f"Backup erfolgreich:\n{output}", True)

    except (asyncssh.Error, OSError) as e:
        logger.error(f"Fehler beim Backup: {e}")
        return (f"Fehler beim Backup: {e}", False)

    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)


async def perform_post_backup_action(action: str):
    """Perform server/container action after backup"""
    async with asyncssh.connect(MC_SERVER_HOST, username=MC_SERVER_USER) as conn:
        if action == "McHot":
            # Do nothing, server stays online
            return
        elif action == "ServerRestart":
            await conn.run("sudo reboot", check=False)
        elif action == "ServerShutdown":
            await conn.run("sudo shutdown now", check=False)
        elif action == "McRestart":
            for container in DOCKER_CONTAINERS:
                await conn.run(f"docker restart {container}", check=False)
        elif action == "McShutdown":
            for container in DOCKER_CONTAINERS:
                await conn.run(f"docker stop {container}", check=False)


class BackupCog(commands.Cog):
    """Backup system with a single command and subchoices."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def has_role(self, member: discord.Member, backup_type: str) -> bool:
        required_role = BACKUP_ROLES.get(backup_type)
        return required_role in [r.name for r in member.roles]

    @app_commands.command(
        name="backup",
        description="Führe ein Minecraft Backup aus"
    )
    @app_commands.describe(backup_type="Welche Art Backup möchtest du durchführen?")
    @app_commands.choices(
        backup_type=[
            app_commands.Choice(name="Server Restart", value="ServerRestart"),
            app_commands.Choice(name="Server Shutdown", value="ServerShutdown"),
            app_commands.Choice(name="Mc Hot", value="McHot"),
            app_commands.Choice(name="Mc Restart", value="McRestart"),
            app_commands.Choice(name="Mc Shutdown", value="McShutdown"),
        ]
    )
    async def backup_main(self, interaction: discord.Interaction, backup_type: app_commands.Choice[str]):

        backup_key = backup_type.value

        # Role check
        if not await self.has_role(interaction.user, backup_key):
            return await interaction.response.send_message(
                f"❌ Du hast nicht die erforderliche Rolle **{BACKUP_ROLES[backup_key]}**!",
                ephemeral=True
            )

        await interaction.response.defer()

        # Start embed
        embed_start = discord.Embed(
            title=f"🔧 Backup gestartet: {backup_type.name}",
            description="Bitte warten…",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed_start)

        # Run backup.py on server
        output, success = await run_backup_script()

        # Final embed
        embed_end = discord.Embed(
            title=("✅ Erfolgreich" if success else "❌ Fehlgeschlagen"),
            description=f"**Backup Typ:** {backup_type.name}\n"
                        f"```{output[:1000]}```",
            color=discord.Color.green() if success else discord.Color.red()
        )
        await interaction.followup.send(embed=embed_end)

        # Perform post-backup action if backup was successful
        if success:
            await perform_post_backup_action(backup_key)


# ----------------------------------------
# SETUP
# ----------------------------------------
async def setup(bot: commands.Bot):
    cog = BackupCog(bot)
    await bot.add_cog(cog)

    # Add to guild tree (same as misc script)
    bot.tree.add_command(cog.backup_main, guild=bot.guild)
