# commands/fun.py
import discord
from discord.ext import commands
from discord import app_commands

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hello", description="Sagt Hallo!")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hi there!")

    @app_commands.command(name="printer", description="Sendet eine Nachricht zurück.")
    async def printer(self, interaction: discord.Interaction, text: str):
        await interaction.response.send_message(text)

    # async def cog_load(self):
    #     # Automatisch alle App-Commands des Cogs zur Guild hinzufügen
    #     for attr in self.__class__.__dict__.values():
    #         if isinstance(attr, app_commands.Command):
    #             self.bot.tree.add_command(attr, guild=self.bot.guild)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Fun(client))
