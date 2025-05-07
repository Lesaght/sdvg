#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для надежного запуска Telegram-бота через workflow.
Решает проблему с конфликтующими экземплярами бота.
"""

import os
import sys
import time
import signal
import subprocess
import psutil

def kill_bot_processes():
    """Находит и завершает все процессы Telegram-бота."""
    bot_keywords = ["python", "main.py", "telebot", "run_telegram_bot.py", "watchdog.py"]
    killed_count = 0
    
    print("Проверка и завершение конфликтующих процессов бота...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Проверяем, что это процесс бота
            cmdline = ' '.join(proc.info['cmdline'] or [])
            is_bot = any(keyword in cmdline for keyword in bot_keywords)
            
            # Не убиваем текущий процесс
            if is_bot and proc.pid != os.getpid() and "run_fixed_bot.py" not in cmdline:
                print(f"Завершение процесса: PID={proc.pid}, CMD={cmdline}")
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                    killed_count += 1
                except Exception as e:
                    print(f"Ошибка при завершении процесса {proc.pid}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    print(f"Завершено {killed_count} конфликтующих процессов")
    return killed_count

def load_env_variables():
    """Загружает переменные окружения из .env файла."""
    if os.path.exists('.env'):
        print("Загрузка переменных окружения из .env файла")
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Устанавливаем токен напрямую (гарантированно)
    os.environ["TELEGRAM_BOT_TOKEN"] = "7935052392:AAH4DiqyOIp5IN9NfR6n-RQROCZeQcROM7c"
    os.environ["BOT_SPECIAL_PASSWORD"] = "Derzhavka"

def run_bot_directly():
    """Запускает бота напрямую через main.py."""
    print("Запуск бота напрямую...")
    
    try:
        # Запускаем бота, держим процесс активным
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        import traceback
        print(traceback.format_exc())

def main():
    """Главная функция запуска бота."""
    print("\n=== ЗАПУСК TELEGRAM БОТА ===")
    
    # Завершаем все существующие процессы бота
    kill_bot_processes()
    
    # Даем время на завершение процессов
    print("Пауза для завершения процессов...")
    time.sleep(2)
    
    # Загружаем переменные окружения
    load_env_variables()
    
    # Запускаем бота
    print("Запуск Telegram бота...")
    run_bot_directly()
    
    print("Бот завершил работу.")

if __name__ == "__main__":
    main()