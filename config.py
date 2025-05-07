import os
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменной окружения
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN не установлен!")
    # Используем прямо заданный токен
    BOT_TOKEN = "7935052392:AAH4DiqyOIp5IN9NfR6n-RQROCZeQcROM7c"
    logger.info("Используется жестко заданный токен")

# Имя пользователя бота (без @)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "bbhhggddqqzzxxccgg_bot")

# Специальный пароль для первого входа (из переменной окружения или стандартный)
SPECIAL_PASSWORD = os.environ.get("BOT_SPECIAL_PASSWORD", "Derzhavka")  # Установлен пароль "Derzhavka"
BOT_ADMIN_ID = os.environ.get("BOT_ADMIN_ID", None)  # ID администратора бота

# Папка, где будут сохраняться файлы
SAVE_FOLDER = "saved_files"

# Папка для пользовательских файлов
USER_FILES_BASE_FOLDER = "saved_files/users"

# Поддерживаемые типы файлов
SUPPORTED_PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']

# Максимальное количество файлов на одной странице
FILES_PER_PAGE = 5

# Время жизни ссылки для обмена файлами (в часах)
SHARE_LINK_TTL = 24  # 24 часа