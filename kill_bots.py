#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для завершения всех процессов Telegram-бота.
"""

import os
import signal
import sys
import psutil

def kill_all_bots():
    """Находит и завершает все процессы связанные с Telegram-ботом."""
    keywords = ["python", "main.py", "telebot", "run_telegram_bot.py", "watchdog.py"]
    killed = 0
    
    print("Поиск и завершение всех процессов бота...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            is_bot_related = any(keyword in cmdline for keyword in keywords)
            
            # Не убиваем текущий процесс и системные процессы
            if is_bot_related and proc.pid != os.getpid() and "kill_bots.py" not in cmdline:
                print(f"Завершение процесса: PID={proc.pid}, CMD={cmdline}")
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                    killed += 1
                except Exception as e:
                    print(f"Ошибка при завершении процесса {proc.pid}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    print(f"Завершено {killed} процессов бота")
    return killed

if __name__ == "__main__":
    print("=== ЗАВЕРШЕНИЕ ВСЕХ ПРОЦЕССОВ TELEGRAM БОТА ===")
    killed = kill_all_bots()
    print("=== ЗАВЕРШЕНИЕ ВЫПОЛНЕНО ===")
    
    if killed > 0:
        print("Все процессы бота остановлены.")
    else:
        print("Не найдено активных процессов бота.")