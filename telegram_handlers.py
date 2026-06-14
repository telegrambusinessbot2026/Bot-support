import discord
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import strings as S
from bridge import ensure_user_channel, get_tg_file_bytes
from config import INTERVIEW_STEPS, RULE_CHANNEL_NAMES
from database import (
    CHANNEL_ADMIN,
    CHANNEL_SUPPORT,
    INTERVIEW_STATUS_COMPLETED,
    INTERVIEW_STATUS_IN_PROGRESS,
    get_active_session,
    get_discord_msg,
    get_interview,
    get_rules,
    save_message_link,
    set_active_session,
    start_interview,
    update_interview,
)
from discord_bot import dc_client, get_guild, get_rules_channel_map, sync_rules_from_channel


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(S.BTN_SUPPORT, callback_data="action:support")],
            [InlineKeyboardButton(S.BTN_ADMIN, callback_data="action:admin")],
            [InlineKeyboardButton(S.BTN_RULES, callback_data="action:rules")],
        ]
    )


def rules_language_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(S.RULES_LANG_LABELS[lang], callback_data=f"rules:{lang}")]
        for lang in RULE_CHANNEL_NAMES
    ]
    rows.append([InlineKeyboardButton(S.BTN_BACK, callback_data="action:menu")])
    return InlineKeyboardMarkup(rows)


async def send_main_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE, text: str = None):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text or S.WELCOME,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_chat.type != "private":
        return
    await send_main_menu(update.effective_chat.id, context)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.from_user:
        return
    await query.answer()

    user = query.from_user
    data = query.data or ""

    if data == "action:menu":
        await query.edit_message_text(S.WELCOME, reply_markup=main_menu_keyboard())
        return

    if data == "action:support":
        await handle_support_action(query, user)
        return

    if data == "action:admin":
        await handle_admin_action(query, user)
        return

    if data == "action:rules":
        await query.edit_message_text(S.RULES_PICK_LANGUAGE, reply_markup=rules_language_keyboard())
        return

    if data.startswith("rules:"):
        language = data.split(":", 1)[1]
        await handle_rules_language(query, language)
        return


async def handle_support_action(query, user):
    guild = get_guild()
    if not guild:
        await query.edit_message_text(S.DISCORD_NOT_READY)
        return

    channel, created = await ensure_user_channel(dc_client, guild, user, CHANNEL_SUPPORT)
    await set_active_session(user.id, CHANNEL_SUPPORT)

    text = S.SUPPORT_READY if created else S.SUPPORT_EXISTING
    await query.edit_message_text(text, reply_markup=main_menu_keyboard())


async def handle_admin_action(query, user):
    guild = get_guild()
    if not guild:
        await query.edit_message_text(S.DISCORD_NOT_READY)
        return

    channel, created = await ensure_user_channel(dc_client, guild, user, CHANNEL_ADMIN)
    await set_active_session(user.id, CHANNEL_ADMIN)

    interview = await get_interview(user.id)
    if not interview:
        await start_interview(user.id)
        first_step = INTERVIEW_STEPS[0]
        await query.edit_message_text(S.INTERVIEW_QUESTIONS[first_step])
        return

    if interview["status"] == INTERVIEW_STATUS_IN_PROGRESS:
        step_key = INTERVIEW_STEPS[min(interview["step"], len(INTERVIEW_STEPS) - 1)]
        await query.edit_message_text(S.INTERVIEW_QUESTIONS[step_key])
        return

    prefix = S.ADMIN_CHANNEL_READY if created else S.ADMIN_CHANNEL_EXISTING
    await query.edit_message_text(prefix, reply_markup=main_menu_keyboard())


async def handle_rules_language(query, language: str):
    content = await get_rules(language)
    if not content.strip():
        rules_map = get_rules_channel_map()
        dc_channel = rules_map.get(language)
        if dc_channel:
            await sync_rules_from_channel(dc_channel, language)
            content = await get_rules(language)

    label = S.RULES_LANG_LABELS.get(language, language.title())
    if not content.strip():
        await query.edit_message_text(S.RULES_EMPTY, reply_markup=rules_language_keyboard())
        return

    body = S.RULES_SENT_PREFIX.format(language=label) + content
    if len(body) > 4000:
        body = body[:3990] + "\n...(truncated)"
    await query.edit_message_text(body, reply_markup=rules_language_keyboard())


async def process_interview_message(update: Update, user, text: str) -> bool:
    interview = await get_interview(user.id)
    if not interview or interview["status"] != INTERVIEW_STATUS_IN_PROGRESS:
        return False

    step_index = interview["step"]
    if step_index >= len(INTERVIEW_STEPS):
        return False

    step_key = INTERVIEW_STEPS[step_index]
    answers = dict(interview["answers"])

    if step_key == "step_age":
        if not text.isdigit() or not (13 <= int(text) <= 100):
            await update.message.reply_text(S.INVALID_AGE)
            return True

    answers[step_key] = text
    next_index = step_index + 1

    if next_index >= len(INTERVIEW_STEPS):
        await update_interview(user.id, next_index, answers, INTERVIEW_STATUS_COMPLETED)
        await update.message.reply_text(S.INTERVIEW_COMPLETE, reply_markup=main_menu_keyboard())
        await send_interview_summary_to_discord(user, answers)
        return True

    await update_interview(user.id, next_index, answers, INTERVIEW_STATUS_IN_PROGRESS)
    next_key = INTERVIEW_STEPS[next_index]
    await update.message.reply_text(S.INTERVIEW_QUESTIONS[next_key])
    return True


async def send_interview_summary_to_discord(user, answers: dict):
    guild = get_guild()
    if not guild:
        return

    channel, _ = await ensure_user_channel(dc_client, guild, user, CHANNEL_ADMIN)
    lines = [
        "**Admin Application Submitted**",
        f"User: `{user.first_name}` (@{user.username or 'N/A'})",
        f"Telegram ID: `{user.id}`",
        "",
    ]
    labels = {
        "step_name": "Full Name",
        "step_age": "Age",
        "step_city": "City/Location",
        "step_telegram": "Telegram Username",
        "step_reason": "Reason",
        "step_experience": "Experience",
    }
    for key in INTERVIEW_STEPS:
        lines.append(f"**{labels[key]}:** {answers.get(key, 'N/A')}")
    await channel.send("\n".join(lines))


async def forward_telegram_to_discord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    msg = update.message

    if msg.text and not msg.text.startswith("/"):
        handled = await process_interview_message(update, user, msg.text.strip())
        if handled:
            return

    active = await get_active_session(user.id)
    if not active:
        await msg.reply_text(S.USE_MENU_FIRST, reply_markup=main_menu_keyboard())
        return

    guild = get_guild()
    if not guild:
        return

    channel, _ = await ensure_user_channel(dc_client, guild, user, active)
    dc_channel = dc_client.get_channel(channel.id) or channel

    content = (msg.text or msg.caption or "").strip()
    reply_to_dc_msg_id = None
    if msg.reply_to_message:
        reply_info = await get_discord_msg(msg.reply_to_message.message_id, user.id)
        if reply_info:
            reply_to_dc_msg_id = reply_info[0]

    files = []
    try:
        if msg.photo:
            photo = msg.photo[-1]
            files.append(
                discord.File(
                    fp=await get_tg_file_bytes(context.bot, photo.file_id),
                    filename=f"image_{photo.file_id}.jpg",
                )
            )
        elif msg.document:
            files.append(
                discord.File(
                    fp=await get_tg_file_bytes(context.bot, msg.document.file_id),
                    filename=msg.document.file_name or f"file_{msg.document.file_id}",
                )
            )
        elif msg.video:
            files.append(
                discord.File(
                    fp=await get_tg_file_bytes(context.bot, msg.video.file_id),
                    filename=msg.video.file_name or f"video_{msg.video.file_id}.mp4",
                )
            )
        elif msg.audio:
            files.append(
                discord.File(
                    fp=await get_tg_file_bytes(context.bot, msg.audio.file_id),
                    filename=msg.audio.file_name or f"audio_{msg.audio.file_id}.mp3",
                )
            )
        elif msg.voice:
            files.append(
                discord.File(
                    fp=await get_tg_file_bytes(context.bot, msg.voice.file_id),
                    filename=f"voice_{msg.voice.file_id}.ogg",
                )
            )
        elif msg.sticker:
            files.append(
                discord.File(
                    fp=await get_tg_file_bytes(context.bot, msg.sticker.file_id),
                    filename=f"sticker_{msg.sticker.file_id}.webp",
                )
            )
    except Exception as e:
        print(f"Telegram media download failed: {e}")

    header = f"**{user.first_name}** (@{user.username or user.id}):\n"
    full_content = header + content if content else header.rstrip(":")

    reference = None
    if reply_to_dc_msg_id:
        reference = discord.MessageReference(
            message_id=reply_to_dc_msg_id,
            channel_id=dc_channel.id,
            fail_if_not_exists=False,
        )

    try:
        sent = await dc_channel.send(content=full_content, files=files, reference=reference)
        await save_message_link(msg.message_id, user.id, sent.id, dc_channel.id)
    except Exception as e:
        print(f"Failed to forward Telegram → Discord: {e}")


def register_telegram_handlers(application):
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, forward_telegram_to_discord))
