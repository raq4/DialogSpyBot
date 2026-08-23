import aiosqlite
from typing import Any, Dict, Optional
from aiogram.types import Message
from config import DB_PATH, MY_USER_ID

# database schema
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS connections (
    connection_id TEXT PRIMARY KEY,
    user_id INTEGER
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'ru',
    show_first_name INTEGER DEFAULT 1,
    show_last_name INTEGER DEFAULT 1,
    show_username INTEGER DEFAULT 1,
    show_user_id INTEGER DEFAULT 1,
    threaded_mode INTEGER DEFAULT 0,
    save_media_mode TEXT DEFAULT 'all'
);

CREATE TABLE IF NOT EXISTS user_topics (
    owner_id INTEGER,
    business_chat_id INTEGER,
    thread_id INTEGER,
    topic_name TEXT,
    PRIMARY KEY (owner_id, business_chat_id)
);

CREATE TABLE IF NOT EXISTS messages (
    chat_id INTEGER,
    message_id INTEGER,
    sender_id INTEGER,
    sender_username TEXT,
    sender_first_name TEXT,
    sender_last_name TEXT,
    content_type TEXT,
    text_content TEXT,
    file_id TEXT,
    PRIMARY KEY (chat_id, message_id)
);
"""

# database initialization
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)

        async with db.execute("PRAGMA table_info(messages)") as cursor:
            cols = [row[1] for row in await cursor.fetchall()]
            if "sender_first_name" not in cols:
                await db.execute("ALTER TABLE messages ADD COLUMN sender_first_name TEXT DEFAULT ''")
            if "sender_last_name" not in cols:
                await db.execute("ALTER TABLE messages ADD COLUMN sender_last_name TEXT DEFAULT ''")

        async with db.execute("PRAGMA table_info(user_settings)") as cursor:
            cols = [row[1] for row in await cursor.fetchall()]
            if "save_media_mode" not in cols:
                await db.execute("ALTER TABLE user_settings ADD COLUMN save_media_mode TEXT DEFAULT 'all'")

        await db.commit()

# user settings queries
async def get_user_settings(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        defaults = {
            "user_id": user_id, "language": "ru",
            "show_first_name": 1, "show_last_name": 1,
            "show_username": 1, "show_user_id": 1,
            "threaded_mode": 0, "save_media_mode": "all"
        }
        await db.execute(
            """INSERT OR IGNORE INTO user_settings 
               (user_id, language, show_first_name, show_last_name, show_username, show_user_id, threaded_mode, save_media_mode) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, "ru", 1, 1, 1, 1, 0, "all")
        )
        await db.commit()
        return defaults

async def update_user_setting(user_id: int, field: str, value: Any):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE user_settings SET {field} = ? WHERE user_id = ?", (value, user_id))
        await db.commit()

# business connection queries
async def save_connection(connection_id: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO connections (connection_id, user_id) VALUES (?, ?)", (connection_id, user_id))
        await db.commit()

async def get_owner_by_connection(connection_id: Optional[str]) -> int:
    if not connection_id:
        return MY_USER_ID
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM connections WHERE connection_id = ?", (connection_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else MY_USER_ID

# message cache queries
async def cache_message(msg: Message):
    sender = msg.from_user
    sender_id = sender.id if sender else 0
    s_uname = sender.username or ""
    s_fname = sender.first_name or ""
    s_lname = sender.last_name or ""

    content_type = msg.content_type
    text_content = msg.text or msg.caption or ""
    file_id = None

    if msg.photo:
        file_id = msg.photo[-1].file_id
        content_type = "photo"
    elif msg.video:
        file_id = msg.video.file_id
        content_type = "video"
    elif msg.voice:
        file_id = msg.voice.file_id
        content_type = "voice"
    elif msg.video_note:
        file_id = msg.video_note.file_id
        content_type = "video_note"
    elif msg.audio:
        file_id = msg.audio.file_id
        content_type = "audio"
    elif msg.document:
        file_id = msg.document.file_id
        content_type = "document"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO messages 
            (chat_id, message_id, sender_id, sender_username, sender_first_name, sender_last_name, content_type, text_content, file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg.chat.id, msg.message_id, sender_id, s_uname, s_fname, s_lname, content_type, text_content, file_id)
        )
        await db.commit()

async def get_cached_message(chat_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)) as cur:
            return await cur.fetchone()

# forum topic queries
async def get_user_topic(owner_id: int, business_chat_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT thread_id FROM user_topics WHERE owner_id = ? AND business_chat_id = ?",
            (owner_id, business_chat_id)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def save_user_topic(owner_id: int, business_chat_id: int, thread_id: int, topic_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_topics (owner_id, business_chat_id, thread_id, topic_name) VALUES (?, ?, ?, ?)",
            (owner_id, business_chat_id, thread_id, topic_name)
        )
        await db.commit()

async def update_user_topic_name(owner_id: int, thread_id: int, topic_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE user_topics SET topic_name = ? WHERE owner_id = ? AND thread_id = ?",
            (topic_name, owner_id, thread_id)
        )
        await db.commit()