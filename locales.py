# localization dictionary
from typing import Dict

LOCALES: Dict[str, Dict[str, str]] = {
    "ru": {
        "start": "👋 <b>Бот анти-удаления активен!</b>\nИспользуйте команду /settings для настройки параметров.",
        "settings_title": "⚙️ <b>Настройки бота:</b>",
        "hdr_settings_title": "👤 <b>Отображение данных отправителя:</b>",
        "lang_settings_title": "🌐 <b>Выберите язык интерфейса:</b>",
        "save_mode_title": "📥 <b>Режим сохранения медиа по ответу (Reply):</b>\n\n"
                           "• <b>По триггеру:</b> сохранение по триггерам (<code>!</code>, <code>+</code>, <code>save</code>, <code>.</code>)\n"
                           "• <b>Любой ответ:</b> сохранение на любой ваш ответ",
        "btn_header": "👤 Заголовок сообщения",
        "btn_threads": "🧵 Темы в ЛС",
        "btn_save_mode": "📥 Сохранение медиа",
        "btn_lang": "🌐 Язык / Language",
        "btn_back": "⬅️ Назад",
        "status_on": "✅ Вкл",
        "status_off": "❌ Выкл",
        "btn_show_fname": "Имя",
        "btn_show_lname": "Фамилия",
        "btn_show_uname": "Username",
        "btn_show_id": "User ID",
        "btn_mode_trigger": "🎯 По триггеру",
        "btn_mode_all": "🔄 На любой ответ",
        "del_text_title": "🗑 <b>Удалено текстовое сообщение</b>",
        "del_media_title": "🗑 <b>Удалено медиасообщение</b>",
        "edit_text_title": "✏️ <b>Сообщение отредактировано</b>",
        "edit_caption_title": "✏️ <b>Подпись отредактирована</b>",
        "saved_media_title": "📥 <b>Медиафайл сохранен</b>",
        "sender_label": "От кого:",
        "content_label": "Содержимое:",
        "old_label": "Было:",
        "new_label": "Стало:",
        "caption_label": "Подпись:",
        "empty": "<i>[Пусто / Без текста]</i>",
        "not_cached": "<i>[Не было сохранено в кэше]</i>",
    },
    "en": {
        "start": "👋 <b>Anti-Delete Bot is active!</b>\nUse /settings to configure options.",
        "settings_title": "⚙️ <b>Bot Settings:</b>",
        "hdr_settings_title": "👤 <b>Sender Information Display:</b>",
        "lang_settings_title": "🌐 <b>Select Interface Language:</b>",
        "save_mode_title": "📥 <b>Media Save Mode (Reply):</b>\n\n"
                           "• <b>By trigger:</b> saves on triggers (<code>!</code>, <code>+</code>, <code>save</code>, <code>.</code>)\n"
                           "• <b>Any reply:</b> saves on any text reply",
        "btn_header": "👤 Message Header",
        "btn_threads": "🧵 PM Topics",
        "btn_save_mode": "📥 Media Saving Mode",
        "btn_lang": "🌐 Language / Язык",
        "btn_back": "⬅️ Back",
        "status_on": "✅ On",
        "status_off": "❌ Off",
        "btn_show_fname": "First Name",
        "btn_show_lname": "Last Name",
        "btn_show_uname": "Username",
        "btn_show_id": "User ID",
        "btn_mode_trigger": "🎯 By trigger",
        "btn_mode_all": "🔄 On any reply",
        "del_text_title": "🗑 <b>Text message deleted</b>",
        "del_media_title": "🗑 <b>Media message deleted</b>",
        "edit_text_title": "✏️ <b>Message edited</b>",
        "edit_caption_title": "✏️ <b>Caption edited</b>",
        "saved_media_title": "📥 <b>Media saved</b>",
        "sender_label": "Sender:",
        "content_label": "Content:",
        "old_label": "Old:",
        "new_label": "New:",
        "caption_label": "Caption:",
        "empty": "<i>[Empty / No text]</i>",
        "not_cached": "<i>[Not cached prior to edit]</i>",
    }
}

# localization helper
def t(lang: str, key: str) -> str:
    return LOCALES.get(lang, LOCALES["ru"]).get(key, LOCALES["ru"].get(key, key))