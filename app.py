#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Этот файл создан для обеспечения совместимости с gunicorn.
Он запускает Telegram-бота вместо веб-приложения.
"""

import os
import time
import logging
import threading

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Запуск бота в отдельном потоке
def start_bot_thread():
    """Запуск бота в отдельном потоке."""
    logger.info("Запуск бота в отдельном потоке...")
    import sys
    
    try:
        # Импортируем main.py чтобы запустить бота
        import main
        
        # Запускаем бота через функцию main.py
        main.run_bot_with_restart()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Запускаем бота в отдельном потоке
bot_thread = threading.Thread(target=start_bot_thread)
bot_thread.daemon = True  # Делаем поток демоном, чтобы он завершался вместе с основным потоком
bot_thread.start()

logger.info("Бот запущен в отдельном потоке")

# Flask-подобный объект, который использует gunicorn
class SimpleApp:
    def __call__(self, environ, start_response):
        status = '200 OK'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return [b"Telegram bot is running! Use the Telegram client to interact with it."]

app = SimpleApp()

if __name__ == "__main__":
    # Запускаем простой бесконечный цикл, чтобы процесс не завершался
    try:
        while True:
            time.sleep(60)  # Проверка каждую минуту
            logger.debug("Бот работает...")
    except KeyboardInterrupt:
        logger.info("Остановка бота пользователем.")