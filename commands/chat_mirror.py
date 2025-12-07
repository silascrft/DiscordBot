# chat_mirror_ssh_tail_subprocess_deaths.py
import discord
from discord.ext import commands
import asyncio
import re
from mcrcon import MCRcon
import shlex
from colorama import Back, Fore, Style
import time


class ChatMirror(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # ===================== KONFIG =====================
        self.MC_HOST = "192.168.188.150"
        self.MC_SSH_USER = "minecraft"
        self.LOG_FILE = "/home/Minecraft/minecraft1/data/logs/latest.log"
        self.DISCORD_CHANNEL_ID = 1443363440021475410
        self.MC_RCON_PASSWORD = "passwort1"
        self.MC_RCON_PORT = 25575

        # Starte Log-Task
        self.bot.loop.create_task(self.stream_minecraft_log())

    # ================= Minecraft ? Discord =================
    async def stream_minecraft_log(self):
        prfx = (Back.BLACK + Fore.GREEN + time.strftime("%H:%M:%S", time.gmtime()) + Back.RESET + Fore.WHITE + Style.BRIGHT)

        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.DISCORD_CHANNEL_ID)
        if not channel:
            print("[DEBUG] Discord Channel nicht gefunden")
            return

        ssh_command = f"ssh {self.MC_SSH_USER}@{self.MC_HOST} tail -n 0 -F {shlex.quote(self.LOG_FILE)}"
        #print(f"[Starte Subprocess: {ssh_command}")
        print(prfx + " Starte Subprocess für Chat-Mirror " + Fore.YELLOW + ssh_command)

        proc = await asyncio.create_subprocess_shell(
            ssh_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async for line_bytes in proc.stdout:
            line = line_bytes.decode(errors="ignore").strip()
            if not line:
                continue
            print("[DEBUG] Log-Zeile:", line)

            # ================= Chat-Nachrichten =================
            chat_match = re.search(r"\[.*\]: <([^>]+)> (.*)", line)
            if chat_match:
                player = chat_match.group(1)
                msg = chat_match.group(2)
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
                await channel.send(f"☠️ **Death:** {cleaned}")
                continue

            # ================= Optional: Kicks / Disconnects =================
#            kick_match = re.search(r"lost connection: (.+)", line)
#            if kick_match:
#                reason = kick_match.group(1)
#                await channel.send(f"**Kicked/Disconnect:** {reason}")
#                continue

            # ================= Player Join =================
            join_match = re.search(r": ([A-Za-z0-9_]+) joined the game", line)
            if join_match:
                player = join_match.group(1)
                await channel.send(f"🟩 **Join:** `{player}` hat den Server betreten.")
                continue

            # ================= Player Leave =================
            leave_match = re.search(r": ([A-Za-z0-9_]+) left the game", line)
            if leave_match:
                player = leave_match.group(1)
                await channel.send(f"🟥 **Leave:** `{player}` hat den Server verlassen.")
                continue

            # ================= Lost Connection / Disconnect =================
#            disconnect_match = re.search(r": ([A-Za-z0-9_]+) lost connection: (.+)", line)
#            if disconnect_match:
#                player = disconnect_match.group(1)
#                reason = disconnect_match.group(2)
#                await channel.send(f"âš ï¸ **Disconnect:** `{player}` â€“ {reason}")
#                continue



            # ================= Optional: Advancements =================
            adv_match = re.search(r"has made the advancement \[(.+)\]", line)
            if adv_match:
                adv = adv_match.group(1)
                await channel.send(f"**Advancement:** {adv}")

        async for err_bytes in proc.stderr:
            err = err_bytes.decode(errors="ignore").strip()
            print("[DEBUG][stderr]", err)

    # ================= Discord ? Minecraft =================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if message.channel.id != self.DISCORD_CHANNEL_ID:
            return

        mc_msg = f"[Discord] {message.author.name}: {message.content}"

        try:
            with MCRcon(self.MC_HOST, self.MC_RCON_PASSWORD, port=self.MC_RCON_PORT) as rcon:

                #rcon.command(f"say {mc_msg}")
                safe_msg = mc_msg.replace('"', "'")
                tellraw_cmd = f'tellraw @a ["",{{"text":"{safe_msg}","color":"white"}}]'
                rcon.command(tellraw_cmd)
        except Exception as e:
            await message.channel.send(f"?? Minecraft Fehler: `{e}`")

    # ================= Discord Commands ? Minecraft =================
    @commands.command(name="mc")
    async def minecraft_command(self, ctx, *, cmd: str):
        """FÃ¼hrt einen Minecraft Befehl Ã¼ber RCON aus."""
        try:
            with MCRcon(self.MC_HOST, self.MC_RCON_PASSWORD, port=self.MC_RCON_PORT) as rcon:
                output = rcon.command(cmd)
            if not output:
                output = "(kein Output)"
            await ctx.send(f"?? **MC Output:**\n```\n{output}\n```")
        except Exception as e:
            await ctx.send(f"?? Fehler: `{e}`")


async def setup(bot):
    await bot.add_cog(ChatMirror(bot))


async def setup(bot: commands.Bot):
    cog = ChatMirror(bot)
    await bot.add_cog(cog)
    # Explicitly add commands to guild tree
    #bot.tree.add_command(cog.server_cmd, guild=bot.guild)