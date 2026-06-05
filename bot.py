import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ForceReply
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import db
import video

# Hardcoded constants
OWNER_ID = 276868456
# CHANNEL_USERNAME = "@trend_gif"
CHANNEL_USERNAME = "@bestgifsintheworld"


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
    tags = db.get_all_hashtags()
    keyboard = [[KeyboardButton(tag)] for tag in tags]
    keyboard.append([KeyboardButton("Cancel")])
    
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, selective=True)
    
    # Send a message just to show the keyboard
    await update.message.reply_text("Here are the available hashtags:", reply_markup=markup)
    
    # Extract file_id to store in memory mapping
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

    # Send the actual prompt for hashtag, forcing a reply
    msg = await update.message.reply_text(
        "Please select a hashtag for this media by replying to THIS message:",
        reply_markup=ForceReply(selective=True),
        reply_to_message_id=update.message.message_id
    )
    
    # Save the mapping of this prompt's message_id to the pending file_id
    if context.chat_data is not None:
        context.chat_data[msg.message_id] = file_id

async def handle_hashtag_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # To find the original media, we rely on `reply_to_message` since we forced a reply.
    if not update.message.reply_to_message:
        return

    text = update.message.text
    bot_prompt_msg = update.message.reply_to_message
    
    if text == "Cancel":
        await update.message.reply_text("Cancelled processing.", reply_to_message_id=update.message.message_id)
        if context.chat_data and bot_prompt_msg.message_id in context.chat_data:
            del context.chat_data[bot_prompt_msg.message_id]
        return
        
    if not db.valid_hashtag(text):
        await update.message.reply_text("Invalid hashtag. Please select from the keyboard or type an existing tag.", reply_to_message_id=update.message.message_id)
        return

    # In Telegram, the API does not send the grandparent message. Thus we stored the file_id in chat_data!
    file_id = context.chat_data.get(bot_prompt_msg.message_id) if context.chat_data is not None else None
    
    if not file_id:
        await update.message.reply_text("Could not find the original media. The bot might have restarted.", reply_to_message_id=update.message.message_id)
        return

    status_msg = await update.message.reply_text("Downloading and processing video... Please wait.")
    
    input_path = f"input_{file_id}.mp4"
    output_path = f"output_{file_id}.mp4"
    
    try:
        media_file = await context.bot.get_file(file_id)
        await media_file.download_to_drive(input_path)
        
        # Add watermark
        success = await video.watermark_video(input_path, output_path, CHANNEL_USERNAME)
        
        if success:
            # Send to channel
            with open(output_path, 'rb') as f:
                await context.bot.send_video(
                    chat_id=CHANNEL_USERNAME,
                    video=f,
                    caption=text
                )
            
            # Log successful post
            db.log_post(update.message.from_user.id)
            await status_msg.edit_text("✅ Video processed and published to channel successfully!")
        else:
            await status_msg.edit_text("❌ Error processing video with FFmpeg.")
            
    except Exception as e:
        logger.error(f"Error handling media: {e}")
        await status_msg.edit_text(f"❌ An error occurred: {e}")
    finally:
        # Clean up mapping
        bot_prompt_msg = update.message.reply_to_message
        if bot_prompt_msg and context.chat_data and bot_prompt_msg.message_id in context.chat_data:
            del context.chat_data[bot_prompt_msg.message_id]
        
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
    
    # Media Handlers
    # Filter for animation or video without audio (or we strip audio anyway so video is fine)
    media_filter = admin_filter & (filters.ANIMATION | filters.VIDEO)
    app.add_handler(MessageHandler(media_filter, handle_media))
    
    # Handle the hashtag reply
    reply_filter = admin_filter & filters.TEXT & filters.REPLY
    app.add_handler(MessageHandler(reply_filter, handle_hashtag_reply))
    
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
