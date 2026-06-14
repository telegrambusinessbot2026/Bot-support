import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'kanthari.db')

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id INTEGER PRIMARY KEY,
                telegram_username TEXT,
                current_state TEXT DEFAULT 'IDLE',
                interview_data TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                telegram_user_id INTEGER,
                discord_channel_id INTEGER,
                category_type TEXT,
                PRIMARY KEY (telegram_user_id, category_type)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS rules (
                language TEXT PRIMARY KEY,
                content TEXT
            )
        ''')
        await db.commit()

async def get_or_create_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT telegram_user_id, current_state FROM users WHERE telegram_user_id = ?', (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.execute('INSERT INTO users (telegram_user_id, telegram_username, current_state) VALUES (?, ?, ?)', (user_id, username, 'IDLE'))
                await db.commit()
                return {'user_id': user_id, 'state': 'IDLE', 'interview_data': {}}
            return {'user_id': user[0], 'state': user[1]}

async def update_user_state(user_id: int, new_state: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET current_state = ? WHERE telegram_user_id = ?', (new_state, user_id))
        await db.commit()

async def get_user_state(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT current_state FROM users WHERE telegram_user_id = ?', (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user:
                return user[0]
            return 'IDLE'

async def save_channel_mapping(user_id: int, channel_id: int, category_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO channels (telegram_user_id, discord_channel_id, category_type) VALUES (?, ?, ?)', (user_id, channel_id, category_type))
        await db.commit()

async def get_discord_channel(user_id: int, category_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT discord_channel_id FROM channels WHERE telegram_user_id = ? AND category_type = ?', (user_id, category_type)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

async def get_telegram_user_from_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT telegram_user_id FROM channels WHERE discord_channel_id = ?', (channel_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

async def delete_channel_mapping(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM channels WHERE discord_channel_id = ?', (channel_id,))
        await db.commit()

async def update_rule(language: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO rules (language, content) VALUES (?, ?)', (language, content))
        await db.commit()

async def get_rule(language: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT content FROM rules WHERE language = ?', (language,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return "Rule content not available."
