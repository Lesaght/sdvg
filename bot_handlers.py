import os
import logging
from telebot import types
from config import SAVE_FOLDER, SUPPORTED_PHOTO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS, FILES_PER_PAGE

logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """Сделать имя файла безопасным для сохранения в файловой системе."""
    # Заменить проблемные символы
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Ограничить длину
    if len(filename) > 100:
        base, ext = os.path.splitext(filename)
        filename = base[:96] + ext
        
    return filename

def get_file_type(file_path):
    """Определить тип файла по его расширению."""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext in SUPPORTED_PHOTO_EXTENSIONS:
        return "photo"
    elif ext in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    else:
        return "document"

def get_file_list(folder_path):
    """Получить список всех файлов в папке."""
    try:
        if not os.path.exists(folder_path):
            return []
            
        # Получить все файлы
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)
        
        # Сортировать по времени изменения (сначала новые)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        return files
    
    except Exception as e:
        logger.error(f"Ошибка при получении списка файлов: {e}")
        return []

def save_file(bot, file_info, save_folder, file_name):
    """Загрузить и сохранить файл, отправленный пользователем."""
    try:
        # Создать папку сохранения, если она не существует
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
            logger.info(f"Создана папка сохранения: {save_folder}")
        
        # Создать безопасное имя файла
        safe_name = sanitize_filename(file_name)
        
        # Подготовить полный путь к файлу
        file_path = os.path.join(save_folder, safe_name)
        
        # Проверить, существует ли файл с таким же именем
        if os.path.exists(file_path):
            base_name, ext = os.path.splitext(safe_name)
            count = 1
            while os.path.exists(file_path):
                new_name = f"{base_name}_{count}{ext}"
                file_path = os.path.join(save_folder, new_name)
                count += 1
        
        # Скачать файл
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохранить файл
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        return file_path
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {e}")
        return None

def start(bot, message):
    """Отправить сообщение при выполнении команды /start."""
    bot.reply_to(message, 
        f"Привет, {message.from_user.first_name}! Я бот для хранения файлов.\n\n"
        f"Вы можете отправлять мне любые файлы, и я сохраню их в папке на вашем компьютере.\n"
        f"Используйте /files для просмотра сохраненных фото и видео.\n"
        f"Используйте /help чтобы увидеть все доступные команды."
    )

def help_command(bot, message):
    """Отправить сообщение при выполнении команды /help."""
    bot.reply_to(message,
        "Вот что я умею:\n\n"
        "- Отправьте мне любой файл, фото или видео, чтобы сохранить его\n"
        "- Используйте /files для просмотра сохраненных фото и видео\n"
        "- При просмотре используйте кнопки навигации для просмотра большего количества файлов\n"
        "- Нажмите на файл, чтобы просмотреть его\n\n"
        "Все файлы сохраняются в папке на вашем компьютере."
    )

def files_command(bot, message):
    """Показать список сохраненных файлов при выполнении команды /files."""
    show_files(bot, message, 0)

def show_files(bot, message, page=0, edit=False):
    """Показать список сохраненных файлов с пагинацией."""
    # Получить список файлов
    all_files = get_file_list(SAVE_FOLDER)
    
    # Отфильтровать поддерживаемые медиа-файлы
    media_files = [f for f in all_files if get_file_type(f) in ['photo', 'video']]
    
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
            file_type = get_file_type(file)
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

def view_file(bot, call, file_path):
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
    
    file_type = get_file_type(file_path)
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

def button_handler(bot, call):
    """Обработать нажатия кнопок."""
    bot.answer_callback_query(call.id)
    
    data = call.data
    
    if data == "files":
        show_files(bot, call.message)
    elif data.startswith("page:"):
        page = int(data.split(":")[1])
        show_files(bot, call, page, edit=True)
    elif data.startswith("view:"):
        file_path = data[5:]  # Удалить префикс "view:"
        view_file(bot, call, file_path)
    else:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Неизвестная кнопка: {data}"
        )

def receive_file(bot, message):
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
        file_path = save_file(bot, file_info, SAVE_FOLDER, file_name)
        
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

def unknown_command(bot, message):
    """Обработать неизвестные команды и сообщения."""
    bot.reply_to(message, "Извините, я не понял эту команду. Используйте /help, чтобы увидеть доступные команды.")