import sqlite3
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
    
    conn.commit()
    conn.close()

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
