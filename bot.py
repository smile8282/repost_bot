from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
import sqlite3

# Константы
ADMIN_CHAT_ID = 123456789  # ID чата для модерации
GROUP_CHAT_ID = -987654321  # ID основного чата
ADMIN_USER_ID = 12345678   # ID главного администратора

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_trusted INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        anonymous_number INTEGER,
        reputation INTEGER DEFAULT 0
    )
    ''')

    # Таблица стоп-слов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stop_words (
        word TEXT PRIMARY KEY
    )
    ''')

    # Таблица сообщений
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_text TEXT,
        message_type TEXT,  # Тип сообщения: text, photo, video, voice
        file_id TEXT,       # ID файла (для фото, видео, голосовых)
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()

# Функция для проверки стоп-слов
def contains_stop_words(text):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT word FROM stop_words")
    stop_words = [row[0] for row in cursor.fetchall()]
    conn.close()
    return any(word in text.lower() for word in stop_words)

# Функция для проверки, является ли пользователь доверенным
def is_trusted(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT is_trusted FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

# Функция для проверки, забанен ли пользователь
def is_banned(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

# Функция для получения следующего порядкового номера
def get_next_user_number():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count + 1

# Функция для присвоения номера пользователю
def assign_user_number(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    user_number = get_next_user_number()
    cursor.execute("UPDATE users SET anonymous_number = ? WHERE user_id = ?", (user_number, user_id))
    conn.commit()
    conn.close()
    return user_number

# Функция для получения информации о пользователе по номеру
def get_user_info(anonymous_number):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, last_name, reputation FROM users WHERE anonymous_number = ?", (anonymous_number,))
    user_info = cursor.fetchone()
    conn.close()
    return user_info

# Функция для получения информации о пользователе по ID
def get_user_info_by_id(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, last_name, anonymous_number, reputation FROM users WHERE user_id = ?", (user_id,))
    user_info = cursor.fetchone()
    conn.close()
    if user_info:
        return {
            "user_id": user_info[0],
            "username": user_info[1],
            "first_name": user_info[2],
            "last_name": user_info[3],
            "anonymous_number": user_info[4],
            "reputation": user_info[5]
        }
    return None

# Функция для обновления информации о пользователе
def update_user_info(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
    VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

# Функция для публикации сообщения
def publish_message(user_id, text=None, file_id=None, message_type="text"):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()

    # Получаем номер пользователя и репутацию
    cursor.execute("SELECT anonymous_number, reputation FROM users WHERE user_id = ?", (user_id,))
    user_number, reputation = cursor.fetchone()

    # Публикация сообщения
    if message_type == "text":
        message = f"#{user_number} (Репутация: {reputation}):\n{text}"
        context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message)
    elif message_type == "photo":
        message = f"#{user_number} (Репутация: {reputation}):"
        context.bot.send_photo(chat_id=GROUP_CHAT_ID, photo=file_id, caption=message)
    elif message_type == "video":
        message = f"#{user_number} (Репутация: {reputation}):"
        context.bot.send_video(chat_id=GROUP_CHAT_ID, video=file_id, caption=message)
    elif message_type == "voice":
        message = f"#{user_number} (Репутация: {reputation}):"
        context.bot.send_voice(chat_id=GROUP_CHAT_ID, voice=file_id, caption=message)

    # Увеличиваем репутацию, если пользователь доверенный
    if is_trusted(user_id):
        cursor.execute("UPDATE users SET reputation = reputation + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

    conn.close()

# Обработчик текстовых сообщений
def handle_text(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name

    # Обновляем информацию о пользователе
    update_user_info(user_id, username, first_name, last_name)

    if is_banned(user_id):
        update.message.reply_text("Вы забанены и не можете отправлять сообщения.")
        return

    if contains_stop_words(update.message.text):
        update.message.reply_text("Ваше сообщение содержит запрещенные слова.")
        return

    if not is_trusted(user_id):
        # Получаем информацию о пользователе
        user_info = get_user_info_by_id(user_id)
        if user_info:
            # Формируем сообщение для модерации
            message = (
                f"Новое сообщение на модерацию:\n"
                f"Номер: #{user_info['anonymous_number']}\n"
                f"ID: {user_info['user_id']}\n"
                f"Имя: {user_info['first_name']}\n"
                f"Фамилия: {user_info['last_name']}\n"
                f"Ник: @{user_info['username']}\n"
                f"Репутация: {user_info['reputation']}\n"
                f"Сообщение:\n{update.message.text}"
            )
            # Отправляем сообщение администратору
            context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
            update.message.reply_text("Ваше сообщение отправлено на модерацию.")
        else:
            update.message.reply_text("Ошибка: информация о пользователе не найдена.")
    else:
        # Публикация без модерации (для доверенных пользователей)
        publish_message(user_id, text=update.message.text)

# Обработчик медиа (фото, видео, голосовые)
def handle_media(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name

    # Обновляем информацию о пользователе
    update_user_info(user_id, username, first_name, last_name)

    if is_banned(user_id):
        update.message.reply_text("Вы забанены и не можете отправлять сообщения.")
        return

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        message_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        message_type = "video"
    elif update.message.voice:
        file_id = update.message.voice.file_id
        message_type = "voice"
    else:
        return

    if not is_trusted(user_id):
        # Получаем информацию о пользователе
        user_info = get_user_info_by_id(user_id)
        if user_info:
            # Формируем сообщение для модерации
            message = (
                f"Новое медиа на модерацию:\n"
                f"Номер: #{user_info['anonymous_number']}\n"
                f"ID: {user_info['user_id']}\n"
                f"Имя: {user_info['first_name']}\n"
                f"Фамилия: {user_info['last_name']}\n"
                f"Ник: @{user_info['username']}\n"
                f"Репутация: {user_info['reputation']}\n"
                f"Тип медиа: {message_type}"
            )
            # Отправляем сообщение администратору
            context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
            update.message.reply_text("Ваше медиа отправлено на модерацию.")
        else:
            update.message.reply_text("Ошибка: информация о пользователе не найдена.")
    else:
        # Публикация без модерации (для доверенных пользователей)
        publish_message(user_id, file_id=file_id, message_type=message_type)

# Панель администратора
def admin_panel(update: Update, context: CallbackContext):
    if update.message.from_user.id == ADMIN_USER_ID:
        keyboard = [
            [InlineKeyboardButton("Проверить пользователя по номеру", callback_data='check_user')],
            [InlineKeyboardButton("Изменить репутацию", callback_data='change_reputation')],
            [InlineKeyboardButton("Забанить/разбанить", callback_data='ban_unban')],
            [InlineKeyboardButton("Сделать доверенным/новичком", callback_data='trust_untrust')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Панель администратора:", reply_markup=reply_markup)

# Обработчик callback-запросов
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'check_user':
        query.edit_message_text(text="Введите номер пользователя (например, #12345):")
        context.user_data['action'] = 'check_user'
    elif query.data == 'change_reputation':
        query.edit_message_text(text="Введите номер пользователя и изменение репутации (например, #12345 +5):")
        context.user_data['action'] = 'change_reputation'
    elif query.data == 'ban_unban':
        query.edit_message_text(text="Введите номер пользователя (например, #12345):")
        context.user_data['action'] = 'ban_unban'
    elif query.data == 'trust_untrust':
        query.edit_message_text(text="Введите номер пользователя (например, #12345):")
        context.user_data['action'] = 'trust_untrust'

# Обработчик текстовых сообщений для админ-панели
def handle_admin_message(update: Update, context: CallbackContext):
    if update.message.from_user.id == ADMIN_USER_ID:
        action = context.user_data.get('action')

        if action == 'check_user':
            try:
                anonymous_number = int(update.message.text.strip('#'))
                user_info = get_user_info(anonymous_number)
                if user_info:
                    user_id, username, first_name, last_name, reputation = user_info
                    message = f"Номер: #{anonymous_number}\nID: {user_id}\n"
                    if first_name:
                        message += f"Имя: {first_name}\n"
                    if last_name:
                        message += f"Фамилия: {last_name}\n"
                    if username:
                        message += f"Ник: @{username}\n"
                    message += f"Репутация: {reputation}"
                    update.message.reply_text(message)
                else:
                    update.message.reply_text("Пользователь с таким номером не найден.")
            except ValueError:
                update.message.reply_text("Неверный формат номера. Введите номер в формате #12345.")

        elif action == 'change_reputation':
            try:
                parts = update.message.text.split()
                anonymous_number = int(parts[0].strip('#'))
                reputation_change = int(parts[1])
                user_info = get_user_info(anonymous_number)
                if user_info:
                    user_id = user_info[0]
                    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET reputation = reputation + ? WHERE user_id = ?", (reputation_change, user_id))
                    conn.commit()
                    conn.close()
                    update.message.reply_text(f"Репутация пользователя #{anonymous_number} изменена на {reputation_change}.")
                else:
                    update.message.reply_text("Пользователь с таким номером не найден.")
            except (IndexError, ValueError):
                update.message.reply_text("Используйте команду так: #12345 +5")

        elif action == 'ban_unban':
            try:
                anonymous_number = int(update.message.text.strip('#'))
                user_info = get_user_info(anonymous_number)
                if user_info:
                    user_id = user_info[0]
                    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
                    is_banned = cursor.fetchone()[0]
                    new_status = 0 if is_banned else 1
                    cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (new_status, user_id))
                    conn.commit()
                    conn.close()
                    status_text = "забанен" if new_status else "разбанен"
                    update.message.reply_text(f"Пользователь #{anonymous_number} {status_text}.")
                else:
                    update.message.reply_text("Пользователь с таким номером не найден.")
            except ValueError:
                update.message.reply_text("Неверный формат номера. Введите номер в формате #12345.")

        elif action == 'trust_untrust':
            try:
                anonymous_number = int(update.message.text.strip('#'))
                user_info = get_user_info(anonymous_number)
                if user_info:
                    user_id = user_info[0]
                    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute("SELECT is_trusted FROM users WHERE user_id = ?", (user_id,))
                    is_trusted = cursor.fetchone()[0]
                    new_status = 0 if is_trusted else 1
                    cursor.execute("UPDATE users SET is_trusted = ? WHERE user_id = ?", (new_status, user_id))
                    conn.commit()
                    conn.close()
                    status_text = "доверенный" if new_status else "новичок"
                    update.message.reply_text(f"Пользователь #{anonymous_number} теперь {status_text}.")
                else:
                    update.message.reply_text("Пользователь с таким номером не найден.")
            except ValueError:
                update.message.reply_text("Неверный формат номера. Введите номер в формате #12345.")

# Основная функция
import root_bot
from some_module import some_function

def main():
    init_db()  # Инициализация базы данных
    updater = Updater("YOUR_BOT_TOKEN", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.photo | Filters.video | Filters.voice, handle_media))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_admin_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
