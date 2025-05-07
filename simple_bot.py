#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import logging
import datetime
import zipfile
import tempfile
import shutil

# Пытаемся импортировать telebot (PyTelegramBotAPI)
try:
    from telebot import TeleBot, types
except ImportError:
    try:
        # Альтернативный вариант импорта
        import telebot
        from telebot import types
        TeleBot = telebot.TeleBot
    except ImportError:
        print("ОШИБКА: Не удалось импортировать библиотеку telebot!")
        print("Установите библиотеку PyTelegramBotAPI: pip install pytelegrambotapi")
        sys.exit(1)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Токен бота из переменной окружения
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не установлен!")
    sys.exit(1)

# Папка, где будут сохраняться файлы
SAVE_FOLDER = "saved_files"

# Словарь для кэширования путей файлов (для операций удаления)
# Ключ: короткий идентификатор, Значение: полный путь к файлу
file_path_cache = {}
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)
    logger.info(f"Создана папка сохранения: {SAVE_FOLDER}")

# Базовая папка для хранения пользовательских файлов
USER_FILES_BASE_FOLDER = os.path.join(SAVE_FOLDER, "users")

# Создаем базовую папку для пользовательских файлов
if not os.path.exists(USER_FILES_BASE_FOLDER):
    os.makedirs(USER_FILES_BASE_FOLDER)
    logger.info(f"Создана папка для пользовательских файлов: {USER_FILES_BASE_FOLDER}")

# Организация общих файлов по типам (для обратной совместимости)
PHOTOS_FOLDER = os.path.join(SAVE_FOLDER, "photos")
VIDEOS_FOLDER = os.path.join(SAVE_FOLDER, "videos")
DOCS_FOLDER = os.path.join(SAVE_FOLDER, "documents")

# Создаем папки для разных типов файлов, если они не существуют
for folder in [PHOTOS_FOLDER, VIDEOS_FOLDER, DOCS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"Создана папка: {folder}")
        
# Словарь для хранения состояний пользователей (ожидание ввода пароля)
user_states = {}

# Функция для получения путей к папкам конкретного пользователя
def get_user_folders(user_id):
    """
    Получить пути к папкам определенного пользователя.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Кортеж (photos_folder, videos_folder, docs_folder, user_folder)
    """
    user_id_str = str(user_id)
    user_folder = os.path.join(USER_FILES_BASE_FOLDER, user_id_str)
    
    # Создаем основную папку пользователя, если ее нет
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
        
    # Папки для разных типов файлов
    photos_folder = os.path.join(user_folder, "photos")
    videos_folder = os.path.join(user_folder, "videos")
    docs_folder = os.path.join(user_folder, "documents")
    
    # Создаем подпапки для типов файлов, если их нет
    for folder in [photos_folder, videos_folder, docs_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            
    return photos_folder, videos_folder, docs_folder, user_folder

# Поддерживаемые типы файлов
SUPPORTED_PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']

# Максимальное количество файлов на одной странице
FILES_PER_PAGE = 5

# Инициализация бота с increased_timeout для больших файлов
try:
    # Пробуем использовать TeleBot из импорта
    bot = TeleBot(BOT_TOKEN, threaded=True, parse_mode="HTML")
    logger.info("Инициализирован бот с помощью TeleBot")
except Exception as e:
    logger.error(f"Ошибка при инициализации бота: {e}")
    try:
        # Пробуем альтернативный вариант
        import telebot
        bot = telebot.TeleBot(BOT_TOKEN, threaded=True, parse_mode="HTML")
        logger.info("Инициализирован бот с помощью telebot.TeleBot")
    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации бота: {e}")
        sys.exit(1)

# Функция-декоратор для проверки верификации пользователя
def require_verification(func):
    """Декоратор для проверки верификации пользователя перед выполнением команды."""
    def wrapper(message, *args, **kwargs):
        from user_storage import user_storage
        
        # Если пользователь не верифицирован, запрашиваем пароль
        if not user_storage.is_user_verified(message.from_user.id):
            # Регистрируем пользователя, если еще не зарегистрирован
            user_storage.register_user(
                message.from_user.id, 
                message.from_user.username or f"user_{message.from_user.id}", 
                message.from_user.first_name
            )
            
            # Запрашиваем у пользователя пароль для первого входа
            user_states[message.from_user.id] = "waiting_for_password"
            bot.send_message(
                message.chat.id,
                "🔐 <b>Требуется верификация</b>\n\n"
                "Чтобы использовать эту команду, необходимо ввести специальный пароль для доступа к функциям бота.\n\n"
                "<i>Если вы не знаете пароль, обратитесь к администратору бота.</i>",
                parse_mode="HTML"
            )
            return  # Прерываем выполнение функции до ввода пароля
        
        # Если пользователь верифицирован, выполняем команду
        return func(message, *args, **kwargs)
    
    return wrapper

# Функции для обработки файлов
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
            os.makedirs(folder_path)
            logger.info(f"Создана папка сохранения: {folder_path}")
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

def create_zip_archive(files, user_id, archive_type="all"):
    """
    Создать ZIP-архив с выбранными файлами пользователя.
    
    Args:
        files: Список путей к файлам для добавления в архив
        user_id: ID пользователя
        archive_type: Тип создаваемого архива ("all", "photos", "videos", "documents")
        
    Returns:
        Путь к созданному архиву
    """
    temp_dir = None
    try:
        # Проверяем, что есть файлы для архивации
        if not files:
            logger.warning(f"Нет файлов для создания архива для пользователя {user_id}")
            return None
        
        # Создаем временную директорию для архива
        temp_dir = tempfile.mkdtemp()
        archive_name = f"user_{user_id}_{archive_type}_{int(time.time())}.zip"
        archive_path = os.path.join(temp_dir, archive_name)
        
        # Логируем информацию о создании архива
        logger.info(f"Создание архива {archive_path} с {len(files)} файлами")
        
        # Создаем ZIP-архив
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                if not os.path.exists(file_path):
                    logger.warning(f"Файл {file_path} не существует, пропускаем")
                    continue
                
                # Добавляем файл в архив с путем относительно базовой директории
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname=arcname)
                logger.debug(f"Добавлен файл {arcname} в архив")
        
        # Проверяем, что архив создан успешно
        if not os.path.exists(archive_path):
            logger.error(f"Архив {archive_path} не был создан")
            return None
        
        # Получаем размер архива
        archive_size = os.path.getsize(archive_path)
        logger.info(f"Архив создан успешно, размер: {archive_size / (1024*1024):.2f} МБ")
        
        return archive_path
    except Exception as e:
        logger.error(f"Ошибка при создании архива: {e}")
        # Удаляем временную директорию в случае ошибки
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None

def save_file(file_info, save_folder, file_name):
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

# Команды бота
@bot.message_handler(commands=['start'])
def start(message):
    """Отправить приветственное сообщение с главным меню при выполнении команды /start."""
    # Проверяем, есть ли в команде параметры
    if message.text and len(message.text.split()) > 1:
        # Получаем параметры после /start
        args = message.text.split(maxsplit=1)[1]
        
        # Если параметр начинается с "share_", обрабатываем его как команду доступа к файлу
        if args.startswith("share_"):
            share_id = args[6:]  # Получаем ID после "share_"
            
            # Регистрируем пользователя
            from user_storage import user_storage
            user_storage.register_user(
                message.from_user.id, 
                message.from_user.username or f"user_{message.from_user.id}", 
                message.from_user.first_name
            )
            
            # Получаем доступ к файлу
            file_info = user_storage.access_shared_file(share_id, message.from_user.id)
            
            if not file_info:
                bot.send_message(
                    message.chat.id,
                    "❌ <b>Файл не найден или ссылка недействительна.</b>\n\nВозможно, срок действия ссылки истек или файл был удален.",
                    parse_mode="HTML"
                )
                # После сообщения об ошибке, показываем стандартное меню
            else:
                # Создаем клавиатуру с кнопками
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📥 Полученные файлы", callback_data="cmd:received"),
                    types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                )
                
                # Отправляем сообщение о успешном получении файла
                file_name = file_info["file_name"]
                file_type = file_info["file_type"]
                file_path = file_info["file_path"]
                
                # Определяем иконку для типа файла
                icon = "🖼️" if file_type == "photo" else "🎬" if file_type == "video" else "📄"
                
                # Получаем информацию о владельце
                owner_id = file_info["owner_id"]
                owner = user_storage.get_user(owner_id)
                owner_name = owner["first_name"] if owner else "Неизвестный"
                
                # Отправляем сообщение о успешном получении файла
                status_message = bot.send_message(
                    message.chat.id,
                    f"✅ <b>Вы получили доступ к файлу!</b>\n\n"
                    f"📋 <b>Информация о файле:</b>\n"
                    f"• <b>Название:</b> {file_name}\n"
                    f"• <b>Тип:</b> {file_type.capitalize()}\n"
                    f"• <b>Владелец:</b> {owner_name}\n\n"
                    f"⏳ <b>Загрузка файла...</b>",
                    parse_mode="HTML"
                )
                
                # Получаем размер файла
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                file_size_str = f"{file_size_mb:.2f} МБ" if file_size_mb >= 1 else f"{file_size_mb * 1024:.2f} КБ"
                
                # Отправляем файл в зависимости от типа
                try:
                    if file_type == "photo":
                        with open(file_path, 'rb') as file:
                            sent_message = bot.send_photo(
                                chat_id=message.chat.id,
                                photo=file,
                                caption=f"{icon} <b>Файл:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}\n👤 <b>От:</b> {owner_name}",
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                    elif file_type == "video":
                        with open(file_path, 'rb') as file:
                            sent_message = bot.send_video(
                                chat_id=message.chat.id,
                                video=file,
                                caption=f"{icon} <b>Файл:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}\n👤 <b>От:</b> {owner_name}",
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                    else:
                        with open(file_path, 'rb') as file:
                            sent_message = bot.send_document(
                                chat_id=message.chat.id,
                                document=file,
                                caption=f"{icon} <b>Файл:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}\n👤 <b>От:</b> {owner_name}",
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                    
                    # Обновляем статус
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=status_message.message_id,
                        text=f"✅ <b>Файл успешно получен!</b>\n\n"
                        f"📋 <b>Информация о файле:</b>\n"
                        f"• <b>Название:</b> {file_name}\n"
                        f"• <b>Тип:</b> {file_type.capitalize()}\n"
                        f"• <b>Размер:</b> {file_size_str}\n"
                        f"• <b>Владелец:</b> {owner_name}\n\n"
                        f"Файл был добавлен в ваш список полученных файлов.",
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                    
                    logger.info(f"Пользователь {message.from_user.id} получил доступ к файлу {file_name} (ID: {share_id})")
                    return  # Выходим из функции, не показывая главное меню
                
                except Exception as e:
                    logger.error(f"Ошибка при отправке файла: {e}")
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=status_message.message_id,
                        text=f"❌ <b>Ошибка при отправке файла.</b>\n\nФайл существует, но возникла проблема при его отправке: {str(e)}",
                        parse_mode="HTML"
                    )
    
    # Если нет параметров или они не относятся к доступу файла, показываем соответствующее меню
    # Регистрация пользователя в системе обмена файлами
    from user_storage import user_storage
    user = user_storage.register_user(
        message.from_user.id, 
        message.from_user.username or f"user_{message.from_user.id}", 
        message.from_user.first_name
    )
    
    # Проверяем, верифицирован ли пользователь
    if not user_storage.is_user_verified(message.from_user.id):
        # Запрашиваем у пользователя пароль для первого входа
        user_states[message.from_user.id] = "waiting_for_password"
        bot.send_message(
            message.chat.id,
            "🔐 <b>Требуется верификация</b>\n\n"
            "Это ваш первый вход в бот. Пожалуйста, введите специальный пароль для доступа к функциям бота.\n\n"
            "<i>Если вы не знаете пароль, обратитесь к администратору бота.</i>",
            parse_mode="HTML"
        )
        return  # Прерываем выполнение функции до ввода пароля
    
    # Пользователь верифицирован, показываем главное меню
    # Создаем красивую разметку с кнопками главного меню
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки для разных типов файлов
    btn_photos = types.InlineKeyboardButton("🖼️ Фотографии", callback_data="cmd:photos")
    btn_videos = types.InlineKeyboardButton("🎬 Видеофайлы", callback_data="cmd:videos")
    btn_docs = types.InlineKeyboardButton("📄 Документы", callback_data="cmd:documents")
    btn_all_files = types.InlineKeyboardButton("📁 Все файлы", callback_data="files")
    
    # Кнопки обмена файлами
    btn_shared_files = types.InlineKeyboardButton("📤 Мои общие файлы", callback_data="cmd:myshared")
    btn_received_files = types.InlineKeyboardButton("📥 Полученные файлы", callback_data="cmd:received")
    
    # Кнопка скачивания архива
    btn_download_zip = types.InlineKeyboardButton("🗃️ Скачать ZIP-архив", callback_data="cmd:download_zip")
    
    # Кнопки функций
    btn_help = types.InlineKeyboardButton("❓ Помощь", callback_data="cmd:help")
    btn_info = types.InlineKeyboardButton("ℹ️ О боте", callback_data="cmd:about")
    
    # Добавляем кнопки в разметку
    markup.add(btn_photos, btn_videos)
    markup.add(btn_docs, btn_all_files)
    markup.add(btn_shared_files, btn_received_files)
    markup.add(btn_download_zip)
    markup.add(btn_help, btn_info)
    
    # Информационный баннер с инструкцией
    upload_banner = "📤 Отправьте мне файл, чтобы сохранить его!"
    
    # Отправляем приветственное сообщение с кнопками
    bot.send_message(
        message.chat.id,
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"🤖 Я <b>File Storage Bot</b> - ваш помощник для хранения и организации файлов.\n\n"
        f"📌 <b>Основные возможности:</b>\n"
        f"• Сохранение фото, видео и документов\n"
        f"• Удобная организация по категориям\n"
        f"• Простой поиск и просмотр\n"
        f"• Обмен файлами с другими пользователями\n"
        f"• Скачивание всех файлов в ZIP-архиве\n\n"
        f"{upload_banner}",
        parse_mode="HTML",
        reply_markup=markup
    )
    
    # Регистрируем пользователя в логах
    logger.info(f"Пользователь {message.from_user.first_name} ({message.from_user.id}) начал использование бота")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Отправить подробную справку с интерактивными кнопками."""
    # Создаем клавиатуру с кнопками
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки разделов файлов
    btn_photos = types.InlineKeyboardButton("🖼️ Просмотр фото", callback_data="cmd:photos")
    btn_videos = types.InlineKeyboardButton("🎬 Просмотр видео", callback_data="cmd:videos")
    btn_docs = types.InlineKeyboardButton("📄 Просмотр документов", callback_data="cmd:documents")
    btn_all = types.InlineKeyboardButton("📁 Все файлы", callback_data="files")
    
    # Кнопки обмена файлами
    btn_shared = types.InlineKeyboardButton("📤 Мои общие файлы", callback_data="cmd:myshared")
    btn_received = types.InlineKeyboardButton("📥 Полученные файлы", callback_data="cmd:received")
    
    # Кнопка возврата в главное меню
    btn_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
    
    # Добавляем кнопку скачивания архива
    btn_download_zip = types.InlineKeyboardButton("🗃️ Скачать ZIP-архив", callback_data="cmd:download_zip")
    
    # Формируем разметку кнопок
    markup.add(btn_photos, btn_videos)
    markup.add(btn_docs, btn_all)
    markup.add(btn_shared, btn_received)
    markup.add(btn_download_zip)
    markup.add(btn_menu)
    
    # Отправляем сообщение помощи с форматированием HTML
    bot.send_message(
        message.chat.id,
        "<b>📚 Справка по использованию бота</b>\n\n"
        "<b>📋 Доступные команды:</b>\n"
        "• /start - Запустить бота и показать главное меню\n"
        "• /help - Показать эту справку\n"
        "• /files - Показать все сохраненные файлы\n"
        "• /photos - Показать только фотографии\n"
        "• /videos - Показать только видеофайлы\n"
        "• /documents - Показать только документы\n"
        "• /share_ID - Получить доступ к общему файлу\n\n"
        
        "<b>💾 Как сохранить файл:</b>\n"
        "Просто отправьте мне фото, видео или документ, и я автоматически сохраню его в соответствующей категории.\n\n"
        
        "<b>🔍 Как найти файлы:</b>\n"
        "Используйте кнопки ниже для просмотра файлов по категориям. При просмотре доступны кнопки навигации и фильтрации.\n\n"
        
        "<b>📤 Обмен файлами:</b>\n"
        "1. Откройте файл через меню просмотра файлов\n"
        "2. Нажмите кнопку \"Поделиться файлом\"\n"
        "3. Отправьте полученную команду другому пользователю\n"
        "4. Пользователь может получить доступ к файлу, отправив эту команду боту\n\n"
        
        "<b>✨ Дополнительные возможности:</b>\n"
        "• Просмотр подробной информации о файле\n"
        "• Удобная навигация между категориями\n"
        "• Обмен файлами между пользователями\n"
        "• Управление своими общими файлами\n"
        "• Скачивание всех файлов в ZIP-архиве",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(commands=['files'])
@require_verification
def files_command(message):
    """Показать список сохраненных файлов при выполнении команды /files."""
    show_files(message, 0)

@bot.message_handler(commands=['photos'])
@require_verification
def photos_command(message):
    """Показать список сохраненных фотографий."""
    show_files(message, 0, file_type="photo")

@bot.message_handler(commands=['videos'])
@require_verification
def videos_command(message):
    """Показать список сохраненных видео."""
    show_files(message, 0, file_type="video")

@bot.message_handler(commands=['documents'])
@require_verification
def documents_command(message):
    """Показать список сохраненных документов."""
    show_files(message, 0, file_type="document")

@bot.message_handler(commands=['menu'])
def menu_command(message):
    """Показать главное меню."""
    # Переиспользуем функцию start для отображения главного меню
    start(message)

@bot.message_handler(commands=['about'])
def about_command(message):
    """Показать информацию о боте."""
    # Создаем клавиатуру с кнопками
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"),
        types.InlineKeyboardButton("📚 Справка", callback_data="cmd:help")
    )
    
    # Получаем статистику
    photos_count = len(get_file_list(PHOTOS_FOLDER))
    videos_count = len(get_file_list(VIDEOS_FOLDER))
    docs_count = len(get_file_list(DOCS_FOLDER))
    total_count = photos_count + videos_count + docs_count
    
    # Регистрация пользователя в системе обмена файлами
    from user_storage import user_storage
    user = user_storage.register_user(
        message.from_user.id, 
        message.from_user.username or f"user_{message.from_user.id}", 
        message.from_user.first_name
    )
    
    # Получаем статистику по обмену файлами
    shared_files = user_storage.get_user_shared_files(message.from_user.id)
    received_files = user_storage.get_user_received_files(message.from_user.id)
    
    # Отправляем информацию о боте
    bot.send_message(
        message.chat.id,
        f"<b>🤖 File Storage Bot v1.0</b>\n\n"
        f"<b>О боте:</b>\n"
        f"Бот для хранения и организации файлов в удобном формате.\n\n"
        
        f"<b>📊 Статистика файлов:</b>\n"
        f"• 🖼️ Фотографии: {photos_count}\n"
        f"• 🎬 Видеофайлы: {videos_count}\n"
        f"• 📄 Документы: {docs_count}\n"
        f"• 📁 Всего файлов: {total_count}\n\n"
        
        f"<b>🔄 Обмен файлами:</b>\n"
        f"• 📤 Вы поделились: {len(shared_files)} файлами\n"
        f"• 📥 Вы получили: {len(received_files)} файлов\n\n"
        
        f"<b>💻 Техническая информация:</b>\n"
        f"• Разработан с использованием pyTelegramBotAPI\n"
        f"• Имеет удобную категоризацию файлов\n"
        f"• Поддерживает фото, видео и документы\n"
        f"• Поддерживает обмен файлами\n"
        f"• Скачивание всех файлов в ZIP-архиве\n"
        f"• Максимальный размер файла: 50 МБ\n\n"
        
        f"<b>Используйте /help для получения справки по командам.</b>",
        parse_mode="HTML",
        reply_markup=markup
    )

def show_files(message, page=0, edit=False, file_type=None):
    """Показать список сохраненных файлов с пагинацией."""
    # Получаем ID пользователя
    user_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
    
    # Получаем пользовательские папки
    user_photos_folder, user_videos_folder, user_docs_folder, _ = get_user_folders(user_id)
    
    # Получить список файлов
    all_files = []
    
    # Если указан конкретный тип файла
    if file_type == "photo":
        all_files = get_file_list(user_photos_folder)  # Используем папку пользователя
        header = "🖼️ <b>Ваши фотографии</b>"
        empty_text = "В вашей папке не найдено фотографий."
    elif file_type == "video":
        all_files = get_file_list(user_videos_folder)  # Используем папку пользователя
        header = "🎬 <b>Ваши видео</b>"
        empty_text = "В вашей папке не найдено видеофайлов."
    elif file_type == "document":
        all_files = get_file_list(user_docs_folder)  # Используем папку пользователя
        header = "📄 <b>Ваши документы</b>"
        empty_text = "В вашей папке не найдено документов."
    else:
        # Получаем все файлы из папок пользователя
        for folder in [user_photos_folder, user_videos_folder, user_docs_folder]:
            all_files.extend(get_file_list(folder))
        header = "📁 <b>Ваши сохраненные файлы</b>"
        empty_text = "В вашем хранилище не найдено файлов."
    
    # Сортируем все файлы по дате изменения (новые сверху)
    all_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    if not all_files:
        text = empty_text
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📷 Фото", callback_data="cmd:photos"),
            types.InlineKeyboardButton("🎥 Видео", callback_data="cmd:videos"),
            types.InlineKeyboardButton("📑 Документы", callback_data="cmd:documents")
        )
    else:
        # Рассчитать пагинацию
        total_pages = max(1, (len(all_files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE)
        
        # Проверка, что страница в допустимом диапазоне
        if page >= total_pages:
            page = total_pages - 1
        if page < 0:
            page = 0
            
        start_idx = page * FILES_PER_PAGE
        end_idx = min(start_idx + FILES_PER_PAGE, len(all_files))
        current_files = all_files[start_idx:end_idx]
        
        # Создать сообщение и клавиатуру
        text = f"{header} (Страница {page+1}/{total_pages})\n\nВсего файлов: {len(all_files)}"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for file in current_files:
            current_type = get_file_type(file)
            icon = "🖼️" if current_type == "photo" else "🎬" if current_type == "video" else "📄"
            display_name = os.path.basename(file)
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            
            # Использовать более короткие идентификаторы для callback_data (Telegram имеет лимит 64 байта)
            short_path = f"{all_files.index(file)}"
            
            markup.add(
                types.InlineKeyboardButton(f"{icon} {display_name}", callback_data=f"view:{short_path}")
            )
        
        # Добавить кнопки фильтров
        filter_buttons = []
        filter_buttons.append(types.InlineKeyboardButton("📷 Фото", callback_data="cmd:photos"))
        filter_buttons.append(types.InlineKeyboardButton("🎥 Видео", callback_data="cmd:videos"))
        filter_buttons.append(types.InlineKeyboardButton("📑 Документы", callback_data="cmd:documents"))
        markup.row(*filter_buttons)
        
        # Добавить кнопки навигации
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                types.InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{page-1}:{file_type or 'all'}")
            )
            
        if end_idx < len(all_files):
            nav_buttons.append(
                types.InlineKeyboardButton("Вперед ➡️", callback_data=f"page:{page+1}:{file_type or 'all'}")
            )
            
        if nav_buttons:
            markup.row(*nav_buttons)
    
    # Сохраняем список файлов в глобальную переменную для доступа по индексу
    global file_list_cache
    file_list_cache = all_files
    
    # Отправить или отредактировать сообщение
    try:
        if edit and hasattr(message, 'message'):
            bot.edit_message_text(
                chat_id=message.message.chat.id,
                message_id=message.message.message_id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при отображении файлов: {e}")
        # Если ошибка связана с тем, что сообщение не изменилось
        if "message is not modified" in str(e).lower():
            pass  # Просто игнорируем
        else:
            # Пробуем отправить новое сообщение в случае других ошибок
            try:
                bot.send_message(
                    chat_id=message.chat.id if not hasattr(message, 'message') else message.message.chat.id,
                    text=f"Произошла ошибка при отображении файлов: {str(e)}"
                )
            except:
                pass

def view_file(call, file_path):
    """Отправить файл пользователю для просмотра."""
    try:
        if not os.path.exists(file_path):
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ <b>Этот файл больше не существует.</b>",
                parse_mode="HTML"
            )
            return
        
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        file_size_str = f"{file_size_mb:.2f} МБ" if file_size_mb >= 1 else f"{file_size_mb * 1024:.2f} КБ"
        
        # Telegram имеет ограничение 50 МБ для ботов
        if file_size > 50 * 1024 * 1024:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"⚠️ <b>Этот файл слишком большой для отправки</b>\n\n"
                    f"📦 Размер: {file_size_mb:.1f} МБ\n"
                    f"📏 Максимальный размер: 50 МБ\n\n"
                    f"Файлы, превышающие 50 МБ, нельзя отправить через Telegram Bot API."
                ),
                parse_mode="HTML"
            )
            return
        
        file_type = get_file_type(file_path)
        file_name = os.path.basename(file_path)
        
        # Создать клавиатуру с кнопками возврата
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Определяем раздел, чтобы вернуться к конкретному виду файлов
        back_section = "files"
        if "photos" in file_path:
            back_section = "cmd:photos"
        elif "videos" in file_path:
            back_section = "cmd:videos"
        elif "documents" in file_path:
            back_section = "cmd:documents"
        
        # Импортируем хранилище пользователей
        from user_storage import user_storage
        
        # Создаем ссылку для обмена файлом
        file_type = get_file_type(file_path)
        file_name = os.path.basename(file_path)
        share_id = user_storage.create_share_link(
            call.from_user.id,
            file_path,
            file_type,
            file_name
        )
        
        # Добавляем кнопки действий
        markup.add(types.InlineKeyboardButton("⬅️ Назад к списку", callback_data=back_section))
        
        # Добавляем кнопку "Поделиться", если файл в кэше
        if share_id:
            markup.add(types.InlineKeyboardButton("📤 Получить ссылку для обмена", callback_data=f"view_share:{share_id}"))
        
        # Добавляем кнопку удаления файла с использованием кэширования пути
        file_id = str(hash(file_path))[:8]  # Используем только первые 8 символов хеша как идентификатор
        file_path_cache[file_id] = file_path  # Сохраняем путь в кэше
        markup.add(types.InlineKeyboardButton("🗑️ Удалить файл", callback_data=f"delete_file:{file_id}"))
        
        # Сообщение о загрузке
        loading_message = bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⏳ <b>Загрузка файла...</b>\n\n📄 {file_name}\n📦 {file_size_str}",
            parse_mode="HTML"
        )
        
        # Отправить файл в зависимости от типа
        if file_type == "photo":
            with open(file_path, 'rb') as file:
                sent_message = bot.send_photo(
                    chat_id=call.message.chat.id,
                    photo=file,
                    caption=f"📷 <b>Фото:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}",
                    reply_markup=markup,
                    parse_mode="HTML"
                )
        elif file_type == "video":
            with open(file_path, 'rb') as file:
                sent_message = bot.send_video(
                    chat_id=call.message.chat.id,
                    video=file,
                    caption=f"🎬 <b>Видео:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}",
                    reply_markup=markup,
                    parse_mode="HTML"
                )
        else:
            with open(file_path, 'rb') as file:
                sent_message = bot.send_document(
                    chat_id=call.message.chat.id,
                    document=file,
                    caption=f"📄 <b>Документ:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}",
                    reply_markup=markup,
                    parse_mode="HTML"
                )
        
        # Получаем дату создания и изменения файла
        file_created = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getctime(file_path)))
        file_modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
        
        # Отредактировать исходное сообщение, чтобы показать информацию о файле
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"✅ <b>Файл отправлен:</b> {file_name}\n\n"
                f"📦 <b>Размер:</b> {file_size_str}\n"
                f"📅 <b>Создан:</b> {file_created}\n"
                f"🔄 <b>Изменен:</b> {file_modified}\n\n"
                f"📁 <b>Путь:</b> <code>{os.path.dirname(file_path)}</code>"
            ),
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка отправки файла {file_path}: {e}")
        try:
            # Пытаемся отправить сообщение об ошибке
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"❌ <b>Ошибка отправки файла</b>\n\n"
                    f"Файл: {os.path.basename(file_path) if file_path else 'Неизвестный'}\n"
                    f"Ошибка: <code>{str(e)}</code>"
                ),
                parse_mode="HTML"
            )
        except Exception as inner_error:
            # Если и это не получилось, пробуем отправить простое сообщение
            logger.error(f"Вторичная ошибка при отправке уведомления: {inner_error}")
            try:
                bot.send_message(
                    call.message.chat.id,
                    "Произошла ошибка при отправке файла. Пожалуйста, попробуйте снова позже."
                )
            except:
                pass

# Глобальная переменная для хранения списка файлов
file_list_cache = []

# Функции для обмена файлами
def share_file(call, file_index):
    """Поделиться файлом с другими пользователями."""
    try:
        # Получаем файл из кэша
        if 0 <= file_index < len(file_list_cache):
            file_path = file_list_cache[file_index]
            file_name = os.path.basename(file_path)
            file_type = get_file_type(file_path)
            
            # Импортируем хранилище пользователей
            from user_storage import user_storage
            
            # Создаем ссылку для обмена файлом
            share_id = user_storage.create_share_link(
                call.from_user.id,
                file_path,
                file_type,
                file_name
            )
            
            if not share_id:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="❌ <b>Ошибка при создании ссылки.</b> Пожалуйста, попробуйте снова.",
                    parse_mode="HTML"
                )
                return
            
            # Создаем клавиатуру с кнопками
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            # Добавляем кнопку для возврата
            markup.add(
                types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"),
                types.InlineKeyboardButton("📤 Мои общие файлы", callback_data="cmd:myshared")
            )
            
            # Создаем команду для быстрого доступа к файлу
            share_command = f"/share_{share_id}"
            
            # Отправляем информацию о созданной ссылке
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"✅ <b>Файл успешно опубликован!</b>\n\n"
                    f"📋 <b>Информация о файле:</b>\n"
                    f"• <b>Имя файла:</b> {file_name}\n"
                    f"• <b>Тип:</b> {file_type.capitalize()}\n"
                    f"• <b>ID публикации:</b> <code>{share_id}</code>\n\n"
                    f"🔗 <b>Ссылка для доступа:</b>\n"
                    f"<code>{share_command}</code>\n\n"
                    f"📝 <b>Инструкция:</b>\n"
                    f"Другие пользователи могут получить доступ к этому файлу, отправив боту команду выше."
                ),
                parse_mode="HTML",
                reply_markup=markup
            )
            
            logger.info(f"Пользователь {call.from_user.id} поделился файлом {file_name} (ID: {share_id})")
            
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ <b>Файл не найден.</b> Возможно, список файлов изменился.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при обмене файлом: {e}")
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"❌ <b>Произошла ошибка при обмене файлом.</b>\n\nОшибка: {str(e)}",
                parse_mode="HTML"
            )
        except:
            pass

def show_shared_files(call, page=0):
    """Показать список файлов, которыми поделился пользователь."""
    try:
        # Импортируем хранилище пользователей
        from user_storage import user_storage
        
        # Получаем список общих файлов пользователя
        shared_files = user_storage.get_user_shared_files(call.from_user.id)
        
        # Создаем разметку с кнопками
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if not shared_files:
            # Если нет общих файлов
            text = (
                "📤 <b>Мои общие файлы</b>\n\n"
                "У вас нет опубликованных файлов.\n\n"
                "Чтобы поделиться файлом, откройте его через меню просмотра файлов и нажмите на кнопку \"Поделиться\"."
            )
            
            markup.add(
                types.InlineKeyboardButton("📁 Просмотр всех файлов", callback_data="files"),
                types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
            )
            
            try:
                # Пытаемся редактировать сообщение
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error  # Переподнимаем другие ошибки
            return
        
        # Рассчитать пагинацию
        total_pages = max(1, (len(shared_files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE)
        
        # Проверка, что страница в допустимом диапазоне
        if page >= total_pages:
            page = total_pages - 1
        if page < 0:
            page = 0
        
        start_idx = page * FILES_PER_PAGE
        end_idx = min(start_idx + FILES_PER_PAGE, len(shared_files))
        current_files = shared_files[start_idx:end_idx]
        
        # Создаем заголовок сообщения
        text = f"📤 <b>Мои общие файлы</b> (Страница {page+1}/{total_pages})\n\nВсего опубликовано: {len(shared_files)}"
        
        # Добавляем кнопки для каждого файла
        for share in current_files:
            share_id = share["id"]
            file_info = share["info"]
            file_name = file_info["file_name"]
            file_type = file_info["file_type"]
            
            # Определяем иконку для типа файла
            icon = "🖼️" if file_type == "photo" else "🎬" if file_type == "video" else "📄"
            
            # Ограничиваем длину имени файла
            if len(file_name) > 30:
                file_name = file_name[:27] + "..."
            
            # Добавляем кнопку для просмотра файла
            markup.add(
                types.InlineKeyboardButton(f"{icon} {file_name}", callback_data=f"access_share:{share_id}")
            )
            
            # Добавляем кнопку для удаления публикации
            markup.add(
                types.InlineKeyboardButton(f"🗑️ Удалить публикацию", callback_data=f"cmd:delete_share:{share_id}")
            )
        
        # Добавляем кнопки навигации
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                types.InlineKeyboardButton("⬅️ Назад", callback_data=f"shared_page:{page-1}")
            )
        
        if end_idx < len(shared_files):
            nav_buttons.append(
                types.InlineKeyboardButton("Вперед ➡️", callback_data=f"shared_page:{page+1}")
            )
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        # Добавляем кнопку возврата в главное меню
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
        
        # Отправляем сообщение
        try:
            # Пытаемся редактировать сообщение
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            if "there is no text in the message to edit" in str(edit_error).lower():
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                raise edit_error  # Переподнимаем другие ошибки
    except Exception as e:
        logger.error(f"Ошибка при отображении общих файлов: {e}")
        try:
            # Если произошла другая ошибка, пытаемся показать сообщение об ошибке
            error_text = f"❌ <b>Произошла ошибка при отображении общих файлов.</b>\n\nПопробуйте еще раз."
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                    )
                )
            except:
                # Если редактирование не удалось, отправляем новое сообщение
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                    )
                )
        except:
            # В крайнем случае просто логируем ошибку
            logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")
            pass

def show_received_files(call, page=0):
    """Показать список файлов, полученных от других пользователей."""
    try:
        # Импортируем хранилище пользователей
        from user_storage import user_storage
        
        # Получаем список полученных файлов
        received_files = user_storage.get_user_received_files(call.from_user.id)
        
        # Создаем разметку с кнопками
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if not received_files:
            # Если нет полученных файлов
            text = (
                "📥 <b>Полученные файлы</b>\n\n"
                "У вас нет полученных файлов.\n\n"
                "Чтобы получить доступ к файлу, отправьте боту команду, полученную от другого пользователя."
            )
            
            # Добавляем кнопку возврата в главное меню
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                # Пытаемся редактировать сообщение
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error  # Переподнимаем другие ошибки
            return
        
        # Рассчитать пагинацию
        total_pages = max(1, (len(received_files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE)
        
        # Проверка, что страница в допустимом диапазоне
        if page >= total_pages:
            page = total_pages - 1
        if page < 0:
            page = 0
        
        start_idx = page * FILES_PER_PAGE
        end_idx = min(start_idx + FILES_PER_PAGE, len(received_files))
        current_files = received_files[start_idx:end_idx]
        
        # Создаем заголовок сообщения
        text = f"📥 <b>Полученные файлы</b> (Страница {page+1}/{total_pages})\n\nВсего получено: {len(received_files)}"
        
        # Добавляем кнопки для каждого файла
        for share in current_files:
            share_id = share["id"]
            file_info = share["info"]
            file_name = file_info["file_name"]
            file_type = file_info["file_type"]
            
            # Получаем информацию о владельце
            owner_id = file_info["owner_id"]
            owner = user_storage.get_user(owner_id)
            owner_name = owner["first_name"] if owner else "Неизвестный"
            
            # Определяем иконку для типа файла
            icon = "🖼️" if file_type == "photo" else "🎬" if file_type == "video" else "📄"
            
            # Ограничиваем длину имени файла
            if len(file_name) > 30:
                file_name = file_name[:27] + "..."
            
            # Добавляем кнопку для просмотра файла
            markup.add(
                types.InlineKeyboardButton(f"{icon} {file_name} от {owner_name}", callback_data=f"access_share:{share_id}")
            )
        
        # Добавляем кнопки навигации
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                types.InlineKeyboardButton("⬅️ Назад", callback_data=f"received_page:{page-1}")
            )
        
        if end_idx < len(received_files):
            nav_buttons.append(
                types.InlineKeyboardButton("Вперед ➡️", callback_data=f"received_page:{page+1}")
            )
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        # Добавляем кнопку возврата в главное меню
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
        
        # Отправляем сообщение
        try:
            # Пытаемся редактировать сообщение
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            if "there is no text in the message to edit" in str(edit_error).lower():
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                raise edit_error  # Переподнимаем другие ошибки
    except Exception as e:
        logger.error(f"Ошибка при отображении полученных файлов: {e}")
        try:
            # Если произошла другая ошибка, пытаемся показать сообщение об ошибке
            error_text = f"❌ <b>Произошла ошибка при отображении полученных файлов.</b>\n\nПопробуйте еще раз."
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                    )
                )
            except:
                # Если редактирование не удалось, отправляем новое сообщение
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                    )
                )
        except:
            # В крайнем случае просто логируем ошибку
            logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")
            pass

def delete_file(call, file_id):
    """Удалить файл пользователя."""
    try:
        # Получаем путь к файлу из кэша
        if file_id in file_path_cache:
            file_path = file_path_cache[file_id]
        else:
            # Если идентификатор не найден в кэше
            text = "❌ <b>Файл не найден.</b>\n\nИнформация о файле устарела."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
            
        # Проверяем, существует ли файл
        if not os.path.exists(file_path):
            # Если файла не существует, сообщаем об этом
            text = "❌ <b>Файл не найден.</b>\n\nВозможно, он уже был удален."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
            
        # Получаем ID пользователя
        user_id = call.from_user.id
        
        # Получаем пользовательские папки
        user_photos_folder, user_videos_folder, user_docs_folder, user_folder = get_user_folders(user_id)
        
        # Проверяем, принадлежит ли файл пользователю
        is_user_file = False
        
        # Проверяем, находится ли файл в папке пользователя
        if file_path.startswith(user_folder):
            is_user_file = True
        
        if not is_user_file:
            # Если файл не принадлежит пользователю, отказываем в удалении
            text = "⛔ <b>Доступ запрещен</b>\n\nВы можете удалять только свои файлы."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
            
        # Получаем информацию о файле
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        file_size_str = f"{file_size_mb:.2f} МБ" if file_size_mb >= 1 else f"{file_size_mb * 1024:.2f} КБ"
        
        # Создаем клавиатуру с кнопками подтверждения
        markup = types.InlineKeyboardMarkup(row_width=2)
        # Используем тот же file_id для подтверждения
        markup.add(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete:{file_id}"),
            types.InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_delete")
        )
        
        # Отправляем сообщение с подтверждением
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"⚠️ <b>Подтверждение удаления</b>\n\n"
                    f"Вы действительно хотите удалить файл?\n\n"
                    f"📄 <b>Файл:</b> {file_name}\n"
                    f"📦 <b>Размер:</b> {file_size_str}\n\n"
                    f"⚠️ <b>Внимание!</b> Это действие нельзя отменить."
                ),
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            if "there is no text in the message to edit" in str(edit_error).lower():
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=(
                        f"⚠️ <b>Подтверждение удаления</b>\n\n"
                        f"Вы действительно хотите удалить файл?\n\n"
                        f"📄 <b>Файл:</b> {file_name}\n"
                        f"📦 <b>Размер:</b> {file_size_str}\n\n"
                        f"⚠️ <b>Внимание!</b> Это действие нельзя отменить."
                    ),
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                raise edit_error
                
    except Exception as e:
        logger.error(f"Ошибка при попытке удаления файла: {e}")
        
        # Отправляем сообщение об ошибке
        text = f"❌ <b>Произошла ошибка при удалении файла.</b>\n\nПопробуйте еще раз."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            try:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except:
                pass

def confirm_delete_file(call, file_id):
    """Подтвердить и выполнить удаление файла."""
    try:
        # Получаем путь к файлу из кэша
        if file_id in file_path_cache:
            file_path = file_path_cache[file_id]
        else:
            # Если идентификатор не найден в кэше
            text = "❌ <b>Файл не найден.</b>\n\nИнформация о файле устарела."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
        
        # Проверяем, существует ли файл
        if not os.path.exists(file_path):
            # Если файла не существует, сообщаем об этом
            text = "❌ <b>Файл не найден.</b>\n\nВозможно, он уже был удален."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
        
        # Запоминаем имя файла перед удалением
        file_name = os.path.basename(file_path)
        
        # Получаем ID пользователя
        user_id = call.from_user.id
        
        # Получаем пользовательские папки
        user_photos_folder, user_videos_folder, user_docs_folder, user_folder = get_user_folders(user_id)
        
        # Проверяем, принадлежит ли файл пользователю
        is_user_file = False
        
        # Проверяем, находится ли файл в папке пользователя
        if file_path.startswith(user_folder):
            is_user_file = True
        
        if not is_user_file:
            # Если файл не принадлежит пользователю, отказываем в удалении
            text = "⛔ <b>Доступ запрещен</b>\n\nВы можете удалять только свои файлы."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
        
        # Удаляем файл
        os.remove(file_path)
        
        # Проверяем, был ли файл успешно удален
        success = not os.path.exists(file_path)
        
        if success:
            # Сообщаем об успешном удалении
            text = f"✅ <b>Файл успешно удален</b>\n\n📄 {file_name}"
            
            # Импортируем хранилище пользователей для удаления связанных общих файлов
            from user_storage import user_storage
            
            # Удаляем все общие ссылки на этот файл
            user_storage.cleanup_by_filepath(file_path)
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📁 Мои файлы", callback_data="files"),
                types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
            )
        else:
            # Сообщаем об ошибке
            text = f"❌ <b>Ошибка при удалении файла</b>\n\n📄 {file_name}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
        
        # Отправляем сообщение о результате
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            if "there is no text in the message to edit" in str(edit_error).lower():
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                raise edit_error
    
    except Exception as e:
        logger.error(f"Ошибка при удалении файла: {e}")
        
        # Отправляем сообщение об ошибке
        text = f"❌ <b>Произошла ошибка при удалении файла.</b>\n\nПопробуйте еще раз."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            try:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except:
                pass

def download_zip_archive(call, file_type="all"):
    """
    Создать и отправить ZIP-архив с файлами пользователя.
    
    Args:
        call: Объект обратного вызова
        file_type: Тип файлов для архивации ("all", "photos", "videos", "documents")
    """
    try:
        # Получаем ID пользователя
        user_id = call.from_user.id
        
        # Получаем папки пользователя
        user_photos_folder, user_videos_folder, user_docs_folder, user_folder = get_user_folders(user_id)
        
        # Определяем, какие файлы нужно архивировать
        if file_type == "photos":
            files = get_file_list(user_photos_folder)
            type_name = "фотографии"
            icon = "🖼️"
        elif file_type == "videos":
            files = get_file_list(user_videos_folder)
            type_name = "видео"
            icon = "🎬"
        elif file_type == "documents":
            files = get_file_list(user_docs_folder)
            type_name = "документы"
            icon = "📄"
        else:  # all
            files = []
            files.extend(get_file_list(user_photos_folder))
            files.extend(get_file_list(user_videos_folder))
            files.extend(get_file_list(user_docs_folder))
            type_name = "все файлы"
            icon = "📁"
        
        # Проверяем, есть ли файлы для архивации
        if not files:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"ℹ️ <b>Нет файлов для архивации.</b>\n\nВ выбранной категории не найдено файлов.",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=f"ℹ️ <b>Нет файлов для архивации.</b>\n\nВ выбранной категории не найдено файлов.",
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            return
        
        # Отправляем сообщение о начале архивации
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"⏳ <b>Создание архива...</b>\n\nПожалуйста, подождите. Архивируем {len(files)} файлов.",
                parse_mode="HTML"
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            if "there is no text in the message to edit" in str(edit_error).lower():
                status_message = bot.send_message(
                    chat_id=call.message.chat.id,
                    text=f"⏳ <b>Создание архива...</b>\n\nПожалуйста, подождите. Архивируем {len(files)} файлов.",
                    parse_mode="HTML"
                )
                call.message.message_id = status_message.message_id
            else:
                raise edit_error
        
        # Создаем архив
        archive_path = create_zip_archive(files, user_id, file_type)
        
        if not archive_path:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"❌ <b>Ошибка при создании архива.</b>\n\nПожалуйста, попробуйте позже.",
                parse_mode="HTML",
                reply_markup=markup
            )
            return
        
        # Получаем размер архива
        archive_size = os.path.getsize(archive_path)
        archive_size_mb = archive_size / (1024 * 1024)
        archive_size_str = f"{archive_size_mb:.2f} МБ" if archive_size_mb >= 1 else f"{(archive_size / 1024):.2f} КБ"
        
        # Формируем имя архива
        archive_name = os.path.basename(archive_path)
        
        # Создаем клавиатуру с кнопками
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📁 Мои файлы", callback_data="files"),
            types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
        )
        
        # Отправляем сообщение о готовности архива
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ <b>Архив готов к скачиванию!</b>\n\n"
                     f"{icon} <b>Тип файлов:</b> {type_name.capitalize()}\n"
                     f"📦 <b>Размер архива:</b> {archive_size_str}\n"
                     f"🗃️ <b>Количество файлов:</b> {len(files)}\n\n"
                     f"⏳ <b>Отправка архива...</b>",
                parse_mode="HTML"
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, логируем ошибку и продолжаем
            logger.error(f"Ошибка при обновлении сообщения: {edit_error}")
        
        # Отправляем архив как документ
        with open(archive_path, 'rb') as archive_file:
            bot.send_document(
                chat_id=call.message.chat.id,
                document=archive_file,
                caption=f"🗃️ <b>Архив:</b> {archive_name}\n📦 <b>Размер:</b> {archive_size_str}\n📁 <b>Включает:</b> {type_name}",
                parse_mode="HTML",
                reply_markup=markup
            )
        
        # Обновляем сообщение с информацией
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ <b>Архив успешно отправлен!</b>\n\n"
                     f"{icon} <b>Тип файлов:</b> {type_name.capitalize()}\n"
                     f"📦 <b>Размер архива:</b> {archive_size_str}\n"
                     f"🗃️ <b>Количество файлов:</b> {len(files)}\n\n"
                     f"Архив с вашими файлами был успешно создан и отправлен.",
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as edit_error:
            logger.error(f"Ошибка при обновлении сообщения об успешной отправке: {edit_error}")
        
        # Удаляем временный архив
        try:
            os.remove(archive_path)
            # Удаляем временную директорию
            temp_dir = os.path.dirname(archive_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Ошибка при удалении временного архива {archive_path}: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка при создании архива: {e}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"❌ <b>Произошла ошибка при архивации файлов.</b>\n\nПопробуйте снова позже.",
                parse_mode="HTML",
                reply_markup=markup
            )
        except:
            # Если не удалось отредактировать, пробуем отправить новое сообщение
            try:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=f"❌ <b>Произошла ошибка при архивации файлов.</b>\n\nПопробуйте снова позже.",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except:
                pass

def delete_shared_file(call, share_id):
    """Удалить общий доступ к файлу."""
    try:
        # Импортируем хранилище пользователей
        from user_storage import user_storage
        
        # Удаляем общий доступ
        success = user_storage.delete_share(share_id, call.from_user.id)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📤 Мои общие файлы", callback_data="cmd:myshared"),
            types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
        )
        
        if success:
            text = "✅ <b>Публикация успешно удалена.</b>\n\nДоступ к файлу для других пользователей прекращен."
        else:
            text = "❌ <b>Ошибка при удалении публикации.</b>\n\nВозможно, вы не являетесь владельцем этого файла."
        
        # Безопасно обновляем сообщение
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое
            if "there is no text in the message to edit" in str(edit_error).lower():
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                raise edit_error  # Переподнимаем другие ошибки
                
    except Exception as e:
        logger.error(f"Ошибка при удалении общего доступа: {e}")
        error_text = f"❌ <b>Произошла ошибка при удалении публикации.</b>\n\nПопробуйте еще раз."
        
        try:
            # Пытаемся редактировать сообщение
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=error_text,
                parse_mode="HTML",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                )
            )
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            try:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                    )
                )
            except:
                # В крайнем случае просто логируем ошибку
                logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")
                pass

@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    """Обработать нажатия кнопок."""
    try:
        # Показать всплывающее уведомление о загрузке (ловим ошибку, если запрос устарел)
        try:
            bot.answer_callback_query(call.id)
        except Exception as e:
            # Игнорируем ошибки устаревших запросов
            if "query is too old" in str(e) or "query ID is invalid" in str(e):
                logger.warning(f"Устаревший запрос: {str(e)}")
            else:
                # Логируем другие ошибки
                logger.error(f"Ошибка ответа на callback: {str(e)}")
        
        data = call.data
        
        # Обработать команды через кнопки
        if data.startswith("cmd:"):
            # Выполнение команды из кнопки
            cmd = data.split(":")[1]
            
            if cmd == "menu":
                # Показать главное меню (перерисовать текущее сообщение)
                # Создаем разметку с кнопками главного меню
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # Кнопки для разных типов файлов
                btn_photos = types.InlineKeyboardButton("🖼️ Фотографии", callback_data="cmd:photos")
                btn_videos = types.InlineKeyboardButton("🎬 Видеофайлы", callback_data="cmd:videos")
                btn_docs = types.InlineKeyboardButton("📄 Документы", callback_data="cmd:documents")
                btn_all_files = types.InlineKeyboardButton("📁 Все файлы", callback_data="files")
                
                # Кнопка скачивания архива
                btn_download_zip = types.InlineKeyboardButton("🗃️ Скачать ZIP-архив", callback_data="cmd:download_zip")
                
                # Кнопки функций
                btn_help = types.InlineKeyboardButton("❓ Помощь", callback_data="cmd:help")
                btn_info = types.InlineKeyboardButton("ℹ️ О боте", callback_data="cmd:about")
                
                # Добавляем кнопки в разметку
                markup.add(btn_photos, btn_videos)
                markup.add(btn_docs, btn_all_files)
                markup.add(btn_download_zip)
                markup.add(btn_help, btn_info)
                
                # Информационный баннер с инструкцией
                upload_banner = "📤 Отправьте мне файл, чтобы сохранить его!"
                
                # Обновляем сообщение с кнопками
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"👋 <b>Главное меню</b>\n\n"
                    f"🤖 Я <b>File Storage Bot</b> - ваш помощник для хранения и организации файлов.\n\n"
                    f"📌 <b>Основные возможности:</b>\n"
                    f"• Сохранение фото, видео и документов\n"
                    f"• Удобная организация по категориям\n"
                    f"• Простой поиск и просмотр\n\n"
                    f"{upload_banner}",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            
            elif cmd == "help":
                # Переиспользуем функцию help, но с редактированием текущего сообщения
                # Создаем разметку с кнопками
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # Кнопки разделов файлов
                btn_photos = types.InlineKeyboardButton("🖼️ Просмотр фото", callback_data="cmd:photos")
                btn_videos = types.InlineKeyboardButton("🎬 Просмотр видео", callback_data="cmd:videos")
                btn_docs = types.InlineKeyboardButton("📄 Просмотр документов", callback_data="cmd:documents")
                btn_all = types.InlineKeyboardButton("📁 Все файлы", callback_data="files")
                
                # Кнопки обмена файлами
                btn_shared = types.InlineKeyboardButton("📤 Мои общие файлы", callback_data="cmd:myshared")
                btn_received = types.InlineKeyboardButton("📥 Полученные файлы", callback_data="cmd:received")
                
                # Кнопка возврата в главное меню
                btn_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                
                # Формируем разметку кнопок
                markup.add(btn_photos, btn_videos)
                markup.add(btn_docs, btn_all)
                markup.add(btn_shared, btn_received)
                markup.add(btn_menu)
                
                # Обновляем сообщение помощи
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="<b>📚 Справка по использованию бота</b>\n\n"
                    "<b>📋 Доступные команды:</b>\n"
                    "• /start - Запустить бота и показать главное меню\n"
                    "• /help - Показать эту справку\n"
                    "• /files - Показать все сохраненные файлы\n"
                    "• /photos - Показать только фотографии\n"
                    "• /videos - Показать только видеофайлы\n"
                    "• /documents - Показать только документы\n"
                    "• /share_ID - Получить доступ к общему файлу\n\n"
                    
                    "<b>💾 Как сохранить файл:</b>\n"
                    "Просто отправьте мне фото, видео или документ, и я автоматически сохраню его в соответствующей категории.\n\n"
                    
                    "<b>🔍 Как найти файлы:</b>\n"
                    "Используйте кнопки ниже для просмотра файлов по категориям. При просмотре доступны кнопки навигации и фильтрации.\n\n"
                    
                    "<b>📤 Обмен файлами:</b>\n"
                    "1. Откройте файл через меню просмотра файлов\n"
                    "2. Нажмите кнопку \"Поделиться файлом\"\n"
                    "3. Отправьте полученную команду другому пользователю\n"
                    "4. Пользователь может получить доступ к файлу, отправив эту команду боту\n\n"
                    
                    "<b>✨ Дополнительные возможности:</b>\n"
                    "• Просмотр подробной информации о файле\n"
                    "• Удобная навигация между категориями\n"
                    "• Обмен файлами между пользователями\n"
                    "• Управление своими общими файлами",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            
            elif cmd == "about":
                # Переиспользуем функцию about, но с редактированием сообщения
                # Создаем клавиатуру с кнопками
                markup = types.InlineKeyboardMarkup(row_width=1)
                
                # Добавляем кнопки
                markup.add(
                    types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu"),
                    types.InlineKeyboardButton("📚 Справка", callback_data="cmd:help")
                )
                
                # Получаем статистику
                photos_count = len(get_file_list(PHOTOS_FOLDER))
                videos_count = len(get_file_list(VIDEOS_FOLDER))
                docs_count = len(get_file_list(DOCS_FOLDER))
                total_count = photos_count + videos_count + docs_count
                
                # Обновляем сообщение с информацией о боте
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"<b>🤖 File Storage Bot v1.0</b>\n\n"
                    f"<b>О боте:</b>\n"
                    f"Бот для хранения и организации файлов в удобном формате.\n\n"
                    
                    f"<b>📊 Статистика файлов:</b>\n"
                    f"• 🖼️ Фотографии: {photos_count}\n"
                    f"• 🎬 Видеофайлы: {videos_count}\n"
                    f"• 📄 Документы: {docs_count}\n"
                    f"• 📁 Всего файлов: {total_count}\n\n"
                    
                    f"<b>💻 Техническая информация:</b>\n"
                    f"• Разработан с использованием pyTelegramBotAPI\n"
                    f"• Имеет удобную категоризацию файлов\n"
                    f"• Поддерживает фото, видео и документы\n"
                    f"• Максимальный размер файла: 50 МБ\n\n"
                    
                    f"<b>Используйте /help для получения справки по командам.</b>",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            
            elif cmd == "photos":
                # Показать только фотографии
                show_files(call, 0, edit=True, file_type="photo")
            
            elif cmd == "videos":
                # Показать только видео
                show_files(call, 0, edit=True, file_type="video")
            
            elif cmd == "documents":
                # Показать только документы
                show_files(call, 0, edit=True, file_type="document")
            
            elif cmd == "myshared":
                # Показать мои общие файлы
                show_shared_files(call)
            
            elif cmd == "received":
                # Показать полученные файлы
                show_received_files(call)
            
            elif cmd == "download_zip":
                # Показываем меню выбора типа архива
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # Кнопки выбора типа архива
                markup.add(
                    types.InlineKeyboardButton("📁 Все файлы", callback_data="cmd:zip_all"),
                    types.InlineKeyboardButton("🖼️ Только фото", callback_data="cmd:zip_photos"),
                    types.InlineKeyboardButton("🎬 Только видео", callback_data="cmd:zip_videos"),
                    types.InlineKeyboardButton("📄 Только документы", callback_data="cmd:zip_docs"),
                    types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                )
                
                # Обновляем сообщение с выбором типа архива
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="<b>🗃️ Скачать ZIP-архив</b>\n\n"
                    "Выберите, какие файлы вы хотите включить в архив:\n\n"
                    "• <b>Все файлы</b> - ZIP-архив со всеми вашими файлами\n"
                    "• <b>Только фото</b> - архив только с фотографиями\n"
                    "• <b>Только видео</b> - архив только с видеофайлами\n"
                    "• <b>Только документы</b> - архив только с документами\n\n"
                    "⚠️ <b>Внимание:</b> В зависимости от размера и количества файлов, создание архива может занять некоторое время.",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            
            elif cmd.startswith("zip_"):
                # Определяем тип файлов для архивации
                archive_type = cmd.split("_")[1]
                
                # Вызываем функцию создания и отправки архива
                if archive_type == "all":
                    download_zip_archive(call, "all")
                elif archive_type == "photos":
                    download_zip_archive(call, "photos")
                elif archive_type == "videos":
                    download_zip_archive(call, "videos")
                elif archive_type == "docs":
                    download_zip_archive(call, "documents")
            
            elif cmd == "share":
                # Поделиться файлом
                # Формат: share:file_index
                try:
                    file_index = int(call.data.split(":")[2])
                    if 0 <= file_index < len(file_list_cache):
                        share_file(call, file_index)
                    else:
                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text="❌ <b>Файл не найден.</b> Возможно, список файлов изменился.",
                            parse_mode="HTML"
                        )
                except (ValueError, IndexError) as e:
                    logger.error(f"Ошибка при обмене файлом: {e}")
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="❌ <b>Ошибка при обмене файлом.</b> Пожалуйста, попробуйте снова.",
                        parse_mode="HTML"
                    )
            
            elif cmd == "delete_share":
                # Удалить общий доступ к файлу
                # Формат: delete_share:share_id
                try:
                    share_id = call.data.split(":")[2]
                    delete_shared_file(call, share_id)
                except (ValueError, IndexError) as e:
                    logger.error(f"Ошибка при удалении общего доступа: {e}")
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="❌ <b>Ошибка при удалении общего доступа.</b> Пожалуйста, попробуйте снова.",
                        parse_mode="HTML"
                    )
            
            else:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"⚠️ Неизвестная команда: {cmd}"
                )
        
        # Обработать кнопку показа всех файлов
        elif data == "files":
            show_files(call, 0, edit=True)
        
        # Обработать кнопки пагинации для файлов
        elif data.startswith("page:"):
            # Формат: page:номер_страницы:тип_файла
            parts = data.split(":")
            page = int(parts[1])
            file_type = parts[2] if len(parts) > 2 else None
            
            # Если тип файла 'all', значит нужно показать все файлы
            if file_type == 'all':
                file_type = None
                
            show_files(call, page, edit=True, file_type=file_type)
            
        # Обработать кнопки пагинации для общих файлов
        elif data.startswith("shared_page:"):
            # Формат: shared_page:номер_страницы
            page = int(data.split(":")[1])
            show_shared_files(call, page)
            
        # Обработать кнопки пагинации для полученных файлов
        elif data.startswith("received_page:"):
            # Формат: received_page:номер_страницы
            page = int(data.split(":")[1])
            show_received_files(call, page)
            
        # Обработать доступ к общему файлу
        elif data.startswith("access_share:"):
            # Формат: access_share:share_id
            share_id = data.split(":")[1]
            # Импортируем хранилище пользователей
            from user_storage import user_storage
            
            # Получаем доступ к файлу
            file_info = user_storage.access_shared_file(share_id, call.from_user.id)
            
            if file_info:
                # Отправляем файл пользователю
                view_file(call, file_info["file_path"])
            else:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="❌ <b>Ошибка доступа к файлу.</b>\n\nВозможно, ссылка устарела или файл был удален.",
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                    )
                )
        
        # Обработать команды просмотра файла
        elif data.startswith("view:"):
            # Получаем индекс файла
            try:
                file_index = int(data.split(":")[1])
                # Проверяем, что индекс валидный
                if 0 <= file_index < len(file_list_cache):
                    file_path = file_list_cache[file_index]
                    view_file(call, file_path)
                else:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="❌ <b>Файл не найден.</b> Возможно, список файлов изменился.",
                        parse_mode="HTML"
                    )
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка при получении файла по индексу: {e}")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="❌ <b>Произошла ошибка при выборе файла.</b>",
                    parse_mode="HTML"
                )
        
        # Обработать команду удаления файла
        elif data.startswith("delete_file:"):
            # Получаем id файла, который нужно удалить
            file_id = data[len("delete_file:"):]
            delete_file(call, file_id)
            
        # Обработать подтверждение удаления файла
        elif data.startswith("confirm_delete:"):
            # Получаем id файла, который нужно удалить
            file_id = data[len("confirm_delete:"):]
            confirm_delete_file(call, file_id)
            
        # Обработать отмену удаления файла
        elif data == "cancel_delete":
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("📁 Мои файлы", callback_data="files"),
                types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
            )
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="❌ <b>Удаление отменено.</b>\n\nФайл не был удален.",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as edit_error:
                # Если не удалось отредактировать, отправляем новое
                if "there is no text in the message to edit" in str(edit_error).lower():
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text="❌ <b>Удаление отменено.</b>\n\nФайл не был удален.",
                        parse_mode="HTML",
                        reply_markup=markup
                    )
                else:
                    raise edit_error
            
        elif data.startswith("view_share:"):
            # Получаем ID общего файла
            share_id = data.split(":")[1]
            # Отправляем новое сообщение со ссылкой для обмена
            from user_storage import user_storage
            
            # Получаем информацию о файле
            share_info = user_storage.get_shared_file(share_id)
            if not share_info:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text="❌ <b>Ошибка получения информации о файле.</b>\n\nВозможно, срок действия ссылки истек.",
                    parse_mode="HTML"
                )
                return
            
            file_name = share_info["file_name"]
            file_type = share_info["file_type"]
            
            # Создаем команду для быстрого доступа к файлу
            share_command = f"/share_{share_id}"
            
            # Создаем клавиатуру с кнопками
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📤 Мои общие файлы", callback_data="cmd:myshared"),
                types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
            )
            
            # Получаем реферальную ссылку
            referral_link = user_storage.get_referral_link(share_id)
            
            # Отправляем новое сообщение с информацией о созданной ссылке
            bot.send_message(
                chat_id=call.message.chat.id,
                text=(
                    f"✅ <b>Ссылка для обмена файлом готова!</b>\n\n"
                    f"📋 <b>Информация о файле:</b>\n"
                    f"• <b>Имя файла:</b> {file_name}\n"
                    f"• <b>Тип:</b> {file_type.capitalize()}\n"
                    f"• <b>ID публикации:</b> <code>{share_id}</code>\n\n"
                    f"🔗 <b>Команда для доступа:</b>\n"
                    f"<code>{share_command}</code>\n\n"
                    f"🔗 <b>Прямая ссылка:</b>\n"
                    f"<code>{referral_link}</code>\n\n"
                    f"📝 <b>Инструкция:</b>\n"
                    f"Другие пользователи могут получить доступ к этому файлу, отправив боту команду выше или перейдя по прямой ссылке."
                ),
                parse_mode="HTML",
                reply_markup=markup
            )
        else:
            # Неизвестная команда
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"⚠️ <b>Неизвестная команда.</b> Пожалуйста, вернитесь в главное меню.",
                parse_mode="HTML",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
                )
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        try:
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"❌ <b>Произошла ошибка при обработке запроса</b>\n\nПопробуйте снова или используйте /start для перезапуска бота.",
                parse_mode="HTML"
            )
        except:
            pass

@bot.message_handler(content_types=['photo', 'video', 'document'])
@require_verification
def receive_file(message):
    """Получить и сохранить файл, отправленный пользователем."""
    try:
        # Получаем папки пользователя
        user_id = message.from_user.id
        user_photos_folder, user_videos_folder, user_docs_folder, _ = get_user_folders(user_id)
        
        # Определить, какой тип файла был отправлен
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)  # Получить фото наибольшего размера
            file_name = f"photo_{message.photo[-1].file_id}.jpg"
            file_type = "фото"
            file_type_icon = "🖼️"
            file_category = "Фотографии"
            save_folder = user_photos_folder  # Используем персональную папку пользователя
        elif message.content_type == 'video':
            file_info = bot.get_file(message.video.file_id)
            file_name = getattr(message.video, 'file_name', None) or f"video_{message.video.file_id}.mp4"
            file_type = "видео"
            file_type_icon = "🎬"
            file_category = "Видеофайлы"
            save_folder = user_videos_folder  # Используем персональную папку пользователя
        elif message.content_type == 'document':
            file_info = bot.get_file(message.document.file_id)
            file_name = getattr(message.document, 'file_name', None) or f"doc_{message.document.file_id}"
            file_type = "документ"
            file_type_icon = "📄"
            file_category = "Документы"
            save_folder = user_docs_folder  # Используем персональную папку пользователя
        else:
            bot.send_message(
                message.chat.id, 
                "❌ <b>Этот формат не поддерживается.</b>\n\nЯ могу сохранять только фото, видео и документы.",
                parse_mode="HTML"
            )
            return

        # Проверяем, что имя файла действительно получено
        if not file_name:
            # Генерируем уникальное имя с временной меткой
            timestamp = int(time.time())
            file_name = f"{file_type}_{timestamp}.{file_info.file_path.split('.')[-1]}"
        
        # Очистить имя файла от недопустимых символов
        file_name = sanitize_filename(file_name)

        # Отправить сообщение о начале загрузки с анимированным эмодзи
        status_message = bot.send_message(
            message.chat.id, 
            f"⏳ <b>Загрузка {file_type}...</b>\n\n"
            f"{file_type_icon} <i>Подготовка файла к сохранению</i>\n"
            f"📥 <i>Загрузка содержимого</i>\n"
            f"📝 <i>Сохранение в категорию \"{file_category}\"</i>",
            parse_mode="HTML"
        )
        
        try:
            # Сохраняем файл
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Сохранить файл
            file_path = os.path.join(save_folder, file_name)
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            # Получить размер файла
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_size_str = f"{file_size_mb:.2f} МБ" if file_size_mb >= 1 else f"{(file_size_mb * 1024):.2f} КБ"
            
            # Создаем клавиатуру с кнопками действий
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # Команда для просмотра категории
            view_category = f"cmd:{file_type_cmd}" if (file_type_cmd := "photos" if file_type == "фото" else "videos" if file_type == "видео" else "documents") else "cmd:menu"
            
            # Кнопки действий
            markup.add(
                types.InlineKeyboardButton(f"📂 Просмотреть {file_category.lower()}", callback_data=view_category),
                types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
            )
            
            # Получаем дату и время сохранения
            now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            # Отправить сообщение об успешном сохранении с деталями файла
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=(
                    f"{file_type_icon} <b>{file_type.capitalize()} успешно сохранено!</b>\n\n"
                    f"📋 <b>Информация о файле:</b>\n"
                    f"• <b>Имя файла:</b> {os.path.basename(file_path)}\n"
                    f"• <b>Размер:</b> {file_size_str}\n"
                    f"• <b>Категория:</b> {file_category}\n"
                    f"• <b>Дата загрузки:</b> {now}\n\n"
                    f"✨ <i>Вы можете найти этот файл в разделе «{file_category}»</i>"
                ),
                parse_mode="HTML",
                reply_markup=markup
            )
            
            # Логгирование
            logger.info(f"Файл {file_name} ({file_size_str}) сохранен пользователем {message.from_user.first_name} (ID: {message.from_user.id})")
        
        except Exception as download_error:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=(
                    f"❌ <b>Ошибка при загрузке {file_type}</b>\n\n"
                    f"Не удалось загрузить файл: {str(download_error)}\n\n"
                    f"Пожалуйста, попробуйте еще раз или отправьте другой файл."
                ),
                parse_mode="HTML"
            )
            logger.error(f"Ошибка при загрузке файла от пользователя {message.from_user.id}: {download_error}")
            
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке файла: {e}")
        try:
            bot.send_message(
                message.chat.id, 
                f"❌ <b>Произошла ошибка при обработке файла</b>\n\n"
                f"<code>{str(e)}</code>\n\n"
                f"Пожалуйста, попробуйте отправить файл снова.",
                parse_mode="HTML"
            )
        except:
            bot.send_message(
                message.chat.id, 
                "Произошла непредвиденная ошибка. Пожалуйста, используйте /start для перезапуска бота."
            )

# Обработчик для проверки пароля при первом входе
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_password")
def check_password(message):
    """Проверить введенный пользователем пароль."""
    from user_storage import user_storage
    
    # Удаляем сообщение с паролем для безопасности
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass  # Игнорируем ошибки при удалении сообщения
    
    # Проверяем пароль
    if user_storage.verify_user(message.from_user.id, message.text):
        # Пароль верный, сбрасываем состояние и показываем меню
        del user_states[message.from_user.id]
        
        # Отправляем сообщение об успешной верификации
        bot.send_message(
            message.chat.id,
            "✅ <b>Верификация успешна!</b>\n\n"
            "Теперь вы имеете полный доступ ко всем функциям бота.",
            parse_mode="HTML"
        )
        
        # Показываем главное меню
        start(message)
    else:
        # Пароль неверный, сохраняем состояние и просим повторить ввод
        bot.send_message(
            message.chat.id,
            "❌ <b>Неверный пароль!</b>\n\n"
            "Пожалуйста, введите правильный пароль или обратитесь к администратору бота.",
            parse_mode="HTML"
        )

@bot.message_handler(func=lambda message: message.text and message.text.startswith('/share_'))
def process_share_command(message):
    """Обработать команду доступа к общему файлу."""
    try:
        # Получаем ID общего файла из команды
        share_id = message.text[7:]  # Убираем префикс "/share_"
        
        # Проверяем, что ID не пустой
        if not share_id:
            bot.send_message(
                message.chat.id,
                "❌ <b>Некорректная команда доступа.</b>\n\nФормат команды должен быть: /share_ID",
                parse_mode="HTML"
            )
            return
        
        # Импортируем хранилище пользователей
        from user_storage import user_storage
        
        # Регистрируем пользователя
        user_storage.register_user(
            message.from_user.id, 
            message.from_user.username or f"user_{message.from_user.id}", 
            message.from_user.first_name
        )
        
        # Получаем доступ к файлу
        file_info = user_storage.access_shared_file(share_id, message.from_user.id)
        
        if not file_info:
            bot.send_message(
                message.chat.id,
                "❌ <b>Файл не найден или ссылка недействительна.</b>\n\nВозможно, срок действия ссылки истек или файл был удален.",
                parse_mode="HTML"
            )
            return
        
        # Создаем клавиатуру с кнопками
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📥 Полученные файлы", callback_data="cmd:received"),
            types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
        )
        
        # Отправляем сообщение о успешном получении файла
        file_name = file_info["file_name"]
        file_type = file_info["file_type"]
        file_path = file_info["file_path"]
        
        # Определяем иконку для типа файла
        icon = "🖼️" if file_type == "photo" else "🎬" if file_type == "video" else "📄"
        
        # Получаем информацию о владельце
        owner_id = file_info["owner_id"]
        owner = user_storage.get_user(owner_id)
        owner_name = owner["first_name"] if owner else "Неизвестный"
        
        # Отправляем сообщение о успешном получении файла
        status_message = bot.send_message(
            message.chat.id,
            f"✅ <b>Вы получили доступ к файлу!</b>\n\n"
            f"📋 <b>Информация о файле:</b>\n"
            f"• <b>Название:</b> {file_name}\n"
            f"• <b>Тип:</b> {file_type.capitalize()}\n"
            f"• <b>Владелец:</b> {owner_name}\n\n"
            f"⏳ <b>Загрузка файла...</b>",
            parse_mode="HTML"
        )
        
        # Получаем размер файла
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        file_size_str = f"{file_size_mb:.2f} МБ" if file_size_mb >= 1 else f"{file_size_mb * 1024:.2f} КБ"
        
        # Отправляем файл в зависимости от типа
        try:
            if file_type == "photo":
                with open(file_path, 'rb') as file:
                    sent_message = bot.send_photo(
                        chat_id=message.chat.id,
                        photo=file,
                        caption=f"{icon} <b>Файл:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}\n👤 <b>От:</b> {owner_name}",
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
            elif file_type == "video":
                with open(file_path, 'rb') as file:
                    sent_message = bot.send_video(
                        chat_id=message.chat.id,
                        video=file,
                        caption=f"{icon} <b>Файл:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}\n👤 <b>От:</b> {owner_name}",
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
            else:
                with open(file_path, 'rb') as file:
                    sent_message = bot.send_document(
                        chat_id=message.chat.id,
                        document=file,
                        caption=f"{icon} <b>Файл:</b> {file_name}\n📦 <b>Размер:</b> {file_size_str}\n👤 <b>От:</b> {owner_name}",
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
            
            # Обновляем статус
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"✅ <b>Файл успешно получен!</b>\n\n"
                f"📋 <b>Информация о файле:</b>\n"
                f"• <b>Название:</b> {file_name}\n"
                f"• <b>Тип:</b> {file_type.capitalize()}\n"
                f"• <b>Размер:</b> {file_size_str}\n"
                f"• <b>Владелец:</b> {owner_name}\n\n"
                f"Файл был добавлен в ваш список полученных файлов.",
                parse_mode="HTML",
                reply_markup=markup
            )
            
            logger.info(f"Пользователь {message.from_user.id} получил доступ к файлу {file_name} (ID: {share_id})")
        
        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}")
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"❌ <b>Ошибка при отправке файла.</b>\n\nФайл существует, но возникла проблема при его отправке: {str(e)}",
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды доступа к файлу: {e}")
        bot.send_message(
            message.chat.id,
            "❌ <b>Произошла ошибка при обработке команды.</b>\n\nПожалуйста, попробуйте еще раз или обратитесь к владельцу файла.",
            parse_mode="HTML"
        )

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    """Обработать неизвестные команды и сообщения."""
    # Создаем клавиатуру с кнопками
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопки действий
    btn_menu = types.InlineKeyboardButton("🏠 Главное меню", callback_data="cmd:menu")
    btn_help = types.InlineKeyboardButton("❓ Помощь", callback_data="cmd:help")
    
    # Добавляем кнопки в разметку
    markup.add(btn_menu, btn_help)
    
    # Отправляем сообщение с кнопками
    bot.send_message(
        message.chat.id, 
        "🤔 <b>Извините, я не понял эту команду</b>\n\n"
        "Я могу выполнять только специальные команды или обрабатывать файлы.\n\n"
        "Используйте кнопки ниже для доступа к функциям бота или отправьте файл для сохранения.",
        parse_mode="HTML",
        reply_markup=markup
    )

# Функция для запуска бота
def run_bot():
    logger.info(f"Запуск бота с токеном {BOT_TOKEN[:5]}...")
    
    try:
        # Проверка папки для сохранения файлов
        if not os.path.exists(SAVE_FOLDER):
            os.makedirs(SAVE_FOLDER)
            logger.info(f"Создана папка для сохранения файлов: {SAVE_FOLDER}")
        else:
            logger.info(f"Папка для сохранения файлов уже существует: {SAVE_FOLDER}")
        
        # Получаем информацию о боте для проверки работоспособности
        bot_info = bot.get_me()
        logger.info(f"Бот успешно подключен: @{bot_info.username} (ID: {bot_info.id})")
        
        # Запуск бота в режиме infinity_polling (опрос)
        logger.info("Запуск infinity_polling...")
        bot.infinity_polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Возвращаем ошибку вместо выхода из программы
        return False
    
    return True

# Запускаем бот напрямую, если файл запущен как скрипт
if __name__ == "__main__":
    success = run_bot()
    if not success:
        sys.exit(1)