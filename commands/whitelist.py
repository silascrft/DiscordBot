# commands/whitelist.py
import discord
from discord.ext import commands
from discord import app_commands
from mcrcon import MCRcon
import os
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_NAME = os.getenv("CHANNEL_NAME")

RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = int(os.getenv("RCON_PORT"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD")


class Whitelist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False

    # --------------------------
    # RCON helper
    # --------------------------
    def run_rcon_command(self, command: str) -> str:
        try:
            with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
                resp = mcr.command(command)
                return resp.strip() if resp else "✔ Command executed successfully."
        except Exception as e:
            return f"❌ Error: {e}"

    # --------------------------
    # Slash-Command /whitelist
    # --------------------------
    @app_commands.command(name="whitelist", description="Fügt Spieler zur Whitelist hinzu oder entfernt sie"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove")
    ])
    @app_commands.describe(name="Name des Spielers, der hinzugefügt/entfernt werden soll")
    async def whitelist(self, interaction: discord.Interaction, action: app_commands.Choice[str], name: str):

        # Kanal prüfen
        if interaction.channel.name != CHANNEL_NAME:
            return await interaction.response.send_message(
                f"❌ Dieser Command darf nur im Kanal **#{CHANNEL_NAME}** verwendet werden.",
                ephemeral=True
            )

        # Rollen prüfen
        role_names = [role.name for role in interaction.user.roles]

        if action.value == "add" and "mcPlayer" not in role_names:
            return await interaction.response.send_message(
                "❌ Du benötigst die Rolle **mcPlayer**, um Spieler hinzuzufügen.",
                ephemeral=True
            )

        if action.value == "remove" and "mcAdmin" not in role_names:
            return await interaction.response.send_message(
                "❌ Nur **mcAdmin** darf Spieler entfernen.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=False)

        # RCON Command bauen
        cmd = f"whitelist {action.value} {name}"
        result = self.run_rcon_command(cmd)
        clean_result = result.lower()

        if "already whitelisted" in clean_result:
            return await interaction.followup.send(f"`{name}` is already whitelisted ✔")

        if "not whitelisted" in clean_result:
            return await interaction.followup.send(f"`{name}` is not on the whitelist ❌")

        if action.value == "add" and ("added" in clean_result or "whitelisted" in clean_result):
            return await interaction.followup.send(f"Added `{name}` to the whitelist! ✨")

        if action.value == "remove" and ("removed" in clean_result):
            return await interaction.followup.send(f"Removed `{name}` from the whitelist! ✔")

        await interaction.followup.send(result)

    # --------------------------
    # Automatic guild registration
    # --------------------------
    # async def cog_load(self):
    #     # Register all app commands from this cog to the guild
    #     for attr in self.__class__.__dict__.values():
    #         if isinstance(attr, app_commands.Command):
    #             self.bot.tree.add_command(attr, guild=self.bot.guild)


# --------------------------
# Setup
# --------------------------
#async def setup(bot: commands.Bot) -> None:
 #   await bot.add_cog(Whitelist(bot))

# ======================================================
# SETUP
# ======================================================
async def setup(bot: commands.Bot):
    cog = Whitelist(bot)
    await bot.add_cog(cog)
    # Explicitly add commands to guild tree
    bot.tree.add_command(cog.whitelist, guild=bot.guild)