#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для надежного запуска Telegram-бота.
Использует функции для устранения конфликтов между экземплярами бота.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import traceback
import psutil

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

def run_telegram_bot():
    """Запускает Telegram-бота после устранения конфликтов."""
    try:
        # Сначала завершаем все конфликтующие процессы
        logger.info("Проверка и устранение конфликтов между экземплярами бота...")
        killed = kill_bot_processes()
        if killed > 0:
            time.sleep(3)  # Даем время на завершение процессов
        
        # Запускаем сторожевой процесс
        logger.info("Запуск сторожевого процесса для Telegram-бота...")
        watchdog_process = subprocess.Popen(
            [sys.executable, "watchdog.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        logger.info(f"Сторожевой процесс запущен (PID: {watchdog_process.pid})")
        logger.info("Бот будет автоматически перезапускаться при сбоях.")
        
        # Загружаем переменные окружения из .env файла, если он существует
        if os.path.exists('.env'):
            logger.info("Загрузка переменных окружения из .env файла")
            with open('.env', 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        
        # Запускаем основной процесс бота
        logger.info("Запуск основного процесса Telegram-бота...")
        # Передаем текущее окружение с переменными
        env = os.environ.copy()
        # Проверяем наличие токена
        if "TELEGRAM_BOT_TOKEN" in env:
            logger.info("TELEGRAM_BOT_TOKEN найден в переменных окружения")
        else:
            logger.warning("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
            # Добавляем токен жестко в окружение
            env["TELEGRAM_BOT_TOKEN"] = "7935052392:AAH4DiqyOIp5IN9NfR6n-RQROCZeQcROM7c"
            
        bot_process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True
        )
        
        logger.info(f"Telegram-бот запущен (PID: {bot_process.pid})")
        
        # Выводим сообщение о успешном запуске
        print("\n=== TELEGRAM BOT STARTED SUCCESSFULLY ===")
        print("Бот успешно запущен и будет автоматически перезапускаться при сбоях")
        print("Для работы с ботом используйте Telegram: @bbhhggddqqzzxxccgg_bot")
        print("Пароль для первого входа: Derzhavka")
        print("==========================================\n")
        
        # Оставляем процесс запущенным
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("Остановка бота пользователем.")
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram-бота: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run_telegram_bot()