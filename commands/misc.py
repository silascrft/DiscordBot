# commands/misc.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncssh
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# ======================================================
# ENVIRONMENT VARIABLES
# ======================================================
MC_SERVER_HOST = os.getenv("SERVER_IP")
MC_SERVER_USER = os.getenv("MC_SERVER_USER", "minecraft")

MISC_ROLES = {
    "Server": os.getenv("ROLE_SERVER_CONTROL", "ServerAdmin"),
    "Docker": os.getenv("ROLE_DOCKER_CONTROL", "ServerAdmin"),
}

DOCKER_CONTAINERS = [c.strip() for c in os.getenv("DOCKER_CONTAINERS", "minecraft1,minecraft2,minecraft3").split(",")]

# ======================================================
# SSH HELPER
# ======================================================
async def run_ssh(command: str) -> str:
    try:
        async with asyncssh.connect(MC_SERVER_HOST, username=MC_SERVER_USER) as conn:
            result = await conn.run(command, check=True)
            logger.info(f"SSH command executed: {command}")
            return result.stdout
    except (asyncssh.Error, OSError) as e:
        logger.error(f"SSH error '{command}': {e}")
        return f"Fehler beim Ausführen des Commands: {e} ❌"

# ======================================================
# MAIN COG
# ======================================================
class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------
    # SERVER COMMAND
    # --------------------------
    @app_commands.command(name="server", description="Server starten/stoppen")
    @app_commands.describe(action="Was soll passieren?")
    @app_commands.choices(action=[
        app_commands.Choice(name="Shutdown", value="shutdown"),
        app_commands.Choice(name="Restart", value="restart")
    ])
    async def server_cmd(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        required_role = MISC_ROLES["Server"]
        if required_role not in [role.name for role in interaction.user.roles]:
            return await interaction.response.send_message(
                f"Du benötigst die Rolle **{required_role}**! 🔐", ephemeral=True
            )

        await interaction.response.defer()

        if action.value == "shutdown":
            await interaction.followup.send("Fahre Server herunter… 🔻")
            output = await run_ssh("sudo shutdown -h now")
        else:
            await interaction.followup.send("Starte Server neu… 🔄")
            output = await run_ssh("sudo reboot")

        await interaction.followup.send(f"**Ergebnis:**\n```\n{output}\n```")

    # --------------------------
    # DOCKER COMMAND
    # --------------------------
    @app_commands.command(name="docker", description="Docker Container starten/stoppen")
    @app_commands.describe(
        action="Was soll passieren?",
        container="Welchen Container möchtest du steuern?"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Start", value="start"),
            app_commands.Choice(name="Stop", value="stop")
        ],
        container=[app_commands.Choice(name=c, value=c) for c in DOCKER_CONTAINERS]
    )
    async def docker_cmd(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        container: app_commands.Choice[str]
    ):
        required_role = MISC_ROLES["Docker"]
        if required_role not in [role.name for role in interaction.user.roles]:
            return await interaction.response.send_message(
                f"Du benötigst die Rolle **{required_role}**! 🔐", ephemeral=True
            )

        await interaction.response.defer()

        if action.value == "start":
            await interaction.followup.send(f"Starte Container **{container.value}**… ⬆️")
            output = await run_ssh(f"Starte Container **{container.value}**… ▶")
        else:
            await interaction.followup.send(f"Stoppe Container **{container.value}**… ⏹️")
            output = await run_ssh(f"docker stop {container.value}")

        await interaction.followup.send(f"**Ergebnis:**\n```\n{output}\n```")

# ======================================================
# SETUP
# ======================================================
async def setup(bot: commands.Bot):
    cog = Misc(bot)
    await bot.add_cog(cog)
    # Explicitly add commands to guild tree
    bot.tree.add_command(cog.server_cmd, guild=bot.guild)
    bot.tree.add_command(cog.docker_cmd, guild=bot.guild)
