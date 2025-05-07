#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сторожевой процесс для постоянного мониторинга и поддержания работы Telegram-бота.
Проверяет, запущен ли бот, и перезапускает его в случае сбоя.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import psutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('watchdog.log')
    ]
)
logger = logging.getLogger(__name__)

# Название процесса бота
BOT_SCRIPT = "main.py"
# Интервал проверки в секундах
CHECK_INTERVAL = 30

def is_bot_running():
    """Проверяет, запущен ли бот."""
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(process.info['cmdline'] or [])
            if 'python' in cmdline and BOT_SCRIPT in cmdline:
                logger.debug(f"Бот найден, PID: {process.info['pid']}")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def start_bot():
    """Запускает процесс бота."""
    try:
        logger.info("Запуск Telegram-бота...")
        proc = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        logger.info(f"Бот запущен с PID: {proc.pid}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False

def main():
    """Основная функция сторожевого процесса."""
    logger.info("Сторожевой процесс запущен")
    
    # Запускаем бота, если он не запущен
    if not is_bot_running():
        logger.info("Бот не запущен при старте сторожевого процесса")
        start_bot()
    
    try:
        # Бесконечный цикл проверки состояния бота
        while True:
            if not is_bot_running():
                logger.warning("Бот не запущен, перезапускаем...")
                start_bot()
            else:
                logger.debug("Бот работает нормально")
            
            # Ждем перед следующей проверкой
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("Сторожевой процесс остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка в работе сторожевого процесса: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info("Сторожевой процесс завершен")

if __name__ == "__main__":
    main()