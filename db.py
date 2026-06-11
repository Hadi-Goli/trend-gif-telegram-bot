import sqlite3
import json
import datetime
import csv
import zipfile
import os

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
    
    # logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            hashtags TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # submissions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            user_display_name TEXT,
            file_id TEXT,
            hashtags TEXT,
            status TEXT DEFAULT 'pending',
            claimed_by INTEGER,
            reviewed_at DATETIME,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # rate_limits
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # hashtags
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hashtags (
            tag_name TEXT PRIMARY KEY,
            category_id INTEGER REFERENCES categories(id)
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
            
    # Migration: Add hashtags to logs
    cursor.execute("PRAGMA table_info(logs)")
    logs_columns = [row[1] for row in cursor.fetchall()]
    if 'hashtags' not in logs_columns:
        cursor.execute('ALTER TABLE logs ADD COLUMN hashtags TEXT')

    # Migration: Add username, reviewed_at, and submitted_at to submissions
    cursor.execute("PRAGMA table_info(submissions)")
    sub_columns = [row[1] for row in cursor.fetchall()]
    if 'username' not in sub_columns:
        cursor.execute('ALTER TABLE submissions ADD COLUMN username TEXT')
    if 'reviewed_at' not in sub_columns:
        cursor.execute('ALTER TABLE submissions ADD COLUMN reviewed_at DATETIME')
    if 'submitted_at' not in sub_columns:
        cursor.execute('ALTER TABLE submissions ADD COLUMN submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP')
        
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

def log_post(admin_id: int, hashtags: str = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (admin_id, hashtags) VALUES (?, ?)', (admin_id, hashtags))
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

def create_submission(user_id: int, display_name: str, file_id: str, hashtags: list, username: str = None) -> int:
    """Create a new community submission. Returns the submission ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO submissions (user_id, username, user_display_name, file_id, hashtags) VALUES (?, ?, ?, ?, ?)',
        (user_id, username, display_name, file_id, json.dumps(hashtags, ensure_ascii=False))
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

# ─── Advanced Reporting & Analytics ────────────────────────────────

def get_user_stats() -> list:
    """Returns aggregated stats grouped by user_id and username."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            user_id, 
            MAX(username) as username, 
            MAX(user_display_name) as display_name,
            COUNT(*) as total_submissions,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_count,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
        FROM submissions 
        GROUP BY user_id
        ORDER BY approved_count DESC, total_submissions DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_hashtag_trends(days: int = 30) -> list:
    """Returns the most used tags from approved submissions and admin logs."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Get approved submissions tags
    cursor.execute('SELECT hashtags FROM submissions WHERE status = ? AND submitted_at >= ?', ('approved', since))
    sub_tags_raw = cursor.fetchall()
    
    # Get admin logs tags
    cursor.execute('SELECT hashtags FROM logs WHERE timestamp >= ?', (since,))
    log_tags_raw = cursor.fetchall()
    conn.close()
    
    tag_counts = {}
    
    for row in sub_tags_raw:
        if row[0]:
            try:
                tags = json.loads(row[0])
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            except:
                pass
                
    for row in log_tags_raw:
        if row[0]: # Admins store space-separated string or just a string of tags
            tags = [t for t in row[0].split() if t.startswith('#')]
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags

def get_admin_review_stats() -> list:
    """Returns admin performance for reviewing community submissions."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            claimed_by,
            COUNT(*) as total_reviewed,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_count,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count
        FROM submissions
        WHERE status IN ('approved', 'rejected') AND claimed_by IS NOT NULL
        GROUP BY claimed_by
        ORDER BY total_reviewed DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_traffic_stats() -> list:
    """Returns aggregated traffic stats (submissions and admin posts) per day."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Submissions by day
    cursor.execute('''
        SELECT date(submitted_at) as day, COUNT(*) 
        FROM submissions 
        GROUP BY day ORDER BY day DESC LIMIT 30
    ''')
    sub_traffic = cursor.fetchall()
    
    # Admin logs by day
    cursor.execute('''
        SELECT date(timestamp) as day, COUNT(*) 
        FROM logs 
        GROUP BY day ORDER BY day DESC LIMIT 30
    ''')
    admin_traffic = cursor.fetchall()
    conn.close()
    
    traffic_dict = {}
    for day, count in sub_traffic:
        traffic_dict[day] = {"submissions": count, "admin_posts": 0}
    for day, count in admin_traffic:
        if day not in traffic_dict:
            traffic_dict[day] = {"submissions": 0, "admin_posts": 0}
        traffic_dict[day]["admin_posts"] = count
        
    sorted_traffic = sorted(traffic_dict.items(), reverse=True)
    return sorted_traffic

def export_csv_reports(zip_filename: str):
    """Exports all advanced stats to a ZIP file containing multiple CSVs."""
    import csv, zipfile, os
    
    # 1. Users
    users_data = get_user_stats()
    with open('users_stats.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["User ID", "Username", "Display Name", "Total Submissions", "Approved", "Rejected", "Pending"])
        for row in users_data:
            writer.writerow(row)
            
    # 2. Hashtags
    hashtags_data = get_hashtag_trends(days=365)
    with open('hashtag_trends.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["Hashtag", "Usage Count"])
        for row in hashtags_data:
            writer.writerow(row)
            
    # 3. Admin Reviews
    admin_reviews = get_admin_review_stats()
    with open('admin_performance.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["Admin ID", "Total Reviewed", "Approved", "Rejected"])
        for row in admin_reviews:
            writer.writerow(row)
            
    # 4. Traffic
    traffic_data = get_traffic_stats()
    with open('traffic_stats.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Community Submissions", "Admin Posts"])
        for day, stats in traffic_data:
            writer.writerow([day, stats["submissions"], stats["admin_posts"]])
            
    # 5. Raw Logs (Admins)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, admin_id, hashtags, timestamp FROM logs ORDER BY timestamp DESC')
    raw_logs = cursor.fetchall()
    conn.close()
    
    with open('raw_logs.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["Log ID", "Admin ID", "Hashtags", "Timestamp"])
        for row in raw_logs:
            writer.writerow(row)
            
    # Zip them up
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write('users_stats.csv')
        zipf.write('hashtag_trends.csv')
        zipf.write('admin_performance.csv')
        zipf.write('traffic_stats.csv')
        zipf.write('raw_logs.csv')
        
    # Cleanup CSVs
    for f in ['users_stats.csv', 'hashtag_trends.csv', 'admin_performance.csv', 'traffic_stats.csv', 'raw_logs.csv']:
        if os.path.exists(f):
            os.remove(f)
