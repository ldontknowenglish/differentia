import sqlite3
import pandas as pd

# db.py 파일 내부의 init_db() 함수 안에 아래 테이블 생성 쿼리를 추가해 주세요.
def init_recipe_db():
    conn = sqlite3.connect('organoid.db')
    c = conn.cursor()
    
    # 레시피 메인 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS material_recipes (
            recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 레시피 성분 상세 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipe_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER,
            material_name TEXT NOT NULL,
            cat_no TEXT,
            amount TEXT,
            FOREIGN KEY (recipe_id) REFERENCES material_recipes (recipe_id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

# 레시피 저장 함수
def save_material_recipe(recipe_name, description, items):
    conn = sqlite3.connect('organoid.db')
    c = conn.cursor()
    c.execute("INSERT INTO material_recipes (recipe_name, description) VALUES (?, ?)", (recipe_name, description))
    recipe_id = c.lastrowid
    
    for item in items:
        c.execute("""
            INSERT INTO recipe_items (recipe_id, material_name, cat_no, amount) 
            VALUES (?, ?, ?, ?)
        """, (recipe_id, item['material_name'], item['cat_no'], item.get('amount', '')))
    
    conn.commit()
    conn.close()

# 레시피 목록 및 상세 조회
def get_all_recipes():
    conn = sqlite3.connect('organoid.db')
    df = pd.read_sql_query("SELECT * FROM material_recipes ORDER BY created_at DESC", conn)
    conn.close()
    return df

def get_recipe_details(recipe_id):
    conn = sqlite3.connect('organoid.db')
    df = pd.read_sql_query("SELECT material_name, cat_no, amount FROM recipe_items WHERE recipe_id = ?", conn, params=(recipe_id,))
    conn.close()
    return df

# 레시피 삭제
def delete_recipe(recipe_id):
    conn = sqlite3.connect('organoid.db')
    c = conn.cursor()
    c.execute("DELETE FROM material_recipes WHERE recipe_id = ?", (recipe_id,))
    c.execute("DELETE FROM recipe_items WHERE recipe_id = ?", (recipe_id,))
    conn.commit()
    conn.close()