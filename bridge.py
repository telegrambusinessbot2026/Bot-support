import io
import re

import discord

from config import (
    ADMIN_CATEGORY_NAME,
    DISCORD_ADMIN_ROLE_ID,
    RULES_CATEGORY_NAME,
    RULE_CHANNEL_NAMES,
    SUPPORT_CATEGORY_NAME,
)
from database import (
    CHANNEL_ADMIN,
    CHANNEL_SUPPORT,
    get_config,
    get_user_channel,
    save_user_channel,
    set_config,
)


def safe_channel_name(user) -> str:
    username = user.username or user.first_name or str(user.id)
    safe = re.sub(r"[^a-z0-9_-]", "-", username.lower())
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe or "user"


def channel_name_for_user(user, channel_type: str) -> str:
    prefix = "support" if channel_type == CHANNEL_SUPPORT else "admin"
    return f"{prefix}-{safe_channel_name(user)}-{user.id}"


async def fetch_discord_channel(dc_client, channel_id):
    if not channel_id:
        return None
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return None
    channel = dc_client.get_channel(channel_id)
    if channel:
        return channel
    try:
        return await dc_client.fetch_channel(channel_id)
    except Exception:
        return None


async def get_or_create_category(dc_client, guild: discord.Guild, name: str, config_key: str):
    stored_id = await get_config(config_key)
    if stored_id:
        channel = await fetch_discord_channel(dc_client, int(stored_id))
        if isinstance(channel, discord.CategoryChannel):
            return channel

    for category in guild.categories:
        if category.name.lower() == name.lower():
            await set_config(config_key, str(category.id))
            return category

    category = await guild.create_category(name)
    await set_config(config_key, str(category.id))
    return category


def private_overwrites(guild: discord.Guild, dc_client: discord.Client):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            attach_files=True,
            embed_links=True,
        ),
    }
    if DISCORD_ADMIN_ROLE_ID:
        role = guild.get_role(DISCORD_ADMIN_ROLE_ID)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                mention_everyone=True,
                attach_files=True,
            )
    return overwrites


async def find_existing_channel(guild: discord.Guild, category_id: int, tg_user_id: int, channel_type: str):
    suffix = f"-{tg_user_id}"
    prefix = "support-" if channel_type == CHANNEL_SUPPORT else "admin-"
    for ch in guild.text_channels:
        if ch.category_id == category_id and ch.name.endswith(suffix) and ch.name.startswith(prefix):
            return ch
    return None


async def ensure_user_channel(dc_client: discord.Client, guild: discord.Guild, user, channel_type: str):
    category_name = SUPPORT_CATEGORY_NAME if channel_type == CHANNEL_SUPPORT else ADMIN_CATEGORY_NAME
    config_key = f"category_{channel_type}_id"
    category = await get_or_create_category(dc_client, guild, category_name, config_key)

    stored_id = await get_user_channel(user.id, channel_type)
    existing = await fetch_discord_channel(dc_client, stored_id) if stored_id else None
    if not existing:
        existing = await find_existing_channel(guild, category.id, user.id, channel_type)

    username = user.username or user.first_name or str(user.id)
    if existing:
        await save_user_channel(user.id, channel_type, username, existing.id)
        return existing, False

    name = channel_name_for_user(user, channel_type)
    overwrites = private_overwrites(guild, dc_client)
    new_channel = await guild.create_text_channel(
        name=name,
        category=category,
        overwrites=overwrites,
        topic=f"Telegram user {username} ({user.id}) — {channel_type}",
    )
    await save_user_channel(user.id, channel_type, username, new_channel.id)

    label = "Support" if channel_type == CHANNEL_SUPPORT else "Admin Application"
    await new_channel.send(
        f"**New {label} channel** for Telegram user `{username}` (ID: `{user.id}`)."
    )
    return new_channel, True


async def ensure_rules_channels(dc_client: discord.Client, guild: discord.Guild):
    category = await get_or_create_category(dc_client, guild, RULES_CATEGORY_NAME, "category_rules_id")
    result = {}

    for language, chan_name in RULE_CHANNEL_NAMES.items():
        config_key = f"rules_channel_{language}_id"
        stored_id = await get_config(config_key)
        channel = await fetch_discord_channel(dc_client, int(stored_id)) if stored_id else None

        if not channel:
            for ch in guild.text_channels:
                if ch.category_id == category.id and ch.name.lower() == chan_name.lower():
                    channel = ch
                    break

        if not channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, read_message_history=True),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    read_message_history=True,
                ),
            }
            if DISCORD_ADMIN_ROLE_ID:
                role = guild.get_role(DISCORD_ADMIN_ROLE_ID)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                    )
            channel = await guild.create_text_channel(
                name=chan_name,
                category=category,
                overwrites=overwrites,
                topic=f"Rules content for {language}. Edit messages here — bot syncs to Telegram.",
            )
            await channel.send(
                f"**Rules channel — {language.title()}**\n"
                f"Admin: rules message idhu post/edit cheythal Telegram users-ku available aavum."
            )

        await set_config(config_key, str(channel.id))
        result[language] = channel

    return result


async def get_tg_file_bytes(tg_bot, file_id):
    file = await tg_bot.get_file(file_id)
    out = io.BytesIO()
    await file.download_to_memory(out)
    out.seek(0)
    return out


def format_discord_mentions(message: discord.Message) -> str:
    text = message.content or ""
    if not message.mentions:
        return text

    for member in message.mentions:
        display = member.display_name or member.name
        text = text.replace(f"<@{member.id}>", f"@{display}")
        text = text.replace(f"<@!{member.id}>", f"@{display}")
    return text


async def forward_discord_to_telegram(message: discord.Message, tg_user_id: int, tg_bot):
    from database import get_telegram_msg, save_message_link

    text_to_send = format_discord_mentions(message)
    if message.author.bot and not text_to_send:
        return

    if not message.author.bot:
        prefix = f"**{message.author.display_name}:** "
        text_to_send = prefix + text_to_send if text_to_send else prefix.rstrip(":")

    reply_to_tg_msg_id = None
    if message.reference and message.reference.message_id:
        reply_info = await get_telegram_msg(message.reference.message_id, message.channel.id)
        if reply_info:
            reply_to_tg_msg_id = reply_info[0]

    sent_tg_msgs = []
    try:
        if message.attachments:
            if len(message.attachments) == 1:
                att = message.attachments[0]
                att_bytes = await att.read()
                common = {
                    "chat_id": tg_user_id,
                    "caption": text_to_send or None,
                    "reply_to_message_id": reply_to_tg_msg_id,
                }
                if att.content_type and att.content_type.startswith("image/"):
                    sent = await tg_bot.send_photo(photo=att_bytes, **common)
                elif att.content_type and att.content_type.startswith("video/"):
                    sent = await tg_bot.send_video(video=att_bytes, **common)
                elif att.content_type and att.content_type.startswith("audio/"):
                    sent = await tg_bot.send_audio(audio=att_bytes, **common)
                else:
                    sent = await tg_bot.send_document(
                        document=att_bytes,
                        filename=att.filename,
                        **common,
                    )
                sent_tg_msgs.append(sent)
            else:
                if text_to_send:
                    sent = await tg_bot.send_message(
                        chat_id=tg_user_id,
                        text=text_to_send,
                        reply_to_message_id=reply_to_tg_msg_id,
                    )
                    sent_tg_msgs.append(sent)
                for att in message.attachments:
                    att_bytes = await att.read()
                    common = {"chat_id": tg_user_id, "reply_to_message_id": reply_to_tg_msg_id}
                    if att.content_type and att.content_type.startswith("image/"):
                        sent = await tg_bot.send_photo(photo=att_bytes, **common)
                    elif att.content_type and att.content_type.startswith("video/"):
                        sent = await tg_bot.send_video(video=att_bytes, **common)
                    elif att.content_type and att.content_type.startswith("audio/"):
                        sent = await tg_bot.send_audio(audio=att_bytes, **common)
                    else:
                        sent = await tg_bot.send_document(
                            document=att_bytes,
                            filename=att.filename,
                            **common,
                        )
                    sent_tg_msgs.append(sent)
        elif text_to_send:
            sent = await tg_bot.send_message(
                chat_id=tg_user_id,
                text=text_to_send,
                reply_to_message_id=reply_to_tg_msg_id,
            )
            sent_tg_msgs.append(sent)

        for tg_msg in sent_tg_msgs:
            await save_message_link(tg_msg.message_id, tg_user_id, message.id, message.channel.id)
    except Exception as e:
        print(f"Failed to forward Discord → Telegram: {e}")
