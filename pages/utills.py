import base64
import datetime
import pandas as pd
import streamlit as st
import db

# Analysis options and presets
ANALYSIS_OPTIONS = [
    "미진행", 
    "단일세포 전사체 (scRNA-seq)", 
    "면역형광 염색 (IF / Confocal)", 
    "Flow Cytometry (FACS)", 
    "Western Blot / PCR", 
    "기타 분석"
]

PLATE_PRESETS = {
    "96-Well Plate (8 x 12)": (8, 12),
    "48-Well Plate (6 x 8)": (6, 8),
    "24-Well Plate (4 x 6)": (4, 6),
    "12-Well Plate (3 x 4)": (3, 4),
    "6-Well Plate (2 x 3)": (2, 3),
    "⚙️ 사용자 지정 (Custom)": "custom"
}

# All helper functions
def file_to_base64(uploaded_file):
    """업로드된 이미지 파일을 Base64 문자열로 변환"""
    if uploaded_file is None:
        return None
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode('utf-8')

def extract_image_data(item):
    """item에서 이미지 base64 데이터 추출"""
    if not item:
        return None
    if item.get('image_data'):
        return item['image_data']
    note = str(item.get('note', ''))
    if '[IMG_DATA:' in note and ']' in note:
        start = note.find('[IMG_DATA:') + len('[IMG_DATA:')
        end = note.rfind(']')
        if start < end:
            return note[start:end].strip()
    return None

def parse_note_basal_image(item):
    """item에서 basal_media, 이미지, 순수 note 분리"""
    if not item:
        return "", "", None
    basal = get_basal_media(item)
    if basal == "-":
        basal = ""
    
    raw_note = str(item.get('note', ''))
    img_data = extract_image_data(item)
    
    pure_note = raw_note
    if '[Media:' in pure_note and ']' in pure_note:
        m_start = pure_note.find('[Media:')
        m_end = pure_note.find(']', m_start)
        if m_end != -1:
            pure_note = (pure_note[:m_start] + pure_note[m_end+1:]).strip()
            
    if '[IMG_DATA:' in pure_note and ']' in pure_note:
        i_start = pure_note.find('[IMG_DATA:')
        i_end = pure_note.rfind(']')
        if i_end != -1:
            pure_note = (pure_note[:i_start] + pure_note[i_end+1:]).strip()
            
    return basal, pure_note.strip(), img_data

def build_combined_note(basal, pure_note, img_b64):
    """Basal media, 순수 note, 이미지 base64를 하나의 note 문자열로 결합"""
    parts = []
    if basal and basal.strip() and basal.strip() != "-":
        parts.append(f"[Media: {basal.strip()}]")
    if pure_note and pure_note.strip():
        parts.append(pure_note.strip())
    if img_b64 and img_b64.strip():
        parts.append(f"[IMG_DATA: {img_b64.strip()}]")
    return " ".join(parts)

def display_image_from_b64(b64_str, caption="", width=None):
    """Base64 문자열을 Streamlit 이미지로 출력"""
    if not b64_str:
        return
    try:
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=True if width is None else False, width=width)
    except Exception:
        st.caption("⚠️ 이미지를 로드할 수 없습니다.")

def get_basal_media(item):
    """Basal Media 정보를 안전하게 추출"""
    if not item:
        return "-"
    if item.get('basal_media') and str(item['basal_media']).strip() and str(item['basal_media']).strip() != '-':
        return str(item['basal_media']).strip()
    note = str(item.get('note', ''))
    if '[Media:' in note and ']' in note:
        start = note.find('[Media:') + len('[Media:')
        end = note.find(']', start)
        if end != -1:
            extracted = note[start:end].strip()
            if extracted:
                return extracted
    return "-"

def get_recipe_options(current_val=""):
    """Material Recipe DB에서 저장된 레시피 목록을 추출"""
    options = ["-"]
    if hasattr(db, 'get_all_recipes'):
        recipes = db.get_all_recipes()
        if isinstance(recipes, list):
            for r in recipes:
                name = r.get('recipe_name') if isinstance(r, dict) else getattr(r, 'recipe_name', None)
                if name and name not in options:
                    options.append(name)
        elif isinstance(recipes, pd.DataFrame) and not recipes.empty and 'recipe_name' in recipes.columns:
            for name in recipes['recipe_name'].dropna().unique():
                if name and name not in options:
                    options.append(str(name))

    if current_val and current_val != "-" and current_val not in options:
        options.append(current_val)
        
    return options

def generate_dynamic_lineage_dot(treatments):
    """사용자가 입력한 treatments 데이터의 cell_info와 날짜 순서를 분석"""
    if not treatments:
        return None

    df = pd.DataFrame(treatments)
    if 'cell_info' not in df.columns:
        return None
        
    df = df[df['cell_info'].notnull() & (df['cell_info'].str.strip() != "")]
    if df.empty:
        return None

    df = df.sort_values(by=['well_position', 'treatment_date'])

    nodes = set()
    edges = set()

    for well, group in df.groupby('well_position'):
        cell_history = []
        for _, row in group.iterrows():
            c_info = str(row['cell_info']).strip()
            t_date = str(row['treatment_date']).strip()
            if c_info:
                if not cell_history or cell_history[-1][0] != c_info:
                    cell_history.append((c_info, t_date))
        
        for c_info, _ in cell_history:
            nodes.add(c_info)

        for i in range(len(cell_history) - 1):
            src, _ = cell_history[i]
            dst, dst_date = cell_history[i + 1]
            if src != dst:
                edges.add((src, dst, dst_date))

    if not nodes:
        return None

    dot_lines = [
        "digraph LineageTree {",
        "    rankdir=LR;",
        "    graph [nodesep=0.3, ranksep=0.6, margin=0, pad=0.1];",
        "    node [shape=box, style=\"filled,rounded\", fillcolor=\"#f8fafc\", color=\"#3b82f6\", fontname=\"Malgun Gothic, sans-serif\", fontsize=9, height=0.28, margin=\"0.1,0.05\"];",
        "    edge [color=\"#64748b\", arrowhead=normal, arrowsize=0.6, penwidth=1.2, fontname=\"Malgun Gothic, sans-serif\", fontsize=8];"
    ]

    for node in nodes:
        clean_node = node.replace('"', '\\"')
        dot_lines.append(f'    "{clean_node}" [label="{clean_node}"];')

    for src, dst, transition_date in edges:
        clean_src = src.replace('"', '\\"')
        clean_dst = dst.replace('"', '\\"')
        clean_date = transition_date.replace('"', '\\"')
        dot_lines.append(f'    "{clean_src}" -> "{clean_dst}" [label=" {clean_date} ", fontcolor="#475569"];')

    dot_lines.append("}")
    return "\n".join(dot_lines)

def format_compound_summary(comp_str, conc_str):
    """물질명과 농도 문자열을 1:1 매칭"""
    if not comp_str:
        return "-"
    
    comps = [c.strip() for c in str(comp_str).split(',') if c.strip()]
    concs = [c.strip() for c in str(conc_str).split(',')] if conc_str else []
    
    paired = []
    for i, comp in enumerate(comps):
        conc = concs[i] if i < len(concs) and concs[i] else ""
        if conc:
            paired.append(f"{comp} {conc}")
        else:
            paired.append(comp)
            
    return ", ".join(paired)
