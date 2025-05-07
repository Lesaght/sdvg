#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для быстрой перезагрузки Telegram-бота.
Завершает все процессы бота и запускает его заново.
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
        logging.FileHandler('restart_bot.log')
    ]
)
logger = logging.getLogger(__name__)

def kill_all_bots():
    """Находит и завершает все процессы связанные с Telegram-ботом."""
    keywords = ["python", "main.py", "run_telegram_bot.py", "watchdog.py"]
    killed = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            is_bot_related = any(keyword in cmdline for keyword in keywords)
            
            # Не убиваем текущий процесс
            if is_bot_related and proc.pid != os.getpid():
                logger.info(f"Завершаем процесс: {proc.pid} ({cmdline})")
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                    killed += 1
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса {proc.pid}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    return killed

def restart_bot():
    """Перезапускает бота."""
    print("=== ПЕРЕЗАПУСК TELEGRAM БОТА ===")
    
    # Завершаем все существующие экземпляры бота
    print("Завершение всех процессов бота...")
    killed = kill_all_bots()
    print(f"Завершено {killed} процессов.")
    
    if killed > 0:
        # Даем время на завершение процессов
        print("Ожидание завершения процессов...")
        time.sleep(3)
    
    # Запускаем бота через run_telegram_bot.py
    print("Запуск нового экземпляра бота...")
    subprocess.Popen(
        [sys.executable, "run_telegram_bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True
    )
    
    print("Бот успешно перезапущен!")
    print("Для работы с ботом используйте Telegram: @bbhhggddqqzzxxccgg_bot")
    print("=================================\n")

if __name__ == "__main__":
    restart_bot()