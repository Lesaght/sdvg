#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска Telegram-бота в отдельном процессе.
"""

import os
import sys
import time
import logging
import subprocess
import threading
import signal

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('run.log')
    ]
)
logger = logging.getLogger(__name__)

# Переменная для хранения процесса бота
bot_process = None

# Функция для запуска телеграм-бота
def start_telegram_bot():
    global bot_process
    
    logger.info("Запуск Telegram-бота...")
    
    try:
        # Запускаем бота в отдельном процессе
        bot_process = subprocess.Popen(
            [sys.executable, "bot_runner.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"Бот запущен (PID: {bot_process.pid})")
        
        # Создаем функцию для чтения вывода процесса
        def log_output(pipe, prefix):
            for line in iter(pipe.readline, ''):
                if line:
                    logger.info(f"{prefix}: {line.strip()}")
        
        # Создаем потоки для чтения stdout и stderr
        stdout_thread = threading.Thread(target=log_output, args=(bot_process.stdout, "BOT STDOUT"))
        stderr_thread = threading.Thread(target=log_output, args=(bot_process.stderr, "BOT STDERR"))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram-бота: {e}")
        return False

# Функция для корректного завершения всех процессов
def cleanup():
    logger.info("Завершение работы...")
    
    if bot_process:
        logger.info(f"Завершение процесса бота (PID: {bot_process.pid})...")
        try:
            bot_process.terminate()
            bot_process.wait(timeout=5)
        except:
            logger.warning("Не удалось корректно завершить процесс бота, принудительно завершаем...")
            try:
                bot_process.kill()
            except:
                pass

# Обработчик сигналов для корректного завершения
def signal_handler(sig, frame):
    logger.info(f"Получен сигнал {sig}, завершаем работу...")
    cleanup()
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Основная функция
if __name__ == "__main__":
    try:
        # Запускаем Telegram-бота
        if not start_telegram_bot():
            logger.error("Не удалось запустить Telegram-бота.")
            sys.exit(1)
        
        # Ждем завершения процесса бота
        exit_code = 0
        if bot_process:
            try:
                # Продолжаем ждать, пока процесс работает
                while bot_process.poll() is None:
                    time.sleep(1)
                exit_code = bot_process.returncode
            except:
                logger.error("Ошибка при ожидании завершения процесса")
                exit_code = 1
        if exit_code != 0:
            logger.error(f"Бот завершился с кодом {exit_code}, перезапускаем...")
            start_telegram_bot()
    
    except KeyboardInterrupt:
        logger.info("Получена команда на завершение (Ctrl+C)")
    finally:
        cleanup()