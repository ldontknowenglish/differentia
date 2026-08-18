import sqlite3
import pandas as pd

DB_NAME = "notebook.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_column(cursor, table, column, coltype):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [r[1] for r in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            group_name TEXT DEFAULT '기본 연구',
            color_code TEXT DEFAULT '#3B82F6',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Plates table (project_id INTEGER 컬럼 추가 완료)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT NOT NULL,
            rows INTEGER DEFAULT 8,
            cols INTEGER DEFAULT 12,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # Treatments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS well_treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_id INTEGER,
            well_position TEXT NOT NULL,
            treatment_date DATE NOT NULL,
            compound_name TEXT NOT NULL,
            concentration TEXT,
            cell_info TEXT,
            note TEXT,
            analysis_status TEXT DEFAULT '미진행',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plate_id) REFERENCES plates(id) ON DELETE CASCADE
        )
    """)

    # Daily log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            log_date DATE,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # Material Recipes table (레시피 메인)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS material_recipes (
            recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_name TEXT NOT NULL,
            category TEXT,
            prepared_date TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Recipe Items table (레시피 성분 상세)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipe_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER,
            material_name TEXT NOT NULL,
            manufacturer TEXT,
            cat_no TEXT,
            amount TEXT,
            FOREIGN KEY (recipe_id) REFERENCES material_recipes (recipe_id) ON DELETE CASCADE
        )
    """)

    # --- 기존 DB와의 호환성을 위한 컬럼 자동 마이그레이션 ---
    for table in ["projects", "plates", "well_treatments", "daily_logs", "material_recipes"]:
        _ensure_column(cursor, table, "is_deleted", "INTEGER DEFAULT 0")
        _ensure_column(cursor, table, "deleted_at", "TIMESTAMP")

    _ensure_column(cursor, "well_treatments", "analysis_status", "TEXT DEFAULT '미진행'")
    _ensure_column(cursor, "material_recipes", "category", "TEXT")
    _ensure_column(cursor, "material_recipes", "prepared_date", "TEXT")
    _ensure_column(cursor, "recipe_items", "manufacturer", "TEXT")

    conn.commit()
    conn.close()

# 프론트엔드 호환용 별칭
init_recipe_db = init_db

# =========================================================
# Projects
# =========================================================
def add_project(name, group_name, color_code, description):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO projects (name, group_name, color_code, description) VALUES (?, ?, ?, ?)",
        (name, group_name, color_code, description)
    )
    conn.commit()
    conn.close()

def get_projects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE is_deleted = 0 ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_project(project_id, name, group_name, color_code, description):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE projects 
        SET name = ?, group_name = ?, color_code = ?, description = ?
        WHERE id = ?
    """, (name, group_name, color_code, description, project_id))
    conn.commit()
    conn.close()

def delete_project(project_id):
    """휴지통으로 이동 (소프트 삭제)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE projects SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

def restore_project(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE projects SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

def permanently_delete_project(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

# =========================================================
# Plates
# =========================================================
def add_plate(project_id, name, rows=8, cols=12):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO plates (project_id, name, rows, cols) VALUES (?, ?, ?, ?)", (project_id, name, rows, cols))
    conn.commit()
    plate_id = cursor.lastrowid
    conn.close()
    return plate_id

def get_plates(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plates WHERE project_id = ? AND is_deleted = 0 ORDER BY id DESC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_plate(plate_id):
    """휴지통으로 이동 (소프트 삭제)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE plates SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (plate_id,))
    conn.commit()
    conn.close()

def restore_plate(plate_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE plates SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (plate_id,))
    conn.commit()
    conn.close()

def permanently_delete_plate(plate_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plates WHERE id = ?", (plate_id,))
    conn.commit()
    conn.close()

# =========================================================
# Well treatments
# =========================================================
def add_treatment(plate_id, well_position, treatment_date, compound_name, concentration, cell_info, note, analysis_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO well_treatments (plate_id, well_position, treatment_date, compound_name, concentration, cell_info, note, analysis_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (plate_id, well_position, treatment_date, compound_name, concentration, cell_info, note, analysis_status))
    conn.commit()
    conn.close()

def update_treatment(treatment_id, well_position, treatment_date, compound_name, concentration, cell_info, note, analysis_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE well_treatments
        SET well_position = ?, treatment_date = ?, compound_name = ?, concentration = ?, cell_info = ?, note = ?, analysis_status = ?
        WHERE id = ?
    """, (well_position, treatment_date, compound_name, concentration, cell_info, note, analysis_status, treatment_id))
    conn.commit()
    conn.close()

def get_treatments_by_plate(plate_id):
    conn = get_connection()
    cursor = conn
