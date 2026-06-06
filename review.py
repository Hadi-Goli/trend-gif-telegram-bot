"""
Admin Review Flow — runs entirely inside the review Telegram group.
All interactions use inline keyboards on the same message (no private-chat redirect).

Callback patterns handled:
  rev_claim|<id>       — Admin claims a pending submission
  rev_approve|<id>     — Approve and publish
  rev_reject|<id>      — Reject the submission
  rev_edit|<id>        — Enter hashtag-editing mode
  rev_tag|<id>|<tag>   — Toggle a hashtag during editing
  rev_tags_done|<id>   — Save edited hashtags, return to review buttons
  rev_tags_back|<id>   — Discard edits, return to review buttons
"""

import logging
import os

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import db
import video
from community import build_review_caption

logger = logging.getLogger(__name__)

CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@bestgifsintheworld")
REVIEW_GROUP_ID = int(os.environ.get("REVIEW_GROUP_ID", 0))

# Temporary in-memory storage for tag-editing sessions.
# Key: submission_id  →  Value: set of tags being edited
_tag_edit_sessions: dict[int, set] = {}

# ─── Keyboard builders ───────────────────────────────────────────

def _review_buttons(submission_id: int) -> InlineKeyboardMarkup:
    """Buttons shown after an admin has claimed a submission."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید و انتشار", callback_data=f"rev_approve|{submission_id}")],
        [
            InlineKeyboardButton("✏️ ویرایش هشتگ‌ها", callback_data=f"rev_edit|{submission_id}"),
            InlineKeyboardButton("❌ رد کردن", callback_data=f"rev_reject|{submission_id}"),
        ],
    ])


def chunk_list(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def _tag_edit_keyboard(submission_id: int, grouped_tags: dict, selected: set) -> InlineKeyboardMarkup:
    """Hashtag toggle keyboard for in-group editing."""
    keyboard = []
    
    for cat_name, tags in grouped_tags.items():
        # Category header
        keyboard.append([InlineKeyboardButton(f"━━━ {cat_name} ━━━", callback_data="rev_ignore")])
        
        # Always use 3 columns
        chunk_size = 3
        
        for chunk in chunk_list(tags, chunk_size):
            row = []
            for tag in chunk:
                label = f"✅ {tag}" if tag in selected else tag
                row.append(InlineKeyboardButton(label, callback_data=f"rev_tag|{submission_id}|{tag}"))
            keyboard.append(row)
            
    keyboard.append([
        InlineKeyboardButton("❌ لغو", callback_data=f"rev_tags_back|{submission_id}"),
        InlineKeyboardButton("✅ تایید و نهایی کردن", callback_data=f"rev_tags_done|{submission_id}"),
    ])
    return InlineKeyboardMarkup(keyboard)


# ─── Helpers ──────────────────────────────────────────────────────

def _admin_name(query) -> str:
    """Return a readable admin display name."""
    name = query.from_user.first_name or "ادمین"
    if query.from_user.username:
        name += f" (@{query.from_user.username})"
    return name


def _is_authorized(query, submission: dict) -> bool:
    """Check that the clicking admin is the one who claimed this submission."""
    if submission['status'] != 'claimed':
        return False
    return submission['claimed_by'] == query.from_user.id


async def _update_caption(query, submission: dict, suffix: str):
    """Edit the review message caption with an optional status suffix."""
    caption = build_review_caption(submission)
    if suffix:
        caption += f"\n\n{suffix}"
    try:
        await query.edit_message_caption(caption=caption, parse_mode='HTML')
    except Exception:
        pass


# ─── Main dispatcher ─────────────────────────────────────────────

async def handle_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all  rev_*  callbacks."""
    query = update.callback_query
    data = query.data

    if data == "rev_ignore":
        await query.answer()
    elif data.startswith("rev_claim|"):
        await _claim(query, context)
    elif data.startswith("rev_approve|"):
        await _approve(query, context)
    elif data.startswith("rev_reject|"):
        await _reject(query, context)
    elif data.startswith("rev_edit|"):
        await _edit_tags_enter(query, context)
    elif data.startswith("rev_tag|"):
        await _edit_tags_toggle(query, context)
    elif data.startswith("rev_tags_done|"):
        await _edit_tags_save(query, context)
    elif data.startswith("rev_tags_back|"):
        await _edit_tags_discard(query, context)


# ─── Claim ────────────────────────────────────────────────────────

async def _claim(query, context):
    sub_id = int(query.data.split("|")[1])
    submission = db.get_submission(sub_id)

    if not submission:
        await query.answer("⚠️ ارسالی پیدا نشد.", show_alert=True)
        return

    if submission['status'] != 'pending':
        await query.answer("⚠️ این ارسالی قبلاً توسط ادمین دیگری رسیدگی شده است.", show_alert=True)
        return

    admin_id = query.from_user.id
    if not db.claim_submission(sub_id, admin_id):
        await query.answer("⚠️ قفل‌کردن ناموفق بود.", show_alert=True)
        return

    await query.answer("🔒 شما این ارسالی را قفل کردید.")

    # Refresh submission data
    submission = db.get_submission(sub_id)
    name = _admin_name(query)

    # Edit caption to show claim status
    caption = build_review_caption(submission) + f"\n\n🔒 <b>در حال رسیدگی توسط:</b> {name}"
    try:
        await query.edit_message_caption(
            caption=caption,
            parse_mode='HTML',
            reply_markup=_review_buttons(sub_id),
        )
    except Exception:
        pass


# ─── Approve ──────────────────────────────────────────────────────

async def _approve(query, context):
    sub_id = int(query.data.split("|")[1])
    submission = db.get_submission(sub_id)

    if not submission:
        await query.answer("⚠️ ارسالی پیدا نشد.", show_alert=True)
        return
    if not _is_authorized(query, submission):
        await query.answer("⚠️ فقط ادمینی که این ارسالی را قفل کرده می‌تواند تأیید کند.", show_alert=True)
        return

    await query.answer("⏳ در حال پردازش و انتشار...")

    # Process: watermark → publish to channel
    file_id = submission['file_id']
    tags_str = " ".join(submission['hashtags'])
    credit = submission['user_display_name']
    caption = f"{tags_str}\n\nارسالی از: {credit}"

    input_path = f"input_sub_{sub_id}.mp4"
    output_path = f"output_sub_{sub_id}.mp4"

    try:
        media_file = await context.bot.get_file(file_id)
        await media_file.download_to_drive(input_path)

        success = await video.watermark_video(input_path, output_path, CHANNEL_USERNAME)

        if success:
            with open(output_path, 'rb') as f:
                channel_msg = await context.bot.send_animation(
                    chat_id=CHANNEL_USERNAME,
                    animation=f,
                    caption=caption,
                )

            db.approve_submission(sub_id)
            db.log_post(query.from_user.id)

            name = _admin_name(query)
            submission = db.get_submission(sub_id)
            final_caption = build_review_caption(submission) + f"\n\n✅ <b>تأیید و منتشر شد توسط:</b> {name}"
            try:
                await query.edit_message_caption(caption=final_caption, parse_mode='HTML', reply_markup=None)
            except Exception:
                pass

            # Notify the user
            try:
                # Build channel post link
                channel_handle = CHANNEL_USERNAME.lstrip('@')
                post_link = f"https://t.me/{channel_handle}/{channel_msg.message_id}"
                await context.bot.send_message(
                    chat_id=submission['user_id'],
                    text=(
                        f"🎉 گیف شما تأیید و در کانال منتشر شد!\n\n"
                        f"🔗 <a href=\"{post_link}\">مشاهده پست</a>"
                    ),
                    parse_mode='HTML',
                )
            except Exception as e:
                logger.warning(f"Could not notify user {submission['user_id']}: {e}")
        else:
            try:
                await query.edit_message_caption(
                    caption=build_review_caption(submission) + "\n\n❌ خطا در واترمارک ویدیو.",
                    parse_mode='HTML',
                    reply_markup=_review_buttons(sub_id),
                )
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Error processing submission #{sub_id}: {e}")
        try:
            await query.edit_message_caption(
                caption=build_review_caption(submission) + f"\n\n❌ خطای سیستمی: {e}",
                parse_mode='HTML',
                reply_markup=_review_buttons(sub_id),
            )
        except Exception:
            pass
    finally:
        import os as _os
        for p in (input_path, output_path):
            if _os.path.exists(p):
                _os.remove(p)


# ─── Reject ───────────────────────────────────────────────────────

async def _reject(query, context):
    sub_id = int(query.data.split("|")[1])
    submission = db.get_submission(sub_id)

    if not submission:
        await query.answer("⚠️ ارسالی پیدا نشد.", show_alert=True)
        return
    if not _is_authorized(query, submission):
        await query.answer("⚠️ فقط ادمینی که این ارسالی را قفل کرده می‌تواند رد کند.", show_alert=True)
        return

    db.reject_submission(sub_id)
    await query.answer("❌ ارسالی رد شد.")

    name = _admin_name(query)
    submission = db.get_submission(sub_id)
    final_caption = build_review_caption(submission) + f"\n\n❌ <b>رد شد توسط:</b> {name}"
    try:
        await query.edit_message_caption(caption=final_caption, parse_mode='HTML', reply_markup=None)
    except Exception:
        pass

    # Notify the submitter
    try:
        await context.bot.send_message(
            chat_id=submission['user_id'],
            text="متأسفانه گیف ارسالی شما تأیید نشد. ❌\nممکن است محتوا مناسب نبوده باشد. می‌توانید گیف دیگری ارسال کنید.",
        )
    except Exception as e:
        logger.warning(f"Could not notify user {submission['user_id']}: {e}")


# ─── Edit Tags (in-group) ────────────────────────────────────────

async def _edit_tags_enter(query, context):
    """Switch the review message keyboard to hashtag-editing mode."""
    sub_id = int(query.data.split("|")[1])
    submission = db.get_submission(sub_id)

    if not submission:
        await query.answer("⚠️ ارسالی پیدا نشد.", show_alert=True)
        return
    if not _is_authorized(query, submission):
        await query.answer("⚠️ فقط ادمین قفل‌کننده می‌تواند ویرایش کند.", show_alert=True)
        return

    # Copy current hashtags into a temp editing session
    _tag_edit_sessions[sub_id] = set(submission['hashtags'])

    grouped_tags = db.get_all_hashtags_grouped()
    await query.answer()
    try:
        await query.edit_message_reply_markup(
            reply_markup=_tag_edit_keyboard(sub_id, grouped_tags, _tag_edit_sessions[sub_id]),
        )
    except Exception:
        pass


async def _edit_tags_toggle(query, context):
    """Toggle a hashtag during editing."""
    parts = query.data.split("|", 2)
    sub_id = int(parts[1])
    tag = parts[2]

    submission = db.get_submission(sub_id)
    if not submission or not _is_authorized(query, submission):
        await query.answer("⚠️ دسترسی ندارید.", show_alert=True)
        return

    selected = _tag_edit_sessions.get(sub_id, set())
    if tag in selected:
        selected.discard(tag)
    else:
        selected.add(tag)
    _tag_edit_sessions[sub_id] = selected

    await query.answer()
    grouped_tags = db.get_all_hashtags_grouped()
    try:
        await query.edit_message_reply_markup(
            reply_markup=_tag_edit_keyboard(sub_id, grouped_tags, selected),
        )
    except Exception:
        pass


async def _edit_tags_save(query, context):
    """Save edited hashtags and return to review buttons."""
    sub_id = int(query.data.split("|")[1])
    submission = db.get_submission(sub_id)

    if not submission or not _is_authorized(query, submission):
        await query.answer("⚠️ دسترسی ندارید.", show_alert=True)
        return

    new_tags = _tag_edit_sessions.pop(sub_id, set())
    if not new_tags:
        await query.answer("لطفاً حداقل یک هشتگ انتخاب کنید!", show_alert=True)
        _tag_edit_sessions[sub_id] = set(submission['hashtags'])
        return

    db.update_submission_hashtags(sub_id, list(new_tags))
    await query.answer("💾 هشتگ‌ها ذخیره شد.")

    # Refresh caption with new hashtags + claim info
    submission = db.get_submission(sub_id)
    name = _admin_name(query)
    caption = build_review_caption(submission) + f"\n\n🔒 <b>در حال رسیدگی توسط:</b> {name}"
    try:
        await query.edit_message_caption(
            caption=caption,
            parse_mode='HTML',
            reply_markup=_review_buttons(sub_id),
        )
    except Exception:
        pass


async def _edit_tags_discard(query, context):
    """Discard tag edits and return to review buttons."""
    sub_id = int(query.data.split("|")[1])
    _tag_edit_sessions.pop(sub_id, None)

    submission = db.get_submission(sub_id)
    if not submission:
        await query.answer("⚠️ ارسالی پیدا نشد.", show_alert=True)
        return

    await query.answer("↩️ تغییرات لغو شد.")
    name = _admin_name(query)
    caption = build_review_caption(submission) + f"\n\n🔒 <b>در حال رسیدگی توسط:</b> {name}"
    try:
        await query.edit_message_caption(
            caption=caption,
            parse_mode='HTML',
            reply_markup=_review_buttons(sub_id),
        )
    except Exception:
        pass


# ─── Admin command: view pending count ────────────────────────────

async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = db.count_pending_submissions()
    await update.message.reply_text(f"📬 تعداد گیف‌های در انتظار بررسی: <b>{count}</b>", parse_mode='HTML')
