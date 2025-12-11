import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
from mcrcon import MCRcon
import shlex
import socket

class ChatMirror(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # ===================== KONFIG =====================
        self.MC_HOST = "192.168.188.150"
        self.MC_SSH_USER = "minecraft"
        self.LOG_FILE = "/home/Minecraft/minecraft1/data/logs/latest.log"
        self.DISCORD_CHANNEL_ID = 1443363440021475410
        self.MC_RCON_PASSWORD = "passwort1"
        self.MC_RCON_PORT = 25575

        self.proc = None
        self.mirror_task = self.bot.loop.create_task(self.chat_mirror_loop())

    # ===================== Helfer =====================
    async def is_server_online(self, host, port=25565, timeout=3):
        try:
            with socket.create_connection((host, port), timeout):
                return True
        except OSError:
            return False

    async def stop_subprocess(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.proc.kill()
            self.proc = None

    # ===================== Subprozess-Stream =====================
    async def stream_subprocess(self):
        channel = self.bot.get_channel(self.DISCORD_CHANNEL_ID)
        ssh_command = f"ssh {self.MC_SSH_USER}@{self.MC_HOST} tail -n 0 -F {shlex.quote(self.LOG_FILE)}"
        try:
            self.proc = await asyncio.create_subprocess_shell(
                ssh_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def read_stdout():
                async for line_bytes in self.proc.stdout:
                    line = line_bytes.decode(errors="ignore").strip()
                    if not line:
                        continue

                    # ================= Chat Messages =================
                    chat_match = re.search(r"\[.*\]: <([^>]+)> (.*)", line)
                    if chat_match:
                        player = chat_match.group(1)
                        msg = chat_match.group(2)
                        if channel:
                            await channel.send(f"**{player}**: {msg}")
                        continue

                    # ================= Death Messages =================
                    death_patterns = [
                        r"was slain by",
                        r"fell from",
                        r"fell off",
                        r"fell out of the world",
                        r"tried to swim in lava",
                        r"was blown up",
                        r"was killed by",
                        r"burned to death",
                        r"drowned",
                        r".+ died",
                        r"was burned to a crisp while fighting"
                    ]
                    if any(re.search(pat, line) for pat in death_patterns):
                        cleaned = re.sub(r".*INFO\]: ", "", line)
                        if channel:
                            await channel.send(f"☠️ **Death:** {cleaned}")
                        continue

                    # ================= Player Join =================
                    join_match = re.search(r": ([A-Za-z0-9_]+) joined the game", line)
                    if join_match and channel:
                        player = join_match.group(1)
                        await channel.send(f"🟩 **Join:** `{player}` hat den Server betreten.")
                        continue

                    # ================= Player Leave =================
                    leave_match = re.search(r": ([A-Za-z0-9_]+) left the game", line)
                    if leave_match and channel:
                        player = leave_match.group(1)
                        await channel.send(f"🟥 **Leave:** `{player}` hat den Server verlassen.")
                        continue

                    # ================= Advancements =================
                    adv_match = re.search(r"has made the advancement \[(.+)\]", line)
                    if adv_match and channel:
                        adv = adv_match.group(1)
                        await channel.send(f"**Advancement:** {adv}")

            async def read_stderr():
                async for line_bytes in self.proc.stderr:
                    line = line_bytes.decode(errors="ignore").strip()
                    if line:
                        print(f"[WARN][stderr] {line}")
                        # Kritische SSH-Fehler → Subprozess stoppen + Pause
                        if "Permission denied" in line or "Could not resolve hostname" in line:
                            await self.stop_subprocess()
                            print("[INFO] Warte 5 Minuten bevor neuer SSH-Versuch...")
                            await asyncio.sleep(300)
                            break

            # Parallel stdout/stderr lesen
            await asyncio.gather(read_stdout(), read_stderr())

        except Exception as e:
            print(f"[ERROR] SSH Subprozess konnte nicht gestartet werden: {e}")
            await self.stop_subprocess()
            await asyncio.sleep(300)

    # ===================== Chat-Mirror Loop =====================
    async def chat_mirror_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if not await self.is_server_online(self.MC_HOST):
                print("[INFO] Minecraft Server offline. Prüfe in 5 Minuten erneut.")
                await asyncio.sleep(300)
                continue

            await self.stop_subprocess()
            print("[INFO] Starte Chat-Mirror Subprozess")
            await self.stream_subprocess()
            await asyncio.sleep(5)

    # ===================== Discord -> Minecraft =====================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if message.channel.id != self.DISCORD_CHANNEL_ID:
            return

        mc_msg = f"[Discord] {message.author.name}: {message.content}"
        try:
            with MCRcon(self.MC_HOST, self.MC_RCON_PASSWORD, port=self.MC_RCON_PORT) as rcon:
                safe_msg = mc_msg.replace('"', "'")
                tellraw_cmd = f'tellraw @a ["",{{"text":"{safe_msg}","color":"white"}}]'
                rcon.command(tellraw_cmd)
        except Exception as e:
            await message.channel.send(f"?? Minecraft Fehler: `{e}`")

    # ===================== App-Command /chatsync reload =====================
    @app_commands.command(
        name="chatsync",
        description="Chat-Mirror Subprozess verwalten"
    )
    @app_commands.describe(action="Aktion")
    @app_commands.choices(action=[
        app_commands.Choice(name="reload", value="reload")
    ])
    async def chatsync_reload(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        if action.value != "reload":
            await interaction.response.send_message("Ungültige Auswahl.", ephemeral=True)
            return

        await self.stop_subprocess()

        # Starte Subprozess als Task im Hintergrund
        async def start_mirror():
            if await self.is_server_online(self.MC_HOST):
                await self.stream_subprocess()

        self.bot.loop.create_task(start_mirror())

        # Sofortige Rückmeldung an Discord
        await interaction.response.send_message(
            "Chat-Mirror Subprozess neu gestartet. Verbindungsaufbau erfolgt automatisch.", ephemeral=True
        )



# ===================== Setup =====================
async def setup(bot: commands.Bot) -> None:
    cog = ChatMirror(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.chatsync_reload, guild=bot.guild)
