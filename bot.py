import logging
from logging.handlers import RotatingFileHandler
import os
import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
import community
import review

# Configurations (loaded from env with defaults)
OWNER_ID = int(os.environ.get("OWNER_ID", 276868456))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@bestgifsintheworld")
KEYBOARD_MODE = os.environ.get("KEYBOARD_MODE", "INLINE").upper() # 'INLINE' or 'REPLY'
REVIEW_GROUP_ID = int(os.environ.get("REVIEW_GROUP_ID", 0))


# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler('logs/bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'),
        logging.StreamHandler()
    ]
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


# ─── Public & Admin Commands ─────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID or db.is_admin(user_id):
        await update.message.reply_text("سلام ادمین! ربات با موفقیت در حال اجراست. 🚀")
    else:
        # Public user — show submit button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 ارسال گیف", callback_data="usub_start")]
        ])
        await update.message.reply_text(
            "سلام! 👋\n\n"
            "به ربات <b>Trend GIF</b> خوش آمدید.\n"
            "شما می‌توانید گیف‌های خود را برای انتشار در کانال ارسال کنید.\n\n"
            "برای شروع، روی دکمه زیر کلیک کنید:",
            reply_markup=keyboard,
            parse_mode='HTML',
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message.from_user else None
    
    is_owner = (user_id == OWNER_ID)
    is_admin = db.is_admin(user_id)
    
    help_text = "🤖 **راهنمای ربات واترمارک Trend GIF**\n\n"
    
    if is_owner:
        help_text += "👑 **دستورات مدیریت کل (Owner):**\n"
        help_text += "🔹 `/start` - بررسی وضعیت ربات\n"
        help_text += "🔹 `/add_admin <user_id>` - افزودن ادمین جدید\n"
        help_text += "🔹 `/remove_admin <user_id>` - حذف ادمین\n"
        help_text += "🔹 `/add_tag <hashtag>` - افزودن هشتگ جدید به لیست\n"
        help_text += "🔹 `/remove_tag <hashtag>` - حذف هشتگ از لیست\n\n"
        
    if is_owner or is_admin:
        help_text += "👥 **راهنمای استفاده (Admins):**\n"
        help_text += "🔹 `/list_tags` - مشاهده لیست هشتگ‌های فعلی\n"
        help_text += "🔹 `/list_admins` - مشاهده لیست ادمین‌ها\n"
        help_text += "🔹 `/report` - دریافت گزارش فعالیت\n"
        help_text += "🔹 `/pending` - تعداد گیف‌های در انتظار بررسی\n"
        help_text += "\n🎥 **نحوه ارسال پست:**\n"
        help_text += "۱. یک فایل **ویدیو** یا **گیف (Animation)** برای ربات ارسال کنید.\n"
        if KEYBOARD_MODE == "INLINE":
            help_text += "۲. ربات در زیر همان پیام دکمه‌های شیشه‌ای شامل هشتگ‌های مجاز به شما نمایش می‌دهد.\n"
            help_text += "۳. کافیست روی یکی از دکمه‌ها کلیک کنید.\n"
            help_text += "۴. ربات به طور خودکار واترمارک کانال را روی ویدیو قرار داده و آن را در کانال منتشر می‌کند.\n\n"
            help_text += "❌ برای لغو عملیات روی دکمه ❌ Cancel کلیک کنید."
        else:
            help_text += "۲. ربات یک کیبورد دکمه‌ای شامل هشتگ‌های مجاز به شما نمایش می‌دهد.\n"
            help_text += "۳. هشتگ مورد نظر را از کیبورد انتخاب کنید یا دستی تایپ کنید.\n"
            help_text += "۴. ربات به طور خودکار واترمارک کانال را روی ویدیو قرار داده و آن را در کانال منتشر می‌کند.\n\n"
            help_text += "❌ برای لغو عملیات روی دکمه Cancel در کیبورد کلیک کنید یا آن را تایپ کنید."

        help_text += "\n\n📬 **بررسی گیف‌های ارسالی کاربران:**\n"
        help_text += "گیف‌های ارسالی کاربران در گروه بررسی ظاهر می‌شوند.\n"
        help_text += "🔹 ابتدا «🔒 رسیدگی می‌کنم» را بزنید تا قفل شود.\n"
        help_text += "🔹 سپس می‌توانید هشتگ‌ها را ویرایش، تأیید یا رد کنید.\n"
    else:
        help_text += "📤 **ارسال گیف برای کانال:**\n"
        help_text += "شما می‌توانید گیف‌های خود را برای انتشار در کانال ارسال کنید.\n"
        help_text += "۱. روی دکمه «📤 ارسال گیف» کلیک کنید.\n"
        help_text += "۲. گیف یا ویدیوی خود را ارسال کنید.\n"
        help_text += "۳. هشتگ‌های مرتبط را انتخاب کنید.\n"
        help_text += "۴. نام خود را تأیید یا تغییر دهید.\n"
        help_text += "۵. گیف شما پس از بررسی ادمین‌ها در کانال منتشر خواهد شد.\n\n"
        help_text += "❌ برای لغو: `/cancel`"
        
    await update.message.reply_text(help_text, parse_mode='Markdown')


# ─── Owner-only Commands ─────────────────────────────────────────

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /add_admin <آیدی_عددی>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        if db.add_admin(new_admin_id):
            await update.message.reply_text(f"✅ ادمین {new_admin_id} اضافه شد.")
        else:
            await update.message.reply_text(f"⚠️ ادمین {new_admin_id} از قبل وجود دارد.")
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عدد باشد.")

async def add_tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /add_tag <هشتگ>\nمثال: /add_tag #خنده")
        return
        
    tag = context.args[0]
    if not tag.startswith('#'):
        tag = '#' + tag
        
    context.user_data['pending_add_tag'] = tag
    
    cats = db.get_categories()
    if not cats:
        await update.message.reply_text("❌ هیچ دسته‌بندی یافت نشد! ابتدا با /add_category یک دسته بسازید.")
        return
        
    keyboard = []
    for cat_id, cat_name in cats:
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"addtag_cat|{cat_id}")])
    
    await update.message.reply_text(f"👇 دسته‌بندی مربوط به هشتگ {tag} را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /add_category <نام دسته‌بندی>\nمثال: /add_category 🎭 احساسات")
        return
        
    name = " ".join(context.args)
    if db.add_category(name):
        await update.message.reply_text(f"✅ دسته‌بندی «{name}» اضافه شد.")
    else:
        await update.message.reply_text(f"⚠️ این دسته‌بندی از قبل وجود دارد.")

async def remove_category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /remove_category <آیدی_دسته>")
        return
        
    try:
        cat_id = int(context.args[0])
        if db.remove_category(cat_id):
            await update.message.reply_text("✅ دسته‌بندی حذف شد.")
        else:
            await update.message.reply_text("❌ دسته‌بندی پیدا نشد.")
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عدد باشد.")

async def list_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = db.get_categories()
    if not cats:
        await update.message.reply_text("هیچ دسته‌بندی ثبت نشده است.")
        return
        
    msg = "📋 <b>لیست دسته‌بندی‌ها:</b>\n\n"
    for cat_id, name in cats:
        msg += f"ID: <code>{cat_id}</code> - {name}\n"
    await update.message.reply_text(msg, parse_mode='HTML')

async def remove_tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /remove_tag <هشتگ>")
        return
        
    tag = context.args[0]
    if not tag.startswith('#'):
        tag = '#' + tag
        
    if db.remove_hashtag(tag):
        await update.message.reply_text(f"✅ هشتگ {tag} حذف شد.")
    else:
        await update.message.reply_text(f"⚠️ هشتگ {tag} پیدا نشد.")

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /remove_admin <آیدی_عددی>")
        return
    
    try:
        del_admin_id = int(context.args[0])
        if db.remove_admin(del_admin_id):
            await update.message.reply_text(f"✅ ادمین {del_admin_id} با موفقیت حذف شد.")
        else:
            await update.message.reply_text(f"⚠️ ادمین {del_admin_id} پیدا نشد.")
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عدد باشد.")

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = db.get_all_admins()
    if not admins:
        await update.message.reply_text("هیچ ادمینی (به جز شما) ثبت نشده است.")
        return
        
    msg = "👥 <b>لیست ادمین‌های ربات:</b>\n\n"
    for admin in admins:
        try:
            chat = await context.bot.get_chat(admin)
            name = chat.first_name or "بدون نام"
            if chat.username:
                name += f" (@{chat.username})"
            name = html.escape(name)
        except Exception:
            name = "ناشناس"
            
        msg += f"▪️ {name} (<code>{admin}</code>)\n"
    await update.message.reply_text(msg, parse_mode='HTML')

async def list_tags_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    grouped = db.get_all_hashtags_grouped()
    if not grouped:
        await update.message.reply_text("هیچ هشتگی ثبت نشده است.")
        return
    
    msg = "📝 <b>لیست هشتگ‌های فعلی:</b>\n\n"
    for cat, tags in grouped.items():
        msg += f"━━━ {html.escape(cat)} ━━━\n"
        msg += " ".join(html.escape(t) for t in tags) + "\n\n"
        
    await update.message.reply_text(msg, parse_mode='HTML')

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = db.get_report_data()
    if not results:
        await update.message.reply_text("در این ماه پستی ارسال نشده است.")
        return
        
    report_lines = ["📊 <b>گزارش فعالیت در این ماه:</b>\n"]
    for admin_id, count in results:
        try:
            chat = await context.bot.get_chat(admin_id)
            name = chat.first_name or "بدون نام"
            if chat.username:
                name += f" (@{chat.username})"
            name = html.escape(name)
        except Exception:
            name = "ناشناس"
            
        report_lines.append(f"👤 {name} (<code>{admin_id}</code>): {count} پست")
        
    await update.message.reply_text("\n".join(report_lines), parse_mode='HTML')


# ─── Admin Media Processing ──────────────────────────────────────

async def process_video_task(file_id, hashtag, context, update_text_func, user_id):
    await update_text_func("⏳ در حال دانلود و پردازش ویدیو...")
    
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
                    caption=hashtag
                )
            
            # Log successful post
            db.log_post(user_id)
            await update_text_func("✅ گیف در کانال منتشر شد!")
        else:
            await update_text_func("❌ خطا در واترمارک ویدیو.")
            
    except Exception as e:
        logger.error(f"Error handling media: {e}")
        await update_text_func(f"❌ خطای سیستمی: {e}")
    finally:
        # Clean up files
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

def chunk_list(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def get_inline_keyboard(grouped_tags, selected_tags, prefix="tag"):
    keyboard = []
    for cat_name, tags in grouped_tags.items():
        # Category header (non-clickable)
        keyboard.append([InlineKeyboardButton(f"━━━ {cat_name} ━━━", callback_data="ignore")])
        
        # Decide chunk size based on average tag length
        # if tags are very long, use 2 columns, otherwise 3
        avg_len = sum(len(t) for t in tags) / len(tags) if tags else 0
        chunk_size = 2 if avg_len > 15 else 3
        
        for chunk in chunk_list(tags, chunk_size):
            row = []
            for tag in chunk:
                display_text = f"✅ {tag}" if tag in selected_tags else tag
                row.append(InlineKeyboardButton(display_text, callback_data=f"{prefix}|{tag}"))
            keyboard.append(row)
            
    keyboard.append([
        InlineKeyboardButton("❌ لغو", callback_data="action|Cancel"),
        InlineKeyboardButton("✅ تأیید و ارسال", callback_data="action|Done")
    ])
    return InlineKeyboardMarkup(keyboard)

def get_reply_keyboard(grouped_tags):
    keyboard = []
    for cat_name, tags in grouped_tags.items():
        keyboard.append([KeyboardButton(f"━━━ {cat_name} ━━━")])
        
        avg_len = sum(len(t) for t in tags) / len(tags) if tags else 0
        chunk_size = 2 if avg_len > 15 else 3
        
        for chunk in chunk_list(tags, chunk_size):
            keyboard.append([KeyboardButton(tag) for tag in chunk])
            
    keyboard.append([KeyboardButton("❌ لغو"), KeyboardButton("✅ تأیید نهایی")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

# Media Handling (Admin-only — direct publish to channel)
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Defensive permission check (safety net beyond the filter)
    user_id = update.message.from_user.id if update.message.from_user else None
    if user_id != OWNER_ID and not db.is_admin(user_id):
        logger.warning(f"handle_media called by non-admin user {user_id} — rejecting. This should not happen.")
        return

    logger.info(f"Admin media handler triggered by user {user_id}")

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
        await update.message.reply_text("❌ لطفاً فقط ویدیو یا گیف ارسال کنید.")
        return

    # Save to user_data (specific to the user handling this interaction)
    context.user_data['pending_media'] = {
        'file_id': file_id,
        'tags': set()
    }

    grouped_tags = db.get_all_hashtags_grouped()
    
    if KEYBOARD_MODE == "INLINE":
        markup = get_inline_keyboard(grouped_tags, set())
        await update.message.reply_text("👇 هشتگ‌های مرتبط با این ویدیو را انتخاب کنید:", reply_markup=markup)
    else:
        markup = get_reply_keyboard(grouped_tags)
        await update.message.reply_text("👇 هشتگ‌های مرتبط را انتخاب کرده و سپس «تأیید نهایی» را بزنید:", reply_markup=markup)

async def handle_inline_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Permission check
    user_id = query.from_user.id
    if user_id != OWNER_ID and not db.is_admin(user_id):
        await query.answer("شما دسترسی ندارید.", show_alert=True)
        return
        
    data = query.data
    if data == "ignore":
        await query.answer()
        return
        
    if data.startswith("addtag_cat|"):
        cat_id = int(data.split("|")[1])
        tag = context.user_data.get('pending_add_tag')
        if not tag:
            await query.answer("⚠️ نشست منقضی شده.", show_alert=True)
            return
            
        if db.add_hashtag(tag, cat_id):
            await query.edit_message_text(f"✅ هشتگ {tag} با موفقیت در دسته‌بندی ذخیره شد.")
        else:
            await query.edit_message_text(f"⚠️ هشتگ {tag} از قبل وجود دارد.")
        del context.user_data['pending_add_tag']
        return
        
    if not (data.startswith("tag|") or data.startswith("action|")):
        return

    pending_media = context.user_data.get('pending_media')
    if not pending_media:
        await query.answer("⚠️ نشست منقضی شده یا فایل پیدا نشد.", show_alert=True)
        try:
            await query.edit_message_text("⚠️ نشست منقضی شده یا فایل پیدا نشد.")
        except Exception:
            pass
        return

    file_id = pending_media['file_id']
    selected_tags = pending_media['tags']

    if data.startswith("action|"):
        action = data.split("|", 1)[1]
        if action == "Cancel" or action == "لغو":
            await query.answer()
            try:
                await query.edit_message_text("🚫 عملیات لغو شد.")
            except Exception:
                pass
            del context.user_data['pending_media']
            return
        elif action == "Done":
            if not selected_tags:
                await query.answer("لطفاً حداقل یک هشتگ انتخاب کنید!", show_alert=True)
                return
            
            await query.answer()
            del context.user_data['pending_media']
            final_hashtags = " ".join(selected_tags)
            
            async def update_text(msg):
                try:
                    await query.edit_message_text(msg)
                except Exception:
                    pass
            await process_video_task(file_id, final_hashtags, context, update_text, user_id)
            return

    if data.startswith("tag|"):
        tag = data.split("|", 1)[1]
        
        if tag == "Cancel" or tag == "لغو" or tag == "❌ لغو":
            await query.answer()
            try:
                await query.edit_message_text("🚫 عملیات لغو شد.")
            except Exception:
                pass
            del context.user_data['pending_media']
            return
            
        if not db.valid_hashtag(tag):
            await query.answer("❌ هشتگ نامعتبر است.", show_alert=True)
            return
            
        if tag in selected_tags:
            selected_tags.remove(tag)
        else:
            selected_tags.add(tag)
            
        await query.answer()
        grouped_tags = db.get_all_hashtags_grouped()
        markup = get_inline_keyboard(grouped_tags, selected_tags)
        try:
            await query.edit_message_reply_markup(reply_markup=markup)
        except Exception:
            pass

async def handle_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if KEYBOARD_MODE == "INLINE":
        return
        
    pending_media = context.user_data.get('pending_media')
    if not pending_media:
        return
        
    text = update.message.text
    
    if text == "Cancel" or text == "لغو" or text == "❌ لغو":
        await update.message.reply_text("🚫 عملیات لغو شد.", reply_markup=ReplyKeyboardRemove())
        del context.user_data['pending_media']
        return
        
    if text == "✅ تأیید نهایی":
        selected_tags = pending_media['tags']
        if not selected_tags:
            await update.message.reply_text("لطفاً حداقل یک هشتگ انتخاب کنید!")
            return
            
        file_id = pending_media['file_id']
        del context.user_data['pending_media']
        final_hashtags = " ".join(selected_tags)
        
        status_msg = await update.message.reply_text("⏳ در حال دانلود و پردازش ویدیو...", reply_markup=ReplyKeyboardRemove())
        
        async def update_text(msg):
            if msg == "⏳ در حال دانلود و پردازش ویدیو...":
                return
            try:
                await status_msg.edit_text(msg)
            except Exception:
                await update.message.reply_text(msg)
                
        await process_video_task(file_id, final_hashtags, context, update_text, update.message.from_user.id)
        return
        
    if db.valid_hashtag(text):
        if text in pending_media['tags']:
            pending_media['tags'].remove(text)
            action_text = "حذف شد"
        else:
            pending_media['tags'].add(text)
            action_text = "اضافه شد"
            
        current_tags = " ".join(pending_media['tags']) if pending_media['tags'] else "(هیچ)"
        await update.message.reply_text(f"✔️ هشتگ {text} {action_text}.\n\nهشتگ‌های فعلی: {current_tags}\n\nهشتگ دیگری انتخاب کنید یا «✅ تأیید نهایی» را بزنید.")
    else:
        await update.message.reply_text("❌ هشتگ نامعتبر است.")


# ─── Routing ──────────────────────────────────────────────────────

async def router_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route media messages to admin or community flows explicitly, bypassing PTB filter caching issues."""
    if not update.message or update.message.chat.type != 'private':
        return
        
    user_id = update.message.from_user.id if update.message.from_user else None
    if user_id == OWNER_ID or db.is_admin(user_id):
        await handle_media(update, context)
    else:
        await community.handle_user_gif(update, context)

async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route text messages to admin or community flows explicitly."""
    if not update.message or update.message.chat.type != 'private':
        return
        
    user_id = update.message.from_user.id if update.message.from_user else None
    if user_id == OWNER_ID or db.is_admin(user_id):
        await handle_text_reply(update, context)
    else:
        await community.handle_user_text(update, context)


# ─── Main ─────────────────────────────────────────────────────────

def main():
    # Initialize Database
    db.init_db()
    
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Exiting.")
        return
        
    IP_ADDRESS = os.environ.get("IP_ADDRESS")
    if not IP_ADDRESS:
        logger.error("IP_ADDRESS environment variable not set. Exiting.")
        return
        
    PORT = int(os.environ.get("PORT", 8443))
    
    if not REVIEW_GROUP_ID:
        logger.warning("REVIEW_GROUP_ID not set. Community submissions will not work.")
    
    # job_queue(None) fixes TypeError: cannot create weak reference to 'Application' object in Python 3.13+ with PTB v20.x
    app = ApplicationBuilder().token(TOKEN).job_queue(None).build()
    
    # ── Owner Commands ──
    app.add_handler(CommandHandler("add_admin", add_admin_command, filters=owner_filter))
    app.add_handler(CommandHandler("remove_admin", remove_admin_command, filters=owner_filter))
    app.add_handler(CommandHandler("add_tag", add_tag_command, filters=owner_filter))
    app.add_handler(CommandHandler("remove_tag", remove_tag_command, filters=owner_filter))
    app.add_handler(CommandHandler("add_category", add_category_command, filters=owner_filter))
    app.add_handler(CommandHandler("remove_category", remove_category_command, filters=owner_filter))
    
    # ── Admin Commands ──
    app.add_handler(CommandHandler("list_tags", list_tags_command, filters=admin_filter))
    app.add_handler(CommandHandler("list_categories", list_categories_command, filters=admin_filter))
    app.add_handler(CommandHandler("list_admins", list_admins_command, filters=admin_filter))
    app.add_handler(CommandHandler("report", report_command, filters=admin_filter))
    app.add_handler(CommandHandler("pending", review.pending_command, filters=admin_filter))
    
    # ── Public Commands (available to everyone) ──
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", community.handle_cancel_command))
    
    # ── Media Router Handlers ──
    app.add_handler(MessageHandler(filters.ANIMATION | filters.VIDEO, router_media))
    
    # Admin inline button callbacks (tag|*, action|*, addtag_cat|*)
    app.add_handler(CallbackQueryHandler(handle_inline_button, pattern=r"^(tag|action|addtag_cat)\|"))
    
    # ── Text Router Handlers ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router_text))
    
    # ── Community Submission Handlers ──
    # Callback queries from users (usub_*)
    app.add_handler(CallbackQueryHandler(community.handle_submission_callback, pattern=r"^usub_"))
    
    # ── Review Handlers (admin actions in review group) ──
    app.add_handler(CallbackQueryHandler(review.handle_review_callback, pattern=r"^rev_"))
    
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
