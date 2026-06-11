"""
Community GIF Submission Flow
Handles the user-facing submission process:
  /start → 📤 Submit GIF → send GIF → pick hashtags → confirm name → send to review group
"""

import logging
import os
import json

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import db

logger = logging.getLogger(__name__)

REVIEW_GROUP_ID = int(os.environ.get("REVIEW_GROUP_ID", 0))

# ─── Keyboards ───────────────────────────────────────────────────

def chunk_list(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def _hashtag_keyboard(grouped_tags: dict, selected: set) -> InlineKeyboardMarkup:
    """Build an inline hashtag toggle keyboard for the user."""
    keyboard = []
    
    for cat_name, tags in grouped_tags.items():
        # Category header (non-clickable)
        keyboard.append([InlineKeyboardButton(f"━━━ {cat_name} ━━━", callback_data="usub_ignore")])
        
        # Always use 3 columns
        chunk_size = 3
        
        for chunk in chunk_list(tags, chunk_size):
            row = []
            for tag in chunk:
                label = f"✅ {tag}" if tag in selected else tag
                row.append(InlineKeyboardButton(label, callback_data=f"usub_tag|{tag}"))
            keyboard.append(row)
            
    keyboard.append([
        InlineKeyboardButton("❌ لغو", callback_data="usub_cancel"),
        InlineKeyboardButton("✅ تایید و نهایی کردن", callback_data="usub_tags_done"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _name_keyboard(name: str) -> InlineKeyboardMarkup:
    """Confirm-or-change credit name keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ بله، «{name}»", callback_data="usub_name_ok"),
            InlineKeyboardButton("✏️ تغییر نام", callback_data="usub_name_change"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="usub_cancel")],
    ])


def _submit_again_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 ارسال گیف دیگر", callback_data="usub_start")]
    ])


# ─── Review-group message builder ────────────────────────────────

def build_review_caption(submission: dict) -> str:
    """Build the caption text for the review-group message."""
    tags_str = " ".join(submission['hashtags'])
    
    user_id = submission.get('user_id')
    username = submission.get('username')
    display_name = submission.get('user_display_name', 'کاربر')
    
    user_link = f"<a href='tg://user?id={user_id}'>{display_name}</a>"
    if username:
        user_info = f"{user_link} ({username}) [<code>{user_id}</code>]"
    else:
        user_info = f"{user_link} [<code>{user_id}</code>]"

    return (
        f"📤 <b>گیف ارسالی جدید</b>\n\n"
        f"🏷 هشتگ‌ها: {tags_str}\n"
        f"👤 ارسالی از: {user_info}\n"
        f"🆔 شناسه: <code>#{submission['id']}</code>"
    )


def review_initial_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    """Buttons shown to admins when a new submission arrives."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 رسیدگی می‌کنم", callback_data=f"rev_claim|{submission_id}")],
    ])


# ─── Callback dispatcher ─────────────────────────────────────────

async def handle_submission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all  usub_*  callbacks."""
    query = update.callback_query
    data = query.data

    if data == "usub_start":
        await _start_submission(query, context)
    elif data == "usub_ignore":
        await query.answer()
    elif data.startswith("usub_tag|"):
        await _toggle_tag(query, context)
    elif data == "usub_tags_done":
        await _tags_done(query, context)
    elif data == "usub_name_ok":
        await _name_confirmed(query, context)
    elif data == "usub_name_change":
        await _name_change_requested(query, context)
    elif data == "usub_cancel":
        await _cancel(query, context)


# ─── Flow steps ──────────────────────────────────────────────────

async def _start_submission(query, context):
    """User clicked 📤 ارسال گیف."""
    user_id = query.from_user.id

    # Rate-limit check
    allowed, msg = db.check_rate_limit(user_id)
    if not allowed:
        await query.answer(msg, show_alert=True)
        return

    context.user_data['sub_state'] = 'awaiting_gif'
    context.user_data.pop('sub_data', None)
    await query.answer()
    await query.edit_message_text(
        "🎬 لطفاً گیف یا ویدیوی مورد نظر خود را ارسال کنید.\n\n"
        "برای لغو /cancel را بفرستید."
    )


async def handle_user_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Non-admin user sent a GIF/video in private chat."""
    user_id = update.message.from_user.id if update.message.from_user else None
    logger.info(f"Community media handler triggered by user {user_id}")

    state = context.user_data.get('sub_state')

    if state != 'awaiting_gif':
        # Not in submission flow — prompt them
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 ارسال گیف", callback_data="usub_start")]
        ])
        await update.message.reply_text(
            "برای ارسال گیف، ابتدا روی دکمه زیر کلیک کنید:",
            reply_markup=keyboard,
        )
        return

    # Rate-limit re-check (in case they waited)
    user_id = update.message.from_user.id
    allowed, msg = db.check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(msg)
        return

    # Extract file_id
    msg = update.message
    file_id = None
    if msg.animation:
        file_id = msg.animation.file_id
    elif msg.video:
        file_id = msg.video.file_id
    elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith('video/'):
        file_id = msg.document.file_id

    if not file_id:
        await msg.reply_text("❌ لطفاً فقط گیف یا ویدیو ارسال کنید.")
        return

    # Save and move to tag selection
    context.user_data['sub_data'] = {
        'file_id': file_id, 
        'tags': set(),
        'user_message_id': msg.message_id
    }
    context.user_data['sub_state'] = 'selecting_tags'

    grouped_tags = db.get_all_hashtags_grouped()
    if not grouped_tags:
        await msg.reply_text("⚠️ هنوز هشتگی تعریف نشده است. لطفاً بعداً تلاش کنید.")
        context.user_data['sub_state'] = None
        return

    keyboard = _hashtag_keyboard(grouped_tags, set())
    await msg.reply_text("👇 هشتگ‌های مرتبط با این گیف را انتخاب کنید:", reply_markup=keyboard)


async def _toggle_tag(query, context):
    """User toggled a hashtag."""
    if context.user_data.get('sub_state') != 'selecting_tags':
        await query.answer("⚠️ نشست منقضی شده. لطفاً دوباره شروع کنید.", show_alert=True)
        return

    tag = query.data.split("|", 1)[1]
    sub_data = context.user_data.get('sub_data', {})
    selected = sub_data.get('tags', set())

    if tag in selected:
        selected.discard(tag)
    else:
        selected.add(tag)
    sub_data['tags'] = selected

    await query.answer()
    grouped_tags = db.get_all_hashtags_grouped()
    try:
        await query.edit_message_reply_markup(reply_markup=_hashtag_keyboard(grouped_tags, selected))
    except Exception:
        pass


async def _tags_done(query, context):
    """User confirmed hashtag selection — ask about credit name."""
    if context.user_data.get('sub_state') != 'selecting_tags':
        await query.answer("⚠️ نشست منقضی شده.", show_alert=True)
        return

    sub_data = context.user_data.get('sub_data', {})
    if not sub_data.get('tags'):
        await query.answer("لطفاً حداقل یک هشتگ انتخاب کنید!", show_alert=True)
        return

    # Determine profile name
    first_name = query.from_user.first_name or "کاربر"
    sub_data['display_name'] = first_name
    context.user_data['sub_state'] = 'confirming_name'

    await query.answer()
    try:
        await query.edit_message_text(
            f"👤 آیا می‌خواهید نام «<b>{first_name}</b>» زیر گیف نمایش داده شود؟",
            reply_markup=_name_keyboard(first_name),
            parse_mode='HTML',
        )
    except Exception:
        pass


async def _name_confirmed(query, context):
    """User accepted the profile name."""
    if context.user_data.get('sub_state') != 'confirming_name':
        await query.answer("⚠️ نشست منقضی شده.", show_alert=True)
        return
    await query.answer()
    await _finalize_submission(query, context)


async def _name_change_requested(query, context):
    """User wants a custom name."""
    if context.user_data.get('sub_state') != 'confirming_name':
        await query.answer("⚠️ نشست منقضی شده.", show_alert=True)
        return

    context.user_data['sub_state'] = 'awaiting_custom_name'
    await query.answer()
    try:
        await query.edit_message_text("✏️ لطفاً نام دلخواه خود را تایپ کنید:")
    except Exception:
        pass


async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Non-admin user sent a text message in private chat."""
    state = context.user_data.get('sub_state')

    if state == 'awaiting_custom_name':
        name = update.message.text.strip()
        if not name or len(name) > 64:
            await update.message.reply_text("❌ نام باید بین ۱ تا ۶۴ کاراکتر باشد.")
            return
        context.user_data['sub_data']['display_name'] = name
        await _finalize_submission_from_message(update, context)
    # else: ignore (or show help)


async def handle_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel for community users to exit submission flow."""
    if not update.message or not update.message.chat or update.message.chat.type != 'private':
        return

    state = context.user_data.get('sub_state')
    if state:
        context.user_data['sub_state'] = None
        context.user_data.pop('sub_data', None)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 ارسال گیف", callback_data="usub_start")]
        ])
        await update.message.reply_text("🚫 عملیات لغو شد.", reply_markup=keyboard)
    else:
        await update.message.reply_text("عملیات فعالی وجود ندارد.")


async def _cancel(query, context):
    """User pressed cancel inline button."""
    context.user_data['sub_state'] = None
    context.user_data.pop('sub_data', None)
    await query.answer()
    try:
        await query.edit_message_text(
            "🚫 عملیات لغو شد.",
            reply_markup=_submit_again_keyboard(),
        )
    except Exception:
        pass


# ─── Finalize & send to review group ─────────────────────────────

async def _finalize_submission(query, context):
    """Create DB record + send to review group (from callback query)."""
    sub_data = context.user_data.get('sub_data', {})
    user_id = query.from_user.id
    username = query.from_user.username
    if username:
        username = f"@{username}"

    sub_id = db.create_submission(
        user_id=user_id,
        display_name=sub_data['display_name'],
        file_id=sub_data['file_id'],
        hashtags=list(sub_data['tags']),
        username=username,
        user_message_id=sub_data.get('user_message_id')
    )
    db.log_rate_limit(user_id)

    submission = db.get_submission(sub_id)

    # Send to review group
    try:
        review_msg = await context.bot.send_animation(
            chat_id=REVIEW_GROUP_ID,
            animation=sub_data['file_id'],
            caption=build_review_caption(submission),
            parse_mode='HTML',
            reply_markup=review_initial_keyboard(sub_id),
        )
        db.set_submission_review_message(sub_id, review_msg.message_id)
    except Exception as e:
        logger.error(f"Failed to send submission #{sub_id} to review group: {e}")

    # Notify user
    context.user_data['sub_state'] = None
    context.user_data.pop('sub_data', None)
    try:
        await query.edit_message_text(
            "✅ گیف شما با موفقیت ارسال شد و منتظر تأیید ادمین‌ها است.\n"
            "پس از بررسی، نتیجه به شما اطلاع داده خواهد شد. 🙏",
            reply_markup=_submit_again_keyboard(),
        )
    except Exception:
        pass


async def _finalize_submission_from_message(update: Update, context):
    """Create DB record + send to review group (from text message)."""
    sub_data = context.user_data.get('sub_data', {})
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    if username:
        username = f"@{username}"

    sub_id = db.create_submission(
        user_id=user_id,
        display_name=sub_data['display_name'],
        file_id=sub_data['file_id'],
        hashtags=list(sub_data['tags']),
        username=username,
        user_message_id=sub_data.get('user_message_id')
    )
    db.log_rate_limit(user_id)

    submission = db.get_submission(sub_id)

    # Send to review group
    try:
        review_msg = await context.bot.send_animation(
            chat_id=REVIEW_GROUP_ID,
            animation=sub_data['file_id'],
            caption=build_review_caption(submission),
            parse_mode='HTML',
            reply_markup=review_initial_keyboard(sub_id),
        )
        db.set_submission_review_message(sub_id, review_msg.message_id)
    except Exception as e:
        logger.error(f"Failed to send submission #{sub_id} to review group: {e}")

    # Notify user
    context.user_data['sub_state'] = None
    context.user_data.pop('sub_data', None)
    await update.message.reply_text(
        "✅ گیف شما با موفقیت ارسال شد و منتظر تأیید ادمین‌ها است.\n"
        "پس از بررسی، نتیجه به شما اطلاع داده خواهد شد. 🙏",
        reply_markup=_submit_again_keyboard(),
    )
