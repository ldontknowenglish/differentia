import datetime
import base64
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
import style

# ======================================================================
# 1. 페이지 및 스타일 기본 설정
# ======================================================================
st.set_page_config(page_title="연구 프로젝트 관리", page_icon="🧪", layout="wide")

st.markdown("""
    <style>
        .main .block-container {
            padding-left: 1.5rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
            margin-left: 0 !important;
        }
        .plate-card-header { font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 6px; }
        .plate-card-sub { font-size: 13px; color: #475569; margin-bottom: 4px; }
        .transfer-box { background-color: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
        .root-cell-box { background-color: #fefce8; border: 1px solid #fef08a; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
    </style>
""", unsafe_allow_html=True)

if hasattr(style, "apply_custom_style"):
    style.apply_custom_style()

# 분석진행 상태 Session State 초기화 (항목 추가/삭제 지원)
DEFAULT_ANALYSIS_OPTIONS = [
    "미진행", 
    "단일세포 전사체 (scRNA-seq)", 
    "면역형광 염색 (IF / Confocal)", 
    "Flow Cytometry (FACS)", 
    "Western Blot / PCR", 
    "기타 분석"
]

if "analysis_options" not in st.session_state:
    st.session_state.analysis_options = DEFAULT_ANALYSIS_OPTIONS.copy()

PLATE_PRESETS = {
    "96-Well Plate (8 x 12)": (8, 12),
    "48-Well Plate (6 x 8)": (6, 8),
    "24-Well Plate (4 x 6)": (4, 6),
    "12-Well Plate (3 x 4)": (3, 4),
    "6-Well Plate (2 x 3)": (2, 3),
    "⚙️ 사용자 지정 (Custom)": "custom"
}

# ======================================================================
# 2. 헬퍼 및 유틸리티 함수
# ======================================================================
def file_to_base64(uploaded_file):
    if not uploaded_file:
        return None
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def extract_image_data(item):
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

def get_basal_media(item):
    if not item:
        return "-"
    if item.get('basal_media') and str(item['basal_media']).strip() not in ['-', '']:
        return str(item['basal_media']).strip()
    note = str(item.get('note', ''))
    if '[Media:' in note and ']' in note:
        start, end = note.find('[Media:'), note.find(']', note.find('[Media:'))
        if end != -1:
            extracted = note[start:end].strip()
            if extracted: return extracted
    return "-"

def get_cell_origin(item):
    """세포 유래 정보를 추출하는 헬퍼 함수"""
    if not item:
        return "-"
    note = str(item.get('note', ''))
    if '[Origin:' in note and ']' in note:
        start = note.find('[Origin:') + len('[Origin:')
        end = note.find(']', start)
        if end != -1:
            return note[start:end].strip()
    return "-"

def get_passage_info(item):
    """계대/이동 관련 상세 정보 추출 (출처, 해취물질, 시딩 세포수)"""
    if not item:
        return "", "", ""
    note = str(item.get('note', ''))
    if '[PassageFrom:' in note and ']' in note:
        try:
            start = note.find('[PassageFrom:') + len('[PassageFrom:')
            end = note.find(']', start)
            content = note[start:end].strip()
            parts = content.split('|')
            src = parts[0] if len(parts) > 0 else ""
            reagent = parts[1] if len(parts) > 1 else ""
            seeding = parts[2] if len(parts) > 2 else ""
            return src, reagent, seeding
        except:
            pass
    return "", "", ""

def parse_note_basal_image(item):
    """Note에서 Basal Media, Origin, PassageInfo, pure_note, img_data 파싱"""
    if not item:
        return "", "", "", "", "", "", None
    
    basal = get_basal_media(item)
    basal = "" if basal == "-" else basal
    
    origin = get_cell_origin(item)
    origin = "" if origin == "-" else origin

    psg_src, psg_reagent, psg_seeding = get_passage_info(item)

    pure_note = str(item.get('note', ''))
    img_data = extract_image_data(item)
    
    for tag in ['[Media:', '[Origin:', '[PassageFrom:']:
        while tag in pure_note:
            s = pure_note.find(tag)
            e = pure_note.find(']', s)
            if e != -1:
                pure_note = (pure_note[:s] + pure_note[e+1:]).strip()
            else:
                break

    if '[IMG_DATA:' in pure_note and ']' in pure_note:
        s, e = pure_note.find('[IMG_DATA:'), pure_note.rfind(']')
        if e != -1: pure_note = (pure_note[:s] + pure_note[e+1:]).strip()
            
    return basal, origin, psg_src, psg_reagent, psg_seeding, pure_note.strip(), img_data

def build_combined_note(basal, origin, psg_src, psg_reagent, psg_seeding, pure_note, img_b64):
    """태그 통합 저장 문자열 생성"""
    parts = []
    if basal and basal.strip() and basal.strip() != "-":
        parts.append(f"[Media: {basal.strip()}]")
    if origin and origin.strip() and origin.strip() != "-":
        parts.append(f"[Origin: {origin.strip()}]")
    if psg_src and psg_src.strip():
        p_str = f"{psg_src.strip()}|{psg_reagent.strip()}|{psg_seeding.strip()}"
        parts.append(f"[PassageFrom: {p_str}]")
    if pure_note and pure_note.strip():
        parts.append(pure_note.strip())
    if img_b64 and img_b64.strip():
        parts.append(f"[IMG_DATA: {img_b64.strip()}]")
    return " ".join(parts)

def get_recipe_options(current_val=""):
    options = ["-"]
    if hasattr(db, 'get_all_recipes'):
        recipes = db.get_all_recipes()
        if isinstance(recipes, list):
            for r in recipes:
                name = r.get('recipe_name') if isinstance(r, dict) else getattr(r, 'recipe_name', None)
                if name and name not in options: options.append(name)
        elif isinstance(recipes, pd.DataFrame) and not recipes.empty and 'recipe_name' in recipes.columns:
            for name in recipes['recipe_name'].dropna().unique():
                if name and name not in options: options.append(str(name))

    if current_val and current_val != "-" and current_val not in options:
        options.append(current_val)
    return options

def get_project_plate_wells_options(project_id, current_val=""):
    """프로젝트 내 존재하는 모든 플레이트 및 Well 목록을 드롭다운 옵션으로 추출"""
    options = ["직접 입력 / 해당 없음"]
    plates = db.get_plates(project_id)
    if plates:
        for pl in plates:
            p_name = pl['name']
            t_list = db.get_treatments_by_plate(pl['id'])
            well_cell_map = {}
            for t in t_list:
                w_pos = t.get('well_position', '').upper()
                c_info = t.get('cell_info', '').strip()
                if w_pos and c_info:
                    well_cell_map[w_pos] = c_info

            rows, cols = pl['rows'], pl['cols']
            for r in range(rows):
                r_label = chr(65 + r)
                for c in range(1, cols + 1):
                    pos = f"{r_label}{c}"
                    cell_info = f" ({well_cell_map[pos]})" if pos in well_cell_map else ""
                    opt_str = f"[{p_name}] {pos}{cell_info}"
                    if opt_str not in options:
                        options.append(opt_str)

    if current_val and current_val not in options:
        options.append(current_val)
    return options

def format_compound_summary(comp_str, conc_str):
    if not comp_str: return "-"
    comps = [c.strip() for c in str(comp_str).split(',') if c.strip()]
    concs = [c.strip() for c in str(conc_str).split(',')] if conc_str else []
    
    paired = []
    for i, comp in enumerate(comps):
        conc = concs[i] if i < len(concs) and concs[i] else ""
        paired.append(f"{comp} {conc}".strip())
    return ", ".join(paired)

def render_compound_inputs(key_prefix, default_comps=None, default_concs=None):
    default_comps = default_comps or []
    default_concs = default_concs or []
    
    st.caption("🧪 **처리 물질 및 농도**")
    num_pairs = st.number_input(
        "물질 개수", min_value=1, max_value=10, 
        value=max(1, len(default_comps), 2), key=f"{key_prefix}_num_pairs"
    )
    
    comps, concs = [], []
    for i in range(0, int(num_pairs), 2):
        pair_cols = st.columns([2, 1, 2, 1])
        def_c1 = default_comps[i] if i < len(default_comps) else ""
        def_n1 = default_concs[i] if i < len(default_concs) else ""
        
        with pair_cols[0]:
            c1_val = st.text_input(f"물질 #{i+1}", value=def_c1, placeholder="예: VEGF", key=f"{key_prefix}_c_{i}")
        with pair_cols[1]:
            n1_val = st.text_input(f"농도 #{i+1}", value=def_n1, placeholder="예: 50 ng/mL", key=f"{key_prefix}_n_{i}")
        if c1_val.strip():
            comps.append(c1_val.strip())
            concs.append(n1_val.strip())
            
        if i + 1 < int(num_pairs):
            def_c2 = default_comps[i+1] if i+1 < len(default_comps) else ""
            def_n2 = default_concs[i+1] if i+1 < len(default_concs) else ""
            with pair_cols[2]:
                c2_val = st.text_input(f"물질 #{i+2}", value=def_c2, placeholder="추가 물질", key=f"{key_prefix}_c_{i+1}")
            with pair_cols[3]:
                n2_val = st.text_input(f"농도 #{i+2}", value=def_n2, placeholder="추가 농도", key=f"{key_prefix}_n_{i+1}")
            if c2_val.strip():
                comps.append(c2_val.strip())
                concs.append(n2_val.strip())
                
    return ", ".join(comps), ", ".join(concs)

def render_analysis_status_manager():
    """분석진행 상태 항목 관리 (추가 및 삭제 기능) UI"""
    with st.expander("⚙️ 분석 진행 상태 항목 관리 (추가/삭제)"):
        st.caption("기본 제공되는 분석 항목 외에 필요한 신규 항목을 추가하거나 불필요한 항목을 삭제할 수 있습니다.")
        m_c1, m_c2 = st.columns([3, 1])
        new_item = m_c1.text_input("새 분석 항목 이름", placeholder="예: RNA-seq (Bulk)", key="new_analysis_item_input")
        if m_c2.button("➕ 항목 추가", key="btn_add_analysis_item", use_container_width=True):
            if new_item.strip():
                if new_item.strip() not in st.session_state.analysis_options:
                    st.session_state.analysis_options.append(new_item.strip())
                    st.toast(f"'{new_item.strip()}' 항목이 추가되었습니다.", icon="✅")
                    st.rerun()
                else:
                    st.warning("이미 존재하는 항목입니다.")
            else:
                st.error("항목 이름을 입력하세요.")

        st.markdown("---")
        del_c1, del_c2 = st.columns([3, 1])
        deletable_opts = [opt for opt in st.session_state.analysis_options if opt != "미진행"]
        item_to_del = del_c1.selectbox("삭제할 분석 항목 선택", options=deletable_opts, key="del_analysis_item_select")
        if del_c2.button("🗑️ 항목 삭제", key="btn_del_analysis_item", use_container_width=True):
            if item_to_del in st.session_state.analysis_options:
                st.session_state.analysis_options.remove(item_to_del)
                st.toast(f"'{item_to_del}' 항목이 삭제되었습니다.", icon="🗑️")
                st.rerun()

# ======================================================================
# 가로(Horizontal) 흐름 및 동일 세포/실험 추적 계통도 생성 함수
# ======================================================================
def generate_project_cell_lineage_dot(project_id):
    plates = db.get_plates(project_id)
    if not plates:
        return None, []

    plate_name_map = {pl['id']: pl['name'] for pl in plates}
    all_treatments = []
    
    for pl in plates:
        t_list = db.get_treatments_by_plate(pl['id'])
        for t in t_list:
            t['plate_name'] = plate_name_map.get(pl['id'], f"Plate_{pl['id']}")
            all_treatments.append(t)

    if not all_treatments:
        return None, []

    df = pd.DataFrame(all_treatments)
    if 'cell_info' not in df.columns:
        return None, []

    # 세포 정보가 빈 값이 아닌 데이터만 필터링
    df = df[df['cell_info'].notnull() & (df['cell_info'].str.strip() != "")]
    if df.empty:
        return None, []

    # 날짜, 플레이트, 웰 순으로 정렬
    df = df.sort_values(by=['treatment_date', 'plate_name', 'well_position'])

    nodes_info = {}
    edges = set()

    # 1. 세포 노드(Node) 및 히스토리 수집
    for (plate_id, well), group in df.groupby(['plate_id', 'well_position']):
        cell_history = []
        for _, row in group.iterrows():
            c_info = str(row['cell_info']).strip()
            t_date = str(row['treatment_date']).strip()
            p_name = row['plate_name']
            w_pos = row['well_position']
            loc_str = f"{p_name} {w_pos}"
            
            if c_info:
                # 동일한 세포/실험명(c_info)이면 노드를 하나로 합치고 위치 및 날짜 업데이트
                loc_str = f"{p_name} {w_pos}"
                if c_info not in nodes_info:
                    nodes_info[c_info] = {
                        'first_date': t_date, 
                        'plates': {p_name}, 
                        'locations': {loc_str}, 
                        'count': 1
                    }
                else:
                    nodes_info[c_info]['plates'].add(p_name)
                    nodes_info[c_info]['locations'].add(loc_str)
                
                if not cell_history or cell_history[-1][0] != c_info:
                    cell_history.append((c_info, t_date, p_name, w_pos))

        # 동일 well 내에서 세포 이름이 변경/전이된 경우 엣지 연결
        for i in range(len(cell_history) - 1):
            src_cell = cell_history[i][0]
            dst_cell = cell_history[i + 1][0]
            dst_date = cell_history[i + 1][1]
            if src_cell != dst_cell:
                edges.add((src_cell, dst_cell, dst_date, "Transition"))

    # 2. 계대 태그 [PassageFrom:] 기반 추적 및 연결(Edge) 생성
    for _, row in df.iterrows():
        c_info = str(row['cell_info']).strip()
        note = str(row.get('note', ''))
        t_date = str(row['treatment_date']).strip()
        
        if "[PassageFrom:" in note:
            try:
                s = note.find("[PassageFrom:") + len("[PassageFrom:")
                e = note.find("]", s)
                content = note[s:e].strip()
                parts = content.split('|')
                src_well_info = parts[0].strip() # 출처 플레이트/웰 또는 세포명
                reagent = parts[1].strip() if len(parts) > 1 else ""
                seeding = parts[2].strip() if len(parts) > 2 else ""
                
                label_details = []
                if reagent: label_details.append(reagent)
                if seeding: label_details.append(seeding)
                detail_str = f" ({', '.join(label_details)})" if label_details else ""

                # 💡 출처 정보를 기반으로 기존 세포 노드 찾기
                for existing_cell, info in nodes_info.items():
                    # 조건 A: 출처 텍스트에 이전 세포 이름이 직접 포함된 경우
                    # 조건 B: 출처 텍스트에 이전 웰 정보(예: "24-Well Plate A1")가 포함된 경우
                    is_matched_cell = existing_cell.lower() in src_well_info.lower()
                    is_matched_loc = any(loc.lower() in src_well_info.lower() for loc in info['locations'])

                    if (is_matched_cell or is_matched_loc):
                        # 동일한 제목/이름이면 자기 자신을 가리키는 순환 참조(Self-loop) 대신 
                        # 노드는 하나로 유지되며 진행 상태로 이어집니다.
                        if existing_cell != c_info:
                            edges.add((existing_cell, c_info, t_date, f"Passage{detail_str}"))
            except Exception:
                pass

    if not nodes_info:
        return None, []

    # 최상위 원천(시작) 세포 탐색
    dst_nodes = {e[1] for e in edges}
    root_cells = [c for c in nodes_info.keys() if c not in dst_nodes]
    if not root_cells:
        min_date = min(n['first_date'] for n in nodes_info.values())
        root_cells = [c for c, n in nodes_info.items() if n['first_date'] == min_date]

    # Graphviz Dot 문법 생성 (가로 방향 LR)
    dot_lines = [
        "digraph ProjectLineage { rankdir=LR; newrank=true;",
        "    graph [nodesep=0.6, ranksep=1.2, margin=0, pad=0.3, splines=ortho];",
        "    node [shape=box, style=\"filled,rounded\", fontname=\"Malgun Gothic, sans-serif\", fontsize=10, height=0.45, margin=\"0.2,0.1\"];",
        "    edge [color=\"#64748b\", arrowhead=normal, arrowsize=0.8, penwidth=1.5, fontname=\"Malgun Gothic, sans-serif\", fontsize=8];"
    ]

    date_to_nodes = {}

    for cell_group, info in nodes_info.items():
        clean_name = cell_group.replace('"', '\\"')
        plates_str = ", ".join(sorted(list(info['plates'])))
        first_date = info['first_date']
        
        date_to_nodes.setdefault(first_date, []).append(clean_name)

        if cell_group in root_cells:
            label = f"👑 [시작 세포]\\n{clean_name}\\n(최초: {first_date})"
            dot_lines.append(
                f'    "{clean_name}" [label="{label}", fillcolor="#fef9c3", color="#ca8a04", penwidth=2.5, fontcolor="#854d0e"];'
            )
        else:
            label = f"🧬 {clean_name}\\n({plates_str})"
            dot_lines.append(
                f'    "{clean_name}" [label="{label}", fillcolor="#eff6ff", color="#2563eb", penwidth=1.2, fontcolor="#1e3a8a"];'
            )

    # 같은 일자의 노드들을 동일한 열(Rank)에 위치시킴
    for t_date, nodes in sorted(date_to_nodes.items()):
        nodes_str = "; ".join([f'"{n}"' for n in nodes])
        dot_lines.append(f'    {{ rank=same; {nodes_str}; }}')

    # 화살표(Edge) 그리기
    for src, dst, t_date, label in edges:
        c_src = src.replace('"', '\\"')
        c_dst = dst.replace('"', '\\"')
        c_date = t_date.replace('"', '\\"')
        dot_lines.append(f'    "{c_src}" -> "{c_dst}" [label=" {c_date}\\n({label}) ", fontcolor="#0284c7"];')

    dot_lines.append("}")
    return "\n".join(dot_lines), root_cells


# ======================================================================
# 3. 각 탭별 Render 함수
# ======================================================================
def render_tab_overview():
    st.markdown("### 🧪 전체 프로젝트의 실험 중인 플레이트 목록")
    st.caption("모든 웰의 분석이 완료된 플레이트는 제외되며, 현재 분석 및 실험이 진행 중인 플레이트만 표시됩니다.")

    def navigate_to_plate(proj_label, pl_key, proj_name, pl_name):
        st.session_state.selected_plate_proj_label = proj_label
        st.session_state.selected_plate_select = pl_key
        st.session_state.active_tab = 1
        st.toast(f"'{proj_name}' 프로젝트의 '{pl_name}' 플레이트로 이동합니다.", icon="🧫")
        st.rerun()

    active_plates = []
    all_projects = db.get_projects()
    
    for proj in all_projects:
        proj_plates = db.get_plates(proj['id'])
        for pl in proj_plates:
            pl_treatments = db.get_treatments_by_plate(pl['id'])
            total_cap = pl['rows'] * pl['cols']
            completed_wells = {t.get('well_position') for t in pl_treatments if t.get('analysis_status') and t.get('analysis_status') != '미진행'}
            
            if len(completed_wells) < total_cap:
                active_plates.append({
                    'project': proj, 'plate': pl, 'treatments': pl_treatments,
                    'total_cap': total_cap, 'completed_count': len(completed_wells)
                })

    if not active_plates:
        st.info("💡 현재 진행 중인 실험 플레이트가 없습니다.")
        return

    grid_cols = st.columns(3)
    for idx, item in enumerate(active_plates):
        proj, pl, pl_treatments = item['project'], item['plate'], item['treatments']
        total_cap, completed_count = item['total_cap'], item['completed_count']
        
        cells = sorted(list({t.get('cell_info', '').strip() for t in pl_treatments if t.get('cell_info')}))
        cell_display = ", ".join(cells) if cells else "미지정 (세포 정보 없음)"
        
        if pl_treatments:
            latest_treat = max(pl_treatments, key=lambda x: str(x.get('treatment_date', '')))
            latest_date = latest_treat.get('treatment_date', '-')
            *_, pure_note, _ = parse_note_basal_image(latest_treat)
            
            task_title = pure_note if pure_note else format_compound_summary(latest_treat.get('compound_name'), latest_treat.get('concentration'))
            if not task_title or task_title == "-":
                task_title = f"최근 처리 진행 ({latest_treat.get('analysis_status', '기본')})"
        else:
            latest_date, task_title = "기록 없음", "작업 기록 없음"

        well_count = len({t.get('well_position') for t in pl_treatments})
        proj_label = f"[{proj['group_name'] if proj['group_name'] else '기본'}] {proj['name']} (ID: {proj['id']})"
        pl_key = f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)"

        with grid_cols[idx % 3]:
            st.markdown(
                f"""
                <div style="border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 12px;">
                    <div style="font-size:12px; color:{proj['color_code']}; font-weight:bold; margin-bottom:4px;">📁 프로젝트: {proj['name']}</div>
                    <div class="plate-card-header">🧫 {pl['name']}</div>
                    <div class="plate-card-sub"><b>📌 규격:</b> {pl['rows']}x{pl['cols']} ({total_cap} Wells)</div>
                    <div class="plate-card-sub"><b>🧬 사용 세포:</b> <span style="color:#2563eb; font-weight:600;">{cell_display}</span></div>
                    <div class="plate-card-sub"><b>📋 최근 조건:</b> {task_title}</div>
                    <div class="plate-card-sub"><b>🔬 분석 진행률:</b> <span style="color:#059669; font-weight:bold;">{completed_count}/{total_cap} Wells 완료</span></div>
                    <div class="plate-card-sub"><b>📅 최근 작업일:</b> {latest_date} ({well_count}/{total_cap} Wells 처리됨)</div>
                </div>
                """, unsafe_allow_html=True
            )
            st.button(
                f"🔍 [{pl['name']}] 편집하러 가기", key=f"btn_goto_pl_{pl['id']}",
                use_container_width=True, type="primary", on_click=navigate_to_plate,
                args=(proj_label, pl_key, proj['name'], pl['name'])
            )

def render_tab_visualization(selected_plate, treatments):
    st.info("💡 **왼쪽 차트**의 Well을 **클릭**하거나 **드래그(Box/Lasso)**하면 **오른쪽 편집 창**에서 바로 수정 및 신규 처리가 가능합니다.")
    left_col, right_col = st.columns([5.5, 6.5], gap="large")

    rows, cols = selected_plate['rows'], selected_plate['cols']
    total_wells = rows * cols
    row_labels = [chr(65 + i) for i in range(rows)]
    dates_available = sorted(list({t['treatment_date'] for t in treatments})) if treatments else []

    with left_col:
        st.markdown("##### 🧫 플레이트 배치 시각화")
        c_v1, c_v2 = st.columns([1.2, 1.8])
        selected_date = c_v1.selectbox("📅 조회 날짜", options=["전체 날짜 (최신 상태)"] + dates_available, key="v_date_select")
        color_by = c_v2.radio("🎨 색상 기준", ["세포 정보별", "처리 유무별"], horizontal=True, key="v_color_radio")

        well_last_map, well_all_map = {}, {}
        for t in treatments:
            if selected_date == "전체 날짜 (최신 상태)" or t['treatment_date'] == selected_date:
                pos = t['well_position'].upper()
                well_all_map.setdefault(pos, []).append(t)
                well_last_map[pos] = t

        palette = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#6366F1", "#F97316", "#06B6D4"]
        unique_cells = sorted(list({t.get('cell_info', '').strip() for t in treatments if t.get('cell_info')})) if treatments else []
        cell_color_map = {cell: palette[i % len(palette)] for i, cell in enumerate(unique_cells)}

        marker_size = 65 if total_wells <= 6 else (55 if total_wells <= 12 else (48 if total_wells <= 24 else (40 if total_wells <= 48 else 32)))
        font_size = 12 if total_wells <= 6 else (11 if total_wells <= 12 else (10 if total_wells <= 12 else (9 if total_wells <= 48 else 8)))

        fig = go.Figure()
        x_vals, y_vals, well_names, marker_colors, hover_texts, text_labels = [], [], [], [], [], []

        for r_idx, r_label in enumerate(row_labels):
            for c in range(1, cols + 1):
                pos = f"{r_label}{c}"
                x_vals.append(c)
                y_vals.append(rows - r_idx)
                well_names.append(pos)

                if pos in well_last_map:
                    item = well_last_map[pos]
                    cell_name = item.get('cell_info', '').strip() or "기타"
                    color = cell_color_map.get(cell_name, "#3B82F6") if color_by == "세포 정보별" else "#10B981"
                    
                    has_img = "📷 사진 유" if extract_image_data(item) else ""
                    cell_short = cell_name[:6] if cell_name else "미지정"
                    analysis_val = item.get('analysis_status', '미진행') or '미진행'
                    analysis_badge = "🔬" if analysis_val != "미진행" else ""
                    
                    text_labels.append(f"<b>{pos}</b><br>{cell_short}{' ' + analysis_badge if analysis_badge else ''}")
                    hover_texts.append(
                        f"<b>[Well {pos}]</b> {has_img}<br>"
                        f"🧫 <b>세포 정보:</b> {item.get('cell_info', '-')}<br>"
                        f"🌱 <b>세포 유래:</b> {get_cell_origin(item)}<br>"
                        f"🔬 <b>분석 진행:</b> {analysis_val}<br>"
                        f"🥛 <b>Basal Media:</b> {get_basal_media(item)}<br>"
                        f"🧪 <b>처리 조건:</b> {format_compound_summary(item['compound_name'], item['concentration'])}<br>"
                        f"📅 <b>일자:</b> {item['treatment_date']}"
                    )
                else:
                    color = "#FFFFFF"
                    text_labels.append(f"<span style='color:#94a3b8;'>{pos}</span>")
                    hover_texts.append(f"<b>[Well {pos}]</b><br>처리 내역 없음 (Empty)")

                marker_colors.append(color)

        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode='markers+text', customdata=well_names,
            marker=dict(size=marker_size, symbol='circle', color=marker_colors, line=dict(width=2, color='#334155')),
            text=text_labels, textposition="middle center", textfont=dict(size=font_size, color="black"),
            hoverinfo='text', hovertext=hover_texts, showlegend=False
        ))

        fig.update_layout(
            title=dict(text=f"🧫 {selected_plate['name']}", x=0.5, font=dict(size=16)),
            dragmode='select', clickmode='event+select',
            xaxis=dict(title="Column", tickmode='array', tickvals=list(range(1, cols + 1)), range=[0.3, cols + 0.7], zeroline=False, fixedrange=True),
            yaxis=dict(title="Row", tickmode='array', tickvals=[rows - i for i in range(rows)], ticktext=row_labels, range=[0.3, rows + 0.7], zeroline=False, fixedrange=True),
            plot_bgcolor='#f1f5f9', paper_bgcolor='#ffffff', height=max(420, rows * 55), margin=dict(l=20, r=20, t=40, b=20)
        )

        plotly_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode=["points", "box", "lasso"])

        if unique_cells and color_by == "세포 정보별":
            st.markdown("##### 🏷️ 세포 정보별 색상 범례")
            leg_cols = st.columns(min(len(unique_cells), 3))
            for idx, (cell_item, c_color) in enumerate(cell_color_map.items()):
                with leg_cols[idx % 3]:
                    st.markdown(
                        f"""<div style="display:flex; align-items:center; background:#f8fafc; padding:4px 8px; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:6px;">
                            <div style="width:12px; height:12px; background-color:{c_color}; border-radius:50%; margin-right:6px; border:1px solid #1e293b;"></div>
                            <span style="font-size:12px; font-weight:bold; color:#0f172a;">{cell_item}</span>
                        </div>""", unsafe_allow_html=True
                    )

    with right_col:
        edit_main_tab1, edit_main_tab2 = st.tabs(["✏️ 선택 Well 편집 & 사진 첨부", "📊 행/열 배치 요약 표"])

        with edit_main_tab1:
            all_well_positions = [f"{r}{c}" for r in row_labels for c in range(1, cols + 1)]
            dragged_wells = []
            if plotly_event and "selection" in plotly_event and plotly_event["selection"].get("points"):
                for pt in plotly_event["selection"]["points"]:
                    if "customdata" in pt:
                        val = pt["customdata"]
                        dragged_wells.append(str(val[0]) if isinstance(val, (list, tuple)) else str(val))
                    elif "point_index" in pt:
                        dragged_wells.append(well_names[pt["point_index"]])

            current_sig = ",".join(sorted(dragged_wells)) if dragged_wells else None
            if current_sig != st.session_state.get("last_dragged_signature"):
                st.session_state["last_dragged_signature"] = current_sig
                if dragged_wells: st.session_state["selected_wells_multiselect"] = dragged_wells

            selected_wells = st.multiselect("📌 대상 Well 선택", options=all_well_positions, key="selected_wells_multiselect")

            # 분석 항목 추가/삭제 관리 UI
            render_analysis_status_manager()

            if selected_wells:
                well_opt_list = get_project_plate_wells_options(selected_plate['project_id'])

                if len(selected_wells) == 1:
                    pos = selected_wells[0]
                    st.success(f"🎯 **Well [{pos}]** 가 선택되었습니다.")
                    items = well_all_map.get(pos, [])

                    with st.expander(f"➕ Well [{pos}] 신규 처리 및 사진 작성", expanded=True):
                        st.markdown("<div class='transfer-box'><b>🔄 이동/계대 배양 도우미</b>", unsafe_allow_html=True)
                        is_transfer = st.checkbox("계대 또는 다른 well/plate에서 옮겨온 세포인가요?", key=f"chk_trans_{pos}")
                        
                        ex_psg_src, ex_psg_reagent, ex_psg_seeding = "", "", ""
                        if is_transfer:
                            p_col1, p_col2, p_col3 = st.columns(3)
                            # 수정 1: 출처 세포/well을 프로젝트 플레이트 선택 드롭다운으로 제공
                            selected_src_opt = p_col1.selectbox("출처 플레이트 / Well 선택", options=well_opt_list, key=f"src_p_select_{pos}")
                            if selected_src_opt == "직접 입력 / 해당 없음":
                                ex_psg_src = p_col1.text_input("출처 세포/Well 직접 입력", value="DE_1 (A1)", key=f"src_p_input_{pos}")
                            else:
                                ex_psg_src = selected_src_opt

                            ex_psg_reagent = p_col2.text_input("해취(탈착) 물질", placeholder="예: TrypLE, EDTA", key=f"reagent_p_{pos}")
                            ex_psg_seeding = p_col3.text_input("시딩 세포수 (Seeding)", placeholder="예: 1x10^5 cells/well", key=f"seed_p_{pos}")
                        st.markdown("</div>", unsafe_allow_html=True)

                        c1, c2, c3 = st.columns(3)
                        ex_d = c1.date_input("처리 일자", datetime.date.today(), key=f"ex_d_{pos}")
                        ex_cell = c2.text_input("세포 정보 (세포군)*", value="DE_1_P1" if is_transfer else "DE_1", key=f"ex_cell_{pos}")
                        ex_origin = c3.text_input("🌱 세포 유래/출처", placeholder="예: iPSC-derived", key=f"ex_origin_{pos}")

                        c4, c5 = st.columns(2)
                        ex_analysis = c4.selectbox("🔬 분석진행 상태", options=st.session_state.analysis_options, key=f"ex_analysis_{pos}")
                        if ex_analysis == "미진행":
                            ex_basal = c5.selectbox("Basal Media", options=get_recipe_options(), key=f"ex_basal_{pos}")
                            ex_comp_str, ex_conc_str = render_compound_inputs(f"ex_{pos}")
                        else:
                            ex_basal = "-"
                            ex_comp_str, ex_conc_str = f"분석 진행 ({ex_analysis})", ""

                        ex_note = st.text_area("📝 연구노트 (실험 세부 과정 및 조건)", placeholder="진행된 실험 과정, 시약 분량 등 상세 기록", height=100, key=f"ex_note_{pos}")
                        ex_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"ex_file_{pos}")

                        if st.button(f"💾 Well [{pos}] 처리 저장", key=f"btn_ex_save_{pos}", use_container_width=True, type="primary"):
                            if ex_analysis != "미진행" or ex_comp_str.strip():
                                comb_note = build_combined_note(ex_basal, ex_origin, ex_psg_src, ex_psg_reagent, ex_psg_seeding, ex_note, file_to_base64(ex_file))
                                db.add_treatment(selected_plate['id'], pos, str(ex_d), ex_comp_str, ex_conc_str, ex_cell.strip(), comb_note, ex_analysis)
                                st.toast(f"Well [{pos}] 처리가 저장되었습니다!", icon="✅")
                                st.rerun()
                            else:
                                st.error("처리 물질명을 입력해 주세요.")

                    if items:
                        st.markdown("---")
                        st.markdown(f"##### 📜 Well [{pos}] 이전 처리 이력 ({len(items)}건)")
                        for item in items:
                            formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                            with st.expander(f"📅 {item['treatment_date']} | 🧬 {item.get('cell_info', '-')} | 🧪 {formatted_cond}"):
                                try: def_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                                except: def_d = datetime.date.today()

                                b_media_val, b_origin_val, psg_src_v, psg_reagent_v, psg_seeding_v, pure_note_val, cur_img_b64 = parse_note_basal_image(item)

                                m_col1, m_col2, m_col3 = st.columns(3)
                                mod_d = m_col1.date_input("처리 일자", value=def_d, key=f"s_date_{item['id']}")
                                mod_pos = m_col2.text_input("웰 위치", value=item['well_position'], key=f"s_pos_{item['id']}")
                                mod_cell = m_col3.text_input("세포 정보", value=item.get('cell_info', ''), key=f"s_cell_{item['id']}")

                                m_col4, m_col5, m_col6 = st.columns(3)
                                mod_origin = m_col4.text_input("🌱 시작 세포 유래", value=b_origin_val, key=f"s_origin_{item['id']}")
                                
                                # 수정 1: 이력 수정 시 출처 세포/well 선택 드롭다운 적용
                                cur_opts = get_project_plate_wells_options(selected_plate['project_id'], psg_src_v)
                                selected_mod_src = m_col5.selectbox("계대 출처 선택", options=cur_opts, index=cur_opts.index(psg_src_v) if psg_src_v in cur_opts else 0, key=f"s_psg_src_select_{item['id']}")
                                mod_psg_src = m_col5.text_input("계대 출처 직접 입력", value=selected_mod_src if selected_mod_src != "직접 입력 / 해당 없음" else psg_src_v, key=f"s_psg_src_{item['id']}")
                                
                                mod_psg_reagent = m_col6.text_input("해취 물질", value=psg_reagent_v, key=f"s_psg_reagent_{item['id']}")

                                m_col7, m_col8 = st.columns(2)
                                mod_psg_seeding = m_col7.text_input("시딩 세포수", value=psg_seeding_v, key=f"s_psg_seeding_{item['id']}")
                                cur_a = item.get('analysis_status', '미진행')
                                analysis_opts = st.session_state.analysis_options
                                mod_analysis = m_col8.selectbox("🔬 분석진행 상태", options=analysis_opts, index=analysis_opts.index(cur_a) if cur_a in analysis_opts else 0, key=f"s_analysis_{item['id']}")
                                
                                if mod_analysis == "미진행":
                                    b_opts = get_recipe_options(b_media_val)
                                    mod_basal = st.selectbox("Basal Media", options=b_opts, index=b_opts.index(b_media_val) if b_media_val in b_opts else 0, key=f"s_basal_{item['id']}")
                                    e_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                                    e_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                                    mod_comp, mod_conc = render_compound_inputs(f"s_{item['id']}", e_comps, e_concs)
                                else:
                                    mod_basal, mod_comp, mod_conc = "-", f"분석 진행 ({mod_analysis})", ""

                                mod_note = st.text_area("📝 연구노트", value=pure_note_val, height=90, key=f"s_note_{item['id']}")
                                del_img = st.checkbox("🗑️ 저장된 사진 삭제", key=f"chk_del_img_{item['id']}") if cur_img_b64 else False
                                new_img_file = st.file_uploader("새 현미경 사진 첨부/교체", type=["png", "jpg", "jpeg"], key=f"file_s_{item['id']}")

                                b_save, b_del = st.columns(2)
                                if b_save.button("💾 저장", key=f"btn_s_save_{item['id']}", type="primary", use_container_width=True):
                                    final_img = None if del_img else (file_to_base64(new_img_file) if new_img_file else cur_img_b64)
                                    comb_note = build_combined_note(mod_basal, mod_origin, mod_psg_src, mod_psg_reagent, mod_psg_seeding, mod_note, final_img)
                                    db.update_treatment(item['id'], mod_pos.strip().upper(), str(mod_d), mod_comp.strip(), mod_conc.strip(), mod_cell.strip(), comb_note, mod_analysis)
                                    st.toast("수정 사항이 저장되었습니다!", icon="✅")
                                    st.rerun()

                                if b_del.button("🗑️ 삭제", key=f"btn_s_del_{item['id']}", type="secondary", use_container_width=True):
                                    db.delete_treatment(item['id'])
                                    st.toast("삭제되었습니다.", icon="🗑️")
                                    st.rerun()
                else:
                    st.success(f"🎯 총 **{len(selected_wells)}개** Well 선택됨")
                    
                    st.markdown("<div class='transfer-box'><b>🔄 선택한 계대 배양 일괄 작성</b>", unsafe_allow_html=True)
                    batch_trans = st.checkbox("계대 또는 이동이 진행된 샘플인가요?", key="batch_trans")
                    b_psg_src, b_psg_reagent, b_psg_seeding = "", "", ""
                    if batch_trans:
                        bp_col1, bp_col2, bp_col3 = st.columns(3)
                        selected_b_src = bp_col1.selectbox("출처 선택", options=well_opt_list, key="batch_src_select")
                        if selected_b_src == "직접 입력 / 해당 없음":
                            b_psg_src = bp_col1.text_input("출처 세포/Well 직접 입력", value="DE_1", key="batch_src_input")
                        else:
                            b_psg_src = selected_b_src

                        b_psg_reagent = bp_col2.text_input("해취 물질", placeholder="예: TrypLE", key="batch_reagent")
                        b_psg_seeding = bp_col3.text_input("시딩 세포수", placeholder="예: 1x10^5 cells/well", key="batch_seeding")
                    st.markdown("</div>", unsafe_allow_html=True)

                    bc1, bc2, bc3 = st.columns(3)
                    b_date = bc1.date_input("일괄 처리 일자", datetime.date.today(), key="batch_date")
                    b_cell = bc2.text_input("세포 정보*", value="DE_1_P1" if batch_trans else "DE_1", key="batch_cell")
                    b_origin = bc3.text_input("🌱 세포 유래", placeholder="예: iPSC", key="batch_origin")

                    bc4, bc5 = st.columns(2)
                    b_analysis = bc4.selectbox("🔬 분석진행 상태", options=st.session_state.analysis_options, key="batch_analysis")
                    if b_analysis == "미진행":
                        b_basal = bc5.selectbox("Basal Media", options=get_recipe_options(), key="batch_basal")
                        b_comp_str, b_conc_str = render_compound_inputs("batch")
                    else:
                        b_basal, b_comp_str, b_conc_str = "-", f"분석 진행 ({b_analysis})", ""

                    b_note = st.text_area("📝 연구노트 (일괄 적용 내용)", height=80, key="batch_note")
                    b_file = st.file_uploader("📷 현미경 사진 첨부", type=["png", "jpg", "jpeg"], key="batch_file")

                    if st.button(f"💾 선택한 {len(selected_wells)}개 Well에 일괄 저장", key="btn_batch_save", use_container_width=True, type="primary"):
                        if b_comp_str.strip():
                            comb_note = build_combined_note(b_basal, b_origin, b_psg_src, b_psg_reagent, b_psg_seeding, b_note, file_to_base64(b_file))
                            for w in selected_wells:
                                db.add_treatment(selected_plate['id'], w, str(b_date), b_comp_str, b_conc_str, b_cell.strip(), comb_note, b_analysis)
                            st.success(f"✅ {len(selected_wells)}개 Well 일괄 저장 완료!")
                            st.rerun()
                        else:
                            st.error("처리 물질명을 입력해 주세요.")
            else:
                st.info("💡 왼쪽 차트에서 Well을 클릭하거나 드래그(Box/Lasso)하세요.")

        with edit_main_tab2:
            def build_summary(is_row=True):
                summary = []
                targets = row_labels if is_row else list(range(1, cols + 1))
                for target in targets:
                    t_list = [well_last_map[p] for p in well_last_map if (p.startswith(target) if is_row else p[1:] == str(target))]
                    if t_list:
                        basal_str = ", ".join(sorted(list({get_basal_media(t) for t in t_list if get_basal_media(t) != "-"}))) or "-"
                        cond_str = " / ".join(sorted(list({format_compound_summary(t['compound_name'], t['concentration']) for t in t_list})))
                        cell_str = ", ".join(sorted(list({t['cell_info'] for t in t_list if t.get('cell_info')}))) or "-"
                        analysis_str = ", ".join(sorted(list({t.get('analysis_status', '미진행') for t in t_list})))
                        count = len(t_list)
                    else:
                        basal_str, cond_str, cell_str, analysis_str, count = "-", "미처리 (Empty)", "-", "-", 0
                    
                    label_title = "행" if is_row else "열"
                    limit = cols if is_row else rows
                    summary.append({
                        label_title: f"{'Row' if is_row else 'Col'} {target}", "처리 수": f"{count}/{limit}",
                        "Basal Media": basal_str, "세포 정보": cell_str, "분석진행": analysis_str, "실험 조건": cond_str
                    })
                return summary

            sub_t1, sub_t2 = st.tabs(["📌 Row (행) 기준 요약", "📌 Column (열) 기준 요약"])
            sub_t1.dataframe(pd.DataFrame(build_summary(True)), use_container_width=True, hide_index=True)
            sub_t2.dataframe(pd.DataFrame(build_summary(False)), use_container_width=True, hide_index=True)

# ======================================================================
# 계통도 탭 Render 함수
# ======================================================================
def render_tab_tree(selected_project):
    st.markdown(f"### 🌳 프로젝트 [{selected_project['name']}] 세포군 계통도")
    st.caption("💡 동일 프로젝트 내 **모든 Well Plate**의 세포 처리 내역을 날짜순으로 추적하여 **세포군(Cell Line)** 단위 계통도로 시각화합니다.")
    
    dot_code, root_cells = generate_project_cell_lineage_dot(selected_project['id'])
    
    if root_cells:
        roots_display = ", ".join([f"**`{rc}`**" for rc in root_cells])
        st.markdown(
            f"""<div class='root-cell-box'>
                🌱 <b>이 프로젝트의 시작(기원) 세포군:</b> {roots_display}
                <br><small style='color:#71717a;'>※ 다른 세포로부터 유래되거나 파생되지 않은 최초의 원천 세포군입니다.</small>
            </div>""", unsafe_allow_html=True
        )

    if dot_code:
        st.graphviz_chart(dot_code, use_container_width=True)
    else:
        st.info("💡 통합 계통도를 생성할 세포 정보(세포군 명칭) 데이터가 없습니다.")

# ======================================================================
# 날짜별 관리 탭 Render 함수
# ======================================================================
def render_tab_management(selected_plate, treatments):
    well_opt_list = get_project_plate_wells_options(selected_plate['project_id'])

    col_top1, col_top2, col_top3 = st.columns(3)
    t_date = col_top1.date_input("처리 일자 (Date)", datetime.date.today(), key="t_date_main")
    t_well = col_top2.text_input("웰 위치 (Well Position)*", placeholder="예: A1, B2 또는 A1,A2", key="t_well_main")
    t_analysis = col_top3.selectbox("🔬 분석진행 상태", options=st.session_state.analysis_options, key="t_analysis_main")

    st.markdown("<div class='transfer-box'><b>🔄 계대 배양 및 연결 정보</b></div>", unsafe_allow_html=True)
    
    col_cell1, col_cell2, col_cell3 = st.columns(3)
    t_cell = col_cell1.text_input("세포/오가노이드 정보*", value="DE_1", placeholder="예: DE_1, DE_1_P1", key="t_cell_main")
    t_origin = col_cell2.text_input("🌱 세포 유래 (선택)", placeholder="예: iPSC", key="t_origin_main")
    
    selected_main_src = col_cell3.selectbox("계대 출처 Plate/Well 선택", options=well_opt_list, key="t_psg_src_select_main")
    if selected_main_src == "직접 입력 / 해당 없음":
        t_psg_src = col_cell3.text_input("계대 출처 직접 입력", placeholder="예: Plate1-A1", key="t_psg_src_input_main")
    else:
        t_psg_src = selected_main_src

    col_cell4, col_cell5 = st.columns(2)
    t_psg_reagent = col_cell4.text_input("해취 물질", placeholder="예: TrypLE", key="t_psg_reagent_main")
    t_psg_seeding = col_cell5.text_input("시딩 세포수", placeholder="예: 1x10^5 cells/well", key="t_psg_seeding_main")

    if t_analysis == "미진행":
        t_basal = st.selectbox("Basal Media (레시피 선택)", options=get_recipe_options(), key="t_basal_main")
        t_comp_str, t_conc_str = render_compound_inputs("t_main")
    else:
        t_basal, t_comp_str, t_conc_str = "-", f"분석 진행 ({t_analysis})", ""
        st.info(f"🔬 **{t_analysis}** 분석 모드입니다.")

    t_note = st.text_area("📝 연구노트 (상세 실험 과정)", placeholder="실험 세부 내용 작성...", height=100, key="t_note_main")
    t_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key="t_file_upload_main")

    if st.button("처리 내역 및 사진 저장", use_container_width=True, type="primary", key="btn_t_main_save"):
        if t_well.strip() and t_comp_str.strip():
            wells = [w.strip().upper() for w in t_well.split(",") if w.strip()]
            comb_note = build_combined_note(t_basal, t_origin, t_psg_src, t_psg_reagent, t_psg_seeding, t_note, file_to_base64(t_file))
            for w in wells:
                db.add_treatment(selected_plate['id'], w, str(t_date), t_comp_str, t_conc_str, t_cell.strip(), comb_note, t_analysis)
            st.success(f"{len(wells)}개 웰({', '.join(wells)})에 기록 완료!")
            st.rerun()
        else:
            st.error("웰 위치와 최소 하나 이상의 물질명을 입력해 주세요.")

    st.markdown("---")
    st.subheader("📋 전체 물질 처리 이력 관리")
    if treatments:
        records = []
        for item in treatments:
            b_media, b_origin, psg_src, psg_reagent, psg_seeding, pure_note, img_b64 = parse_note_basal_image(item)
            records.append({
                "ID": item['id'],
                "선택": False,
                "웰 위치": item['well_position'],
                "일자": item['treatment_date'],
                "세포 정보": item.get('cell_info', ''),
                "세포 유래": b_origin,
                "계대 출처": psg_src,
                "해취 물질": psg_reagent,
                "시딩 수": psg_seeding,
                "분석 상태": item.get('analysis_status', '미진행'),
                "Basal Media": b_media,
                "처리 물질": item.get('compound_name', ''),
                "농도": item.get('concentration', ''),
                "연구노트": pure_note,
                "사진 유무": "📷 유" if img_b64 else "무"
            })
        
        df_treatments = pd.DataFrame(records)

        st.caption("💡 표 좌측 체크박스를 선택하여 여러 처리 내역을 **일괄 삭제**하거나 **일괄 수정**할 수 있습니다.")
        edited_df = st.data_editor(
            df_treatments,
            key="treatment_multiselect_editor",
            column_config={
                "ID": None,
                "선택": st.column_config.CheckboxColumn("선택", help="일괄 수정/삭제할 항목 선택"),
            },
            disabled=["ID", "사진 유무"],
            hide_index=True,
            use_container_width=True
        )

        selected_rows = edited_df[edited_df["선택"] == True]
        selected_count = len(selected_rows)

        if selected_count > 0:
            st.info(f"🎯 총 **{selected_count}개** 항목이 선택되었습니다.")
            m_col1, m_col2 = st.columns(2)

            with m_col1:
                if st.button(f"🗑️ 선택한 {selected_count}개 항목 일괄 삭제", type="secondary", use_container_width=True):
                    for _, row in selected_rows.iterrows():
                        db.delete_treatment(row["ID"])
                    st.toast(f"{selected_count}개 항목이 삭제되었습니다.", icon="🗑️")
                    st.rerun()

            with m_col2:
                with st.popover(f"✏️ 선택한 {selected_count}개 항목 일괄 수정", use_container_width=True):
                    st.markdown("##### 선택된 항목에 아래 입력한 값만 공통 적용합니다.")
                    
                    b_col1, b_col2, b_col3 = st.columns(3)
                    mod_d = b_col1.date_input("변경할 일자", value=None, key="m_batch_d")
                    mod_cell = b_col2.text_input("변경할 세포 정보", placeholder="예: DE_1_P2", key="m_batch_cell")
                    mod_origin = b_col3.text_input("변경할 세포 유래", placeholder="예: iPSC", key="m_batch_origin")

                    b_col4, b_col5, b_col6 = st.columns(3)
                    mod_psg_src = b_col4.selectbox("계대 출처 변경", options=["(변경 안 함)"] + well_opt_list, key="m_batch_psg_src")
                    mod_psg_reagent = b_col5.text_input("해취 물질", key="m_batch_psg_reagent")
                    mod_psg_seeding = b_col6.text_input("시딩 수", key="m_batch_psg_seeding")

                    b_col7, b_col8 = st.columns(2)
                    mod_analysis = b_col7.selectbox("분석 상태", options=["(변경 안 함)"] + st.session_state.analysis_options, key="m_batch_analysis")
                    mod_comp = b_col8.text_input("변경할 물질명", placeholder="예: VEGF", key="m_batch_comp")

                    if st.button("💾 일괄 수정 사항 적용", type="primary", use_container_width=True):
                        for _, row in selected_rows.iterrows():
                            item_id = row["ID"]
                            orig_item = next(t for t in treatments if t['id'] == item_id)
                            b_media_val, b_origin_val, psg_src_v, psg_reagent_v, psg_seeding_v, pure_note_val, cur_img_b64 = parse_note_basal_image(orig_item)

                            final_d = str(mod_d) if mod_d else orig_item['treatment_date']
                            final_cell = mod_cell.strip() if mod_cell.strip() else orig_item.get('cell_info', '')
                            final_origin = mod_origin.strip() if mod_origin.strip() else b_origin_val
                            final_psg_src = mod_psg_src if (mod_psg_src and mod_psg_src != "(변경 안 함)") else psg_src_v
                            final_psg_reagent = mod_psg_reagent.strip() if mod_psg_reagent.strip() else psg_reagent_v
                            final_psg_seeding = mod_psg_seeding.strip() if mod_psg_seeding.strip() else psg_seeding_v
                            final_analysis = mod_analysis if mod_analysis != "(변경 안 함)" else orig_item.get('analysis_status', '미진행')
                            final_comp = mod_comp.strip() if mod_comp.strip() else orig_item.get('compound_name', '')

                            comb_note = build_combined_note(b_media_val, final_origin, final_psg_src, final_psg_reagent, final_psg_seeding, pure_note_val, cur_img_b64)
                            db.update_treatment(item_id, orig_item['well_position'], final_d, final_comp, orig_item.get('concentration', ''), final_cell, comb_note, final_analysis)
                        st.toast(f"{selected_count}개 항목이 성공적으로 수정되었습니다!", icon="✅")
                        st.rerun()

        st.markdown("---")
        st.markdown("##### 🔍 개별 세부 수정 및 현미경 사진 교체")
        list_cols = st.columns(2)
        for idx, item in enumerate(treatments):
            with list_cols[idx % 2]:
                b_media_val, b_origin_val, psg_src_v, psg_reagent_v, psg_seeding_v, pure_note_val, cur_img_b64 = parse_note_basal_image(item)
                img_flag = "📷 " if cur_img_b64 else ""
                formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                analysis_lbl = item.get('analysis_status', '미진행')
                
                with st.expander(f"{img_flag}📍 Well [{item['well_position']}] | 📅 {item['treatment_date']} | 🧬 {item.get('cell_info', '-')} ({analysis_lbl}) | 🧪 {formatted_cond}"):
                    try: default_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                    except: default_d = datetime.date.today()

                    e_c1, e_c2, e_c3 = st.columns(3)
                    e_date = e_c1.date_input("처리 일자", value=default_d, key=f"t_e_date_{item['id']}")
                    e_pos = e_c2.text_input("웰 위치", value=item['well_position'], key=f"t_e_pos_{item['id']}")
                    e_cell = e_c3.text_input("세포 정보", value=item.get('cell_info', ''), key=f"t_e_cell_{item['id']}")

                    e_c4, e_c5, e_c6 = st.columns(3)
                    e_origin = e_c4.text_input("🌱 세포 유래", value=b_origin_val, key=f"t_e_origin_{item['id']}")
                    
                    e_opts = get_project_plate_wells_options(selected_plate['project_id'], psg_src_v)
                    sel_e_src = e_c5.selectbox("계대 출처 선택", options=e_opts, index=e_opts.index(psg_src_v) if psg_src_v in e_opts else 0, key=f"t_e_psg_src_select_{item['id']}")
                    e_psg_src = e_c5.text_input("계대 출처 직접 입력", value=sel_e_src if sel_e_src != "직접 입력 / 해당 없음" else psg_src_v, key=f"t_e_psg_src_{item['id']}")
                    
                    e_psg_reagent = e_c6.text_input("해취 물질", value=psg_reagent_v, key=f"t_e_psg_reagent_{item['id']}")

                    e_c7, e_c8 = st.columns(2)
                    e_psg_seeding = e_c7.text_input("시딩 세포수", value=psg_seeding_v, key=f"t_e_psg_seeding_{item['id']}")
                    e_cur_a = item.get('analysis_status', '미진행')
                    analysis_opts = st.session_state.analysis_options
                    e_analysis = e_c8.selectbox("🔬 분석진행 상태", options=analysis_opts, index=analysis_opts.index(e_cur_a) if e_cur_a in analysis_opts else 0, key=f"t_e_analysis_{item['id']}")
                    
                    if e_analysis == "미진행":
                        e_b_opts = get_recipe_options(b_media_val)
                        e_basal = st.selectbox("Basal Media", options=e_b_opts, index=e_b_opts.index(b_media_val) if b_media_val in e_b_opts else 0, key=f"t_e_basal_{item['id']}")
                        e_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                        e_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                        e_comp, e_conc = render_compound_inputs(f"t_e_{item['id']}", e_comps, e_concs)
                    else:
                        e_basal, e_comp, e_conc = "-", f"분석 진행 ({e_analysis})", ""

                    e_note = st.text_area("📝 연구노트", value=pure_note_val, height=80, key=f"t_e_note_{item['id']}")
                    del_img = st.checkbox("사진 삭제", key=f"chk_del_t_{item['id']}") if cur_img_b64 else False
                    new_img = st.file_uploader("사진 교체/추가", type=["png", "jpg", "jpeg"], key=f"f_e_{item['id']}")

                    b_c1, b_c2 = st.columns(2)
                    if b_c1.button("💾 저장", key=f"btn_t_update_{item['id']}", use_container_width=True):
                        final_img = None if del_img else (file_to_base64(new_img) if new_img else cur_img_b64)
                        comb_note = build_combined_note(e_basal, e_origin, e_psg_src, e_psg_reagent, e_psg_seeding, e_note, final_img)
                        db.update_treatment(item['id'], e_pos.strip().upper(), str(e_date), e_comp.strip(), e_conc.strip(), e_cell.strip(), comb_note, e_analysis)
                        st.toast("수정되었습니다!", icon="✅")
                        st.rerun()

                    if b_c2.button("🗑️ 삭제", key=f"btn_t_del_{item['id']}", type="secondary", use_container_width=True):
                        db.delete_treatment(item['id'])
                        st.toast("삭제되었습니다.", icon="🗑️")
                        st.rerun()
    else:
        st.caption("아직 처리된 내역이 없습니다.")

# ======================================================================
# 4. 메인 실행 흐름
# ======================================================================
db.init_db()
st.title("🧫 시각화 및 세포 오가노이드 처리 관리")

projects = db.get_projects()
if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다. 먼저 **'프로젝트 관리'** 메뉴에서 프로젝트를 생성해 주세요.")
else:
    proj_map = {f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID: {p['id']})": p for p in projects}
    options = list(proj_map.keys())

    if "selected_plate_proj_label" not in st.session_state or st.session_state.selected_plate_proj_label not in options:
        st.session_state.selected_plate_proj_label = options[0]

    # --- 사이드바 ---
    with st.sidebar:
        st.markdown("### 🗂️ 프로젝트 및 플레이트 관리")
        selected_label = st.selectbox("📌 프로젝트 선택", options=options, key="selected_plate_proj_label")
        selected_proj = proj_map[selected_label]

        st.markdown(
            f"""
            <div style="padding:10px 14px; border-left: 6px solid {selected_proj['color_code']}; background-color: #f8fafc; border-radius: 6px; margin-top: 4px; margin-bottom: 15px;">
                <p style="margin:0; color:#0f172a; font-weight:bold; font-size:14px;">{selected_proj['name']}</p>
                <p style="margin:2px 0 0 0; color:#475569; font-size:12px;"><b>그룹:</b> {selected_proj['group_name']} | <b>설명:</b> {selected_proj['description'] or '없음'}</p>
            </div>
            """, unsafe_allow_html=True
        )

        plates = db.get_plates(selected_proj['id'])
        if plates:
            plate_dict = {f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)": pl for pl in plates}
            if "selected_plate_select" not in st.session_state or st.session_state.selected_plate_select not in plate_dict:
                st.session_state.selected_plate_select = list(plate_dict.keys())[0]

            selected_plate_name = st.selectbox("🧫 작업 대상 플레이트 선택", list(plate_dict.keys()), key="selected_plate_select")
            selected_plate = plate_dict[selected_plate_name]
            
            if st.button("🗑️ 선택 플레이트 삭제", type="secondary", use_container_width=True, key="btn_del_plate_top"):
                db.delete_plate(selected_plate['id'])
                st.toast("플레이트가 삭제되었습니다.", icon="🗑️")
                st.rerun()
        else:
            st.info("💡 선택된 프로젝트에 등록된 플레이트가 없습니다.")
            selected_plate = None

        st.markdown("---")
        with st.expander("➕ 새 규격 플레이트 생성", expanded=not bool(plates)):
            with st.form("add_plate_form", clear_on_submit=True):
                plate_name = st.text_input("플레이트 이름*", placeholder="예: 96-Well Plate #1")
                selected_preset = st.selectbox("🧫 플레이트 표준 규격 선택*", list(PLATE_PRESETS.keys()))

                if PLATE_PRESETS[selected_preset] == "custom":
                    p_rows = st.number_input("행 개수 (Rows)", min_value=1, max_value=16, value=8)
                    p_cols = st.number_input("열 개수 (Cols)", min_value=1, max_value=24, value=12)
                else:
                    p_rows, p_cols = PLATE_PRESETS[selected_preset]
                    st.caption(f"💡 선택된 규격: **{p_rows} 행 x {p_cols} 열**")

                if st.form_submit_button("플레이트 추가", use_container_width=True):
                    if plate_name.strip():
                        db.add_plate(selected_proj['id'], plate_name.strip(), p_rows, p_cols)
                        st.success(f"'{plate_name}' 플레이트 생성 완료!")
                        st.rerun()
                    else:
                        st.error("플레이트 이름을 입력해 주세요.")

         
    # --- 메인 탭 영역 ---
    if selected_plate:
        treatments = db.get_treatments_by_plate(selected_plate['id'])
        
        tab_overview, tab_view, tab_tree, tab_treat = st.tabs([
            "📋 전체 플레이트 개요 (Overview)",
            "🔴 Well Plate 시각화 & 편집", 
            "🌳 프로젝트 통합 세포 계통도", 
            "📝 날짜별 물질/세포 처리 입력 및 전체 관리"
        ])

        with tab_overview:
            render_tab_overview()
        with tab_view:
            render_tab_visualization(selected_plate, treatments)
        with tab_tree:
            render_tab_tree(selected_proj)
        with tab_treat:
            render_tab_management(selected_plate, treatments)
