import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import db
import video

# Configurations (loaded from env with defaults)
OWNER_ID = int(os.environ.get("OWNER_ID", 276868456))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@bestgifsintheworld")


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Custom filters
class AdminFilter(filters.BaseFilter):
    def filter(self, message):
        user_id = message.from_user.id if message.from_user else None
        if user_id == OWNER_ID:
            return True
        return db.is_admin(user_id)

class OwnerFilter(filters.BaseFilter):
    def filter(self, message):
        user_id = message.from_user.id if message.from_user else None
        return user_id == OWNER_ID

admin_filter = AdminFilter()
owner_filter = OwnerFilter()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello Owner! The bot is running.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message.from_user else None
    
    is_owner = (user_id == OWNER_ID)
    is_admin = db.is_admin(user_id)
    
    help_text = "🤖 **راهنمای ربات واترمارک Trend GIF**\n\n"
    
    if is_owner:
        help_text += "👑 **دستورات مدیریت کل (Owner):**\n"
        help_text += "🔹 `/start` - بررسی وضعیت ربات\n"
        help_text += "🔹 `/add_admin <user_id>` - افزودن ادمین جدید\n"
        help_text += "🔹 `/add_tag <hashtag>` - افزودن هشتگ جدید به لیست\n"
        help_text += "🔹 `/remove_tag <hashtag>` - حذف هشتگ از لیست\n"
        help_text += "🔹 `/report` - دریافت گزارش فعالیت ادمین‌ها\n\n"
        
    if is_owner or is_admin:
        help_text += "👥 **راهنمای ارسال پست (Admins):**\n"
        help_text += "۱. یک فایل **ویدیو** یا **گیف (Animation)** برای ربات ارسال کنید.\n"
        help_text += "۲. ربات در زیر همان پیام دکمه‌های شیشه‌ای شامل هشتگ‌های مجاز به شما نمایش می‌دهد.\n"
        help_text += "۳. کافیست روی یکی از دکمه‌ها کلیک کنید.\n"
        help_text += "۴. ربات به طور خودکار واترمارک کانال را روی ویدیو قرار داده و آن را در کانال منتشر می‌کند.\n\n"
        help_text += "❌ برای لغو عملیات روی دکمه ❌ Cancel کلیک کنید."
    else:
        help_text += "⛔️ **عدم دسترسی**\n"
        help_text += "شما جزء ادمین‌های مجاز این ربات نیستید. این ربات یک ابزار خصوصی برای واترمارک ویدیوها است و استفاده عمومی ندارد."
        
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /add_admin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        if db.add_admin(new_admin_id):
            await update.message.reply_text(f"Admin {new_admin_id} added successfully.")
        else:
            await update.message.reply_text(f"Admin {new_admin_id} is already in the database.")
    except ValueError:
        await update.message.reply_text("User ID must be an integer.")

async def add_tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /add_tag <hashtag>")
        return
        
    tag = context.args[0]
    if not tag.startswith('#'):
        tag = '#' + tag
        
    if db.add_hashtag(tag):
        await update.message.reply_text(f"Hashtag {tag} added successfully.")
    else:
        await update.message.reply_text(f"Hashtag {tag} is already in the database.")

async def remove_tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /remove_tag <hashtag>")
        return
        
    tag = context.args[0]
    if not tag.startswith('#'):
        tag = '#' + tag
        
    if db.remove_hashtag(tag):
        await update.message.reply_text(f"Hashtag {tag} removed successfully.")
    else:
        await update.message.reply_text(f"Hashtag {tag} was not found.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report_text = db.get_report()
    await update.message.reply_text(report_text)


# Media Handling
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Extract file_id to store in user_data
    original_message = update.message
    file_id = None
    if original_message.animation:
        file_id = original_message.animation.file_id
    elif original_message.video:
        file_id = original_message.video.file_id
    elif original_message.document and original_message.document.mime_type.startswith('video/'):
        file_id = original_message.document.file_id

    if not file_id:
        await update.message.reply_text("Unsupported media type.")
        return

    # Save to user_data (specific to the user handling this interaction)
    context.user_data['pending_file_id'] = file_id

    tags = db.get_all_hashtags()
    keyboard = []
    
    # Group tags into rows of 2
    row = []
    for tag in tags:
        row.append(InlineKeyboardButton(tag, callback_data=f"tag|{tag}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="tag|Cancel")])
    
    markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Please select a hashtag for this media:", reply_markup=markup)

async def handle_inline_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Permission check
    user_id = query.from_user.id
    if user_id != OWNER_ID and not db.is_admin(user_id):
        await query.answer("You are not authorized.", show_alert=True)
        return
        
    await query.answer()
    
    data = query.data
    if not data.startswith("tag|"):
        return
        
    text = data.split("|", 1)[1]
    
    if text == "Cancel":
        await query.edit_message_text("Cancelled processing.")
        if 'pending_file_id' in context.user_data:
            del context.user_data['pending_file_id']
        return
        
    if not db.valid_hashtag(text):
        await query.edit_message_text("Invalid hashtag. Please select a valid one.")
        return

    file_id = context.user_data.get('pending_file_id')
    
    if not file_id:
        await query.edit_message_text("Could not find the original media. The bot might have restarted, or you need to send the file again.")
        return

    await query.edit_message_text("Downloading and processing video... Please wait.")
    
    input_path = f"input_{file_id}.mp4"
    output_path = f"output_{file_id}.mp4"
    
    try:
        media_file = await context.bot.get_file(file_id)
        await media_file.download_to_drive(input_path)
        
        # Add watermark
        success = await video.watermark_video(input_path, output_path, CHANNEL_USERNAME)
        
        if success:
            # Send to channel as ANIMATION (GIF)
            with open(output_path, 'rb') as f:
                await context.bot.send_animation(
                    chat_id=CHANNEL_USERNAME,
                    animation=f,
                    caption=text
                )
            
            # Log successful post
            db.log_post(query.from_user.id)
            await query.edit_message_text("✅ Video processed and published to channel successfully!")
        else:
            await query.edit_message_text("❌ Error processing video with FFmpeg.")
            
    except Exception as e:
        logger.error(f"Error handling media: {e}")
        await query.edit_message_text(f"❌ An error occurred: {e}")
    finally:
        # Clean up memory mapping
        if 'pending_file_id' in context.user_data:
            del context.user_data['pending_file_id']
        
        # Clean up files
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)


def main():
    # Initialize Database
    db.init_db()
    # Add OWNER to admins implicitly or ensure the filter handles it. Filter already does.
    
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Exiting.")
        return
        
    IP_ADDRESS = os.environ.get("IP_ADDRESS")
    if not IP_ADDRESS:
        logger.error("IP_ADDRESS environment variable not set. Exiting.")
        return
        
    PORT = int(os.environ.get("PORT", 8443))
    
    # job_queue(None) fixes TypeError: cannot create weak reference to 'Application' object in Python 3.13+ with PTB v20.x
    app = ApplicationBuilder().token(TOKEN).job_queue(None).build()
    
    # Owner Commands
    app.add_handler(CommandHandler("start", start_command, filters=owner_filter))
    app.add_handler(CommandHandler("add_admin", add_admin_command, filters=owner_filter))
    app.add_handler(CommandHandler("add_tag", add_tag_command, filters=owner_filter))
    app.add_handler(CommandHandler("remove_tag", remove_tag_command, filters=owner_filter))
    app.add_handler(CommandHandler("report", report_command, filters=owner_filter))
    
    # Public Commands
    app.add_handler(CommandHandler("help", help_command))
    
    # Media Handlers
    # Filter for animation or video without audio (or we strip audio anyway so video is fine)
    media_filter = admin_filter & (filters.ANIMATION | filters.VIDEO)
    app.add_handler(MessageHandler(media_filter, handle_media))
    
    # Handle the inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_inline_button, pattern="^tag\\|"))
    
    logger.info(f"Starting bot webhook on port {PORT}...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://{IP_ADDRESS}:{PORT}/{TOKEN}",
        cert="public.pem",
        key="private.key"
    )

if __name__ == '__main__':
    main()
