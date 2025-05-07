#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска единственного экземпляра Telegram-бота.
Убивает все другие экземпляры перед запуском.
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
        logging.FileHandler('single_bot.log')
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

def run_single_bot():
    """Запускает единственный экземпляр бота."""
    # Сначала убиваем все существующие экземпляры бота
    logger.info("Завершение всех существующих экземпляров бота...")
    killed = kill_all_bots()
    logger.info(f"Завершено {killed} процессов")
    
    if killed > 0:
        # Даем время на завершение процессов
        time.sleep(3)
    
    # Запускаем телеграм-бота
    logger.info("Запуск нового экземпляра бота...")
    
    # Загружаем переменные из .env файла
    if os.path.exists('.env'):
        logger.info("Загружаем переменные из .env файла")
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Запускаем бота
    try:
        # Прямой запуск main.py для избежания лишних процессов
        print("\n=== ЗАПУСК TELEGRAM БОТА ===")
        print("Бот запускается, пожалуйста подождите...")
        result = subprocess.run(
            [sys.executable, "main.py"],
            check=True
        )
        print("Бот остановлен.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        print(f"Ошибка при запуске бота: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Бот остановлен пользователем.")

if __name__ == "__main__":
    run_single_bot()