import sqlite3
import datetime
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, 'bot.db')

def reset_stats():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # گرفتن آمار خلاصه
    cursor.execute('''
        SELECT admin_id, COUNT(*) 
        FROM logs 
        GROUP BY admin_id
    ''')
    stats = cursor.fetchall()
    
    # گرفتن تمامی لاگ‌ها
    cursor.execute('SELECT id, admin_id, timestamp FROM logs ORDER BY timestamp ASC')
    all_logs = cursor.fetchall()
    
    if not all_logs:
        print("هیچ آماری برای ریست کردن وجود ندارد (جدول logs خالی است).")
        conn.close()
        return

    # ذخیره در فایل
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = os.path.join(SCRIPT_DIR, f"stats_backup_{timestamp_str}.txt")
    
    with open(backup_filename, 'w', encoding='utf-8') as f:
        f.write(f"--- آمار ربات Trend Gif ---\n")
        f.write(f"تاریخ و زمان بک‌آپ: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("خلاصه آمار ادمین‌ها:\n")
        for admin_id, count in stats:
            f.write(f"ادمین {admin_id}: {count} گیف ارسالی\n")
            
        f.write("\nلیست کامل لاگ‌ها:\n")
        for log_id, admin_id, ts in all_logs:
            f.write(f"ID: {log_id} | ادمین: {admin_id} | زمان: {ts}\n")
            
    print(f"آمار با موفقیت در فایل زیر بک‌آپ گرفته شد:\n{backup_filename}")
    
    # پاک کردن لاگ‌ها
    cursor.execute('DELETE FROM logs')
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()
    
    print("تمامی آمار گیف‌های ارسالی ادمین‌ها صفر شد.")

if __name__ == "__main__":
    reset_stats()
