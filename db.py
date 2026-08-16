import sqlite3

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

    # Plates table
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

    # --- 휴지통(Trash) 지원을 위한 컬럼 마이그레이션 ---
    # 기존 DB 파일에도 안전하게 컬럼을 추가합니다 (이미 있으면 건너뜀).
    for table in ["projects", "plates", "well_treatments", "daily_logs"]:
        _ensure_column(cursor, table, "is_deleted", "INTEGER DEFAULT 0")
        _ensure_column(cursor, table, "deleted_at", "TIMESTAMP")

    conn.commit()
    conn.close()

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
def add_treatment(plate_id, well_position, treatment_date, compound_name, concentration, cell_info, note):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO well_treatments (plate_id, well_position, treatment_date, compound_name, concentration, cell_info, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (plate_id, well_position, treatment_date, compound_name, concentration, cell_info, note))
    conn.commit()
    conn.close()

def update_treatment(treatment_id, well_position, treatment_date, compound_name, concentration, cell_info, note):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE well_treatments
        SET well_position = ?, treatment_date = ?, compound_name = ?, concentration = ?, cell_info = ?, note = ?
        WHERE id = ?
    """, (well_position, treatment_date, compound_name, concentration, cell_info, note, treatment_id))
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

def get_trash_count():
    return (
        len(get_trash_projects())
        + len(get_trash_plates())
        + len(get_trash_treatments())
        + len(get_trash_daily_logs())
    )
