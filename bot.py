

import asyncio

import logging

import sqlite3

import html

import io

import os

from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher

from aiogram.types import (

    Message,

    BusinessMessagesDeleted,

    BufferedInputFile

)

from aiogram.filters import Command

from aiogram.client.default import DefaultBotProperties

from aiogram.enums import ParseMode

from aiohttp import web

# ==============================

# НАСТРОЙКИ

# ==============================

BOT_TOKEN = "8809141088:AAEXgnBNDxBUchGqlVom6qs5aE_ms_01dA4"

ADMIN_ID = 815509230

MY_USERNAME = "rafaelkazaryan"

DB_PATH = "business_cache.db"

PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_НОВЫЙ_ТОКЕН":

    raise RuntimeError("Вставь токен бота в BOT_TOKEN")

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

    default=DefaultBotProperties(parse_mode=ParseMode.HTML)

)

dp = Dispatcher()

# ==============================

# DATABASE

# ==============================

db = sqlite3.connect(DB_PATH, check_same_thread=False)

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

    username = (msg.from_user.username or "").lower()

    if username == MY_USERNAME.lower():

        return

    media_type = None

    file_id = None

    if msg.photo:

        media_type, file_id = "photo", msg.photo[-1].file_id

    elif msg.video:

        media_type, file_id = "video", msg.video.file_id

    elif msg.video_note:

        media_type, file_id = "video_note", msg.video_note.file_id

    elif msg.voice:

        media_type, file_id = "voice", msg.voice.file_id

    elif msg.audio:

        media_type, file_id = "audio", msg.audio.file_id

    elif msg.document:

        media_type, file_id = "document", msg.document.file_id

    elif msg.animation:

        media_type, file_id = "animation", msg.animation.file_id

    elif msg.sticker:

        media_type, file_id = "sticker", msg.sticker.file_id

    text = msg.html_text or ""

    user_name = (

        f"@{msg.from_user.username}"

        if msg.from_user.username

        else msg.from_user.first_name or "Unknown"

    )

    cursor.execute("""

    REPLACE INTO messages

    (message_id, chat_id, user_name, text, media_type, file_id)

    VALUES (?, ?, ?, ?, ?, ?)

    """, (

        msg.message_id,

        msg.chat.id,

        user_name,

        text,

        media_type,

        file_id

    ))

    db.commit()

def get_message(message_id, chat_id):

    cursor.execute("""

    SELECT user_name, text, media_type, file_id

    FROM messages

    WHERE message_id = ? AND chat_id = ?

    """, (message_id, chat_id))

    return cursor.fetchone()

# ==============================

# MEDIA DETECTION

# ==============================

def get_media(msg):

    if msg.photo:

        return "photo", msg.photo[-1].file_id, "jpg"

    if msg.video:

        return "video", msg.video.file_id, "mp4"

    if msg.video_note:

        return "video_note", msg.video_note.file_id, "mp4"

    if msg.voice:

        return "voice", msg.voice.file_id, "ogg"

    if msg.audio:

        return "audio", msg.audio.file_id, "mp3"

    if msg.document:

        filename = msg.document.file_name or "file.bin"

        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"

        return "document", msg.document.file_id, ext

    if msg.animation:

        return "animation", msg.animation.file_id, "mp4"

    if msg.sticker:

        ext = "webm" if msg.sticker.is_video else "webp"

        return "sticker", msg.sticker.file_id, ext

    return None, None, None

# ==============================

# MEDIA DOWNLOAD

# ==============================

async def download_media(file_id, filename):

    buffer = io.BytesIO()

    await bot.download(

        file=file_id,

        destination=buffer

    )

    data = buffer.getvalue()

    if not data:

        raise RuntimeError("Telegram вернул пустой файл")

    return BufferedInputFile(

        data,

        filename=filename

    )

# ==============================

# MEDIA SENDING

# ==============================

async def send_media(media_type, file, caption):

    if media_type == "photo":

        await bot.send_photo(ADMIN_ID, photo=file, caption=caption)

    elif media_type == "video":

        await bot.send_video(ADMIN_ID, video=file, caption=caption)

    elif media_type == "video_note":

        await bot.send_message(ADMIN_ID, caption)

        await bot.send_video_note(ADMIN_ID, video_note=file)

    elif media_type == "voice":

        await bot.send_voice(ADMIN_ID, voice=file, caption=caption)

    elif media_type == "audio":

        await bot.send_audio(ADMIN_ID, audio=file, caption=caption)

    elif media_type == "document":

        await bot.send_document(ADMIN_ID, document=file, caption=caption)

    elif media_type == "animation":

        await bot.send_animation(ADMIN_ID, animation=file, caption=caption)

    elif media_type == "sticker":

        await bot.send_sticker(ADMIN_ID, sticker=file)

        await bot.send_message(ADMIN_ID, caption)

    else:

        raise ValueError(f"Неизвестный тип медиа: {media_type}")

# ==============================

# START

# ==============================

@dp.message(Command("start"))

async def cmd_start(message: Message):

    if message.from_user and message.from_user.id == ADMIN_ID:

        await message.answer(

            "✅ <b>Бот мониторинга активен.</b>\n\n"

            "Перехват медиа работает через ответы на сообщения."

        )

# ==============================

# BUSINESS MESSAGE

# ==============================

@dp.business_message()

async def handle_business_message(message: Message):

    if not message.from_user:

        return

    username = (message.from_user.username or "").lower()

    if username == MY_USERNAME.lower() and message.reply_to_message:

        rep = message.reply_to_message

        media_type, file_id, ext = get_media(rep)

        if not file_id:

            return

        status = await bot.send_message(

            ADMIN_ID,

            f"⏳ <i>Скачиваю {media_type}...</i>"

        )

        try:

            input_file = await download_media(

                file_id,

                f"intercepted.{ext}"

            )

            caption = (

                f"🔥 <b>Перехвачено</b>\n"

                f"🕐 <code>{msk_now()}</code>\n"

                f"📦 Тип: <code>{media_type}</code>"

            )

            await send_media(media_type, input_file, caption)

            logger.info("Media intercepted: %s", media_type)

        except Exception as e:

            logger.exception("Media interception error")

            await bot.send_message(

                ADMIN_ID,

                f"❌ <b>Ошибка перехвата</b>\n"

                f"Тип: <code>{safe_html(media_type)}</code>\n"

                f"<code>{safe_html(e)}</code>"

            )

        finally:

            try:

                await bot.delete_message(

                    ADMIN_ID,

                    status.message_id

                )

            except Exception:

                pass

        return

    save_message(message)

# ==============================

# EDITED BUSINESS MESSAGE

# ==============================

@dp.edited_business_message()

async def handle_edited_message(message: Message):

    if not message.from_user:

        return

    if (message.from_user.username or "").lower() == MY_USERNAME.lower():

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

            f"❌ <b>Было:</b>\n{old_msg[1] or '—'}\n\n"

            f"✅ <b>Стало:</b>\n{new_text or '—'}"

        )

    save_message(message)

# ==============================

# DELETED BUSINESS MESSAGES

# ==============================

@dp.deleted_business_messages()

async def handle_deleted_messages(deleted: BusinessMessagesDeleted):

    for msg_id in deleted.message_ids:

        old_msg = get_message(msg_id, deleted.chat.id)

        if not old_msg:

            continue

        user_name, text, media_type, file_id = old_msg

        if user_name.replace("@", "").lower() == MY_USERNAME.lower():

            continue

        caption = (

            f"🗑 <b>Сообщение удалено</b>\n"

            f"🕐 <code>{msk_now()}</code>\n"

            f"👤 {safe_html(user_name)}"

        )

        try:

            if media_type and file_id:

                if media_type == "sticker":

                    await bot.send_sticker(ADMIN_ID, sticker=file_id)

                    await bot.send_message(ADMIN_ID, caption)

                elif media_type == "video_note":

                    await bot.send_message(ADMIN_ID, caption)

                    await bot.send_video_note(ADMIN_ID, video_note=file_id)

                else:

                    await send_media(

                        media_type,

                        file_id,

                        caption + (f"\n📝 {text}" if text else "")

                    )

            else:

                await bot.send_message(

                    ADMIN_ID,

                    caption + f"\n📝 {text or '—'}"

                )

        except Exception:

            logger.exception("Deleted message recovery failed: %s", msg_id)

            await bot.send_message(

                ADMIN_ID,

                caption + "\n⚠️ Не удалось восстановить медиа."

            )

        finally:

            cursor.execute(

                "DELETE FROM messages WHERE message_id=? AND chat_id=?",

                (msg_id, deleted.chat.id)

            )

            db.commit()

# ==============================

# RENDER

# ==============================

async def health(request):

    return web.Response(text="OK")

async def start_web_server():

    app = web.Application()

    app.router.add_get("/", health)

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)

    await site.start()

    logger.info("Health server started on port %s", PORT)

    return runner

# ==============================

# MAIN

# ==============================

async def main():

    runner = await start_web_server()

    try:

        await bot.delete_webhook(drop_pending_updates=True)

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