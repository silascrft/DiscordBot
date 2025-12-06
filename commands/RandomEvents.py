# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
import os
from dotenv import load_dotenv

GUILD_ID = int(os.getenv("GUILD_ID"))

class RandomEvents(commands.Cog):
    """Cog fÃ¼r zufÃ¤llige Events wie Top/Bottom oder MÃ¼nzwurf."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # AntwortmÃ¶glichkeiten + Wahrscheinlichkeiten
        self.responses = {
            "top_or_bottom": [
                ("top", 0.45),
                ("bottom", 0.45),
                ("both", 0.10),
            ],
            "kopf_oder_zahl": [
                ("Kopf", 0.50),
                ("Zahl", 0.50),
            ],
        }

    # ================================
    # Helper: Weighted Random
    # ================================
    def get_weighted_random(self, entries):
        texts = [text for text, _ in entries]
        weights = [weight for _, weight in entries]
        return random.choices(texts, weights=weights, k=1)[0]

    # ================================
    # /top_or_bottom
    # ================================
    @app_commands.command(
        name="top_or_bottom",
        description="WÃ¤hlt zufÃ¤llig top, bottom oder both"
    )
    async def top_or_bottom_cmd(self, interaction: discord.Interaction):
        result = self.get_weighted_random(self.responses["top_or_bottom"])
        await interaction.response.send_message(f"ðŸŽ² Ergebnis: **{result}**")

    # ================================
    # /kopf_oder_zahl
    # ================================
    @app_commands.command(
        name="kopf_oder_zahl",
        description="Wirft eine MÃ¼nze"
    )
    async def kopf_oder_zahl_cmd(self, interaction: discord.Interaction):
        result = self.get_weighted_random(self.responses["kopf_oder_zahl"])
        await interaction.response.send_message(f"ðŸª™ Ergebnis: **{result}**")


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
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RandomEvents(bot))





