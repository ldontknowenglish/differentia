import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import base64
import db
import style

# --- 1. 페이지 설정 및 디자인 서식 적용 ---
st.set_page_config(page_title="연구 프로젝트 관리", page_icon="🧪", layout="wide")

st.markdown("""
    <style>
        .main .block-container {
            padding-left: 1.5rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
            margin-left: 0 !important;
        }
    </style>
""", unsafe_allow_html=True)

if hasattr(style, "apply_custom_style"):
    style.apply_custom_style()

st.title("🧫 시각화 및 세포 오가노이드 처리 관리")

# ======================================================================
# [이미지 및 데이터 파싱 헬퍼 함수]
# ======================================================================
def file_to_base64(uploaded_file):
    if uploaded_file is None:
        return None
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode('utf-8')

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

def parse_note_basal_image(item):
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

def build_combined_note(basal, pure_note, img_b64, parent_info=""):
    parts = []
    if parent_info and parent_info.strip():
        parts.append(f"[Parent: {parent_info.strip()}]")
    if basal and basal.strip() and basal.strip() != "-":
        parts.append(f"[Media: {basal.strip()}]")
    if pure_note and pure_note.strip():
        parts.append(pure_note.strip())
    if img_b64 and img_b64.strip():
        parts.append(f"[IMG_DATA: {img_b64.strip()}]")
    return " ".join(parts)

def display_image_from_b64(b64_str, caption="", width=None):
    if not b64_str:
        return
    try:
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=True if width is None else False, width=width)
    except Exception:
        st.caption("⚠️ 이미지를 로드할 수 없습니다.")

def get_basal_media(item):
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

def format_compound_summary(comp_str, conc_str):
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

# ======================================================================
# [3. 프로젝트 전체 플레이트 간 세포 계통도 생성 함수 (사이드바 및 왼쪽 배치)]
# ======================================================================
def generate_project_wide_lineage_dot(project_id):
    """시작 세포(Seed)와 프로젝트 내 전체 플레이트간 세포 계통 트리 생성"""
    plates = db.get_plates(project_id)
    if not plates:
        return None

    # session_state 내 저장된 시작 세포 가져오기
    seed_cells = st.session_state.get(f"seed_cells_{project_id}", ["iPSC", "Stem Cell"])

    dot_lines = [
        "digraph ProjectLineageTree {",
        "    rankdir=LR;",
        "    graph [nodesep=0.35, ranksep=0.7, margin=0, pad=0.1];",
        "    node [shape=box, style=\"filled,rounded\", fillcolor=\"#f8fafc\", color=\"#3b82f6\", fontname=\"Malgun Gothic, sans-serif\", fontsize=9];",
        "    edge [color=\"#64748b\", arrowhead=normal, arrowsize=0.6, penwidth=1.2, fontname=\"Malgun Gothic, sans-serif\", fontsize=8];"
    ]

    nodes = set()
    edges = set()

    # 1. Root 시작 세포 노드 추가
    for seed in seed_cells:
        clean_seed = seed.replace('"', '\\"')
        dot_lines.append(f'    "{clean_seed}" [label="🌱 {clean_seed}", fillcolor="#dcfce7", color="#16a34a"];')
        nodes.add(seed)

    # 2. 플레이트별 세포 변이 및 계대 연결 추적
    all_treatments = []
    plate_map = {p['id']: p['name'] for p in plates}

    for pl in plates:
        tr_list = db.get_treatments_by_plate(pl['id'])
        for t in tr_list:
            t['plate_name'] = pl['name']
            all_treatments.append(t)

    if not all_treatments:
        if nodes:
            dot_lines.append("}")
            return "\n".join(dot_lines)
        return None

    df = pd.DataFrame(all_treatments)
    if 'cell_info' not in df.columns:
        return None

    df = df[df['cell_info'].notnull() & (df['cell_info'].str.strip() != "")]
    if df.empty:
        return None

    df = df.sort_values(by=['plate_name', 'well_position', 'treatment_date'])

    for (pl_name, well), group in df.groupby(['plate_name', 'well_position']):
        cell_history = []
        for _, row in group.iterrows():
            c_info = str(row['cell_info']).strip()
            t_date = str(row['treatment_date']).strip()
            if c_info:
                if not cell_history or cell_history[-1][0] != c_info:
                    cell_history.append((c_info, t_date, pl_name, well))

        for c_info, _, p_n, w_p in cell_history:
            node_id = f"{p_n}:{w_p} ({c_info})"
            nodes.add(node_id)
            clean_node = node_id.replace('"', '\\"')
            dot_lines.append(f'    "{clean_node}" [label="[{p_n}] {w_p}\\n🧬 {c_info}"];')

            # 시작 세포와 최초 노드 연결
            for seed in seed_cells:
                if seed.lower() in c_info.lower() or c_info.lower() in seed.lower():
                    edges.add((seed, node_id, "Init"))

        for i in range(len(cell_history) - 1):
            src_info, _, src_p, src_w = cell_history[i]
            dst_info, dst_date, dst_p, dst_w = cell_history[i + 1]
            src_id = f"{src_p}:{src_w} ({src_info})"
            dst_id = f"{dst_p}:{dst_w} ({dst_info})"
            if src_id != dst_id:
                edges.add((src_id, dst_id, dst_date))

    for src, dst, label in edges:
        clean_src = src.replace('"', '\\"')
        clean_dst = dst.replace('"', '\\"')
        clean_lbl = label.replace('"', '\\"')
        dot_lines.append(f'    "{clean_src}" -> "{clean_dst}" [label=" {clean_lbl} "];')

    dot_lines.append("}")
    return "\n".join(dot_lines)


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
    "384-Well Plate (16 x 24)": (16, 24),
    "⚙️ 사용자 지정 (Custom)": "custom"
}

db.init_db()
projects = db.get_projects()

if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다. 먼저 프로젝트를 생성해 주세요.")
else:
    proj_map = {f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID: {p['id']})": p for p in projects}
    options = list(proj_map.keys())

    if "selected_plate_proj_label" not in st.session_state or st.session_state.selected_plate_proj_label not in options:
        st.session_state.selected_plate_proj_label = options[0]

    # ======================================================================
    # [사이드바: 프로젝트/플레이트 관리 + 계통도 시각화]
    # ======================================================================
    with st.sidebar:
        st.markdown("### 🗂️ 프로젝트 및 플레이트 관리")
        
        selected_label = st.selectbox("📌 프로젝트 선택", options=options, key="selected_plate_proj_label")
        selected_proj = proj_map[selected_label]

        st.markdown(
            f"""
            <div style="padding:10px 14px; border-left: 6px solid {selected_proj['color_code']}; background-color: #f8fafc; border-radius: 6px; margin-top: 4px; margin-bottom: 15px;">
                <p style="margin:0; color:#0f172a; font-weight:bold; font-size:14px;">{selected_proj['name']}</p>
                <p style="margin:2px 0 0 0; color:#475569; font-size:12px;"><b>그룹:</b> {selected_proj['group_name']} | <b>설명:</b> {selected_proj['description'] if selected_proj['description'] else '없음'}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        plates = db.get_plates(selected_proj['id'])

        if plates:
            plate_dict = {f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)": pl for pl in plates}
            selected_plate_name = st.selectbox("🧫 작업 대상 플레이트 선택", list(plate_dict.keys()), key="selected_plate_select")
            selected_plate = plate_dict[selected_plate_name]
            
            if st.button("🗑️ 선택 플레이트 삭제", type="secondary", use_container_width=True, key="btn_del_plate_top"):
                db.delete_plate(selected_plate['id'])
                st.toast("플레이트가 삭제되었습니다.", icon="🗑️")
                st.rerun()
        else:
            st.info("💡 등록된 플레이트가 없습니다. 아래에서 규격을 커스텀하여 추가해 주세요.")
            selected_plate = None

        st.markdown("---")
        
        # 2. 플레이트 규격 커스텀 및 생성
        with st.expander("➕ 플레이트 규격 생성/커스텀", expanded=not bool(plates)):
            with st.form("add_plate_form", clear_on_submit=True):
                plate_name = st.text_input("플레이트 이름*", placeholder="예: Passage #2 (24-Well)")
                selected_preset_label = st.selectbox("🧫 플레이트 규격 선택*", list(PLATE_PRESETS.keys()))

                if PLATE_PRESETS[selected_preset_label] == "custom":
                    st.caption("⚙️ **커스텀 플레이트 규격 설정**")
                    p_rows = st.number_input("행 개수 (Rows)", min_value=1, max_value=24, value=8)
                    p_cols = st.number_input("열 개수 (Cols)", min_value=1, max_value=48, value=12)
                else:
                    p_rows, p_cols = PLATE_PRESETS[selected_preset_label]
                    st.caption(f"💡 선택된 규격: **{p_rows} 행 x {p_cols} 열**")

                p_submit = st.form_submit_button("플레이트 추가", use_container_width=True)
                if p_submit:
                    if plate_name.strip():
                        db.add_plate(selected_proj['id'], plate_name.strip(), p_rows, p_cols)
                        st.success(f"'{plate_name}' 플레이트 ({p_rows}x{p_cols}) 생성 완료!")
                        st.rerun()
                    else:
                        st.error("플레이트 이름을 입력해 주세요.")

        st.markdown("---")

        # 3. 사이드바 영역 계통도 탭
        st.markdown("### 🌳 통합 세포 계통도 (Lineage)")
        dot_code = generate_project_wide_lineage_dot(selected_proj['id'])
        if dot_code:
            st.graphviz_chart(dot_code, use_container_width=True)
        else:
            st.caption("💡 계통도를 생성할 세포 처리 데이터가 없습니다.")

    # ======================================================================
    # [메인 화면 탭 구성 (시작 세포 관리 탭 신설)]
    # ======================================================================
    if selected_plate:
        treatments = db.get_treatments_by_plate(selected_plate['id'])
        
        tab_view, tab_seed, tab_treat = st.tabs([
            "🔴 Well Plate 시각화 & 편집", 
            "🌱 시작 세포 관리 (Seed Cells)", 
            "📝 날짜별 물질/세포 처리 및 이력 관리",
        ])

        # ======================================================================
        # [TAB 1] Plotly 시각화 및 편집
        # ======================================================================
        with tab_view:
            st.info("💡 **왼쪽 차트**의 Well을 **클릭**하거나 **드래그(Box/Lasso)**하면 **오른쪽 편집 창**에서 바로 수정, 사진 첨부 및 신규 처리를 할 수 있습니다.")
            
            left_col, right_col = st.columns([5.5, 6.5], gap="large")

            rows = selected_plate['rows']
            cols = selected_plate['cols']
            total_wells = rows * cols
            row_labels = [chr(65 + i) for i in range(rows)]
            dates_available = sorted(list(set([t['treatment_date'] for t in treatments]))) if treatments else []

            with left_col:
                st.markdown("##### 🧫 플레이트 배치 시각화")
                col_v1, col_v2 = st.columns([1.2, 1.8])
                with col_v1:
                    selected_date = st.selectbox("📅 조회 날짜", options=["전체 날짜 (최신 상태)"] + dates_available, key="v_date_select")
                with col_v2:
                    color_by = st.radio("🎨 색상 기준", ["세포 정보별", "처리 유무별"], horizontal=True, key="v_color_radio")

                well_last_map = {}
                well_all_map = {}
                for t in treatments:
                    if selected_date == "전체 날짜 (최신 상태)" or t['treatment_date'] == selected_date:
                        pos = t['well_position'].upper()
                        if pos not in well_all_map:
                            well_all_map[pos] = []
                        well_all_map[pos].append(t)
                        well_last_map[pos] = t

                palette = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#6366F1", "#F97316", "#06B6D4"]
                unique_cells = sorted(list(set([t.get('cell_info', '').strip() for t in treatments if t.get('cell_info')]))) if treatments else []
                cell_color_map = {cell: palette[i % len(palette)] for i, cell in enumerate(unique_cells)}

                if total_wells <= 6:
                    marker_size, font_size = 65, 12
                elif total_wells <= 12:
                    marker_size, font_size = 55, 11
                elif total_wells <= 24:
                    marker_size, font_size = 48, 10
                elif total_wells <= 48:
                    marker_size, font_size = 40, 9
                else:
                    marker_size, font_size = 28, 7

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
                            cell_name = item.get('cell_info', '').strip() if item.get('cell_info') else "기타"
                            
                            color = cell_color_map.get(cell_name, "#3B82F6") if color_by == "세포 정보별" else "#10B981"
                            has_img = "📷 사진 유" if extract_image_data(item) else ""
                            cell_short = cell_name[:6] if cell_name else "미지정"
                            
                            analysis_val = item.get('analysis_status', '-') if item.get('analysis_status') else '미진행'
                            analysis_badge = "🔬" if analysis_val != "미진행" else ""
                            
                            text_labels.append(f"<b>{pos}</b><br>{cell_short}{' ' + analysis_badge if analysis_badge else ''}")
                            
                            basal_text = get_basal_media(item)
                            treatment_summary = format_compound_summary(item['compound_name'], item['concentration'])
                            
                            hover_html = (
                                f"<b>[Well {pos}]</b> {has_img}<br>"
                                f"🧫 <b>세포 정보:</b> {item.get('cell_info', '-')}<br>"
                                f"🔬 <b>분석 진행:</b> {analysis_val}<br>"
                                f"🥛 <b>Basal Media:</b> {basal_text}<br>"
                                f"🧪 <b>처리 조건:</b> {treatment_summary}<br>"
                                f"📅 <b>일자:</b> {item['treatment_date']}"
                            )
                            hover_texts.append(hover_html)
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

            with right_col:
                edit_main_tab1, edit_main_tab2 = st.tabs(["✏️ 선택 Well 편집", "📊 배치 요약 표"])

                with edit_main_tab1:
                    all_well_positions = [f"{r}{c}" for r in row_labels for c in range(1, cols + 1)]

                    if "last_dragged_signature" not in st.session_state:
                        st.session_state["last_dragged_signature"] = None

                    dragged_wells = []
                    if plotly_event and "selection" in plotly_event and plotly_event["selection"].get("points"):
                        for pt in plotly_event["selection"]["points"]:
                            if "customdata" in pt:
                                val = pt["customdata"]
                                if isinstance(val, (list, tuple)) and len(val) > 0:
                                    dragged_wells.append(str(val[0]))
                                elif val:
                                    dragged_wells.append(str(val))

                    current_sig = ",".join(sorted(dragged_wells)) if dragged_wells else None
                    if current_sig != st.session_state["last_dragged_signature"]:
                        st.session_state["last_dragged_signature"] = current_sig
                        if dragged_wells:
                            st.session_state["selected_wells_multiselect"] = dragged_wells

                    selected_wells = st.multiselect(
                        "📌 대상 Well 선택",
                        options=all_well_positions,
                        key="selected_wells_multiselect"
                    )

                    if selected_wells:
                        if len(selected_wells) == 1:
                            pos = selected_wells[0]
                            st.success(f"🎯 **Well [{pos}]** 가 선택되었습니다.")
                            items = well_all_map.get(pos, [])

                            with st.expander(f"➕ Well [{pos}] 신규 처리 작성", expanded=True):
                                r1_c1, r1_c2 = st.columns(2)
                                with r1_c1:
                                    ex_d = st.date_input("처리 일자", datetime.date.today(), key=f"ex_d_{pos}")
                                with r1_c2:
                                    st.text_input("웰 위치", value=pos, disabled=True, key=f"ex_pos_{pos}")

                                seed_options = st.session_state.get(f"seed_cells_{selected_proj['id']}", ["iPSC", "HIO", "ESC"])
                                ex_cell = st.selectbox("세포 정보 (시작 세포 연동)", options=seed_options, key=f"ex_cell_{pos}")
                                
                                ex_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key=f"ex_analysis_{pos}")
                                ex_analysis_val = st.session_state.get(f"ex_analysis_{pos}", "미진행")
                                
                                if ex_analysis_val == "미진행":
                                    ex_basal = st.selectbox("Basal Media", options=get_recipe_options(), key=f"ex_basal_{pos}")
                                    ex_comp_str = st.text_input("물질명", placeholder="예: VEGF", key=f"ex_c_{pos}")
                                    ex_conc_str = st.text_input("농도", placeholder="예: 50 ng/mL", key=f"ex_n_{pos}")
                                else:
                                    ex_basal = "-"
                                    ex_comp_str = f"분석 진행 ({ex_analysis_val})"
                                    ex_conc_str = ""

                                ex_note = st.text_input("비고", placeholder="상세 조건", key=f"ex_note_{pos}")
                                ex_file = st.file_uploader("📷 현미경 사진", type=["png", "jpg", "jpeg"], key=f"ex_file_{pos}")

                                if st.button(f"💾 Well [{pos}] 처리 저장", key=f"btn_ex_save_{pos}", type="primary", use_container_width=True):
                                    img_b64 = file_to_base64(ex_file)
                                    comb_note = build_combined_note(ex_basal, ex_note, img_b64)
                                    db.add_treatment(
                                        selected_plate['id'], pos, str(ex_d),
                                        ex_comp_str, ex_conc_str, ex_cell, comb_note, ex_analysis
                                    )
                                    st.toast("저장되었습니다!", icon="✅")
                                    st.rerun()

                with edit_main_tab2:
                    st.caption("📊 행/열 단면 요약 정보")

        # ======================================================================
        # [TAB 2] 시작 세포 관리 탭 (Seed Cells)
        # ======================================================================
        with tab_seed:
            st.markdown("### 🌱 프로젝트 시작 세포(Origin/Seed Cell) 설정")
            st.caption("💡 동일 프로젝트 내에서 진행되는 모든 Well Plate의 계통 시작점이 되는 기원 세포주를 관리합니다.")

            proj_seed_key = f"seed_cells_{selected_proj['id']}"
            if proj_seed_key not in st.session_state:
                st.session_state[proj_seed_key] = ["iPSC-HiPSC-12", "H9 ESC", "Human Primary EC"]

            c_seed1, c_seed2 = st.columns([2, 1])

            with c_seed1:
                st.markdown("##### 📋 현재 등록된 시작 세포 목록")
                for idx, s_cell in enumerate(st.session_state[proj_seed_key]):
                    st.text(f"  {idx+1}. {s_cell}")

            with c_seed2:
                st.markdown("##### ➕ 새 시작 세포 등록")
                new_seed_name = st.text_input("시작 세포/조직명", placeholder="예: iPSC-Clone #3")
                if st.button("🌱 시작 세포 추가", use_container_width=True):
                    if new_seed_name.strip() and new_seed_name not in st.session_state[proj_seed_key]:
                        st.session_state[proj_seed_key].append(new_seed_name.strip())
                        st.success(f"'{new_seed_name}' 등록 완료!")
                        st.rerun()

        # ======================================================================
        # [TAB 3] 물질/세포 처리 및 이력 관리
        # ======================================================================
        with tab_treat:
            st.markdown("### 📝 날짜별 물질/세포 처리 작성")
            t_date = st.date_input("처리 일자", datetime.date.today(), key="t_date_main")
            t_well = st.text_input("웰 위치 (Well Position)*", placeholder="예: A1, B2", key="t_well_main")
            
            seed_opts = st.session_state.get(f"seed_cells_{selected_proj['id']}", ["iPSC"])
            t_cell = st.selectbox("세포/오가노이드 정보", options=seed_opts, key="t_cell_main")
            
            t_comp = st.text_input("처리 물질", placeholder="예: Chir99021", key="t_comp_main")
            t_conc = st.text_input("농도", placeholder="예: 3 uM", key="t_conc_main")
            t_note = st.text_input("비고", placeholder="특이사항", key="t_note_main")

            if st.button("처리 내역 저장", use_container_width=True, type="primary"):
                if t_well.strip():
                    wells = [w.strip().upper() for w in t_well.split(",") if w.strip()]
                    comb_note = build_combined_note("-", t_note, None)
                    for w in wells:
                        db.add_treatment(selected_plate['id'], w, str(t_date), t_comp, t_conc, t_cell, comb_note, "미진행")
                    st.success("저장 완료!")
                    st.rerun()