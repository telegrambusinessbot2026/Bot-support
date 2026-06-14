import json
from datetime import datetime, timezone

import aiosqlite

DB_NAME = "bridge.db"

CHANNEL_SUPPORT = "support"
CHANNEL_ADMIN = "admin"

INTERVIEW_STATUS_IN_PROGRESS = "in_progress"
INTERVIEW_STATUS_COMPLETED = "completed"

RULE_LANGUAGES = ("english", "malayalam", "hindi", "manglish")


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_channels (
                telegram_user_id INTEGER NOT NULL,
                channel_type TEXT NOT NULL,
                telegram_username TEXT,
                discord_channel_id INTEGER NOT NULL UNIQUE,
                PRIMARY KEY (telegram_user_id, channel_type)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS message_links (
                telegram_message_id INTEGER,
                telegram_chat_id INTEGER,
                discord_message_id INTEGER,
                discord_channel_id INTEGER,
                PRIMARY KEY (telegram_message_id, telegram_chat_id)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                language TEXT PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_interviews (
                telegram_user_id INTEGER PRIMARY KEY,
                step INTEGER NOT NULL DEFAULT 0,
                answers TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'in_progress'
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                telegram_user_id INTEGER PRIMARY KEY,
                active_channel_type TEXT,
                updated_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_links_discord "
            "ON message_links (discord_message_id, discord_channel_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_channels_discord "
            "ON user_channels (discord_channel_id)"
        )
        for lang in RULE_LANGUAGES:
            await db.execute(
                "INSERT OR IGNORE INTO rules (language, content, updated_at) VALUES (?, '', NULL)",
                (lang,),
            )
        await db.commit()


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


async def save_user_channel(tg_user_id: int, channel_type: str, tg_username: str, dc_channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO user_channels
            (telegram_user_id, channel_type, telegram_username, discord_channel_id)
            VALUES (?, ?, ?, ?)
            """,
            (tg_user_id, channel_type, tg_username, dc_channel_id),
        )
        await db.commit()


async def get_user_channel(tg_user_id: int, channel_type: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT discord_channel_id FROM user_channels WHERE telegram_user_id = ? AND channel_type = ?",
            (tg_user_id, channel_type),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_telegram_user_by_channel(dc_channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT telegram_user_id, channel_type FROM user_channels WHERE discord_channel_id = ?",
            (dc_channel_id,),
        ) as cursor:
            return await cursor.fetchone()


async def get_all_user_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT telegram_user_id, channel_type, telegram_username, discord_channel_id FROM user_channels"
        ) as cursor:
            return await cursor.fetchall()


async def save_message_link(tg_msg_id: int, tg_chat_id: int, dc_msg_id: int, dc_chan_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO message_links
            (telegram_message_id, telegram_chat_id, discord_message_id, discord_channel_id)
            VALUES (?, ?, ?, ?)
            """,
            (tg_msg_id, tg_chat_id, dc_msg_id, dc_chan_id),
        )
        await db.commit()


async def get_discord_msg(tg_msg_id: int, tg_chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT discord_message_id, discord_channel_id FROM message_links
            WHERE telegram_message_id = ? AND telegram_chat_id = ?
            """,
            (tg_msg_id, tg_chat_id),
        ) as cursor:
            return await cursor.fetchone()


async def get_telegram_msg(dc_msg_id: int, dc_chan_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT telegram_message_id, telegram_chat_id FROM message_links
            WHERE discord_message_id = ? AND discord_channel_id = ?
            """,
            (dc_msg_id, dc_chan_id),
        ) as cursor:
            return await cursor.fetchone()


async def save_rules(language: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO rules (language, content, updated_at) VALUES (?, ?, ?)",
            (language, content, _utc_now()),
        )
        await db.commit()


async def get_rules(language: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT content FROM rules WHERE language = ?", (language,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else ""


async def set_active_session(tg_user_id: int, channel_type):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO user_sessions (telegram_user_id, active_channel_type, updated_at)
            VALUES (?, ?, ?)
            """,
            (tg_user_id, channel_type, _utc_now()),
        )
        await db.commit()


async def get_active_session(tg_user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT active_channel_type FROM user_sessions WHERE telegram_user_id = ?",
            (tg_user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def start_interview(tg_user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO admin_interviews (telegram_user_id, step, answers, status)
            VALUES (?, 0, '{}', 'in_progress')
            """,
            (tg_user_id,),
        )
        await db.commit()


async def get_interview(tg_user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT step, answers, status FROM admin_interviews WHERE telegram_user_id = ?",
            (tg_user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            step, answers_json, status = row
            return {"step": step, "answers": json.loads(answers_json or "{}"), "status": status}


async def update_interview(tg_user_id: int, step: int, answers: dict, status: str = INTERVIEW_STATUS_IN_PROGRESS):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO admin_interviews (telegram_user_id, step, answers, status)
            VALUES (?, ?, ?, ?)
            """,
            (tg_user_id, step, json.dumps(answers, ensure_ascii=False), status),
        )
        await db.commit()


async def clear_interview(tg_user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM admin_interviews WHERE telegram_user_id = ?", (tg_user_id,))
        await db.commit()


async def get_config(key: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM system_config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_config(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()
