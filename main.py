import discord
from discord.ext import commands
from colorama import Back, Fore, Style
import time
import json
import platform
import os
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))


class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('.'), intents=discord.Intents().all())
        self.coglist = ["commands.AutoShutdown", "commands.fun", "commands.wake","commands.RandomEvents", "commands.whitelist", "commands.misc", "commands.McStats", "commands.infos", "commands.chat_mirror", "commands.backup"]
        self.guild = discord.Object(id=GUILD_ID)

    async def setup_hook(self):
        prfx = (Back.BLACK + Fore.GREEN + time.strftime("%H:%M:%S", time.gmtime()) + Back.RESET + Fore.WHITE + Style.BRIGHT)

        #Clear guild commands first
        self.tree.clear_commands(guild=self.guild)
        print(prfx + f" Cleared all guild commands for {Fore.YELLOW}{GUILD_ID}{Fore.WHITE}")

        #Load all cogs (commands are now registered)
        for ext in self.coglist:
            await self.load_extension(ext)
            print(prfx + f" Loaded cog {Fore.YELLOW}{ext}{Fore.WHITE}")

        #Sync guild commands to Discord
        await self.tree.sync(guild=self.guild)
        print(prfx + f" Guild commands synced for {Fore.YELLOW}{GUILD_ID}{Fore.WHITE}")


    async def on_ready(self):
        prfx = (Back.BLACK + Fore.GREEN + time.strftime("%H:%M:%S", time.gmtime()) + Back.RESET + Fore.WHITE + Style.BRIGHT)
        print(prfx + " Logged in as " + Fore.YELLOW + self.user.name)
        print(prfx + " Bot ID " + Fore.YELLOW + str(self.user.id))
        print(prfx + " Discord Version " + Fore.YELLOW + discord.__version__)
        print(prfx + " Python Version " + Fore.YELLOW + str(platform.python_version()))
        #synced = await self.tree.sync()
        commands_list = self.tree.get_commands(guild=self.guild)
        print(prfx + f"Registered guild commands: {[cmd.name for cmd in commands_list]}")


        

client = Client()

client.run(TOKEN)
