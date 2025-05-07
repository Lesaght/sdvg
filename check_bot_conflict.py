#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для проверки и устранения конфликтов между экземплярами Telegram-бота.
Завершает все другие экземпляры бота перед запуском нового.
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
        logging.FileHandler('bot_conflict.log')
    ]
)
logger = logging.getLogger(__name__)

def kill_bot_processes():
    """Находит и завершает все процессы Telegram-бота."""
    bot_keywords = ["python", "main.py"]
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Проверяем, что это процесс Python и запускает main.py
            cmdline = ' '.join(proc.info['cmdline'] or [])
            is_bot = all(keyword in cmdline for keyword in bot_keywords)
            
            # Не убиваем текущий процесс
            if is_bot and proc.pid != os.getpid():
                logger.info(f"Найден конфликтующий процесс бота (PID: {proc.pid}), завершаем...")
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                    killed_count += 1
                except Exception as e:
                    logger.error(f"Не удалось завершить процесс {proc.pid}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    logger.info(f"Завершено {killed_count} конфликтующих процессов бота")
    return killed_count

if __name__ == "__main__":
    logger.info("Проверка и устранение конфликтов между экземплярами бота...")
    kill_bot_processes()
    
    logger.info("Запуск нового экземпляра бота...")
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)