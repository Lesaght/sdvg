import os
import logging
from telebot.types import File

logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """Сделать имя файла безопасным для сохранения в файловой системе."""
    # Заменить проблемные символы
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Ограничить длину
    if len(filename) > 100:
        base, ext = os.path.splitext(filename)
        filename = base[:96] + ext
        
    return filename

def get_file_type(file_path, photo_extensions, video_extensions):
    """Определить тип файла по его расширению."""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext in photo_extensions:
        return "photo"
    elif ext in video_extensions:
        return "video"
    else:
        return "document"

def get_file_list(folder_path):
    """Получить список всех файлов в папке."""
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logger.info(f"Создана папка сохранения: {folder_path}")
            return []
            
        # Получить все файлы
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)
        
        # Сортировать по времени изменения (сначала новые)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        return files
    
    except Exception as e:
        logger.error(f"Ошибка при получении списка файлов: {e}")
        return []

def save_file(bot, file_info, save_folder, file_name):
    """Загрузить и сохранить файл, отправленный пользователем."""
    try:
        # Создать папку сохранения, если она не существует
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
            logger.info(f"Создана папка сохранения: {save_folder}")
        
        # Создать безопасное имя файла
        safe_name = sanitize_filename(file_name)
        
        # Подготовить полный путь к файлу
        file_path = os.path.join(save_folder, safe_name)
        
        # Проверить, существует ли файл с таким же именем
        if os.path.exists(file_path):
            base_name, ext = os.path.splitext(safe_name)
            count = 1
            while os.path.exists(file_path):
                new_name = f"{base_name}_{count}{ext}"
                file_path = os.path.join(save_folder, new_name)
                count += 1
        
        # Скачать файл
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохранить файл
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        return file_path
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {e}")
        return None