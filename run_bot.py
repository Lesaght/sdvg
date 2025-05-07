#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска Telegram-бота.
Этот файл должен запускаться отдельно от веб-приложения.
"""

import os
import sys
import time
import logging
import subprocess

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

# Импортируем токен бота
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

def check_process_running(process_name):
    """Проверяет, запущен ли уже процесс с заданным именем."""
    try:
        output = subprocess.check_output(f"ps aux | grep '{process_name}' | grep -v grep", shell=True)
        return len(output.strip()) > 0
    except subprocess.CalledProcessError:
        return False

def run_bot():
    """Запускает Telegram-бота."""
    # Проверяем, что токен установлен
    if not TOKEN:
        logger.error("Не задан TELEGRAM_BOT_TOKEN. Установите эту переменную окружения.")
        sys.exit(1)
    
    logger.info("Запуск Telegram-бота...")
    
    # Проверяем, не запущен ли уже бот
    if check_process_running('simple_bot.py'):
        logger.info("Бот уже запущен.")
        return
    
    # Запускаем бота напрямую как отдельный процесс
    try:
        logger.info("Запуск бота как отдельный процесс...")
        
        # Запускаем бота в фоновом режиме
        process = subprocess.Popen(
            ["python", "simple_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Логируем PID процесса
        logger.info(f"Бот запущен, PID процесса: {process.pid}")
        
        # Бесконечный цикл для поддержания работы скрипта
        while True:
            # Проверяем, жив ли процесс
            if process.poll() is not None:
                # Процесс остановился, проверим код возврата
                return_code = process.poll()
                stderr_output = process.stderr.read().decode('utf-8')
                logger.error(f"Бот остановился с кодом {return_code}. Ошибка: {stderr_output}")
                
                # Перезапускаем бота
                logger.info("Попытка перезапуска бота...")
                process = subprocess.Popen(
                    ["python", "simple_bot.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                logger.info(f"Бот перезапущен, новый PID: {process.pid}")
            
            # Логируем статус
            logger.info("Бот работает. Статус проверен.")
            
            # Ждем перед следующей проверкой
            time.sleep(60)  # Проверка каждую минуту
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки. Останавливаем бота...")
        # Завершаем процесс бота
        if 'process' in locals() and process:
            process.terminate()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run_bot()