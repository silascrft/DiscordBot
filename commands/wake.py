# commands/wake.py

import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from utils.wake_utils import power_on_server, is_server_online

load_dotenv()
GUILD_ID = int(os.getenv("GUILD_ID"))


class Wake(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="wake",
        description="Startet den Minecraft-Server über GPIO oder testweise."
    )
    async def wake(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        if is_server_online():
            return await interaction.followup.send("🟢 Der Server läuft bereits!")

        result = power_on_server()

        await interaction.followup.send(f"⚡ {result}")

    # async def cog_load(self):
    #     # Automatisch alle App-Commands des Cogs zur Guild hinzufügen
    #     for attr in self.__class__.__dict__.values():
    #         if isinstance(attr, app_commands.Command):
    #             self.bot.tree.add_command(attr, guild=self.bot.guild)




# async def setup(bot: commands.Bot):
#     await bot.add_cog(Wake(bot))


# ------------------------- Cog Setup -------------------------
async def setup(bot: commands.Bot):
    cog = Wake(bot)
    await bot.add_cog(cog)

    guild = discord.Object(id=GUILD_ID)
    bot.tree.add_command(cog.wake, guild=guild)