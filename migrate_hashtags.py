import sqlite3
import os

DB_NAME = "bot.db"

def migrate():
    print(f"Connecting to {DB_NAME}...")
    if not os.path.exists(DB_NAME):
        print("Database file not found!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print("Clearing existing hashtags and categories...")
    # Clear existing tags and categories
    cursor.execute("DELETE FROM hashtags")
    cursor.execute("DELETE FROM categories")
    
    # Reset auto-increment
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='categories'")
    
    conn.commit()

    new_categories = {
        "🎭 واکنشها و احساسات": [
            "#خنده", "#تعجب", "#فشار", "#واکنش_صادقانه", "#پوکر_فیس", "#آره", "#نه", "#pain"
        ],
        "🗣 تکیهکلام و میم ها": [
            "#ببین_اخوی", "#فکرشو_نمیکردی", "#بینظیره", "#فعک_نکنم", "#سس_ماست", 
            "#اونایی_که_میدونن", "#کلیچه", "#منطقی"
        ],
        "🐶 حیوانات": [
            "#سگ", "#گربه", "#میمون", "#shiba_inu", "#marmot"
        ],
        "👤 اشخاص و چهرهها": [
            "#علی_منصور", "#بهنام_تشکر", "#کوکسل_بابا", "#ابوطالب", "#کیومرث"
        ],
        "🍿 انیمیشن و کارتون": [
            "#باب_اسفنجی", "#پاتریک", "#باب", "#انیمیشن"
        ],
        "📺 موضوعات (ورزش، هنر، جامعه)": [
            "#فوتبال", "#رپ", "#سریال", "#هالیوود", "#سیاسی", "#بیزنس", "#ایرانی", "#کرج"
        ],
        "❤️ Mood": [
            "#عاشقانه", "#بغل", "#مرام_و_معرفت", "#گل", "#نینی"
        ],
        "💁♂️ وضعیت": [
            "#رقص", "#دلقک", "#وضعیت", "#پیگیری", "#خوشتیپ", "#برق", "#smoke"
        ],
        "📌 سایر": [
            "#مفهومی", "#فینگلیش", "#متفرقه"
        ]
    }

    print("Inserting new categories and hashtags...")
    order = 10
    for cat_name, tags in new_categories.items():
        cursor.execute('INSERT INTO categories (name, display_order) VALUES (?, ?)', (cat_name, order))
        cat_id = cursor.lastrowid
        
        for tag in tags:
            # We append @trend_gif as it seems the original db init did it, wait!
            # The prompt says: "طبق این لیست مجدد هشتگ هارو تنظیم کنه توی دیتابیس:"
            # Did the user want @trend_gif appended? 
            # In their prompt, they didn't include it. " #خنده " etc.
            # I will insert exactly what they provided.
            cursor.execute('INSERT INTO hashtags (tag_name, category_id) VALUES (?, ?)', (tag, cat_id))
            
        order += 10
        
    conn.commit()
    conn.close()
    
    print("Migration complete! Database has been updated with the new categories and hashtags.")

if __name__ == "__main__":
    migrate()
