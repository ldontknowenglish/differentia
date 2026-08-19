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
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM well_treatments WHERE plate_id = ? AND is_deleted = 0 ORDER BY treatment_date ASC, well_position ASC", (plate_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_treatments_by_project(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT wt.*, p.name as plate_name 
        FROM well_treatments wt 
        JOIN plates p ON wt.plate_id = p.id 
        WHERE p.project_id = ? AND wt.is_deleted = 0 AND p.is_deleted = 0
        ORDER BY wt.treatment_date ASC, p.name ASC, wt.well_position ASC
    """, (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_treatment(treatment_id):
    """휴지통으로 이동 (소프트 삭제)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE well_treatments SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (treatment_id,))
    conn.commit()
    conn.close()

def restore_treatment(treatment_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE well_treatments SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (treatment_id,))
    conn.commit()
    conn.close()

def permanently_delete_treatment(treatment_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM well_treatments WHERE id = ?", (treatment_id,))
    conn.commit()
    conn.close()

# =========================================================
# Daily logs
# =========================================================
def add_daily_log(project_id, log_date, content):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO daily_logs (project_id, log_date, content) VALUES (?, ?, ?)", (project_id, log_date, content))
    conn.commit()
    conn.close()

def get_daily_logs(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_logs WHERE project_id = ? AND is_deleted = 0 ORDER BY log_date DESC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_daily_log(log_id):
    """휴지통으로 이동 (소프트 삭제)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE daily_logs SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()

def restore_daily_log(log_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE daily_logs SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()

def permanently_delete_daily_log(log_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_logs WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()

# =========================================================
# Material Recipes (시약 및 레시피 관리)
# =========================================================
def save_material_recipe(recipe_name, category, prepared_date, description, items):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO material_recipes (recipe_name, category, prepared_date, description) 
        VALUES (?, ?, ?, ?)
    """, (recipe_name, category, prepared_date, description))
    
    recipe_id = cursor.lastrowid
    
    for item in items:
        cursor.execute("""
            INSERT INTO recipe_items (recipe_id, material_name, manufacturer, cat_no, amount) 
            VALUES (?, ?, ?, ?, ?)
        """, (
            recipe_id, 
            item.get('material_name', ''), 
            item.get('manufacturer', ''), 
            item.get('cat_no', ''), 
            item.get('amount', '')
        ))
    
    conn.commit()
    conn.close()
    return recipe_id

def get_all_recipes(as_df=False):
    conn = get_connection()
    if as_df:
        df = pd.read_sql_query("SELECT * FROM material_recipes WHERE is_deleted = 0 ORDER BY created_at DESC", conn)
        conn.close()
        return df
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM material_recipes WHERE is_deleted = 0 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def get_all_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM material_recipes WHERE is_deleted = 0 AND category IS NOT NULL AND category != ''")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

def get_recipe_details(recipe_id, as_df=False):
    conn = get_connection()
    if as_df:
        df = pd.read_sql_query("SELECT material_name, manufacturer, cat_no, amount FROM recipe_items WHERE recipe_id = ?", conn, params=(recipe_id,))
        conn.close()
        return df
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, recipe_id, material_name, manufacturer, cat_no, amount FROM recipe_items WHERE recipe_id = ?", (recipe_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def delete_recipe(recipe_id):
    """휴지통으로 이동 (소프트 삭제)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE material_recipes SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE recipe_id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def restore_recipe(recipe_id):
    """휴지통에서 레시피 복구"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE material_recipes SET is_deleted = 0, deleted_at = NULL WHERE recipe_id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def permanently_delete_recipe(recipe_id):
    """영구 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM material_recipes WHERE recipe_id = ?", (recipe_id,))
    cursor.execute("DELETE FROM recipe_items WHERE recipe_id = ?", (recipe_id,))
    conn.commit()
    conn.close()

# =========================================================
# Trash (휴지통)
# =========================================================
def get_trash_projects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE is_deleted = 1 ORDER BY deleted_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_trash_plates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pl.*, p.name as project_name
        FROM plates pl
        LEFT JOIN projects p ON pl.project_id = p.id
        WHERE pl.is_deleted = 1
        ORDER BY pl.deleted_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_trash_treatments():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT wt.*, pl.name as plate_name, pr.name as project_name
        FROM well_treatments wt
        LEFT JOIN plates pl ON wt.plate_id = pl.id
        LEFT JOIN projects pr ON pl.project_id = pr.id
        WHERE wt.is_deleted = 1
        ORDER BY wt.deleted_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_trash_daily_logs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT dl.*, p.name as project_name
        FROM daily_logs dl
        LEFT JOIN projects p ON dl.project_id = p.id
        WHERE dl.is_deleted = 1
        ORDER BY dl.deleted_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_trash_recipes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM material_recipes WHERE is_deleted = 1 ORDER BY deleted_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_trash_count():
    return (
        len(get_trash_projects())
        + len(get_trash_plates())
        + len(get_trash_treatments())
        + len(get_trash_daily_logs())
        + len(get_trash_recipes())
    )
# db.py 맨 아래에 아래 코드를 추가/확장해주세요.

def init_analysis_tables():
    """분석 데이터(Cell Count, qPCR, FACS) 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()

    # 분석 데이터 통합 관리 테이블 (Cell Count, qPCR, FACS 등)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            data_type TEXT NOT NULL, -- 'Cell Count', 'qPCR', 'FACS'
            sample_name TEXT,
            metric_1_name TEXT,     -- 예: Concentration_M_mL, Relative_Expression, Pos_Pct
            metric_1_val REAL,
            metric_2_name TEXT,     -- 예: Viability_pct
            metric_2_val REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


def save_analysis_data(batch_id, data_type, df):
    """Dataframe 형태의 분석 결과를 DB에 저장"""
    conn = get_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        sample = row.get("Sample", row.get("Gene", row.get("Marker", "-")))

        # 컬럼 위치 기반 저장 logic
        cols = [c for c in df.columns if c not in ["Batch_ID", "Sample", "Gene", "Marker"]]
        val1_name = cols[0] if len(cols) > 0 else None
        val1_val = row[val1_name] if val1_name else None

        val2_name = cols[1] if len(cols) > 1 else None
        val2_val = row[val2_name] if val2_name else None

        cursor.execute(
            """
            INSERT INTO analysis_results (batch_id, data_type, sample_name, metric_1_name, metric_1_val, metric_2_name, metric_2_val)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                batch_id,
                data_type,
                str(sample),
                val1_name,
                val1_val,
                val2_name,
                val2_val,
            ),
        )

    conn.commit()
    conn.close()


def get_analysis_data(batch_id, data_type=None):
    """배치 ID로 분석 결과 조회"""
    conn = get_connection()
    if data_type:
        df = pd.read_sql_query(
            "SELECT * FROM analysis_results WHERE batch_id = ? AND data_type = ? ORDER BY id DESC",
            conn,
            params=(batch_id, data_type),
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM analysis_results WHERE batch_id = ? ORDER BY id DESC",
            conn,
            params=(batch_id,),
        )
    conn.close()
    return df
