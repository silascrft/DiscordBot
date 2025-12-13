import discord
from discord.ext import commands
from colorama import Fore
import platform
import os
import logging
from dotenv import load_dotenv
from config import COMMANDS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('.'), intents=discord.Intents().all())
        self.coglist = COMMANDS
        self.guild = discord.Object(id=GUILD_ID)

    async def setup_hook(self):
        self._clear_guild_commands()
        await self._load_cogs()
        await self._sync_guild_commands()
    
    async def on_ready(self):
        prfx = self._retrieveTimestampWithStyles()
        _log_bot_info()

        commands_list = self.tree.get_commands(guild=self.guild)
        print(prfx + f"Registered guild commands: {[cmd.name for cmd in commands_list]}")

    async def _sync_guild_commands(self):
        await self.tree.sync(guild=self.guild)
        logger.info(f"Guild commands synced for {Fore.YELLOW}{GUILD_ID}{Fore.WHITE}")

    def _clear_guild_commands(self):
        self.tree.clear_commands(guild=self.guild)
        logger.info(f"Cleared all guild commands for {Fore.YELLOW}{GUILD_ID}{Fore.WHITE}")

    async def _load_cogs(self):
        for ext in self.coglist:
            await self.load_extension(ext)
            logger.info(f"Loaded cog {Fore.YELLOW}{ext}{Fore.WHITE}")

def _log_bot_info(client: Client):
    logger.info(f"Logged in as {client.user.name}")
    logger.info(f"Bot ID: {client.user.id}")
    logger.info(f"Discord Version: {discord.__version__}")
    logger.info(f"Python Version: {platform.python_version()}")

client = Client()
client.run(TOKEN)
