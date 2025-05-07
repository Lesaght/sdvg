#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import uuid
import urllib.parse
from datetime import datetime, timedelta
from config import BOT_USERNAME, SHARE_LINK_TTL

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Путь к файлу с данными пользователя
USERS_DATA_FILE = "users_data.json"
SHARED_FILES_DATA = "shared_files.json"

# Импортируем из конфига, если значения не переданы с аргументами

class UserStorage:
    """Класс для хранения информации о пользователях и общих файлах."""
    
    def __init__(self):
        """Инициализация хранилища пользователей."""
        self.users = {}
        self.shared_files = {}
        self.load_data()
        # Исправляем пути к файлам в шаринге при запуске
        self.fix_shared_file_paths()
    
    def load_data(self):
        """Загрузить данные о пользователях и общих файлах."""
        # Загрузка данных пользователей
        if os.path.exists(USERS_DATA_FILE):
            try:
                with open(USERS_DATA_FILE, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
                logger.info(f"Загружены данные о {len(self.users)} пользователях")
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных пользователей: {e}")
                self.users = {}
        
        # Загрузка данных об общих файлах
        if os.path.exists(SHARED_FILES_DATA):
            try:
                with open(SHARED_FILES_DATA, 'r', encoding='utf-8') as f:
                    self.shared_files = json.load(f)
                logger.info(f"Загружены данные о {len(self.shared_files)} общих файлах")
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных об общих файлах: {e}")
                self.shared_files = {}
    
    def save_data(self):
        """Сохранить данные о пользователях и общих файлах."""
        # Сохранение данных пользователей
        try:
            with open(USERS_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранены данные о {len(self.users)} пользователях")
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных пользователей: {e}")
        
        # Сохранение данных об общих файлах
        try:
            with open(SHARED_FILES_DATA, 'w', encoding='utf-8') as f:
                json.dump(self.shared_files, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранены данные о {len(self.shared_files)} общих файлах")
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных об общих файлах: {e}")
    
    def register_user(self, user_id, username, first_name):
        """Регистрация нового пользователя или обновление существующего."""
        user_id_str = str(user_id)
        
        if user_id_str in self.users:
            # Обновляем данные существующего пользователя
            self.users[user_id_str]["username"] = username
            self.users[user_id_str]["first_name"] = first_name
            self.users[user_id_str]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Создаем нового пользователя
            self.users[user_id_str] = {
                "username": username,
                "first_name": first_name,
                "registered_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "shared_files": [],
                "received_files": [],
                "verified": False
            }
            logger.info(f"Зарегистрирован новый пользователь: {username} (ID: {user_id})")
        
        self.save_data()
        return self.users[user_id_str]
    
    def get_user(self, user_id):
        """Получить информацию о пользователе."""
        user_id_str = str(user_id)
        return self.users.get(user_id_str)
    
    def update_user_activity(self, user_id):
        """Обновить время последней активности пользователя."""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            self.users[user_id_str]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_data()
            
    def verify_user(self, user_id, password):
        """Проверить пароль пользователя и установить статус верификации.
        
        Args:
            user_id: ID пользователя
            password: Введенный пароль
            
        Returns:
            True, если верификация успешна, False в противном случае
        """
        from config import SPECIAL_PASSWORD, BOT_ADMIN_ID
        
        user_id_str = str(user_id)
        
        # Если пользователь не существует
        if user_id_str not in self.users:
            logger.error(f"Попытка верификации несуществующего пользователя с ID {user_id}")
            return False
        
        # Если пользователь уже верифицирован
        if self.users[user_id_str].get("verified", False):
            logger.info(f"Пользователь {user_id} уже верифицирован")
            return True
        
        # Админу не нужна верификация
        if BOT_ADMIN_ID and user_id_str == str(BOT_ADMIN_ID):
            self.users[user_id_str]["verified"] = True
            self.save_data()
            logger.info(f"Администратор {user_id} автоматически верифицирован")
            return True
        
        # Проверяем пароль
        if password == SPECIAL_PASSWORD:
            self.users[user_id_str]["verified"] = True
            self.save_data()
            logger.info(f"Пользователь {user_id} успешно верифицирован")
            return True
        else:
            logger.warning(f"Неудачная попытка верификации пользователя {user_id}")
            return False
            
    def is_user_verified(self, user_id):
        """Проверить, верифицирован ли пользователь.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True, если пользователь верифицирован, False в противном случае
        """
        user_id_str = str(user_id)
        
        # Если пользователь не существует
        if user_id_str not in self.users:
            return False
        
        return self.users[user_id_str].get("verified", False)
    
    def create_share_link(self, user_id, file_path, file_type, file_name, ttl=SHARE_LINK_TTL):
        """Создать ссылку для обмена файлом.
        
        Args:
            user_id: ID пользователя, создающего ссылку
            file_path: Путь к файлу
            file_type: Тип файла (photo, video, document)
            file_name: Имя файла
            ttl: Время жизни ссылки в часах
            
        Returns:
            Уникальный идентификатор общего файла
        """
        user_id_str = str(user_id)
        
        # Проверка существования пользователя
        if user_id_str not in self.users:
            logger.error(f"Пользователь с ID {user_id} не зарегистрирован")
            return None
        
        # Проверка существования файла
        if not os.path.exists(file_path):
            logger.error(f"Файл не существует: {file_path}")
            return None
        
        # Генерация уникального идентификатора
        share_id = str(uuid.uuid4())
        
        # Расчет времени истечения ссылки
        expiry_time = (datetime.now() + timedelta(hours=ttl)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Добавление файла в список общих файлов
        self.shared_files[share_id] = {
            "owner_id": user_id_str,
            "file_path": file_path,
            "file_type": file_type,
            "file_name": file_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expiry_time,
            "access_count": 0,
            "shared_with": []
        }
        
        # Добавление в список общих файлов пользователя
        if "shared_files" not in self.users[user_id_str]:
            self.users[user_id_str]["shared_files"] = []
        
        self.users[user_id_str]["shared_files"].append(share_id)
        
        self.save_data()
        logger.info(f"Создана ссылка для обмена файлом '{file_name}' пользователем {user_id} (ID ссылки: {share_id})")
        
        return share_id
    
    def get_shared_file(self, share_id):
        """Получить информацию о общем файле."""
        if share_id not in self.shared_files:
            return None
        
        shared_file = self.shared_files[share_id]
        
        # Проверяем, не истекла ли ссылка
        expires_at = datetime.strptime(shared_file["expires_at"], "%Y-%m-%d %H:%M:%S")
        if expires_at < datetime.now():
            logger.info(f"Ссылка с ID {share_id} истекла")
            return None
        
        return shared_file
        
    def get_referral_link(self, share_id):
        """Создать реферальную ссылку для доступа к файлу.
        
        Args:
            share_id: ID общего файла
            
        Returns:
            URL для прямого доступа к файлу через Telegram
        """
        if share_id not in self.shared_files:
            return None
            
        # Проверяем, не истекла ли ссылка
        shared_file = self.get_shared_file(share_id)
        if not shared_file:
            return None
            
        # Формируем команду для Telegram
        command = f"/share_{share_id}"
        
        # Формируем URL для прямого доступа
        # Формат: https://t.me/bot_username?start=command
        share_url = f"https://t.me/{BOT_USERNAME}?start=share_{share_id}"
        
        return share_url
    
    def access_shared_file(self, share_id, user_id):
        """Получить доступ к общему файлу.
        
        Args:
            share_id: ID общего файла
            user_id: ID пользователя, запрашивающего доступ
            
        Returns:
            Информация о файле или None, если файл не найден или ссылка истекла
        """
        user_id_str = str(user_id)
        
        # Проверяем существование пользователя
        if user_id_str not in self.users:
            logger.error(f"Пользователь с ID {user_id} не зарегистрирован")
            return None
        
        # Получаем информацию о файле
        shared_file = self.get_shared_file(share_id)
        if not shared_file:
            return None
        
        # Проверяем, существует ли файл физически, и при необходимости исправляем путь
        correct_path = self.check_file_exists(
            shared_file["file_path"],
            shared_file["owner_id"],
            shared_file["file_type"]
        )
        
        if not correct_path:
            logger.error(f"Файл не существует: {shared_file['file_path']}")
            return None
            
        # Обновляем путь к файлу, если он изменился
        if correct_path != shared_file["file_path"]:
            logger.info(f"Исправлен путь к файлу: {shared_file['file_path']} -> {correct_path}")
            self.shared_files[share_id]["file_path"] = correct_path
            self.save_data()
        
        # Обновляем информацию о доступе
        self.shared_files[share_id]["access_count"] += 1
        
        # Добавляем пользователя в список тех, кому был открыт доступ
        if user_id_str not in self.shared_files[share_id]["shared_with"]:
            self.shared_files[share_id]["shared_with"].append(user_id_str)
        
        # Добавляем файл в список полученных для пользователя
        if "received_files" not in self.users[user_id_str]:
            self.users[user_id_str]["received_files"] = []
        
        if share_id not in self.users[user_id_str]["received_files"]:
            self.users[user_id_str]["received_files"].append(share_id)
        
        self.save_data()
        logger.info(f"Пользователь {user_id} получил доступ к файлу с ID {share_id}")
        
        return shared_file
    
    def cleanup_expired_shares(self):
        """Очистить истекшие ссылки на файлы."""
        current_time = datetime.now()
        expired_shares = []
        
        for share_id, share_info in list(self.shared_files.items()):
            expires_at = datetime.strptime(share_info["expires_at"], "%Y-%m-%d %H:%M:%S")
            if expires_at < current_time:
                expired_shares.append(share_id)
                # Удаляем из списка общих файлов
                self.shared_files.pop(share_id)
                
                # Удаляем из списка пользователя
                owner_id = share_info["owner_id"]
                if owner_id in self.users and "shared_files" in self.users[owner_id]:
                    if share_id in self.users[owner_id]["shared_files"]:
                        self.users[owner_id]["shared_files"].remove(share_id)
                
                # Удаляем из списков получателей
                for user_id, user_info in self.users.items():
                    if "received_files" in user_info and share_id in user_info["received_files"]:
                        user_info["received_files"].remove(share_id)
        
        if expired_shares:
            self.save_data()
            logger.info(f"Очищено {len(expired_shares)} истекших ссылок: {', '.join(expired_shares)}")
    
    def get_user_shared_files(self, user_id):
        """Получить список файлов, которыми поделился пользователь."""
        user_id_str = str(user_id)
        
        if user_id_str not in self.users:
            return []
        
        # Получаем список идентификаторов общих файлов пользователя
        shared_file_ids = self.users[user_id_str].get("shared_files", [])
        
        # Фильтруем только существующие и не истекшие файлы
        valid_shares = []
        for share_id in shared_file_ids:
            share_info = self.get_shared_file(share_id)
            if share_info:
                valid_shares.append({
                    "id": share_id,
                    "info": share_info
                })
        
        return valid_shares
    
    def get_user_received_files(self, user_id):
        """Получить список файлов, полученных пользователем."""
        user_id_str = str(user_id)
        
        if user_id_str not in self.users:
            return []
        
        # Получаем список идентификаторов полученных файлов
        received_file_ids = self.users[user_id_str].get("received_files", [])
        
        # Фильтруем только существующие и не истекшие файлы
        valid_shares = []
        for share_id in received_file_ids:
            share_info = self.get_shared_file(share_id)
            if share_info:
                valid_shares.append({
                    "id": share_id,
                    "info": share_info
                })
        
        return valid_shares
    
    def cleanup_by_filepath(self, file_path):
        """Удалить все общие ссылки на конкретный файл.
        
        Args:
            file_path: Путь к файлу, который был удален
            
        Returns:
            Количество удаленных ссылок
        """
        # Сохраняем ID файлов для удаления
        shares_to_delete = []
        
        # Находим все общие файлы, которые указывают на данный путь или относятся к удаленному файлу
        for share_id, share_info in list(self.shared_files.items()):
            # Проверяем точное совпадение пути
            if share_info["file_path"] == file_path:
                shares_to_delete.append(share_id)
            else:
                # Проверяем, относится ли запись к тому же файлу под другим путем
                file_name = os.path.basename(file_path)
                share_file_name = os.path.basename(share_info["file_path"])
                
                if file_name == share_file_name:
                    # Проверяем существование файла
                    if not os.path.exists(share_info["file_path"]):
                        shares_to_delete.append(share_id)
        
        # Если нет ссылок на этот файл, возвращаем 0
        if not shares_to_delete:
            return 0
        
        # Удаляем все найденные ссылки
        for share_id in shares_to_delete:
            # Получаем ID владельца
            owner_id = self.shared_files[share_id]["owner_id"]
            
            # Удаляем из списка общих файлов
            self.shared_files.pop(share_id)
            
            # Удаляем из списка пользователя-владельца
            if owner_id in self.users and "shared_files" in self.users[owner_id]:
                if share_id in self.users[owner_id]["shared_files"]:
                    self.users[owner_id]["shared_files"].remove(share_id)
            
            # Удаляем из списков получателей
            for user_id, user_info in self.users.items():
                if "received_files" in user_info and share_id in user_info["received_files"]:
                    user_info["received_files"].remove(share_id)
        
        # Сохраняем изменения
        self.save_data()
        logger.info(f"Удалено {len(shares_to_delete)} общих ссылок на файл {file_path}")
        
        return len(shares_to_delete)
    
    def delete_share(self, share_id, user_id):
        """Удалить общий доступ к файлу (только для владельца).
        
        Args:
            share_id: ID общего файла
            user_id: ID пользователя (должен быть владельцем)
            
        Returns:
            True если успешно, False в противном случае
        """
        user_id_str = str(user_id)
        
        # Проверяем существование общего файла
        if share_id not in self.shared_files:
            logger.error(f"Общий файл с ID {share_id} не найден")
            return False
        
        # Проверяем, является ли пользователь владельцем
        share_info = self.shared_files[share_id]
        if share_info["owner_id"] != user_id_str:
            logger.error(f"Пользователь {user_id} не является владельцем файла с ID {share_id}")
            return False
        
        # Удаляем из списка общих файлов
        self.shared_files.pop(share_id)
        
        # Удаляем из списка пользователя
        if "shared_files" in self.users[user_id_str] and share_id in self.users[user_id_str]["shared_files"]:
            self.users[user_id_str]["shared_files"].remove(share_id)
        
        # Удаляем из списков получателей
        for user_id, user_info in self.users.items():
            if "received_files" in user_info and share_id in user_info["received_files"]:
                user_info["received_files"].remove(share_id)
        
        self.save_data()
        logger.info(f"Удален общий доступ к файлу с ID {share_id}")
        
        return True

    def fix_shared_file_paths(self):
        """
        Исправляет пути к файлам в общих ссылках.
        Проверяет все ссылки на общие файлы и обновляет пути,
        если они не соответствуют новой структуре с папками пользователей.
        """
        logger.info("Запуск проверки и исправления путей к файлам в общих ссылках")
        fixed_count = 0
        removed_count = 0
        
        for share_id, share_info in list(self.shared_files.items()):
            file_path = share_info["file_path"]
            file_type = share_info["file_type"]
            owner_id = share_info["owner_id"]
            
            # Проверяем, существует ли файл
            if not os.path.exists(file_path):
                # Если файл не существует по указанному пути, проверяем, существует ли он в папке пользователя
                # Определяем, к какой папке должен принадлежать файл
                user_folder = f"saved_files/users/{owner_id}"
                
                if file_type == "photo":
                    user_type_folder = f"{user_folder}/photos"
                elif file_type == "video":
                    user_type_folder = f"{user_folder}/videos"
                else:  # document
                    user_type_folder = f"{user_folder}/documents"
                
                # Получаем имя файла из старого пути
                file_name = os.path.basename(file_path)
                
                # Новый путь в папке пользователя
                new_path = os.path.join(user_type_folder, file_name)
                
                # Проверяем, существует ли файл по новому пути
                if os.path.exists(new_path):
                    # Обновляем путь в записи о шаринге
                    self.shared_files[share_id]["file_path"] = new_path
                    logger.info(f"Исправлен путь к файлу для шаринга {share_id}: {file_path} -> {new_path}")
                    fixed_count += 1
                else:
                    # Проверяем, существует ли файл в общей папке
                    old_type_folder = f"saved_files/{file_type}s"
                    if os.path.exists(os.path.join(old_type_folder, file_name)):
                        # Создаем папки пользователя, если они не существуют
                        os.makedirs(user_type_folder, exist_ok=True)
                        
                        # Копируем файл из общей папки в папку пользователя
                        old_full_path = os.path.join(old_type_folder, file_name)
                        import shutil
                        try:
                            shutil.copy2(old_full_path, new_path)
                            logger.info(f"Файл скопирован из {old_full_path} в {new_path}")
                            
                            # Обновляем путь в записи о шаринге
                            self.shared_files[share_id]["file_path"] = new_path
                            fixed_count += 1
                        except Exception as e:
                            logger.error(f"Ошибка при копировании файла: {e}")
                            # Удаляем шаринг, если не удалось скопировать файл
                            self.shared_files.pop(share_id)
                            # Удаляем из списка пользователя
                            if owner_id in self.users and "shared_files" in self.users[owner_id]:
                                if share_id in self.users[owner_id]["shared_files"]:
                                    self.users[owner_id]["shared_files"].remove(share_id)
                            removed_count += 1
                    else:
                        # Если файл не найден ни в одной папке, удаляем запись о шаринге
                        self.shared_files.pop(share_id)
                        # Удаляем из списка пользователя
                        if owner_id in self.users and "shared_files" in self.users[owner_id]:
                            if share_id in self.users[owner_id]["shared_files"]:
                                self.users[owner_id]["shared_files"].remove(share_id)
                        
                        logger.info(f"Удален шаринг {share_id}, так как файл не найден: {file_path}")
                        removed_count += 1
        
        if fixed_count > 0 or removed_count > 0:
            self.save_data()
            logger.info(f"Исправлено {fixed_count} и удалено {removed_count} записей о шаринге")
    
    def check_file_exists(self, file_path, owner_id, file_type):
        """
        Проверяет существование файла и возвращает корректный путь.
        
        Args:
            file_path: Путь к файлу
            owner_id: ID владельца
            file_type: Тип файла (photo, video, document)
            
        Returns:
            Корректный путь к файлу или None, если файл не найден
        """
        # Сначала проверяем, существует ли файл по указанному пути
        if os.path.exists(file_path):
            return file_path
        
        # Если файл не найден, пробуем найти его в папке пользователя
        file_name = os.path.basename(file_path)
        user_folder = f"saved_files/users/{owner_id}"
        
        if file_type == "photo":
            user_type_folder = f"{user_folder}/photos"
        elif file_type == "video":
            user_type_folder = f"{user_folder}/videos"
        else:  # document
            user_type_folder = f"{user_folder}/documents"
        
        new_path = os.path.join(user_type_folder, file_name)
        
        if os.path.exists(new_path):
            return new_path
            
        # Проверяем старую структуру папок
        old_type_folder = f"saved_files/{file_type}s"
        old_path = os.path.join(old_type_folder, file_name)
        
        if os.path.exists(old_path):
            return old_path
            
        # Файл не найден
        return None

# Создание глобального экземпляра хранилища
user_storage = UserStorage()

# Запуск очистки истекших ссылок при импорте модуля
user_storage.cleanup_expired_shares()