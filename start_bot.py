#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска единственного экземпляра Telegram-бота.
Завершает все существующие экземпляры и запускает новый.
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
        logging.FileHandler('start_bot.log')
    ]
)
logger = logging.getLogger(__name__)

def kill_bot_processes():
    """Находит и завершает все процессы Telegram-бота."""
    bot_keywords = ["python", "main.py", "telebot"]
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Проверяем, что это процесс Python
            cmdline = ' '.join(proc.info['cmdline'] or [])
            is_bot = any(keyword in cmdline for keyword in bot_keywords)
            
            # Не убиваем текущий процесс
            if is_bot and proc.pid != os.getpid():
                print(f"Завершение конфликтующего процесса (PID: {proc.pid})")
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                    killed_count += 1
                except Exception as e:
                    print(f"Ошибка при завершении процесса {proc.pid}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    print(f"Завершено {killed_count} конфликтующих процессов")
    return killed_count

def load_env_file():
    """Загружает переменные окружения из .env файла."""
    if os.path.exists('.env'):
        print("Загрузка переменных окружения из .env файла")
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

def start_bot():
    """Запускает единственный экземпляр бота."""
    print("\n=== ЗАПУСК TELEGRAM БОТА ===")
    
    # Завершаем все существующие процессы бота
    print("Проверка и завершение других экземпляров бота...")
    killed = kill_bot_processes()
    
    if killed > 0:
        print("Ожидание 3 секунды для завершения процессов...")
        time.sleep(3)
    
    # Загружаем переменные окружения
    load_env_file()
    
    # Запускаем бота напрямую
    print("Запуск бота...")
    try:
        # Устанавливаем токен напрямую в переменные окружения
        os.environ["TELEGRAM_BOT_TOKEN"] = "7935052392:AAH4DiqyOIp5IN9NfR6n-RQROCZeQcROM7c"
        
        # Запускаем бота напрямую через Python
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    start_bot()