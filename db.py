import sqlite3
import json
import datetime

DB_NAME = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. admins: columns (user_id INTEGER PRIMARY KEY)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # 2. hashtags: columns (tag_name TEXT PRIMARY KEY)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hashtags (
            tag_name TEXT PRIMARY KEY
        )
    ''')
    
    # 3. logs: columns (id INTEGER PRIMARY KEY, admin_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 4. submissions: community GIF submissions awaiting review
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_display_name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            hashtags TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            claimed_by INTEGER,
            review_message_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME
        )
    ''')
    
    # 5. rate_limits: tracks submission timestamps per user for anti-spam
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ─── Admin helpers ───────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_admin(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO admins (user_id) VALUES (?)', (user_id,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def get_all_admins() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM admins')
    admins = [row[0] for row in cursor.fetchall()]
    conn.close()
    return admins

def remove_admin(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# ─── Hashtag helpers ─────────────────────────────────────────────

def get_all_hashtags() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT tag_name FROM hashtags')
    tags = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tags

def add_hashtag(tag_name: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO hashtags (tag_name) VALUES (?)', (tag_name,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def remove_hashtag(tag_name: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM hashtags WHERE tag_name = ?', (tag_name,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def valid_hashtag(tag_name: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM hashtags WHERE tag_name = ?', (tag_name,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# ─── Logging helpers ─────────────────────────────────────────────

def log_post(admin_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (admin_id) VALUES (?)', (admin_id,))
    conn.commit()
    conn.close()

def get_report_data() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # query logs for this month
    now = datetime.datetime.now()
    start_of_month = f"{now.year}-{now.month:02d}-01 00:00:00"
    
    cursor.execute('''
        SELECT admin_id, COUNT(*) 
        FROM logs 
        WHERE timestamp >= ? 
        GROUP BY admin_id
    ''', (start_of_month,))
    
    results = cursor.fetchall()
    conn.close()
    return results

# ─── Submission helpers ──────────────────────────────────────────

def create_submission(user_id: int, display_name: str, file_id: str, hashtags: list) -> int:
    """Create a new community submission. Returns the submission ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO submissions (user_id, user_display_name, file_id, hashtags) VALUES (?, ?, ?, ?)',
        (user_id, display_name, file_id, json.dumps(hashtags, ensure_ascii=False))
    )
    conn.commit()
    sub_id = cursor.lastrowid
    conn.close()
    return sub_id

def get_submission(submission_id: int) -> dict | None:
    """Get a submission by ID. Returns dict or None."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM submissions WHERE id = ?', (submission_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    result['hashtags'] = json.loads(result['hashtags'])
    return result

def set_submission_review_message(submission_id: int, message_id: int):
    """Store the review group message ID for later edits."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE submissions SET review_message_id = ? WHERE id = ?',
        (message_id, submission_id)
    )
    conn.commit()
    conn.close()

def claim_submission(submission_id: int, admin_id: int) -> bool:
    """Claim a pending submission. Returns False if already claimed."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE submissions SET status = ?, claimed_by = ? WHERE id = ? AND status = ?',
        ('claimed', admin_id, submission_id, 'pending')
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def update_submission_hashtags(submission_id: int, hashtags: list):
    """Update the hashtags of a submission."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE submissions SET hashtags = ? WHERE id = ?',
        (json.dumps(hashtags, ensure_ascii=False), submission_id)
    )
    conn.commit()
    conn.close()

def approve_submission(submission_id: int):
    """Mark a submission as approved."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE submissions SET status = ?, reviewed_at = ? WHERE id = ?',
        ('approved', datetime.datetime.now().isoformat(), submission_id)
    )
    conn.commit()
    conn.close()

def reject_submission(submission_id: int):
    """Mark a submission as rejected."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE submissions SET status = ?, reviewed_at = ? WHERE id = ?',
        ('rejected', datetime.datetime.now().isoformat(), submission_id)
    )
    conn.commit()
    conn.close()

def count_pending_submissions() -> int:
    """Count submissions with 'pending' or 'claimed' status."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM submissions WHERE status IN ('pending', 'claimed')")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ─── Rate-limit helpers ──────────────────────────────────────────

def log_rate_limit(user_id: int):
    """Record a submission timestamp for rate-limiting."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO rate_limits (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def check_rate_limit(user_id: int) -> tuple[bool, str]:
    """
    Tiered rate-limit check.
    Returns (allowed: bool, message: str).
    
    Tiers (per calendar day):
      - 0-9 submissions today  → unlimited (first 10 are free)
      - 10-19 today            → max 3 per 10 minutes
      - 20-29 today            → max 1 per 30 minutes
      - 30+ today              → locked until tomorrow
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    now = datetime.datetime.now()
    start_of_day = now.strftime("%Y-%m-%d 00:00:00")
    
    # Count today's submissions
    cursor.execute(
        'SELECT COUNT(*) FROM rate_limits WHERE user_id = ? AND submitted_at >= ?',
        (user_id, start_of_day)
    )
    today_count = cursor.fetchone()[0]
    
    if today_count < 10:
        conn.close()
        return (True, "")
    
    if today_count >= 30:
        conn.close()
        return (False, "⛔️ شما به حد مجاز روزانه (۳۰ گیف) رسیده‌اید.\nلطفاً فردا دوباره تلاش کنید.")
    
    if today_count >= 20:
        # Max 1 per 30 minutes
        since = (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            'SELECT COUNT(*) FROM rate_limits WHERE user_id = ? AND submitted_at >= ?',
            (user_id, since)
        )
        recent = cursor.fetchone()[0]
        conn.close()
        if recent >= 1:
            return (False, "⏳ شما اخیراً گیف ارسال کرده‌اید.\nلطفاً ۳۰ دقیقه صبر کنید.")
        return (True, "")
    
    # today_count >= 10
    # Max 3 per 10 minutes
    since = (now - datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        'SELECT COUNT(*) FROM rate_limits WHERE user_id = ? AND submitted_at >= ?',
        (user_id, since)
    )
    recent = cursor.fetchone()[0]
    conn.close()
    if recent >= 3:
        return (False, "⏳ شما اخیراً چند گیف ارسال کرده‌اید.\nلطفاً ۱۰ دقیقه صبر کنید.")
    return (True, "")
