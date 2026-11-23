import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    BusinessMessagesDeleted,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MY_USER_ID = int(os.getenv("MY_USER_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "messages_cache.db")

MSK = timezone(timedelta(hours=3))
SAVE_TRIGGERS = {"!", ".", "+", "save", "сохранить", "сейв", "/save", "s", "с"}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def msk_now() -> str:
    return datetime.now(MSK).strftime("%d.%m.%Y %H:%M:%S")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                save_mode TEXT DEFAULT 'trigger'
            )
        """)
        await db.commit()


async def get_save_mode(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT save_mode FROM settings WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else "trigger"


async def set_save_mode(user_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (user_id, save_mode) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET save_mode = excluded.save_mode",
            (user_id, mode),
        )
        await db.commit()


async def save_message(msg: Message):
    if not msg.from_user or msg.from_user.id == MY_USER_ID:
        return

    media_type, file_id = None, None
    if msg.photo:
        media_type, file_id = "photo", msg.photo[-1].file_id
    elif msg.video:
        media_type, file_id = "video", msg.video.file_id
    elif msg.video_note:
        media_type, file_id = "video_note", msg.video_note.file_id
    elif msg.voice:
        media_type, file_id = "voice", msg.voice.file_id
    elif msg.document:
        media_type, file_id = "document", msg.document.file_id
    elif msg.sticker:
        media_type, file_id = "sticker", msg.sticker.file_id

    text = msg.html_text or ""
    user_name = f"@{msg.from_user.username}" if msg.from_user.username else (msg.from_user.first_name or "Unknown")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "REPLACE INTO messages (message_id, chat_id, user_name, text, media_type, file_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg.message_id, msg.chat.id, user_name, text, media_type, file_id),
        )
        await db.commit()


async def get_message(message_id: int, chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_name, text, media_type, file_id FROM messages WHERE message_id = ? AND chat_id = ?",
            (message_id, chat_id),
        ) as cur:
            return await cur.fetchone()


def settings_kb(mode: str) -> InlineKeyboardMarkup:
    t_mark = "✅ " if mode == "trigger" else ""
    a_mark = "✅ " if mode == "all" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{t_mark}По триггеру (!, ., +, save)", callback_data="mode_trigger")],
        [InlineKeyboardButton(text=f"{a_mark}На любой мой ответ (Reply)", callback_data="mode_all")],
    ])


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id != MY_USER_ID:
        return
    await message.answer(
        "✅ <b>Бот мониторинга 24/7 активен.</b>\n\n"
        "• Удаленные и измененные сообщения приходят сюда автоматически.\n"
        "• Чтобы перехватить <b>исчезающее фото/видео/кружок/голосовое</b>, ответьте на него в чате символом <code>!</code> (или настройте режим в /settings)."
    )


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    if message.from_user.id != MY_USER_ID:
        return
    mode = await get_save_mode(MY_USER_ID)
    await message.answer("⚙️ <b>Режим перехвата исчезающих медиа:</b>", reply_markup=settings_kb(mode))


@dp.callback_query(F.data.startswith("mode_"))
async def cb_mode(call: CallbackQuery):
    if call.from_user.id != MY_USER_ID:
        return
    new_mode = call.data.split("_")[1]
    await set_save_mode(MY_USER_ID, new_mode)
    await call.message.edit_reply_markup(reply_markup=settings_kb(new_mode))
    await call.answer("Сохранено")


@dp.business_message()
async def handle_business_message(message: Message):
    # 1. Перехват исчезающих медиа при вашем ответе (Reply)
    if message.from_user and message.from_user.id == MY_USER_ID and message.reply_to_message:
        mode = await get_save_mode(MY_USER_ID)
        txt = (message.text or "").strip().lower()
        if mode == "trigger" and txt not in SAVE_TRIGGERS:
            return

        rep = message.reply_to_message
        if rep.photo or rep.video or rep.video_note or rep.voice or rep.document:
            if rep.photo:
                status_text = "⏳ <i>Скачиваю защищённое фото...</i>"
                media_type, ext, file_id = "photo", "jpg", rep.photo[-1].file_id
            elif rep.video:
                status_text = "⏳ <i>Скачиваю защищённое видео...</i>"
                media_type, ext, file_id = "video", "mp4", rep.video.file_id
            elif rep.video_note:
                status_text = "⏳ <i>Скачиваю защищённый кружок...</i>"
                media_type, ext, file_id = "video_note", "mp4", rep.video_note.file_id
            elif rep.voice:
                status_text = "⏳ <i>Скачиваю защищённое голосовое...</i>"
                media_type, ext, file_id = "voice", "ogg", rep.voice.file_id
            else:
                status_text = "⏳ <i>Скачиваю защищённый файл...</i>"
                media_type = "document"
                ext = rep.document.file_name.split(".")[-1] if rep.document.file_name else "bin"
                file_id = rep.document.file_id

            sender = rep.from_user.username or rep.from_user.first_name if rep.from_user else "Собеседник"
            status_msg = await bot.send_message(MY_USER_ID, status_text)

            try:
                downloaded_io = await bot.download(file_id)
                input_file = BufferedInputFile(downloaded_io.read(), filename=f"intercepted.{ext}")
                caption = f"🔥 <b>Перехвачено от {sender}</b> ({msk_now()})"

                if media_type == "photo":
                    await bot.send_photo(MY_USER_ID, photo=input_file, caption=caption)
                elif media_type == "video":
                    await bot.send_video(MY_USER_ID, video=input_file, caption=caption)
                elif media_type == "video_note":
                    await bot.send_message(MY_USER_ID, caption)
                    await bot.send_video_note(MY_USER_ID, video_note=input_file)
                elif media_type == "voice":
                    await bot.send_voice(MY_USER_ID, voice=input_file, caption=caption)
                elif media_type == "document":
                    await bot.send_document(MY_USER_ID, document=input_file, caption=caption)
            except Exception as e:
                await bot.send_message(MY_USER_ID, f"❌ Ошибка перехвата медиа: <code>{e}</code>")
            finally:
                try:
                    await bot.delete_message(MY_USER_ID, status_msg.message_id)
                except Exception:
                    pass
        return

    # 2. Кэширование входящих сообщений собеседника
    if message.from_user and message.from_user.id != MY_USER_ID:
        await save_message(message)


@dp.edited_business_message()
async def handle_edited_message(message: Message):
    if not message.from_user or message.from_user.id == MY_USER_ID:
        return

    old_msg = await get_message(message.message_id, message.chat.id)
    new_text = message.html_text or ""
    user_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    if old_msg and old_msg[1] != new_text:
        await bot.send_message(
            MY_USER_ID,
            f"✏️ <b>Изменено</b>\n"
            f"🕐 <b>Время (МСК):</b> <code>{msk_now()}</code>\n"
            f"👤 <b>Кто:</b> <code>{user_name}</code>\n\n"
            f"❌ <b>Было:</b> {old_msg[1]}\n"
            f"✅ <b>Стало:</b> {new_text}",
        )
    await save_message(message)


@dp.deleted_business_messages()
async def handle_deleted_messages(deleted: BusinessMessagesDeleted):
    for msg_id in deleted.message_ids:
        old_msg = await get_message(msg_id, deleted.chat.id)
        if not old_msg:
            continue

        user_name, text, media_type, file_id = old_msg
        time_str = msk_now()
        caption = (
            f"🗑 <b>Удалено</b>\n"
            f"🕐 <b>Время (МСК):</b> <code>{time_str}</code>\n"
            f"👤 <b>Кто:</b> <code>{user_name}</code>"
        )

        try:
            if media_type == "photo":
                await bot.send_photo(MY_USER_ID, file_id, caption=f"{caption}\n📝 <b>Текст:</b> {text}")
            elif media_type == "video":
                async def health(request):
    return web.Response(text="Bot is running 24/7")

async def main():
    await init_db()
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
    )

if __name__ == "__main__":
    asyncio.run(main())
