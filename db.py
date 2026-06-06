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
    
    # 6. categories: grouping for hashtags
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            display_order INTEGER DEFAULT 0
        )
    ''')
    
    # 2. hashtags: columns (tag_name TEXT PRIMARY KEY, category_id INTEGER)
    # Check if category_id exists (for migration)
    cursor.execute("PRAGMA table_info(hashtags)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'category_id' not in columns:
        # Recreate the table with the new column since SQLite ALTER TABLE ADD COLUMN
        # with foreign keys can be tricky, but ADD COLUMN works if not enforcing right now.
        cursor.execute('ALTER TABLE hashtags ADD COLUMN category_id INTEGER REFERENCES categories(id)')
        
        # Populate initial categories requested by the user
        initial_categories = {
            "🎭 واکنشها و احساسات": ["#خنده@trend_gif", "#تعجب@trend_gif", "#فشار@trend_gif", "#واکنش_صادقانه@trend_gif", "#پوکر_فیس@trend_gif", "#آره@trend_gif", "#نه@trend_gif", "#pain@trend_gif"],
            "🗣 تکیهکلام و میم ها": ["#ببین_اخوی@trend_gif", "#فکرشو_نمیکردی@trend_gif", "#بینظیره@trend_gif", "#فعک_نکنم@trend_gif", "#سس_ماست@trend_gif", "#اونایی_که_میدونن@trend_gif", "#کلیچه@trend_gif", "#منطقی@trend_gif"],
            "🐶 حیوانات": ["#سگ@trend_gif", "#گربه@trend_gif", "#میمون@trend_gif", "#shiba_inu@trend_gif", "#marmot@trend_gif"],
            "👤 اشخاص و چهرهها": ["#علی_منصور@trend_gif", "#بهنام_تشکر@trend_gif", "#کوکسل_بابا@trend_gif", "#ابوطالب@trend_gif", "#کیومرث@trend_gif"],
            "🍿 انیمیشن و کارتون": ["#باب_اسفنجی@trend_gif", "#پاتریک@trend_gif", "#باب@trend_gif", "#انیمیشن@trend_gif"],
            "📺 موضوعات (ورزش، هنر، جامعه)": ["#فوتبال@trend_gif", "#رپ@trend_gif", "#سریال@trend_gif", "#هالیوود@trend_gif", "#سیاسی@trend_gif", "#بیزنس@trend_gif", "#ایرانی@trend_gif", "#کرج@trend_gif"],
            "❤️ Mood": ["#عاشقانه@trend_gif", "#بغل@trend_gif", "#مرام_و_معرفت@trend_gif", "#گل@trend_gif", "#نینی@trend_gif"],
            "💁♂️ وضعیت": ["#رقص@trend_gif", "#دلقک@trend_gif", "#وضعیت@trend_gif", "#پیگیری@trend_gif", "#خوشتیپ@trend_gif", "#برق@trend_gif", "#smoke@trend_gif"],
            "📌 سایر": ["#مفهومی@trend_gif", "#فینگلیش@trend_gif", "#متفرقه@trend_gif"]
        }
        
        order = 10
        for cat_name, tags in initial_categories.items():
            cursor.execute('INSERT OR IGNORE INTO categories (name, display_order) VALUES (?, ?)', (cat_name, order))
            cursor.execute('SELECT id FROM categories WHERE name = ?', (cat_name,))
            cat_id = cursor.fetchone()[0]
            
            for tag in tags:
                cursor.execute('INSERT OR IGNORE INTO hashtags (tag_name, category_id) VALUES (?, ?)', (tag, cat_id))
                cursor.execute('UPDATE hashtags SET category_id = ? WHERE tag_name = ?', (cat_id, tag))
            order += 10
            
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

# ─── Categories & Hashtags ───────────────────────────────────────

def get_categories() -> list[tuple[int, str]]:
    """Returns a list of (id, name) for all categories."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories ORDER BY display_order ASC, id ASC')
    cats = cursor.fetchall()
    conn.close()
    return cats

def add_category(name: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def remove_category(cat_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if we have a "📌 سایر" category to move tags to
    cursor.execute('SELECT id FROM categories WHERE name = ?', ("📌 سایر",))
    default_cat = cursor.fetchone()
    if default_cat and default_cat[0] != cat_id:
        cursor.execute('UPDATE hashtags SET category_id = ? WHERE category_id = ?', (default_cat[0], cat_id))
    else:
        cursor.execute('UPDATE hashtags SET category_id = NULL WHERE category_id = ?', (cat_id,))
        
    cursor.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_all_hashtags() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT tag_name FROM hashtags')
    tags = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tags

def get_all_hashtags_grouped() -> dict:
    """Returns a dict mapping category name to a list of its hashtags."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = '''
        SELECT c.name, h.tag_name 
        FROM hashtags h
        LEFT JOIN categories c ON h.category_id = c.id
        ORDER BY c.display_order ASC, c.id ASC, h.tag_name ASC
    '''
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    grouped = {}
    for cat_name, tag in rows:
        cat = cat_name if cat_name else "دسته‌بندی نشده"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(tag)
        
    return grouped

def add_hashtag(tag_name: str, category_id: int = None) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO hashtags (tag_name, category_id) VALUES (?, ?)', (tag_name, category_id))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def update_hashtag_category(tag_name: str, category_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE hashtags SET category_id = ? WHERE tag_name = ?', (category_id, tag_name))
    success = cursor.rowcount > 0
    conn.commit()
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
