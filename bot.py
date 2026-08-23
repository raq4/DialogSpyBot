# configuration & setup
import asyncio
import logging
from typing import Any, Dict, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ContentType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BusinessConnection,
    BusinessMessagesDeleted,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import database as db
from locales import t

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

SAVE_TRIGGERS = {"!", ".", "+", "save", "сохранить", "сейв", "/save", "s", "с"}

# formatting helpers
def format_sender_header(cached: Any, settings: Dict[str, Any], lang: str) -> str:
    parts = []
    fname = cached["sender_first_name"]
    lname = cached["sender_last_name"]
    uname = cached["sender_username"]
    uid = cached["sender_id"]

    if settings["show_first_name"] and fname:
        parts.append(fname)
    if settings["show_last_name"] and lname:
        parts.append(lname)
    if settings["show_username"] and uname:
        parts.append(f"(@{uname})")
    if settings["show_user_id"] and uid:
        parts.append(f"[<code>{uid}</code>]")

    who = " ".join(parts) if parts else f"<code>{uid}</code>"
    return f"👤 <b>{t(lang, 'sender_label')}</b> {who}"

def make_topic_title(chat: Any) -> str:
    if chat.title:
        return f"{chat.title[:100]} [{chat.id}]"
    
    parts = [p for p in [chat.first_name, chat.last_name] if p]
    if chat.username:
        parts.append(f"(@{chat.username})")
    
    full_name = " ".join(parts)
    return f"{full_name[:100]} [{chat.id}]" if full_name else f"User [{chat.id}]"

# routing & message delivery helpers
async def get_or_create_pm_thread(owner_id: int, business_chat: Any) -> Optional[int]:
    st = await db.get_user_settings(owner_id)
    if not st["threaded_mode"]:
        return None

    thread_id = await db.get_user_topic(owner_id, business_chat.id)
    if thread_id:
        return thread_id

    topic_title = make_topic_title(business_chat)
    try:
        topic = await bot.create_forum_topic(chat_id=owner_id, name=topic_title)
        await db.save_user_topic(owner_id, business_chat.id, topic.message_thread_id, topic_title)
        return topic.message_thread_id
    except TelegramBadRequest as e:
        logging.warning(f"Failed to create forum topic: {e}")
        return None

async def send_to_owner(owner_id: int, business_chat: Any, send_func, **kwargs):
    thread_id = await get_or_create_pm_thread(owner_id, business_chat)
    try:
        return await send_func(chat_id=owner_id, message_thread_id=thread_id, **kwargs)
    except TelegramBadRequest as e:
        if any(err in str(e).lower() for err in ["topic", "thread"]):
            topic_title = make_topic_title(business_chat)
            try:
                new_topic = await bot.create_forum_topic(chat_id=owner_id, name=topic_title)
                await db.save_user_topic(owner_id, business_chat.id, new_topic.message_thread_id, topic_title)
                return await send_func(chat_id=owner_id, message_thread_id=new_topic.message_thread_id, **kwargs)
            except Exception:
                pass
        return await send_func(chat_id=owner_id, message_thread_id=None, **kwargs)

async def dispatch_media_message(owner_id: int, chat: Any, content_type: str, file_id: str, caption: Optional[str] = None):
    if content_type in ("photo", ContentType.PHOTO):
        return await send_to_owner(owner_id, chat, bot.send_photo, photo=file_id, caption=caption)
    elif content_type in ("video", ContentType.VIDEO):
        return await send_to_owner(owner_id, chat, bot.send_video, video=file_id, caption=caption)
    elif content_type in ("voice", ContentType.VOICE):
        return await send_to_owner(owner_id, chat, bot.send_voice, voice=file_id, caption=caption)
    elif content_type in ("video_note", ContentType.VIDEO_NOTE):
        return await send_to_owner(owner_id, chat, bot.send_video_note, video_note=file_id)
    elif content_type in ("audio", ContentType.AUDIO):
        return await send_to_owner(owner_id, chat, bot.send_audio, audio=file_id, caption=caption)
    elif content_type in ("document", ContentType.DOCUMENT):
        return await send_to_owner(owner_id, chat, bot.send_document, document=file_id, caption=caption)
    return None

# inline keyboards
def get_settings_keyboard(st: Dict[str, Any]) -> InlineKeyboardMarkup:
    lang = st["language"]
    th_status = t(lang, "status_on") if st["threaded_mode"] else t(lang, "status_off")
    save_m_text = t(lang, "btn_mode_trigger") if st["save_media_mode"] == "trigger" else t(lang, "btn_mode_all")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_header"), callback_data="menu_header")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_threads')}: {th_status}", callback_data="toggle_threaded")],
        [InlineKeyboardButton(text=f"{t(lang, 'btn_save_mode')}: {save_m_text}", callback_data="menu_save_mode")],
        [InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="menu_lang")],
    ])

def get_header_keyboard(st: Dict[str, Any]) -> InlineKeyboardMarkup:
    lang = st["language"]
    def btn_txt(name, val):
        return f"{name}: {t(lang, "status_on") if val else t(lang, "status_off")}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_txt(t(lang, "btn_show_fname"), st["show_first_name"]), callback_data="toggle_hdr_first_name")],
        [InlineKeyboardButton(text=btn_txt(t(lang, "btn_show_lname"), st["show_last_name"]), callback_data="toggle_hdr_last_name")],
        [InlineKeyboardButton(text=btn_txt(t(lang, "btn_show_uname"), st["show_username"]), callback_data="toggle_hdr_username")],
        [InlineKeyboardButton(text=btn_txt(t(lang, "btn_show_id"), st["show_user_id"]), callback_data="toggle_hdr_user_id")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu_main")],
    ])

def get_save_mode_keyboard(st: Dict[str, Any]) -> InlineKeyboardMarkup:
    lang = st["language"]
    cur = st["save_media_mode"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'👉 ' if cur == 'trigger' else ''}{t(lang, 'btn_mode_trigger')}", callback_data="set_smode_trigger")],
        [InlineKeyboardButton(text=f"{'👉 ' if cur == 'all' else ''}{t(lang, 'btn_mode_all')}", callback_data="set_smode_all")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu_main")],
    ])

def get_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")],
        [InlineKeyboardButton(text="⬅️ Back / Назад", callback_data="menu_main")],
    ])

# command handlers
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    st = await db.get_user_settings(msg.from_user.id)
    await msg.answer(t(st["language"], "start"))

@dp.message(Command("settings"))
async def cmd_settings(msg: Message):
    st = await db.get_user_settings(msg.from_user.id)
    await msg.answer(t(st["language"], "settings_title"), reply_markup=get_settings_keyboard(st))

# callback query handlers
@dp.callback_query(F.data.startswith("menu_"))
async def cb_menus(call: CallbackQuery):
    st = await db.get_user_settings(call.from_user.id)
    lang = st["language"]
    menu = call.data.split("_")[1]

    if menu == "main":
        await call.message.edit_text(t(lang, "settings_title"), reply_markup=get_settings_keyboard(st))
    elif menu == "header":
        await call.message.edit_text(t(lang, "hdr_settings_title"), reply_markup=get_header_keyboard(st))
    elif menu == "lang":
        await call.message.edit_text(t(lang, "lang_settings_title"), reply_markup=get_lang_keyboard())
    elif menu == "save":
        await call.message.edit_text(t(lang, "save_mode_title"), reply_markup=get_save_mode_keyboard(st))
    await call.answer()

@dp.callback_query(F.data.startswith("set_smode_"))
async def cb_set_save_mode(call: CallbackQuery):
    mode = call.data.replace("set_smode_", "")
    await db.update_user_setting(call.from_user.id, "save_media_mode", mode)
    st = await db.get_user_settings(call.from_user.id)
    await call.message.edit_text(t(st["language"], "save_mode_title"), reply_markup=get_save_mode_keyboard(st))
    await call.answer()

@dp.callback_query(F.data.startswith("toggle_hdr_"))
async def cb_toggle_hdr(call: CallbackQuery):
    field = call.data.replace("toggle_hdr_", "show_")
    st = await db.get_user_settings(call.from_user.id)
    new_val = 0 if st[field] else 1
    await db.update_user_setting(call.from_user.id, field, new_val)
    st[field] = new_val
    await call.message.edit_reply_markup(reply_markup=get_header_keyboard(st))
    await call.answer()

@dp.callback_query(F.data == "toggle_threaded")
async def cb_toggle_threaded(call: CallbackQuery):
    st = await db.get_user_settings(call.from_user.id)
    new_val = 0 if st["threaded_mode"] else 1
    await db.update_user_setting(call.from_user.id, "threaded_mode", new_val)
    st["threaded_mode"] = new_val
    await call.message.edit_reply_markup(reply_markup=get_settings_keyboard(st))
    await call.answer()

@dp.callback_query(F.data.startswith("set_lang_"))
async def cb_set_lang(call: CallbackQuery):
    lang = call.data.split("_")[2]
    await db.update_user_setting(call.from_user.id, "language", lang)
    st = await db.get_user_settings(call.from_user.id)
    await call.message.edit_text(t(lang, "settings_title"), reply_markup=get_settings_keyboard(st))
    await call.answer()

# topic management handlers
@dp.message(F.forum_topic_edited)
async def on_topic_edited(msg: Message):
    await db.update_user_topic_name(msg.chat.id, msg.message_thread_id, msg.forum_topic_edited.name)

# business event handlers
@dp.business_connection()
async def on_business_connection(conn: BusinessConnection):
    if conn.is_enabled:
        await db.save_connection(conn.id, conn.user.id)

@dp.business_message()
async def on_business_message(msg: Message):
    await db.cache_message(msg)

    if msg.reply_to_message:
        replied = msg.reply_to_message
        owner_id = await db.get_owner_by_connection(msg.business_connection_id)

        if msg.from_user and msg.from_user.id == owner_id:
            st = await db.get_user_settings(owner_id)
            user_text = (msg.text or "").strip().lower()

            if st["save_media_mode"] == "trigger" and user_text not in SAVE_TRIGGERS:
                return

            file_id = None
            if replied.photo: file_id = replied.photo[-1].file_id
            elif replied.video: file_id = replied.video.file_id
            elif replied.voice: file_id = replied.voice.file_id
            elif replied.video_note: file_id = replied.video_note.file_id

            if file_id:
                lang = st["language"]
                author_data = {
                    "sender_first_name": replied.from_user.first_name if replied.from_user else "",
                    "sender_last_name": replied.from_user.last_name if replied.from_user else "",
                    "sender_username": replied.from_user.username if replied.from_user else "",
                    "sender_id": replied.from_user.id if replied.from_user else 0,
                }
                caption = f"{t(lang, 'saved_media_title')}\n{format_sender_header(author_data, st, lang)}"
                if replied.caption:
                    caption += f"\n💬 <b>{t(lang, 'caption_label')}</b> {replied.caption}"

                try:
                    sent = await dispatch_media_message(owner_id, msg.chat, replied.content_type, file_id, caption)
                    if sent and replied.video_note:
                        await sent.reply(caption)
                except Exception as e:
                    logging.error(f"Error saving media reply: {e}")

@dp.edited_business_message()
async def on_edited_business_message(msg: Message):
    cached = await db.get_cached_message(msg.chat.id, msg.message_id)
    owner_id = await db.get_owner_by_connection(msg.business_connection_id)
    st = await db.get_user_settings(owner_id)
    lang = st["language"]

    new_text = msg.text or msg.caption or ""
    old_text = cached["text_content"] if cached else None

    if old_text != new_text:
        author_data = cached or {
            "sender_first_name": msg.from_user.first_name if msg.from_user else "",
            "sender_last_name": msg.from_user.last_name if msg.from_user else "",
            "sender_username": msg.from_user.username if msg.from_user else "",
            "sender_id": msg.from_user.id if msg.from_user else 0,
        }
        title = t(lang, "edit_caption_title") if (msg.photo or msg.video or msg.document) else t(lang, "edit_text_title")
        old_val = old_text if old_text is not None else t(lang, "not_cached")

        body = (
            f"{title}\n"
            f"{format_sender_header(author_data, st, lang)}\n\n"
            f"🔴 <b>{t(lang, 'old_label')}</b>\n{old_val if old_val else t(lang, 'empty')}\n\n"
            f"🟢 <b>{t(lang, 'new_label')}</b>\n{new_text if new_text else t(lang, 'empty')}"
        )
        try:
            await send_to_owner(owner_id, msg.chat, bot.send_message, text=body)
        except Exception as e:
            logging.error(f"Error sending edit notification: {e}")

    await db.cache_message(msg)

@dp.deleted_business_messages()
async def on_business_messages_deleted(event: BusinessMessagesDeleted):
    owner_id = await db.get_owner_by_connection(event.business_connection_id)
    st = await db.get_user_settings(owner_id)
    lang = st["language"]

    for msg_id in event.message_ids:
        cached = await db.get_cached_message(event.chat.id, msg_id)
        if not cached:
            continue

        sender_hdr = format_sender_header(cached, st, lang)
        content_type = cached["content_type"]
        file_id = cached["file_id"]
        text_content = cached["text_content"]

        try:
            if content_type == "text" or not file_id:
                body = (
                    f"{t(lang, 'del_text_title')}\n"
                    f"{sender_hdr}\n\n"
                    f"💬 <b>{t(lang, 'content_label')}</b>\n{text_content if text_content else t(lang, 'empty')}"
                )
                await send_to_owner(owner_id, event.chat, bot.send_message, text=body)
            else:
                caption = text_content if text_content else None
                sent = await dispatch_media_message(owner_id, event.chat, content_type, file_id, caption)
                info = f"{t(lang, 'del_media_title')}\n{sender_hdr}"
                if sent:
                    await sent.reply(info)
                else:
                    await send_to_owner(owner_id, event.chat, bot.send_message, text=info)
        except Exception as e:
            logging.error(f"Error sending delete notification: {e}")

# entry point
async def main():
    await db.init_db()
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
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())