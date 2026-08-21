import datetime
import base64
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
    </style>
""", unsafe_allow_html=True)

if hasattr(style, "apply_custom_style"):
    style.apply_custom_style()

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

def parse_note_basal_image(item):
    if not item:
        return "", "", None
    basal = get_basal_media(item)
    basal = "" if basal == "-" else basal
    
    pure_note = str(item.get('note', ''))
    img_data = extract_image_data(item)
    
    if '[Media:' in pure_note and ']' in pure_note:
        s, e = pure_note.find('[Media:'), pure_note.find(']', pure_note.find('[Media:'))
        if e != -1: pure_note = (pure_note[:s] + pure_note[e+1:]).strip()
            
    if '[IMG_DATA:' in pure_note and ']' in pure_note:
        s, e = pure_note.find('[IMG_DATA:'), pure_note.rfind(']')
        if e != -1: pure_note = (pure_note[:s] + pure_note[e+1:]).strip()
            
    return basal, pure_note.strip(), img_data

def build_combined_note(basal, pure_note, img_b64):
    parts = []
    if basal and basal.strip() and basal.strip() != "-":
        parts.append(f"[Media: {basal.strip()}]")
    if pure_note and pure_note.strip():
        parts.append(pure_note.strip())
    if img_b64 and img_b64.strip():
        parts.append(f"[IMG_DATA: {img_b64.strip()}]")
    return " ".join(parts)

def display_image_from_b64(b64_str, caption="", width=None):
    if not b64_str: return
    try:
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=(width is None), width=width)
    except Exception:
        st.caption("⚠️ 이미지를 로드할 수 없습니다.")

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
    """중복되는 물질 및 농도 (2쌍 레이아웃) 입력 폼 공통 모듈"""
    default_comps = default_comps or []
    default_concs = default_concs or []
    
    st.caption("🧪 **처리 물질 및 농도 (2쌍씩 입력 가능)**")
    num_pairs = st.number_input(
        "입력할 물질 쌍 개수", min_value=1, max_value=10, 
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

def generate_dynamic_lineage_dot(treatments):
    """
    12-well -> 24-well 이동 및 DE_1 실험 진행에 맞춘 계통도 연결 알고리즘 개선
    """
    if not treatments: return None
    df = pd.DataFrame(treatments)
    if 'cell_info' not in df.columns: return None
        
    df = df[df['cell_info'].notnull() & (df['cell_info'].str.strip() != "")]
    if df.empty: return None

    df = df.sort_values(by=['treatment_date', 'well_position'])
    nodes, edges = set(), set()

    # 웰별 및 전체 처리 이력 분석
    for well, group in df.groupby('well_position'):
        cell_history = []
        for _, row in group.iterrows():
            c_info, t_date = str(row['cell_info']).strip(), str(row['treatment_date']).strip()
            note_str = str(row.get('note', ''))
            
            # 세포 정보 표시에 Well 및 Note 출처 추가
            node_label = f"{c_info} ({well})"
            if c_info and (not cell_history or cell_history[-1][0] != node_label):
                cell_history.append((node_label, t_date, note_str))
        
        for n_label, _, _ in cell_history: nodes.add(n_label)

        for i in range(len(cell_history) - 1):
            src, dst, dst_date = cell_history[i][0], cell_history[i + 1][0], cell_history[i + 1][1]
            if src != dst: edges.add((src, dst, dst_date, "Passage/Treatment"))

    if not nodes: return None

    dot_lines = [
        "digraph LineageTree { rankdir=LR;",
        "    graph [nodesep=0.4, ranksep=0.8, margin=0, pad=0.2];",
        "    node [shape=box, style=\"filled,rounded\", fillcolor=\"#eff6ff\", color=\"#2563eb\", fontname=\"Malgun Gothic, sans-serif\", fontsize=10, height=0.32, margin=\"0.15,0.08\"];",
        "    edge [color=\"#475569\", arrowhead=normal, arrowsize=0.7, penwidth=1.4, fontname=\"Malgun Gothic, sans-serif\", fontsize=8];"
    ]
    for node in nodes:
        clean_node = node.replace('"', '\\"')
        dot_lines.append(f'    "{clean_node}" [label="{clean_node}"];')

    for src, dst, transition_date, label in edges:
        c_src, c_dst, c_date = src.replace('"', '\\"'), dst.replace('"', '\\"'), transition_date.replace('"', '\\"')
        dot_lines.append(f'    "{c_src}" -> "{c_dst}" [label=" {c_date} ({label}) ", fontcolor="#0284c7"];')

    dot_lines.append("}")
    return "\n".join(dot_lines)

# ======================================================================
# 3. 각 탭별 Render 함수
# ======================================================================
def render_tab_overview():
    st.markdown("### 🧪 전체 프로젝트의 실험 중인 플레이트 목록")
    st.caption("모든 웰의 분석이 완료된 플레이트는 제외되며, 현재 분석 및 실험이 진행 중인 플레이트만 표시됩니다.")

    def navigate_to_plate(proj_label, pl_key, proj_name, pl_name):
        st.session_state.selected_plate_proj_label = proj_label
        st.session_state.selected_plate_select = pl_key
        st.toast(f"'{proj_name}' 프로젝트의 '{pl_name}' 플레이트로 이동합니다.", icon="🧫")

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
            _, pure_note, _ = parse_note_basal_image(latest_treat)
            
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
        font_size = 12 if total_wells <= 6 else (11 if total_wells <= 12 else (10 if total_wells <= 24 else (9 if total_wells <= 48 else 8)))

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

            if selected_wells:
                if len(selected_wells) == 1:
                    pos = selected_wells[0]
                    st.success(f"🎯 **Well [{pos}]** 가 선택되었습니다.")
                    items = well_all_map.get(pos, [])

                    with st.expander(f"➕ Well [{pos}] 신규 처리 및 사진 작성", expanded=True):
                        
                        # --- 계대/이동 옵션 도우미 ---
                        st.markdown("<div class='transfer-box'><b>🔄 이동/계대 배양 도우미</b>", unsafe_allow_html=True)
                        is_transfer = st.checkbox("다른 플레이트에서 옮겨온 샘플인가요?", key=f"chk_trans_{pos}")
                        source_info = ""
                        if is_transfer:
                            src_p = st.text_input("출처", value="12WP-A1", key=f"src_p_{pos}")
                            source_info = f"[Transferred from {src_p}]"
                        st.markdown("</div>", unsafe_allow_html=True)

                        ex_d = st.date_input("처리 일자", datetime.date.today(), key=f"ex_d_{pos}")
                        ex_cell = st.text_input("세포 정보", value="DE_1_P1" if is_transfer else "DE_1", placeholder="예: DE_1, DE_1_P1", key=f"ex_cell_{pos}")
                        ex_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key=f"ex_analysis_{pos}")
                        
                        if ex_analysis == "미진행":
                            ex_basal = st.selectbox("Basal Media (레시피 선택)", options=get_recipe_options(), key=f"ex_basal_{pos}")
                            ex_comp_str, ex_conc_str = render_compound_inputs(f"ex_{pos}")
                        else:
                            ex_basal = "-"
                            ex_comp_str, ex_conc_str = f"분석 진행 ({ex_analysis})", ""
                            st.info(f"🔬 **{ex_analysis}** 분석 모드입니다.")

                        ex_note = st.text_input("비고", value=f"passaging {source_info}".strip(), placeholder="상세 조건", key=f"ex_note_{pos}")
                        ex_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"ex_file_{pos}")

                        if st.button(f"💾 Well [{pos}] 처리 저장", key=f"btn_ex_save_{pos}", use_container_width=True, type="primary"):
                            if ex_analysis != "미진행" or ex_comp_str.strip():
                                comb_note = build_combined_note(ex_basal, ex_note, file_to_base64(ex_file))
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

                                b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)
                                mod_d = st.date_input("처리 일자", value=def_d, key=f"s_date_{item['id']}")
                                mod_pos = st.text_input("웰 위치", value=item['well_position'], key=f"s_pos_{item['id']}")
                                mod_cell = st.text_input("세포 정보", value=item.get('cell_info', ''), key=f"s_cell_{item['id']}")
                                
                                cur_a = item.get('analysis_status', '미진행')
                                mod_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, index=ANALYSIS_OPTIONS.index(cur_a) if cur_a in ANALYSIS_OPTIONS else 0, key=f"s_analysis_{item['id']}")
                                
                                if mod_analysis == "미진행":
                                    b_opts = get_recipe_options(b_media_val)
                                    mod_basal = st.selectbox("Basal Media", options=b_opts, index=b_opts.index(b_media_val) if b_media_val in b_opts else 0, key=f"s_basal_{item['id']}")
                                    e_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                                    e_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                                    mod_comp, mod_conc = render_compound_inputs(f"s_{item['id']}", e_comps, e_concs)
                                else:
                                    mod_basal, mod_comp, mod_conc = "-", f"분석 진행 ({mod_analysis})", ""

                                mod_note = st.text_input("비고", value=pure_note_val, key=f"s_note_{item['id']}")
                                del_img = st.checkbox("🗑️ 저장된 사진 삭제", key=f"chk_del_img_{item['id']}") if cur_img_b64 else False
                                new_img_file = st.file_uploader("새 현미경 사진 첨부/교체", type=["png", "jpg", "jpeg"], key=f"file_s_{item['id']}")

                                b_save, b_del = st.columns(2)
                                if b_save.button("💾 저장", key=f"btn_s_save_{item['id']}", type="primary", use_container_width=True):
                                    final_img = None if del_img else (file_to_base64(new_img_file) if new_img_file else cur_img_b64)
                                    comb_note = build_combined_note(mod_basal, mod_note, final_img)
                                    db.update_treatment(item['id'], mod_pos.strip().upper(), str(mod_d), mod_comp.strip(), mod_conc.strip(), mod_cell.strip(), comb_note, mod_analysis)
                                    st.toast("수정 사항이 저장되었습니다!", icon="✅")
                                    st.rerun()

                                if b_del.button("🗑️ 삭제", key=f"btn_s_del_{item['id']}", type="secondary", use_container_width=True):
                                    db.delete_treatment(item['id'])
                                    st.toast("삭제되었습니다.", icon="🗑️")
                                    st.rerun()
                else:
                    st.success(f"🎯 총 **{len(selected_wells)}개** Well 선택됨")
                    
                    st.markdown("<div class='transfer-box'><b>🔄 선택한 Well 전체 12-well -> 24-well 이동 일괄 작성</b>", unsafe_allow_html=True)
                    batch_trans = st.checkbox("12-well 플레이트에서 일괄 이식된 샘플인가요?", key="batch_trans")
                    batch_src = ""
                    if batch_trans:
                        batch_src = st.text_input("출처 12-well 위치", value="12WP-A1", key="batch_src")
                    st.markdown("</div>", unsafe_allow_html=True)

                    b_date = st.date_input("일괄 처리 일자", datetime.date.today(), key="batch_date")
                    b_cell = st.text_input("세포 정보", value="DE_1_P1" if batch_trans else "DE_1", key="batch_cell")
                    b_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key="batch_analysis")
                    
                    if b_analysis == "미진행":
                        b_basal = st.selectbox("Basal Media", options=get_recipe_options(), key="batch_basal")
                        b_comp_str, b_conc_str = render_compound_inputs("batch")
                    else:
                        b_basal, b_comp_str, b_conc_str = "-", f"분석 진행 ({b_analysis})", ""

                    default_batch_note = f"12WP({batch_src})에서 24WP로 계대 분할" if batch_trans else ""
                    b_note = st.text_input("비고", value=default_batch_note, key="batch_note")
                    b_file = st.file_uploader("📷 현미경 사진 첨부", type=["png", "jpg", "jpeg"], key="batch_file")

                    if st.button(f"💾 선택한 {len(selected_wells)}개 Well에 일괄 저장", key="btn_batch_save", use_container_width=True, type="primary"):
                        if b_comp_str.strip():
                            comb_note = build_combined_note(b_basal, b_note, file_to_base64(b_file))
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

def render_tab_tree(treatments):
    st.caption("💡 작성하신 **`세포 정보`**(예: DE_1, DE_1_P1)와 **`Well 위치`**, **`처리 일자`**의 흐름을 분석하여 계통도로 시각화합니다.")
    dot_code = generate_dynamic_lineage_dot(treatments)
    if dot_code:
        st.graphviz_chart(dot_code, use_container_width=True)
    else:
        st.info("💡 계통도를 그릴 세포 정보 데이터가 없습니다.")

def render_tab_management(selected_plate, treatments):
    r1_c1, r1_c2 = st.columns(2)
    t_date = r1_c1.date_input("처리 일자 (Date)", datetime.date.today(), key="t_date_main")
    t_well = r1_c2.text_input("웰 위치 (Well Position)*", placeholder="예: A1, B2 또는 A1,A2,A3", key="t_well_main")
    
    # --- 12-well -> 24-well 계대/이동 가이드 ---
    st.markdown("<div class='transfer-box'><b>🔄 DE_1 실험: 12-well -> 24-well 계대/이동 기록 가이드</b><br><small>12-well에서 분할 이식하는 경우 세포 정보에 'DE_1_P1' 또는 비고란에 출처 웰을 명시하면 계통도 추적이 수월해집니다.</small></div>", unsafe_allow_html=True)
    
    t_cell = st.text_input("세포/오가노이드 정보", value="DE_1", placeholder="예: DE_1, DE_1_P1", key="t_cell_main")
    t_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key="t_analysis_main")

    if t_analysis == "미진행":
        t_basal = st.selectbox("Basal Media (레시피 선택)", options=get_recipe_options(), key="t_basal_main")
        t_comp_str, t_conc_str = render_compound_inputs("t_main")
    else:
        t_basal, t_comp_str, t_conc_str = "-", f"분석 진행 ({t_analysis})", ""
        st.info(f"🔬 **{t_analysis}** 분석 모드입니다.")

    t_note = st.text_input("비고 / 상세 조건", placeholder="예: 12-well Plate A1에서 24-well Plate로 계대(Subculture) 이동", key="t_note_main")
    t_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key="t_file_upload_main")

    if st.button("처리 내역 및 사진 저장", use_container_width=True, type="primary", key="btn_t_main_save"):
        if t_well.strip() and t_comp_str.strip():
            wells = [w.strip().upper() for w in t_well.split(",") if w.strip()]
            comb_note = build_combined_note(t_basal, t_note, file_to_base64(t_file))
            for w in wells:
                db.add_treatment(selected_plate['id'], w, str(t_date), t_comp_str, t_conc_str, t_cell.strip(), comb_note, t_analysis)
            st.success(f"{len(wells)}개 웰({', '.join(wells)})에 기록 완료!")
            st.rerun()
        else:
            st.error("웰 위치와 최소 하나 이상의 물질명을 입력해 주세요.")

    st.markdown("---")
    st.subheader("📋 전체 물질 처리 이력 관리")
    if treatments:
        list_cols = st.columns(2)
        for idx, item in enumerate(treatments):
            with list_cols[idx % 2]:
                b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)
                img_flag = "📷 " if cur_img_b64 else ""
                formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                analysis_lbl = item.get('analysis_status', '미진행')
                
                with st.expander(f"{img_flag}📍 Well [{item['well_position']}] | 📅 {item['treatment_date']} | 🧬 {item.get('cell_info', '-')} ({analysis_lbl}) | 🧪 {formatted_cond}"):
                    try: default_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                    except: default_d = datetime.date.today()

                    e_date = st.date_input("처리 일자", value=default_d, key=f"t_e_date_{item['id']}")
                    e_pos = st.text_input("웰 위치", value=item['well_position'], key=f"t_e_pos_{item['id']}")
                    e_cell = st.text_input("세포 정보", value=item.get('cell_info', ''), key=f"t_e_cell_{item['id']}")
                    
                    e_cur_a = item.get('analysis_status', '미진행')
                    e_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, index=ANALYSIS_OPTIONS.index(e_cur_a) if e_cur_a in ANALYSIS_OPTIONS else 0, key=f"t_e_analysis_{item['id']}")
                    
                    if e_analysis == "미진행":
                        e_b_opts = get_recipe_options(b_media_val)
                        e_basal = st.selectbox("Basal Media", options=e_b_opts, index=e_b_opts.index(b_media_val) if b_media_val in e_b_opts else 0, key=f"t_e_basal_{item['id']}")
                        e_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                        e_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                        e_comp, e_conc = render_compound_inputs(f"t_e_{item['id']}", e_comps, e_concs)
                    else:
                        e_basal, e_comp, e_conc = "-", f"분석 진행 ({e_analysis})", ""

                    e_note = st.text_input("비고", value=pure_note_val, key=f"t_e_note_{item['id']}")
                    del_img = st.checkbox("사진 삭제", key=f"chk_del_t_{item['id']}") if cur_img_b64 else False
                    new_img = st.file_uploader("사진 교체/추가", type=["png", "jpg", "jpeg"], key=f"f_e_{item['id']}")

                    b_c1, b_c2 = st.columns(2)
                    if b_c1.button("💾 저장", key=f"btn_t_update_{item['id']}", use_container_width=True):
                        final_img = None if del_img else (file_to_base64(new_img) if new_img else cur_img_b64)
                        comb_note = build_combined_note(e_basal, e_note, final_img)
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
            "🌳 사용자 데이터 기반 계통도", 
            "📝 날짜별 물질/세포 처리 입력 및 전체 관리"
        ])

        with tab_overview:
            render_tab_overview()
        with tab_view:
            render_tab_visualization(selected_plate, treatments)
        with tab_tree:
            render_tab_tree(treatments)
        with tab_treat:
            render_tab_management(selected_plate, treatments)
