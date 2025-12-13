# McStats.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import shlex
import os
from dotenv import load_dotenv

# ------------------------- Load environment variables -------------------------
load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))
MC_HOST = os.getenv("SERVER_IP", "127.0.0.1")
MC_SSH_USER = os.getenv("MC_SERVER_USER", "minecraft")
STATS_PATH = os.getenv("MC_STATS_PATH", f"/home/Minecraft/minecraft1/data/world/stats/")
USERCACHE_PATH = os.getenv("MC_USERCACHE_PATH", f"/home/Minecraft/minecraft1/data/usercache.json")


# ------------------------- Cog -------------------------
class MCStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.MC_HOST = MC_HOST
        self.MC_SSH_USER = MC_SSH_USER
        self.STATS_PATH = STATS_PATH
        self.USERCACHE_PATH = USERCACHE_PATH

        self.valid_stats = [
            "distance_traveled", "block_broken", "block_placed", "damage_done",
            "damage_taken", "deaths", "player_kills", "entity_kills", "playtime"
        ]

    # ------------------------- Safe SSH JSON loader -------------------------
    async def ssh_cat_json(self, path):
        """
        Fetch JSON from Minecraft server over SSH safely.
        Uses -T to disable TTY allocation and BatchMode=yes to prevent hanging.
        """
        cmd = (
        f"ssh -o BatchMode=yes -T -n "
        f"-o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null "
        f"{self.MC_SSH_USER}@{self.MC_HOST} cat {shlex.quote(path)}"
        )
        print(f"[DEBUG SSH] Running: {cmd}")  # debug print

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        output_lines = []

        try:
            async for line_bytes in proc.stdout:
                line = line_bytes.decode(errors="ignore").strip()
                if line:
                    output_lines.append(line)

            async for err_bytes in proc.stderr:
                err = err_bytes.decode(errors="ignore").strip()
                if err:
                    print(f"[SSH ERROR] {err}")

            await proc.wait()

        except Exception as e:
            print(f"[SSH Exception] {e}")
            return None

        if not output_lines:
            return None

        try:
            return json.loads("\n".join(output_lines))
        except Exception as e:
            print(f"[JSON ERROR] {e}")
            return None

    # ------------------------- UUID & Stats -------------------------
    async def get_uuid(self, player_name):
        users = await self.ssh_cat_json(self.USERCACHE_PATH)
        if not users:
            return None
        for user in users:
            if user["name"].lower() == player_name.lower():
                return user["uuid"]
        return None

    async def fetch_stats(self, uuid):
        path = os.path.join(self.STATS_PATH, f"{uuid}.json")
        return await self.ssh_cat_json(path)

    # ------------------------- /stats command -------------------------
    @app_commands.command(name="stats", description="Zeigt Minecraft Stats eines Spielers")
    async def stats(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        try:
            print(f"[DEBUG] Getting UUID for {player}")
            uuid = await self.get_uuid(player)
            print(f"[DEBUG] UUID: {uuid}")

            if not uuid:
                return await interaction.followup.send(f"Spieler `{player}` nicht gefunden.")

            data = await self.fetch_stats(uuid)
            print(f"[DEBUG] Stats data: {data}")

            if not data or "stats" not in data:
                return await interaction.followup.send(f"Keine Stats für `{player}` gefunden.")

            stats = data["stats"]
            embed = discord.Embed(title=f"Stats von {player}", color=discord.Color.green())
            custom = stats.get("minecraft:custom", {})

            # Distance travelled
            distance_keys = [
                "walk_one_cm", "walk_under_water_one_cm", "walk_on_water_one_cm",
                "swim_one_cm", "fly_one_cm", "aviate_one_cm",
                "climb_one_cm", "crouch_one_cm", "sprint_one_cm",
                "fall_one_cm", "horse_one_cm", "pig_one_cm",
                "boat_one_cm", "minecart_one_cm", "strider_one_cm",
                "happy_ghast_one_cm"
            ]
            total_distance_cm = sum(custom.get(f"minecraft:{k}", 0) for k in distance_keys)
            distance_km = round(total_distance_cm / 100000, 2)
            embed.add_field(name="Distance Traveled", value=f"{distance_km:,} km  ✈️", inline=True)

            mined = stats.get("minecraft:mined", {})
            embed.add_field(name="Blocks Broken", value=f"{sum(mined.values()):,} ⛏️", inline=True)

            used = stats.get("minecraft:used", {})
            embed.add_field(name="Blocks Placed", value=f"{sum(used.values()):,} 🦺", inline=True)

            # Damage
            def round_half(x): return round(x*2)/2
            damage_done = round_half(custom.get("minecraft:damage_dealt", 0)/20)
            damage_taken = round_half(custom.get("minecraft:damage_taken", 0)/20)

            embed.add_field(name="Damage Done", value=f"{damage_done:.1f} 🗡️", inline=True)
            embed.add_field(name="Damage Taken", value=f"{damage_taken:.1f} 💔", inline=True)

            embed.add_field(name="Deaths", value=f"{custom.get('minecraft:deaths', 0):,}🪦", inline=True)
            embed.add_field(name="Player Kills", value=f"{custom.get('minecraft:player_kills', 0):,} ⚔️", inline=True)

            killed = stats.get("minecraft:killed", {})
            entity_kills = sum(v for k, v in killed.items() if k != "minecraft:player")
            embed.add_field(name="Entity Kills", value=f"{entity_kills:,}", inline=True)

            playtime_hours = round(custom.get("minecraft:play_time", 0)/20/60/60, 2)
            embed.add_field(name="Playtime", value=f"{playtime_hours:,} h ⌛", inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Fehler beim Abrufen der Stats: `{e}`")

    # ------------------------- /top command -------------------------
    @app_commands.command(name="top", description="Zeigt Top Spieler für eine Kategorie")
    @app_commands.describe(number="Anzahl der Spieler", stat_type="Statistiktyp")
    @app_commands.choices(
        stat_type=[app_commands.Choice(name=s.replace("_", " ").title(), value=s) 
                for s in [
                    "distance_traveled", "block_broken", "block_placed",
                    "damage_done", "damage_taken", "deaths", "player_kills",
                    "entity_kills", "playtime"
                ]]
    )
    async def top(self, interaction: discord.Interaction, number: int, stat_type: app_commands.Choice[str]):
        await interaction.response.defer()
        try:
            stat_type_lower = stat_type.value

            # Liste der Dateien über SSH
            cmd = (
                f"ssh -o BatchMode=yes -T -n "
                f"-o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null "
                f"{self.MC_SSH_USER}@{self.MC_HOST} ls {shlex.quote(self.STATS_PATH)}"
            )

            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            files = []
            async for line_bytes in proc.stdout:
                line = line_bytes.decode(errors="ignore").strip()
                if line:
                    files.append(line)
            async for err_bytes in proc.stderr:
                err = err_bytes.decode(errors="ignore").strip()
                if err:
                    print(f"[SSH ERROR] {err}")

            await proc.wait()
            files = [f for f in files if f.endswith(".json")]

            users = await self.ssh_cat_json(self.USERCACHE_PATH)
            uuid_to_name = {u["uuid"]: u["name"] for u in users} if users else {}

            player_stats = []

            for f in files:
                uuid = f.replace(".json", "")
                data = await self.fetch_stats(uuid)
                if not data or "stats" not in data:
                    continue

                stats = data["stats"]
                custom = stats.get("minecraft:custom", {})
                mined = stats.get("minecraft:mined", {})
                used = stats.get("minecraft:used", {})
                killed = stats.get("minecraft:killed", {})

                value = 0
                if stat_type_lower == "distance_traveled":
                    distance_keys = [
                        "walk_one_cm", "walk_under_water_one_cm", "walk_on_water_one_cm",
                        "swim_one_cm", "fly_one_cm", "aviate_one_cm",
                        "climb_one_cm", "crouch_one_cm", "sprint_one_cm",
                        "fall_one_cm", "horse_one_cm", "pig_one_cm",
                        "boat_one_cm", "minecart_one_cm", "strider_one_cm",
                        "happy_ghast_one_cm"
                    ]
                    value = sum(custom.get(f"minecraft:{k}", 0) for k in distance_keys) / 100000
                elif stat_type_lower == "block_broken":
                    value = sum(mined.values())
                elif stat_type_lower == "block_placed":
                    value = sum(used.values())
                elif stat_type_lower == "damage_done":
                    value = round(custom.get("minecraft:damage_dealt", 0) / 20 * 2) / 2
                elif stat_type_lower == "damage_taken":
                    value = round(custom.get("minecraft:damage_taken", 0) / 20 * 2) / 2
                elif stat_type_lower == "deaths":
                    value = custom.get("minecraft:deaths", 0)
                elif stat_type_lower == "player_kills":
                    value = custom.get("minecraft:player_kills", 0)
                elif stat_type_lower == "entity_kills":
                    value = sum(v for k, v in killed.items() if k != "minecraft:player")
                elif stat_type_lower == "playtime":
                    value = round(custom.get("minecraft:play_time", 0) / 20 / 60 / 60, 2)

                name = uuid_to_name.get(uuid, uuid)
                player_stats.append((name, value))

            top_players = sorted(player_stats, key=lambda x: x[1], reverse=True)[:number]

            # Emojis nur hinter die Überschrift
            emoji_map = {
                "distance_traveled": "✈️",
                "block_broken": "⛏️",
                "block_placed": "🦺",
                "damage_done": "🗡️",
                "damage_taken": "💔",
                "deaths": "🪦",
                "player_kills": "⚔️",
                "entity_kills": "👾",
                "playtime": "⌛"
            }
            title_emoji = emoji_map.get(stat_type_lower, "")
            msg = f"Top {number} Spieler für {stat_type_lower.replace('_', ' ').title()} {title_emoji}\n"

            for i, p in enumerate(top_players):
                if stat_type_lower == "distance_traveled":
                    msg += f"{i+1}. {p[0]} — {p[1]:,.2f} km\n"
                elif stat_type_lower == "playtime":
                    msg += f"{i+1}. {p[0]} — {p[1]:,.2f} h\n"
                else:
                    msg += f"{i+1}. {p[0]} — {p[1]:,}\n"

            await interaction.followup.send(f"```{msg}```")

        except Exception as e:
            await interaction.followup.send(f"Fehler beim Abrufen der Top Stats: `{e}`")



# ------------------------- Cog Setup -------------------------
async def setup(bot: commands.Bot):
    cog = MCStats(bot)
    await bot.add_cog(cog)

    guild = discord.Object(id=GUILD_ID)
    bot.tree.add_command(cog.stats, guild=guild)
    bot.tree.add_command(cog.top, guild=guild)
