#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

from user_storage import user_storage

print("Запуск проверки и исправления путей в shared_files.json...")
user_storage.fix_shared_file_paths()
print("Готово!")