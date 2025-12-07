import discord
from discord.ext import commands
from discord import app_commands


class Infos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------
    # /map
    # --------------------------
    # @app_commands.command(name="map", description="Öffnet die Minecraft Dynmap.")
    # async def map_cmd(self, interaction: discord.Interaction):

    #     button = discord.ui.Button(
    #         label="🗺️ Karte Öffnen",
    #         url="http://mc.Murmelbahn1337.de:8100/",
    #         style=discord.ButtonStyle.link
    #     )

    #     view = discord.ui.View()
    #     view.add_item(button)

    #     await interaction.response.send_message(
    #         "Hier ist die Kegelbahn Minecraft Map 🌍",
    #         view=view
    #     )

     # --------------------------
    # /modrinth
    # --------------------------
    @app_commands.command(name="map", description="Öffnet die Minecraft Dynmap.")
    async def map_cmd(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🌍 Kegelbahn Minecraft Map 🌍",
            description="[🗺️ Karte Öffnen 🗺️](http://mc.Murmelbahn1337.de:8100/)",
            color=discord.Color.green()
        )
        embed.set_footer(text="Bereitgestellt vom Copper Golem")

        await interaction.response.send_message(embed=embed)



    # --------------------------
    # /modrinth
    # --------------------------
    @app_commands.command(name="modrinth", description="Zeigt den Modrinth Modpack Download.")
    async def modrinth_cmd(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="📦 Modrinth Modpack 📦",
            description="[📦 Modpack Download 📦](https://modrinth.com)",
            color=discord.Color.green()
        )
        embed.set_footer(text="Bereitgestellt vom Copper Golem")

        await interaction.response.send_message(embed=embed)

    # --------------------------
    # /ip
    # --------------------------
    @app_commands.command(name="ip", description="Zeigt die Murmelbahn Server IP")
    async def ip_cmd(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🌐 MURMELBAHN SERVER IP 🌐",
            description="**`mc.Murmelbahn1337.de`**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Bereitgestellt vom Copper Golem")

        await interaction.response.send_message(embed=embed)

    # --------------------------
    # /help
    # --------------------------
    @app_commands.command(name="help", description="Zeigt alle verfügbaren Commands.")
    async def help_cmd(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="Verfügbare Commands 📜",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🖥️ Server",
            value=(
                "`/wake`\n"
                "`/backup`\n"
                "`/status`\n"
                "`/players`"
            ),
            inline=True
        )

        embed.add_field(
            name="👤 Whitelist",
            value="`/whitelist add <NAME>`",
            inline=True
        )

        embed.add_field(
            name="🔗 Links",
            value="`/modrinth`\n`/map`",
            inline=False
        )

        embed.set_footer(text="Bereitgestellt vom Copper Golem")

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    cog = Infos(bot)
    await bot.add_cog(cog)
    # Explicitly add commands to guild tree
    bot.tree.add_command(cog.map_cmd, guild=bot.guild)
    bot.tree.add_command(cog.help_cmd, guild=bot.guild)
    bot.tree.add_command(cog.ip_cmd, guild=bot.guild)
    bot.tree.add_command(cog.modrinth_cmd, guild=bot.guild)