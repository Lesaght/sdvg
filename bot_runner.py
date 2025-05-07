#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой скрипт для запуска Telegram-бота.
"""

import os
import sys
import logging
import traceback

# Импортируем telebot с обработкой ошибок
try:
    from telebot import TeleBot
except ImportError:
    # Попробуем установить библиотеку, если её нет
    import subprocess
    print("Установка необходимых библиотек...")
    subprocess.call([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI"])
    
    # Повторная попытка импорта
    try:
        from telebot import TeleBot
    except ImportError as e:
        print(f"Ошибка импорта telebot: {e}")
        print("Пожалуйста, установите библиотеку вручную: pip install pyTelegramBotAPI")
        sys.exit(1)

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

# Токен из переменной окружения
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("Не задан TELEGRAM_BOT_TOKEN. Бот не может быть запущен.")
    sys.exit(1)

# Создаем экземпляр бота
bot = TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

# Папка для сохранения файлов
SAVE_FOLDER = "saved_files"
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)
    logger.info(f"Создана папка сохранения: {SAVE_FOLDER}")
else:
    logger.info(f"Папка сохранения уже существует: {SAVE_FOLDER}")

# Базовая папка для хранения пользовательских файлов
USER_FILES_BASE_FOLDER = os.path.join(SAVE_FOLDER, "users")
if not os.path.exists(USER_FILES_BASE_FOLDER):
    os.makedirs(USER_FILES_BASE_FOLDER)
    logger.info(f"Создана папка для пользовательских файлов: {USER_FILES_BASE_FOLDER}")

# Импортируем обработчики из simple_bot.py
try:
    # Импортируем только необходимые функции
    from simple_bot import (
        start, help_command, files_command, photos_command, videos_command, 
        documents_command, menu_command, about_command, unknown_command,
        button_handler, receive_file, check_password, process_share_command
    )
    
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
    
    # Запускаем бота
    logger.info("Запуск бота в режиме infinity_polling...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
    
except Exception as e:
    logger.error(f"Ошибка при запуске бота: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1)