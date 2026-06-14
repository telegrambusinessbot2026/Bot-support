import discord

from config import DISCORD_GUILD_ID, RULE_CHANNEL_NAMES
from database import get_config, get_telegram_user_by_channel, save_rules
from bridge import ensure_rules_channels


dc_client = discord.Client(intents=discord.Intents.default() | discord.Intents(message_content=True, members=True))

_primary_guild = None
_rules_channel_map = {}
_discord_ready = False
_tg_bot = None


def get_guild():
    return _primary_guild


def get_rules_channel_map():
    return _rules_channel_map


def set_tg_bot(bot):
    global _tg_bot
    _tg_bot = bot


def is_discord_ready() -> bool:
    return _discord_ready


async def language_for_rules_channel(channel_id: int):
    for language in RULE_CHANNEL_NAMES:
        stored = await get_config(f"rules_channel_{language}_id")
        if stored and int(stored) == channel_id:
            return language
    for language, ch in _rules_channel_map.items():
        if ch.id == channel_id:
            return language
    return None


async def sync_rules_from_channel(channel: discord.TextChannel, language: str):
    parts = []
    async for msg in channel.history(limit=50, oldest_first=True):
        if msg.author.bot and msg.content.startswith("**Rules channel"):
            continue
        text = (msg.content or "").strip()
        if text:
            parts.append(text)
    content = "\n\n".join(parts).strip()
    if content:
        await save_rules(language, content)


async def sync_all_rules_channels():
    for language, channel in _rules_channel_map.items():
        await sync_rules_from_channel(channel, language)


@dc_client.event
async def on_ready():
    global _primary_guild, _rules_channel_map, _discord_ready
    print(f"Kanthari Command | Discord logged in as {dc_client.user}")

    guild = dc_client.get_guild(DISCORD_GUILD_ID) if DISCORD_GUILD_ID else None
    if not guild and dc_client.guilds:
        guild = dc_client.guilds[0]
    _primary_guild = guild

    if guild:
        _rules_channel_map = await ensure_rules_channels(dc_client, guild)
        await sync_all_rules_channels()
        print(f"Rules channels ready: {list(_rules_channel_map.keys())}")

    _discord_ready = True


@dc_client.event
async def on_message(message: discord.Message):
    if message.author == dc_client.user:
        return

    language = await language_for_rules_channel(message.channel.id)
    if language:
        if not message.author.bot:
            await sync_rules_from_channel(message.channel, language)
        return

    mapping = await get_telegram_user_by_channel(message.channel.id)
    if not mapping or not _tg_bot:
        return

    tg_user_id, _channel_type = mapping
    if message.author.bot:
        return

    from bridge import forward_discord_to_telegram

    await forward_discord_to_telegram(message, tg_user_id, _tg_bot)


@dc_client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    language = await language_for_rules_channel(after.channel.id)
    if language and not after.author.bot:
        await sync_rules_from_channel(after.channel, language)
