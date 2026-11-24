import asyncio
import logging
import sqlite3
import html
import os
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BusinessMessagesDeleted
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

# ==============================
# НАСТРОЙКИ
# ==============================
BOT_TOKEN = "8809141088:AAEXgnBNDxBUchGqlVom6qs5aE_ms_01dA4"
ADMIN_ID = 815509230
MY_USER_ID = 815509230
MY_USERNAME = "rafaelkazaryan"
DB_PATH = os.getenv("DB_PATH", "business_cache.db")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_НОВЫЙ_ТОКЕН":
    raise RuntimeError("Вставь новый токен бота в BOT_TOKEN")

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


def msk_now():
    return datetime.now(MSK).strftime("%d.%m.%Y %H:%M:%S")


def safe_html(value):
    return html.escape(str(value or ""))


# ==============================
# BOT
# ==============================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)
dp = Dispatcher()

# ==============================
# DATABASE
# ==============================
db = sqlite3.connect(
    DB_PATH,
    check_same_thread=False
)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER,
    chat_id INTEGER,
    user_name TEXT,
    text TEXT,
    media_type TEXT,
    file_id TEXT,
    PRIMARY KEY (message_id, chat_id)
)
""")
db.commit()


def save_message(msg: Message):
    if not msg.from_user:
        return
    # Игнорируем собственные сообщения по ID
    if msg.from_user.id == MY_USER_ID:
        return
    # Сохраняем только текст.
    # Медиа не скачиваем и не сохраняем.
    if any((
        msg.photo,
        msg.video,
        msg.video_note,
        msg.voice,
        msg.audio,
        msg.document,
        msg.animation,
        msg.sticker
    )):
        return

    text = msg.html_text or ""
    if not text.strip():
        return

    user_name = (
        f"@{msg.from_user.username}"
        if msg.from_user.username
        else msg.from_user.first_name or "Unknown"
    )

    cursor.execute("""
    REPLACE INTO messages
    (message_id, chat_id, user_name, text, media_type, file_id)
    VALUES (?, ?, ?, ?, NULL, NULL)
    """, (
        msg.message_id,
        msg.chat.id,
        user_name,
        text
    ))
    db.commit()


def get_message(message_id, chat_id):
    cursor.execute("""
    SELECT user_name, text, media_type, file_id
    FROM messages
    WHERE message_id = ? AND chat_id = ?
    """, (
        message_id,
        chat_id
    ))
    return cursor.fetchone()


# ==============================
# START
# ==============================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user and message.from_user.id == ADMIN_ID:
        await message.answer(
            "✅ <b>Бот мониторинга активен.</b>\n\n"
            "Обычные медиа игнорируются.\n"
            "Сохраняются только текстовые сообщения."
        )


# ==============================
# BUSINESS MESSAGE
# ==============================
@dp.business_message()
async def handle_business_message(message: Message):
    if not message.from_user:
        return
    # Игнорируем сообщения владельца аккаунта
    if message.from_user.id == MY_USER_ID:
        return
    # Не обрабатываем медиа
    if any((
        message.photo,
        message.video,
        message.video_note,
        message.voice,
        message.audio,
        message.document,
        message.animation,
        message.sticker
    )):
        return
    save_message(message)


# ==============================
# EDITED BUSINESS MESSAGE
# ==============================
@dp.edited_business_message()
async def handle_edited_message(message: Message):
    if not message.from_user:
        return
    # Игнорируем собственные сообщения по ID
    if message.from_user.id == MY_USER_ID:
        return
    # Игнорируем медиа
    if any((
        message.photo,
        message.video,
        message.video_note,
        message.voice,
        message.audio,
        message.document,
        message.animation,
        message.sticker
    )):
        return

    old_msg = get_message(
        message.message_id,
        message.chat.id
    )
    new_text = message.html_text or ""
    user_name = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else message.from_user.first_name or "Unknown"
    )

    if old_msg and old_msg[1] != new_text:
        await bot.send_message(
            ADMIN_ID,
            f"✏️ <b>Сообщение изменено</b>\n"
            f"🕐 <code>{msk_now()}</code>\n"
            f"👤 {safe_html(user_name)}\n\n"
            f"❌ <b>Было:</b>\n"
            f"{old_msg[1] or '—'}\n\n"
            f"✅ <b>Стало:</b>\n"
            f"{new_text or '—'}"
        )

    save_message(message)


# ==============================
# DELETED BUSINESS MESSAGES
# ==============================
@dp.deleted_business_messages()
async def handle_deleted_messages(
    deleted: BusinessMessagesDeleted
):
    for msg_id in deleted.message_ids:
        old_msg = get_message(
            msg_id,
            deleted.chat.id
        )
        if not old_msg:
            continue

        user_name, text, media_type, file_id = old_msg
        caption = (
            f"🗑 <b>Сообщение удалено</b>\n"
            f"🕐 <code>{msk_now()}</code>\n"
            f"👤 {safe_html(user_name)}\n\n"
            f"📝 <b>Текст:</b>\n"
            f"{text or '—'}"
        )

        try:
            await bot.send_message(
                ADMIN_ID,
                caption
            )
            logger.info(
                "Deleted text message: %s",
                msg_id
            )
        except Exception:
            logger.exception(
                "Deleted message notification failed: %s",
                msg_id
            )
        finally:
            cursor.execute(
                """
                DELETE FROM messages
                WHERE message_id = ? AND chat_id = ?
                """,
                (
                    msg_id,
                    deleted.chat.id
                )
            )
            db.commit()


# ==============================
# RENDER HEALTH CHECK
# ==============================
async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )
    await site.start()
    logger.info(
        "Health server started on port %s",
        PORT
    )
    return runner


# ==============================
# MAIN
# ==============================
async def main():
    runner = await start_web_server()
    try:
        await bot.delete_webhook(
            drop_pending_updates=True
        )
        logger.info("Bot started successfully")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await runner.cleanup()
        db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
