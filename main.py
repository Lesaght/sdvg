#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Прямой запуск Telegram-бота с использованием PyTelegramBotAPI.
"""

import os
import sys
import re
import time
import logging
import datetime
import json
from functools import wraps

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Пытаемся импортировать telebot (PyTelegramBotAPI)
try:
    from telebot import TeleBot, types
except ImportError:
    try:
        # Пробуем установить необходимую библиотеку
        import subprocess
        logger.info("Установка библиотеки PyTelegramBotAPI...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI"])
        from telebot import TeleBot, types
    except Exception as e:
        logger.error(f"Не удалось импортировать библиотеку telebot: {e}")
        sys.exit(1)

# Импортируем необходимые модули
try:
    from config import (
        SPECIAL_PASSWORD, BOT_TOKEN, BOT_USERNAME,
        SAVE_FOLDER, USER_FILES_BASE_FOLDER,
        SUPPORTED_PHOTO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS,
        FILES_PER_PAGE, SHARE_LINK_TTL
    )
except ImportError:
    # Задаем значения по умолчанию
    logger.warning("Не удалось импортировать config.py, используем значения по умолчанию.")
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    SPECIAL_PASSWORD = os.environ.get("BOT_SPECIAL_PASSWORD", "Derzhavka")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "bbhhggddqqzzxxccgg_bot")
    SAVE_FOLDER = "saved_files"
    USER_FILES_BASE_FOLDER = os.path.join(SAVE_FOLDER, "users")
    SUPPORTED_PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    FILES_PER_PAGE = 5
    SHARE_LINK_TTL = 24  # 24 часа

if not BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN не установлен!")
    # Устанавливаем токен жестко для тестирования/отладки
    BOT_TOKEN = "7935052392:AAH4DiqyOIp5IN9NfR6n-RQROCZeQcROM7c"
    logger.info("Использую жестко заданный токен для тестирования")

# Создаем папку для сохранения файлов, если её нет
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)
    logger.info(f"Создана папка сохранения: {SAVE_FOLDER}")

# Создаем папку для хранения пользовательских файлов
if not os.path.exists(USER_FILES_BASE_FOLDER):
    os.makedirs(USER_FILES_BASE_FOLDER)
    logger.info(f"Создана папка для пользовательских файлов: {USER_FILES_BASE_FOLDER}")

# Создаем папки для разных типов файлов
photos_folder = os.path.join(SAVE_FOLDER, "photos")
videos_folder = os.path.join(SAVE_FOLDER, "videos")
documents_folder = os.path.join(SAVE_FOLDER, "documents")

for folder in [photos_folder, videos_folder, documents_folder]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"Создана папка: {folder}")

# Инициализируем бота
bot = TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)
logger.info(f"Бот @{BOT_USERNAME} инициализирован")

# Загружаем данные о пользователях
USER_DATA_FILE = "users_data.json"
shared_files_file = "shared_files.json"

# Словарь для хранения информации о пользователях
users_data = {}
shared_files = {}

# Загружаем данные о пользователях, если файл существует
if os.path.exists(USER_DATA_FILE):
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
        logger.info(f"Данные о пользователях загружены из {USER_DATA_FILE}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных о пользователях: {e}")

# Загружаем данные о общих файлах, если файл существует
if os.path.exists(shared_files_file):
    try:
        with open(shared_files_file, 'r', encoding='utf-8') as f:
            shared_files = json.load(f)
        logger.info(f"Данные о общих файлах загружены из {shared_files_file}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных о общих файлах: {e}")

def save_users_data():
    """Сохранить данные о пользователях в файл."""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных о пользователях: {e}")

def save_shared_files():
    """Сохранить данные о общих файлах в файл."""
    try:
        with open(shared_files_file, 'w', encoding='utf-8') as f:
            json.dump(shared_files, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных о общих файлах: {e}")

# Загружаем модули с функциями из simple_bot.py
from simple_bot import (
    get_user_folders, require_verification, sanitize_filename, 
    get_file_type, get_file_list, create_zip_archive, save_file,
    start, help_command, files_command, photos_command, videos_command,
    documents_command, menu_command, about_command, show_files,
    view_file, share_file, show_shared_files, show_received_files, 
    delete_file, confirm_delete_file, download_zip_archive, 
    delete_shared_file, button_handler, receive_file, check_password, 
    process_share_command, unknown_command
)

def register_handlers():
    """Регистрация обработчиков команд бота."""
    # Регистрируем обработчики команд
    bot.register_message_handler(start, commands=['start'])
    bot.register_message_handler(help_command, commands=['help'])
    bot.register_message_handler(files_command, commands=['files'])
    bot.register_message_handler(photos_command, commands=['photos'])
    bot.register_message_handler(videos_command, commands=['videos'])
    bot.register_message_handler(documents_command, commands=['documents'])
    bot.register_message_handler(menu_command, commands=['menu'])
    bot.register_message_handler(about_command, commands=['about'])
    
    # Регистрируем обработчики файлов
    bot.register_message_handler(receive_file, content_types=['photo', 'video', 'document'])
    
    # Регистрируем обработчик для проверки пароля
    bot.register_message_handler(check_password, func=lambda message: message.text and not message.text.startswith('/'))
    
    # Регистрируем обработчик callback-кнопок (inline buttons)
    bot.register_callback_query_handler(button_handler, func=lambda call: True)

    logger.info("Обработчики команд зарегистрированы")

def run_bot_with_restart():
    """Функция для запуска бота с автоматическим перезапуском при сбоях."""
    while True:
        try:
            # Регистрируем обработчики
            register_handlers()
            
            # Запускаем бота с бесконечным опросом и настройками для стабильности
            logger.info("Бот запущен и ожидает сообщения.")
            bot.infinity_polling(timeout=60, 
                               long_polling_timeout=60, 
                               allowed_updates=None,
                               skip_pending=True,
                               restart_on_change=False,  # Отключаем, чтобы избежать проблем с watchdog
                               none_stop=True)
        except KeyboardInterrupt:
            logger.info("Остановка бота пользователем.")
            break
        except Exception as e:
            logger.error(f"Ошибка при работе бота: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.info("Перезапуск бота через 5 секунд...")
            time.sleep(5)
            continue

if __name__ == "__main__":
    logger.info("Запуск бота...")
    run_bot_with_restart()