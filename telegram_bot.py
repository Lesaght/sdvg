import logging
import os
import sys
import telebot
from telebot import types
from config import BOT_TOKEN, SAVE_FOLDER, SUPPORTED_PHOTO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS, FILES_PER_PAGE
import file_utils

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка токена бота
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не установлен!")
    sys.exit(1)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    """Отправить сообщение при выполнении команды /start."""
    bot.reply_to(message, 
        f"Привет, {message.from_user.first_name}! Я бот для хранения файлов.\n\n"
        f"Вы можете отправлять мне любые файлы, и я сохраню их в папке на вашем компьютере.\n"
        f"Используйте /files для просмотра сохраненных фото и видео.\n"
        f"Используйте /help чтобы увидеть все доступные команды."
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    """Отправить сообщение при выполнении команды /help."""
    bot.reply_to(message,
        "Вот что я умею:\n\n"
        "- Отправьте мне любой файл, фото или видео, чтобы сохранить его\n"
        "- Используйте /files для просмотра сохраненных фото и видео\n"
        "- При просмотре используйте кнопки навигации для просмотра большего количества файлов\n"
        "- Нажмите на файл, чтобы просмотреть его\n\n"
        "Все файлы сохраняются в папке на вашем компьютере."
    )

@bot.message_handler(commands=['files'])
def files_command(message):
    """Показать список сохраненных файлов при выполнении команды /files."""
    show_files(message, 0)

def show_files(message, page=0, edit=False):
    """Показать список сохраненных файлов с пагинацией."""
    # Получить список файлов
    all_files = file_utils.get_file_list(SAVE_FOLDER)
    
    # Отфильтровать поддерживаемые медиа-файлы
    media_files = [f for f in all_files if file_utils.get_file_type(f, SUPPORTED_PHOTO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS) in ['photo', 'video']]
    
    if not media_files:
        text = "В папке хранения не найдено медиа-файлов."
        markup = None
    else:
        # Рассчитать пагинацию
        start_idx = page * FILES_PER_PAGE
        end_idx = start_idx + FILES_PER_PAGE
        current_files = media_files[start_idx:end_idx]
        
        # Создать сообщение и клавиатуру
        text = f"📁 Ваши сохраненные файлы (Страница {page+1}/{max(1, (len(media_files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE)}):"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for file in current_files:
            file_type = file_utils.get_file_type(file, SUPPORTED_PHOTO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS)
            icon = "🖼️" if file_type == "photo" else "🎬"
            display_name = os.path.basename(file)
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            
            markup.add(
                types.InlineKeyboardButton(f"{icon} {display_name}", callback_data=f"view:{file}")
            )
        
        # Добавить кнопки навигации
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                types.InlineKeyboardButton("⬅️ Предыдущая", callback_data=f"page:{page-1}")
            )
            
        if end_idx < len(media_files):
            nav_buttons.append(
                types.InlineKeyboardButton("Следующая ➡️", callback_data=f"page:{page+1}")
            )
            
        if nav_buttons:
            markup.row(*nav_buttons)
    
    # Отправить или отредактировать сообщение
    if edit and hasattr(message, 'message'):
        bot.edit_message_text(
            chat_id=message.message.chat.id,
            message_id=message.message.message_id,
            text=text,
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=markup
        )

def view_file(call, file_path):
    """Отправить файл пользователю для просмотра."""
    if not os.path.exists(file_path):
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Этот файл больше не существует."
        )
        return
    
    file_size = os.path.getsize(file_path)
    # Telegram имеет ограничение 50 МБ для ботов
    if file_size > 50 * 1024 * 1024:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Этот файл слишком большой для отправки (Размер: {file_size/(1024*1024):.1f} МБ, Максимум: 50 МБ)."
        )
        return
    
    file_type = file_utils.get_file_type(file_path, SUPPORTED_PHOTO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS)
    file_name = os.path.basename(file_path)
    
    # Создать кнопку назад
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Вернуться к списку", callback_data="files"))
    
    try:
        # Отправить файл
        if file_type == "photo":
            with open(file_path, 'rb') as file:
                bot.send_photo(
                    chat_id=call.message.chat.id,
                    photo=file,
                    caption=f"📄 {file_name}",
                    reply_markup=markup
                )
        elif file_type == "video":
            with open(file_path, 'rb') as file:
                bot.send_video(
                    chat_id=call.message.chat.id,
                    video=file,
                    caption=f"📄 {file_name}",
                    reply_markup=markup
                )
        else:
            with open(file_path, 'rb') as file:
                bot.send_document(
                    chat_id=call.message.chat.id,
                    document=file,
                    caption=f"📄 {file_name}",
                    reply_markup=markup
                )
            
        # Отредактировать исходное сообщение, чтобы показать, что файл отправлен
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Отправлен файл: {file_name}\nИспользуйте кнопки под файлом, чтобы вернуться назад.",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка отправки файла {file_path}: {e}")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Ошибка отправки файла: {str(e)}",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    """Обработать нажатия кнопок."""
    bot.answer_callback_query(call.id)
    
    data = call.data
    
    if data == "files":
        show_files(call.message)
    elif data.startswith("page:"):
        page = int(data.split(":")[1])
        show_files(call, page, edit=True)
    elif data.startswith("view:"):
        file_path = data[5:]  # Удалить префикс "view:"
        view_file(call, file_path)
    else:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Неизвестная кнопка: {data}"
        )

@bot.message_handler(content_types=['photo', 'video', 'document'])
def receive_file(message):
    """Получить и сохранить файл, отправленный пользователем."""
    try:
        # Определить, какой тип файла был отправлен
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)  # Получить фото наибольшего размера
            file_name = f"photo_{message.photo[-1].file_id}.jpg"
            file_type = "фото"
        elif message.content_type == 'video':
            file_info = bot.get_file(message.video.file_id)
            file_name = getattr(message.video, 'file_name', None) or f"video_{message.video.file_id}.mp4"
            file_type = "видео"
        elif message.content_type == 'document':
            file_info = bot.get_file(message.document.file_id)
            file_name = getattr(message.document, 'file_name', None) or f"doc_{message.document.file_id}"
            file_type = "документ"
        else:
            bot.reply_to(message, "Я могу сохранять только фото, видео и документы.")
            return

        # Отправить сообщение о обработке
        status_message = bot.reply_to(message, f"Обрабатываю ваш {file_type}...")
        
        # Сохраняем файл
        file_path = file_utils.save_file(bot, file_info, SAVE_FOLDER, file_name)
        
        if file_path and os.path.exists(file_path):
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"Ваш {file_type} был успешно сохранен!"
            )
            logger.info(f"Файл сохранен по пути {file_path}")
        else:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"Не удалось сохранить ваш {file_type}. Пожалуйста, попробуйте еще раз."
            )
            logger.error(f"Не удалось сохранить файл {file_name}")
            
    except Exception as e:
        logger.error(f"Ошибка в receive_file: {e}")
        bot.reply_to(message, f"Произошла ошибка при сохранении вашего файла: {str(e)}")

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    """Обработать неизвестные команды и сообщения."""
    bot.reply_to(message, "Извините, я не понял эту команду. Используйте /help, чтобы увидеть доступные команды.")

def main():
    """Запустить бота."""
    # Создать папку сохранения, если она не существует
    if not os.path.exists(SAVE_FOLDER):
        os.makedirs(SAVE_FOLDER)
        logger.info(f"Создана папка сохранения: {SAVE_FOLDER}")

    logger.info("Запуск бота...")
    print(f"Запуск бота с токеном {BOT_TOKEN[:5]}...")
    
    try:
        # Запуск бота в режиме polling (опрос)
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()