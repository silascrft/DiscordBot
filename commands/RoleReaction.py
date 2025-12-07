import discord
from discord.ext import commands
from dotenv import load_dotenv
import os


load_dotenv()
MessageID = int(os.getenv("RoleReact_MessageID"))
ChannelID = int(os.getenv("RoleReact_ChannelID"))
RoleReact_Role = os.getenv("RoleReact_Role")
if RoleReact_Role != "@everyone":
    RoleReact_Role = int(RoleReact_Role)



class RoleReaction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # === KONFIGURATION ===
        self.TARGET_MESSAGE_ID = MessageID  # ID der Nachricht, auf der reagiert wird
        self.CHANNEL_ID = ChannelID         # ID des Channels, in dem die Nachricht ist

        # Emoji -> Role-ID Mapping
        self.EMOJI_ROLE_MAPPING = {
            "⛏️": 1442948328617935059,  # Beispielrolle 1
#            "🚬": 1447243553544733015,  # Beispielrolle 2
        }

        # Optional: Nur Benutzer mit einer bestimmten Rolle dürfen reagieren
        self.ALLOWED_ROLE = "@everyone"  # nur Mitglieder mit dieser Rolle können Rollen bekommen

    # === Emoji automatisch hinzufügen, wenn Bot ready ist ===
    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if channel is None:
            print(f"RoleReaction: Kanal {self.CHANNEL_ID} nicht gefunden!")
            return
        try:
            message = await channel.fetch_message(self.TARGET_MESSAGE_ID)
        except discord.NotFound:
            print(f"RoleReaction: Nachricht {self.TARGET_MESSAGE_ID} nicht gefunden!")
            return
        except discord.Forbidden:
            print("RoleReaction: Keine Berechtigung, Nachricht abzurufen!")
            return

        for emoji in self.EMOJI_ROLE_MAPPING.keys():
            if emoji not in [str(r.emoji) for r in message.reactions]:
                await message.add_reaction(emoji)

    # === Rollen vergeben, wenn User reagiert ===
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.TARGET_MESSAGE_ID:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        # Berechtigung check
        if self.ALLOWED_ROLE not in [role.name for role in member.roles]:
            # Entfernt unerlaubte Reaktionen
            channel = guild.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(payload.emoji, member)
            return

        role_id = self.EMOJI_ROLE_MAPPING.get(str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role not in member.roles:
                await member.add_roles(role)
        else:
            # Entfernt alle nicht erlaubten Reaktionen
            channel = guild.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(payload.emoji, member)

    # === Optional: Rollen entfernen, wenn Reaction entfernt wird ===
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.TARGET_MESSAGE_ID:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        role_id = self.EMOJI_ROLE_MAPPING.get(str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role in member.roles:
                await member.remove_roles(role)

# === SETUP ===
async def setup(bot: commands.Bot):
    cog = RoleReaction(bot)
    await bot.add_cog(cog)
