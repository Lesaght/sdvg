import logging
import os
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Folder where files will be saved
SAVE_FOLDER = os.environ.get("SAVE_FOLDER", "saved_files")

# Supported file types
SUPPORTED_PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']

# Maximum number of files to display in one page
FILES_PER_PAGE = 5

def save_file(bot: Bot, file_obj, save_folder: str, file_name: str) -> str:
    """Download and save a file sent by the user."""
    try:
        # Get the file from Telegram
        file = bot.get_file(file_obj.file_id)
        
        # Create a safe file name
        safe_name = sanitize_filename(file_name)
        
        # Prepare the full file path
        file_path = os.path.join(save_folder, safe_name)
        
        # Check if a file with the same name already exists
        if os.path.exists(file_path):
            base_name, ext = os.path.splitext(safe_name)
            count = 1
            while os.path.exists(file_path):
                new_name = f"{base_name}_{count}{ext}"
                file_path = os.path.join(save_folder, new_name)
                count += 1
        
        # Download the file
        file.download(file_path)
        
        return file_path
    
    except TelegramError as e:
        logger.error(f"Telegram error while saving file: {e}")
        return ""
    
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return ""

def get_file_list(folder_path: str) -> list:
    """Get a list of all files in a folder."""
    try:
        if not os.path.exists(folder_path):
            return []
            
        # Get all files
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        return files
    
    except Exception as e:
        logger.error(f"Error getting file list: {e}")
        return []

def get_file_type(file_path: str) -> str:
    """Determine the type of a file based on its extension."""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext in SUPPORTED_PHOTO_EXTENSIONS:
        return "photo"
    elif ext in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    else:
        return "document"

def sanitize_filename(filename: str) -> str:
    """Make a filename safe for saving to the filesystem."""
    # Replace problematic characters
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 100:
        base, ext = os.path.splitext(filename)
        filename = base[:96] + ext
        
    return filename

def start(update, context):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_html(
        f"Hi {user.first_name}! I'm your file storage bot.\n\n"
        f"You can send me any files, and I'll save them to a folder on your computer.\n"
        f"Use /files to browse your saved photos and videos.\n"
        f"Use /help to see all available commands."
    )

def help_command(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text(
        "Here's what I can do:\n\n"
        "- Send me any file, photo, or video to save it\n"
        "- Use /files to browse saved photos and videos\n"
        "- When browsing, use navigation buttons to see more files\n"
        "- Click on a file to view it\n\n"
        "All files are saved to a folder on your computer."
    )

def files_command(update, context):
    """Show the list of saved files when the command /files is issued."""
    show_files(update, context, 0)

def receive_file(update, context):
    """Receive and save a file sent by the user."""
    try:
        message = update.message
        chat_id = message.chat_id
        
        # Determine what type of file was sent
        if message.photo:
            file_obj = message.photo[-1]  # Get the largest photo size
            file_name = f"photo_{file_obj.file_unique_id}.jpg"
            file_type = "photo"
        elif message.video:
            file_obj = message.video
            file_name = message.video.file_name or f"video_{file_obj.file_unique_id}.mp4"
            file_type = "video"
        elif message.document:
            file_obj = message.document
            file_name = message.document.file_name or f"doc_{file_obj.file_unique_id}"
            file_type = "document"
        else:
            message.reply_text("I can only save photos, videos, and documents.")
            return

        # Send a processing message
        status_message = message.reply_text(f"Processing your {file_type}...")
        
        # Download and save the file
        file_path = save_file(context.bot, file_obj, SAVE_FOLDER, file_name)
        
        if file_path and os.path.exists(file_path):
            status_message.edit_text(f"Your {file_type} has been saved successfully!")
            logger.info(f"File saved to {file_path}")
        else:
            status_message.edit_text(f"Failed to save your {file_type}. Please try again.")
            logger.error(f"Failed to save file {file_name}")
            
    except Exception as e:
        logger.error(f"Error in receive_file: {e}")
        update.message.reply_text(f"An error occurred while saving your file: {str(e)}")

def show_files(update, context, page=0):
    """Show the list of saved files with pagination."""
    query = update.callback_query
    
    # Get the list of files
    all_files = get_file_list(SAVE_FOLDER)
    
    # Filter for supported media files
    media_files = [f for f in all_files if get_file_type(f) in ['photo', 'video']]
    
    if not media_files:
        message_text = "No media files found in the storage folder."
        keyboard = []
    else:
        # Calculate pagination
        start_idx = page * FILES_PER_PAGE
        end_idx = start_idx + FILES_PER_PAGE
        current_files = media_files[start_idx:end_idx]
        
        # Create message and keyboard
        message_text = f"📁 Your saved files (Page {page+1}/{max(1, (len(media_files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE)}):"
        
        keyboard = []
        for file in current_files:
            file_type = get_file_type(file)
            icon = "🖼️" if file_type == "photo" else "🎬"
            display_name = os.path.basename(file)
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            
            keyboard.append([
                InlineKeyboardButton(f"{icon} {display_name}", 
                                     callback_data=f"view:{file}")
            ])
        
        # Add navigation buttons
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{page-1}")
            )
            
        if end_idx < len(media_files):
            nav_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"page:{page+1}")
            )
            
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or edit message
    if query:
        query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )

def view_file(update, context, file_path):
    """Send the file to the user for viewing."""
    query = update.callback_query
    
    if not os.path.exists(file_path):
        query.edit_message_text(text="This file no longer exists.")
        return
    
    file_size = os.path.getsize(file_path)
    # Telegram has a 50MB limit for bots
    if file_size > 50 * 1024 * 1024:
        query.edit_message_text(
            text=f"This file is too large to be sent (Size: {file_size/(1024*1024):.1f} MB, Max: 50 MB)."
        )
        return
    
    file_type = get_file_type(file_path)
    file_name = os.path.basename(file_path)
    
    # Create back button
    keyboard = [[InlineKeyboardButton("⬅️ Back to list", callback_data="files")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Send the file
        with open(file_path, 'rb') as file:
            if file_type == "photo":
                query.message.reply_photo(
                    photo=file,
                    caption=f"📄 {file_name}",
                    reply_markup=reply_markup
                )
            elif file_type == "video":
                query.message.reply_video(
                    video=file,
                    caption=f"📄 {file_name}",
                    reply_markup=reply_markup
                )
            else:
                query.message.reply_document(
                    document=file,
                    caption=f"📄 {file_name}",
                    reply_markup=reply_markup
                )
            
        # Edit original message to show that file has been sent
        query.edit_message_text(
            text=f"Sent file: {file_name}\nUse the buttons below the file to navigate back.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending file {file_path}: {e}")
        query.edit_message_text(
            text=f"Error sending file: {str(e)}",
            reply_markup=reply_markup
        )

def button_handler(update, context):
    """Handle button clicks from InlineKeyboardMarkup."""
    query = update.callback_query
    query.answer()
    
    data = query.data
    
    if data == "files":
        show_files(update, context)
    elif data.startswith("page:"):
        page = int(data.split(":")[1])
        show_files(update, context, page)
    elif data.startswith("view:"):
        file_path = data[5:]  # Remove "view:" prefix
        view_file(update, context, file_path)
    else:
        query.edit_message_text(text=f"Unknown button: {data}")

def unknown_command(update, context):
    """Handle unknown commands."""
    update.message.reply_text(
        "Sorry, I didn't understand that command. Try /help to see available commands."
    )

def error_handler(update, context):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Send a message to the user
    if update and update.effective_message:
        update.effective_message.reply_text(
            "An error occurred while processing your request. Please try again later."
        )

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(BOT_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Create save folder if it doesn't exist
    if not os.path.exists(SAVE_FOLDER):
        os.makedirs(SAVE_FOLDER)
        logger.info(f"Created save folder at {SAVE_FOLDER}")

    # Add handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("files", files_command))
    
    # Handle file messages
    dispatcher.add_handler(MessageHandler(
        Filters.photo | Filters.video | Filters.document, 
        receive_file
    ))
    
    # Handle button callbacks
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    # Handle unknown commands
    dispatcher.add_handler(MessageHandler(Filters.command, unknown_command))
    
    # Register error handler
    dispatcher.add_error_handler(error_handler)

    # Start the Bot
    logger.info("Starting bot...")
    updater.start_polling()
    
    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()