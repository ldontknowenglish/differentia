import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import base64
import db
import style

# --- 1. 페이지 설정 및 디자인 서식 적용 ---
st.set_page_config(page_title="연구 프로젝트 관리", page_icon="🧪", layout="wide")

# 화면 전체 레이아웃을 좌측 밀착(Left-aligned)시키는 Custom CSS
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

st.title("🧫 treatment confirm")

# ======================================================================
# [이미지 및 데이터 파싱 헬퍼 함수][cite: 1]
# ======================================================================
def file_to_base64(uploaded_file):
    """업로드된 이미지 파일을 Base64 문자열로 변환"""[cite: 1]
    if uploaded_file is None:
        return None
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode('utf-8')

def extract_image_data(item):
    """item에서 이미지 base64 데이터 추출 (DB 컬럼 또는 note 파싱)"""[cite: 1]
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
    """item에서 basal_media, 이미지, 순수 note 분리"""[cite: 1]
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
    """Basal media, 순수 note, 이미지 base64를 하나의 note 문자열로 결합"""[cite: 1]
    parts = []
    if basal and basal.strip() and basal.strip() != "-":
        parts.append(f"[Media: {basal.strip()}]")
    if pure_note and pure_note.strip():
        parts.append(pure_note.strip())
    if img_b64 and img_b64.strip():
        parts.append(f"[IMG_DATA: {img_b64.strip()}]")
    return " ".join(parts)

def display_image_from_b64(b64_str, caption="", width=None):
    """Base64 문자열을 Streamlit 이미지로 출력"""[cite: 1]
    if not b64_str:
        return
    try:
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=True if width is None else False, width=width)
    except Exception:
        st.caption("⚠️ 이미지를 로드할 수 없습니다.")

def get_basal_media(item):
    """Basal Media 정보를 안전하게 추출"""[cite: 1]
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
    """Material Recipe DB에서 저장된 레시피 목록을 추출하여 드롭다운 옵션 생성"""[cite: 1]
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
    """사용자가 입력한 treatments 데이터의 cell_info와 날짜 순서를 분석해 Graphviz DOT 생성"""[cite: 1]
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
    """물질명과 농도 문자열을 1:1 매칭하여 '물질 농도' 형태로 정형화"""[cite: 1]
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

db.init_db()
projects = db.get_projects()

if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다. 먼저 **'1. Experiments(프로젝트 관리)'** 메뉴에서 프로젝트를 생성해 주세요.")[cite: 1]
else:
    proj_map = {f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID: {p['id']})": p for p in projects}
    options = list(proj_map.keys())

    if "selected_plate_proj_label" not in st.session_state or st.session_state.selected_plate_proj_label not in options:
        st.session_state.selected_plate_proj_label = options[0]

    # === [사이드바 설정 영역: 프로젝트 선택, 플레이트 선택 및 생성] ===
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
                st.toast("플레이트가 휴지통으로 이동되었습니다.", icon="🗑️")
                st.rerun()
        else:
            st.info("💡 선택된 프로젝트에 등록된 플레이트가 없습니다. 아래에서 생성해 주세요.")[cite: 1]
            selected_plate = None

        st.markdown("---")
        with st.expander("➕ 새 규격 플레이트 생성", expanded=not bool(plates)):
            # [수정] st.form 내 동적 위젯 오류 방지를 위해 일반 컨테이너 기반 또는 안전한 입력 구조로 변경
            plate_name = st.text_input("플레이트 이름*", placeholder="예: 96-Well Plate #1", key="input_new_plate_name")
            selected_preset_label = st.selectbox("🧫 플레이트 표준 규격 선택*", list(PLATE_PRESETS.keys()), key="select_plate_preset")

            if PLATE_PRESETS[selected_preset_label] == "custom":
                p_rows = st.number_input("행 개수 (Rows)", min_value=1, max_value=16, value=8, key="custom_p_rows")
                p_cols = st.number_input("열 개수 (Cols)", min_value=1, max_value=24, value=12, key="custom_p_cols")
            else:
                p_rows, p_cols = PLATE_PRESETS[selected_preset_label]
                st.caption(f"💡 선택된 규격: **{p_rows} 행 x {p_cols} 열**")

            if st.button("플레이트 추가", use_container_width=True, key="btn_submit_plate"):
                if plate_name.strip():
                    db.add_plate(selected_proj['id'], plate_name.strip(), p_rows, p_cols)
                    st.success(f"'{plate_name}' 플레이트 생성 완료!")
                    st.rerun()
                else:
                    st.error("플레이트 이름을 입력해 주세요.")[cite: 1]

    # 5개 탭 구성
    tab_view, tab_tree, tab_treat, tab_compare, tab_log = st.tabs([
        "🔴 Well Plate 시각화 & 편집", 
        "🌳 사용자 데이터 기반 계통도", 
        "📝 날짜별 물질/세포 처리 입력 및 전체 관리",
        "📸 날짜별 & 조건별 사진 비교 시각화",
        "📅 연구 데일리 로그"
    ])

    if selected_plate:
        treatments = db.get_treatments_by_plate(selected_plate['id'])

        # ======================================================================
        # [TAB 1] Plotly 시각화 및 편집
        # ======================================================================
        with tab_view:
            st.info("💡 **왼쪽 차트**의 Well을 **클릭**하거나 **드래그(Box/Lasso)**하면 **오른쪽 편집 창**에서 바로 수정, 사진 첨부 및 신규 처리를 할 수 있습니다.")[cite: 1]
            
            left_col, right_col = st.columns([5.5, 6.5], gap="large")

            rows = selected_plate['rows']
            cols = selected_plate['cols']
            total_wells = rows * cols
            row_labels = [chr(65 + i) for i in range(rows)]
            dates_available = sorted(list(set([t['treatment_date'] for t in treatments]))) if treatments else []

            with left_col:
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
                    marker_size, font_size = 32, 8

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
                            elif "point_index" in pt:
                                dragged_wells.append(well_names[pt["point_index"]])

                    current_sig = ",".join(sorted(dragged_wells)) if dragged_wells else None
                    if current_sig != st.session_state["last_dragged_signature"]:
                        st.session_state["last_dragged_signature"] = current_sig
                        if dragged_wells:
                            st.session_state["selected_wells_multiselect"] = dragged_wells

                    selected_wells = st.multiselect(
                        "📌 대상 Well 선택 (차트에서 클릭/드래그 시 자동 선택)",
                        options=all_well_positions,
                        key="selected_wells_multiselect"
                    )

                    if selected_wells:
                        if len(selected_wells) == 1:
                            pos = selected_wells[0]
                            st.success(f"🎯 **Well [{pos}]** 가 선택되었습니다.")

                            if pos in well_all_map:
                                items = well_all_map[pos]
                                st.markdown(f"##### 📝 Well [{pos}] 기존 처리 이력 ({len(items)}건)")
                                
                                for item in items:
                                    formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                                    with st.expander(f"📅 {item['treatment_date']} | 🧬 {item.get('cell_info', '-')} | 🧪 {formatted_cond}", expanded=True):
                                        try:
                                            def_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                                        except:
                                            def_d = datetime.date.today()

                                        b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)

                                        r1_c1, r1_c2 = st.columns(2)
                                        with r1_c1:
                                            mod_d = st.date_input("처리 일자", value=def_d, key=f"s_date_{item['id']}")
                                        with r1_c2:
                                            mod_pos = st.text_input("웰 위치", value=item['well_position'], key=f"s_pos_{item['id']}")
                                        
                                        mod_cell = st.text_input("세포 정보", value=item.get('cell_info', ''), key=f"s_cell_{item['id']}")
                                        
                                        cur_analysis = item.get('analysis_status', '미진행')
                                        a_idx = ANALYSIS_OPTIONS.index(cur_analysis) if cur_analysis in ANALYSIS_OPTIONS else 0
                                        
                                        r2_c1, r2_c2 = st.columns(2)
                                        with r2_c1:
                                            mod_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, index=a_idx, key=f"s_analysis_{item['id']}")
                                        
                                        cur_s_analysis = st.session_state.get(f"s_analysis_{item['id']}", cur_analysis)
                                        
                                        with r2_c2:
                                            if cur_s_analysis == "미진행":
                                                b_opts = get_recipe_options(b_media_val)
                                                b_idx = b_opts.index(b_media_val) if b_media_val in b_opts else 0
                                                mod_basal = st.selectbox("Basal Media (레시피 선택)", options=b_opts, index=b_idx, key=f"s_basal_{item['id']}")
                                            else:
                                                mod_basal = "-"
                                                st.text_input("Basal Media", value="-", disabled=True, key=f"s_basal_disabled_{item['id']}")

                                        if cur_s_analysis == "미진행":
                                            st.caption("🧪 **처리 물질 및 농도**")
                                            existing_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                                            existing_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                                            
                                            num_s_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=max(1, len(existing_comps)), key=f"s_num_pairs_{item['id']}")
                                            
                                            s_comps, s_concs = [], []
                                            for i in range(0, int(num_s_pairs), 2):
                                                pair_cols = st.columns([2, 1, 2, 1])
                                                def_c1 = existing_comps[i] if i < len(existing_comps) else ""
                                                def_n1 = existing_concs[i] if i < len(existing_concs) else ""
                                                with pair_cols[0]:
                                                    c1_val = st.text_input(f"물질 #{i+1}", value=def_c1, key=f"s_c_{item['id']}_{i}")
                                                with pair_cols[1]:
                                                    n1_val = st.text_input(f"농도 #{i+1}", value=def_n1, key=f"s_n_{item['id']}_{i}")
                                                if c1_val.strip():
                                                    s_comps.append(c1_val.strip())
                                                    s_concs.append(n1_val.strip())
                                                    
                                                if i + 1 < int(num_s_pairs):
                                                    def_c2 = existing_comps[i+1] if i+1 < len(existing_comps) else ""
                                                    def_n2 = existing_concs[i+1] if i+1 < len(existing_concs) else ""
                                                    with pair_cols[2]:
                                                        c2_val = st.text_input(f"물질 #{i+2}", value=def_c2, key=f"s_c_{item['id']}_{i+1}")
                                                    with pair_cols[3]:
                                                        n2_val = st.text_input(f"농도 #{i+2}", value=def_n2, key=f"s_n_{item['id']}_{i+1}")
                                                    if c2_val.strip():
                                                        s_comps.append(c2_val.strip())
                                                        s_concs.append(n2_val.strip())
                                            mod_comp = ", ".join(s_comps)
                                            mod_conc = ", ".join(s_concs)
                                        else:
                                            mod_comp = f"분석 진행 ({cur_s_analysis})"
                                            mod_conc = ""

                                        mod_note = st.text_input("비고 / 상세 조건", value=pure_note_val, key=f"s_note_{item['id']}")
                                        if cur_img_b64:
                                            display_image_from_b64(cur_img_b64, caption=f"Well {pos} 등록 사진")
                                            del_img = st.checkbox("🗑️ 저장된 사진 삭제", key=f"chk_del_img_{item['id']}")
                                        else:
                                            del_img = False

                                        new_img_file = st.file_uploader("새 현미경 사진 첨부/교체", type=["png", "jpg", "jpeg"], key=f"file_s_{item['id']}")

                                        b_save, b_del = st.columns(2)
                                        with b_save:
                                            if st.button("💾 저장", key=f"btn_s_save_{item['id']}", type="primary", use_container_width=True):
                                                final_img_b64 = cur_img_b64
                                                if del_img:
                                                    final_img_b64 = None
                                                if new_img_file is not None:
                                                    final_img_b64 = file_to_base64(new_img_file)

                                                comb_note = build_combined_note(mod_basal, mod_note, final_img_b64)
                                                # [수정] 8개 인자 정확히 맞춤
                                                db.update_treatment(
                                                    item['id'], mod_pos.strip().upper(), str(mod_d),
                                                    mod_comp.strip(), mod_conc.strip(), mod_cell.strip(), comb_note, mod_analysis
                                                )
                                                st.toast("수정 사항이 저장되었습니다!", icon="✅")
                                                st.rerun()
                                        with b_del:
                                            if st.button("🗑️ 삭제", key=f"btn_s_del_{item['id']}", type="secondary", use_container_width=True):
                                                db.delete_treatment(item['id'])
                                                st.toast("삭제되었습니다.", icon="🗑️")
                                                st.rerun()

                                with st.expander(f"➕ Well [{pos}]에 추가 처리 및 사진 작성", expanded=False):
                                    r1_c1, r1_c2 = st.columns(2)
                                    with r1_c1:
                                        ex_d = st.date_input("처리 일자", datetime.date.today(), key=f"ex_d_{pos}")
                                    with r1_c2:
                                        st.text_input("웰 위치", value=pos, disabled=True, key=f"ex_pos_{pos}")

                                    ex_cell = st.text_input("세포 정보", placeholder="예: iPSC", key=f"ex_cell_{pos}")
                                    
                                    r2_c1, r2_c2 = st.columns(2)
                                    with r2_c1:
                                        ex_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key=f"ex_analysis_{pos}")
                                    ex_analysis_val = st.session_state.get(f"ex_analysis_{pos}", "미진행")
                                    
                                    with r2_c2:
                                        if ex_analysis_val == "미진행":
                                            ex_basal = st.selectbox("Basal Media", options=get_recipe_options(), key=f"ex_basal_{pos}")
                                        else:
                                            ex_basal = "-"
                                            st.text_input("Basal Media", value="-", disabled=True, key=f"ex_basal_disabled_{pos}")

                                    if ex_analysis_val == "미진행":
                                        num_ex_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key=f"ex_num_pairs_{pos}")
                                        ex_comps, ex_concs = [], []
                                        for i in range(0, int(num_ex_pairs), 2):
                                            pair_cols = st.columns([2, 1, 2, 1])
                                            with pair_cols[0]:
                                                c1_val = st.text_input(f"물질 #{i+1}", key=f"ex_c_{pos}_{i}")
                                            with pair_cols[1]:
                                                n1_val = st.text_input(f"농도 #{i+1}", key=f"ex_n_{pos}_{i}")
                                            if c1_val.strip():
                                                ex_comps.append(c1_val.strip())
                                                ex_concs.append(n1_val.strip())
                                                
                                            if i + 1 < int(num_ex_pairs):
                                                with pair_cols[2]:
                                                    c2_val = st.text_input(f"물질 #{i+2}", key=f"ex_c_{pos}_{i+1}")
                                                with pair_cols[3]:
                                                    n2_val = st.text_input(f"농도 #{i+2}", key=f"ex_n_{pos}_{i+1}")
                                                if c2_val.strip():
                                                    ex_comps.append(c2_val.strip())
                                                    ex_concs.append(n2_val.strip())
                                        ex_comp_str = ", ".join(ex_comps)
                                        ex_conc_str = ", ".join(ex_concs)
                                    else:
                                        ex_comp_str = f"분석 진행 ({ex_analysis_val})"
                                        ex_conc_str = ""

                                    ex_note = st.text_input("비고", key=f"ex_note_{pos}")
                                    ex_file = st.file_uploader("📷 현미경 사진 첨부", type=["png", "jpg", "jpeg"], key=f"ex_file_{pos}")

                                    if st.button(f"💾 Well [{pos}] 추가 저장", key=f"btn_ex_save_{pos}", use_container_width=True, type="primary"):
                                        if ex_analysis_val != "미진행" or ex_comp_str.strip():
                                            img_b64 = file_to_base64(ex_file)
                                            comb_note = build_combined_note(ex_basal, ex_note, img_b64)
                                            # [수정] 8개 인자 일치
                                            db.add_treatment(
                                                selected_plate['id'], pos, str(ex_d),
                                                ex_comp_str, ex_conc_str, ex_cell.strip(), comb_note, ex_analysis
                                            )
                                            st.toast(f"Well [{pos}] 추가 저장 완료!", icon="✅")
                                            st.rerun()
                                        else:
                                            st.error("처리 물질명을 입력해 주세요.")
                            else:
                                st.markdown(f"##### ➕ Well [{pos}] 신규 물질 처리 및 사진 작성")
                                r1_c1, r1_c2 = st.columns(2)
                                with r1_c1:
                                    e_d = st.date_input("처리 일자", datetime.date.today(), key=f"e_d_{pos}")
                                with r1_c2:
                                    st.text_input("웰 위치", value=pos, disabled=True, key=f"e_pos_{pos}")

                                e_cell = st.text_input("세포 정보", placeholder="예: DE", key=f"e_cell_{pos}")
                                r2_c1, r2_c2 = st.columns(2)
                                with r2_c1:
                                    e_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key=f"e_analysis_{pos}")
                                with r2_c2:
                                    e_analysis_val = st.session_state.get(f"e_analysis_{pos}", "미진행")
                                    if e_analysis_val == "미진행":
                                        e_basal = st.selectbox("Basal Media", options=get_recipe_options(), key=f"e_basal_{pos}")
                                    else:
                                        e_basal = "-"
                                        st.text_input("Basal Media", value="-", disabled=True, key=f"e_basal_disabled_{pos}")

                                if e_analysis_val == "미진행":
                                    num_e_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key=f"e_num_pairs_{pos}")
                                    e_comps, e_concs = [], []
                                    for i in range(0, int(num_e_pairs), 2):
                                        pair_cols = st.columns([2, 1, 2, 1])
                                        with pair_cols[0]:
                                            c_val = st.text_input(f"물질 #{i+1}", key=f"e_c_{pos}_{i}")
                                        with pair_cols[1]:
                                            n_val = st.text_input(f"농도 #{i+1}", key=f"e_n_{pos}_{i}")
                                        if c_val.strip():
                                            e_comps.append(c_val.strip())
                                            e_concs.append(n_val.strip())
                                            
                                        if i + 1 < int(num_e_pairs):
                                            with pair_cols[2]:
                                                c2_val = st.text_input(f"물질 #{i+2}", key=f"e_c_{pos}_{i+1}")
                                            with pair_cols[3]:
                                                n2_val = st.text_input(f"농도 #{i+2}", key=f"e_n_{pos}_{i+1}")
                                            if c2_val.strip():
                                                e_comps.append(c2_val.strip())
                                                e_concs.append(n2_val.strip())
                                    comb_comp = ", ".join(e_comps)
                                    comb_conc = ", ".join(e_concs)
                                else:
                                    comb_comp = f"분석 진행 ({e_analysis_val})"
                                    comb_conc = ""

                                e_note = st.text_input("비고", key=f"e_note_{pos}")
                                e_file = st.file_uploader("📷 현미경 사진 첨부", type=["png", "jpg", "jpeg"], key=f"e_file_{pos}")

                                if st.button(f"💾 Well [{pos}] 처리 저장", key=f"btn_empty_save_{pos}", use_container_width=True, type="primary"):
                                    if comb_comp:
                                        img_b64 = file_to_base64(e_file)
                                        comb_note = build_combined_note(e_basal, e_note, img_b64)
                                        # [수정] 8개 인자 일치
                                        db.add_treatment(
                                            selected_plate['id'], pos, str(e_d),
                                            comb_comp, comb_conc, e_cell.strip(), comb_note, e_analysis
                                        )
                                        st.success(f"✅ Well [{pos}] 저장 완료!")
                                        st.rerun()
                                    else:
                                        st.error("물질명을 입력해 주세요.")

                        else:
                            st.success(f"🎯 총 **{len(selected_wells)}개** Well 선택됨")
                            tab_sub_batch, tab_sub_info = st.tabs(["✏️ 일괄 물질 처리", "📝 개별 조회"])

                            with tab_sub_batch:
                                r1_c1, r1_c2 = st.columns(2)
                                with r1_c1:
                                    b_date = st.date_input("처리 일자", datetime.date.today(), key="batch_date")
                                with r1_c2:
                                    st.text_input("대상 웰", value=", ".join(selected_wells), disabled=True, key="batch_wells_display")
                                
                                b_cell = st.text_input("세포 정보", key="batch_cell")
                                r2_c1, r2_c2 = st.columns(2)
                                with r2_c1:
                                    b_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key="batch_analysis")
                                with r2_c2:
                                    batch_analysis_val = st.session_state.get("batch_analysis", "미진행")
                                    if batch_analysis_val == "미진행":
                                        b_basal = st.selectbox("Basal Media", options=get_recipe_options(), key="batch_basal")
                                    else:
                                        b_basal = "-"
                                        st.text_input("Basal Media", value="-", disabled=True, key="batch_basal_disabled")

                                if batch_analysis_val == "미진행":
                                    num_b_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key="batch_num_pairs")
                                    b_comps, b_concs = [], []
                                    for i in range(0, int(num_b_pairs), 2):
                                        pair_cols = st.columns([2, 1, 2, 1])
                                        with pair_cols[0]:
                                            c_val = st.text_input(f"물질 #{i+1}", key=f"batch_c_{i}")
                                        with pair_cols[1]:
                                            n_val = st.text_input(f"농도 #{i+1}", key=f"batch_n_{i}")
                                        if c_val.strip():
                                            b_comps.append(c_val.strip())
                                            b_concs.append(n_val.strip())
                                            
                                        if i + 1 < int(num_b_pairs):
                                            with pair_cols[2]:
                                                c2_val = st.text_input(f"물질 #{i+2}", key=f"batch_c_{i+1}")
                                            with pair_cols[3]:
                                                n2_val = st.text_input(f"농도 #{i+2}", key=f"batch_n_{i+1}")
                                            if c2_val.strip():
                                                b_comps.append(c2_val.strip())
                                                b_concs.append(n2_val.strip())
                                    combined_compounds = ", ".join(b_comps)
                                    combined_concs = ", ".join(b_concs)
                                else:
                                    combined_compounds = f"분석 진행 ({batch_analysis_val})"
                                    combined_concs = ""

                                b_note = st.text_input("비고", key="batch_note")
                                b_file = st.file_uploader("📷 사진 일괄 첨부", type=["png", "jpg", "jpeg"], key="batch_file")

                                if st.button(f"💾 {len(selected_wells)}개 Well 일괄 저장", key="btn_batch_save", use_container_width=True, type="primary"):
                                    if combined_compounds:
                                        img_b64 = file_to_base64(b_file)
                                        comb_note = build_combined_note(b_basal, b_note, img_b64)
                                        
                                        for w in selected_wells:
                                            # [수정] 8개 인자 일치
                                            db.add_treatment(
                                                selected_plate['id'], w, str(b_date),
                                                combined_compounds, combined_concs, b_cell.strip(), comb_note, b_analysis
                                            )
                                        st.success(f"✅ 일괄 처리 저장 완료!")
                                        st.rerun()
                                    else:
                                        st.error("물질명을 입력해 주세요.")

                            with tab_sub_info:
                                for pos in selected_wells:
                                    if pos in well_all_map:
                                        st.markdown(f"**📍 Well {pos}** ({len(well_all_map[pos])}건)")

                    else:
                        st.info("💡 왼쪽 차트에서 Well을 선택하세요.")

                with edit_main_tab2:
                    row_summary = []
                    for r_label in row_labels:
                        row_treatments = [well_last_map[pos] for pos in well_last_map if pos.startswith(r_label)]
                        if row_treatments:
                            basal_list = sorted(list(set([get_basal_media(t) for t in row_treatments if get_basal_media(t) != "-"])))
                            basal_str = ", ".join(basal_list) if basal_list else "-"
                            cond_list = sorted(list(set([format_compound_summary(t['compound_name'], t['concentration']) for t in row_treatments])))
                            cond_str = " / ".join(cond_list)
                            cell_list = sorted(list(set([t['cell_info'] for t in row_treatments if t.get('cell_info')])))
                            cell_str = ", ".join(cell_list) if cell_list else "-"
                            analysis_list = sorted(list(set([t.get('analysis_status', '미진행') for t in row_treatments])))
                            analysis_str = ", ".join(analysis_list)
                            well_count = len(row_treatments)
                        else:
                            basal_str, cond_str, cell_str, analysis_str, well_count = "-", "미처리 (Empty)", "-", "-", 0
                        
                        row_summary.append({
                            "행": f"Row {r_label}", "처리 수": f"{well_count}/{cols}",
                            "Basal Media": basal_str, "세포 정보": cell_str, "분석진행": analysis_str, "실험 조건": cond_str
                        })

                    col_summary = []
                    for c_idx in range(1, cols + 1):
                        col_treatments = [well_last_map[pos] for pos in well_last_map if pos[1:] == str(c_idx)]
                        if col_treatments:
                            basal_list = sorted(list(set([get_basal_media(t) for t in col_treatments if get_basal_media(t) != "-"])))
                            basal_str = ", ".join(basal_list) if basal_list else "-"
                            cond_list = sorted(list(set([format_compound_summary(t['compound_name'], t['concentration']) for t in col_treatments])))
                            cond_str = " / ".join(cond_list)
                            cell_list = sorted(list(set([t['cell_info'] for t in col_treatments if t.get('cell_info')])))
                            cell_str = ", ".join(cell_list) if cell_list else "-"
                            analysis_list = sorted(list(set([t.get('analysis_status', '미진행') for t in col_treatments])))
                            analysis_str = ", ".join(analysis_list)
                            well_count = len(col_treatments)
                        else:
                            basal_str, cond_str, cell_str, analysis_str, well_count = "-", "미처리 (Empty)", "-", "-", 0
                        
                        col_summary.append({
                            "열": f"Col {c_idx}", "처리 수": f"{well_count}/{rows}",
                            "Basal Media": basal_str, "세포 정보": cell_str, "분석진행": analysis_str, "실험 조건": cond_str
                        })

                    sub_summary_t1, sub_summary_t2 = st.tabs(["📌 Row 기준", "📌 Column 기준"])
                    with sub_summary_t1: st.dataframe(pd.DataFrame(row_summary), use_container_width=True, hide_index=True)
                    with sub_summary_t2: st.dataframe(pd.DataFrame(col_summary), use_container_width=True, hide_index=True)

        # ======================================================================
        # [TAB 2] 계통도 탭
        # ======================================================================
        with tab_tree:
            st.caption("💡 세포/오가노이드 정보와 처리 일자 순서를 분석해 계통도를 시각화합니다.")[cite: 1]
            dot_code = generate_dynamic_lineage_dot(treatments)
            if dot_code:
                st.graphviz_chart(dot_code, use_container_width=True)
            else:
                st.info("💡 계통도를 그릴 세포 정보 데이터가 없습니다.")[cite: 1]

        # ======================================================================
        # [TAB 3] 물질/세포 처리 입력 및 전체 이력 관리
        # ======================================================================  
        with tab_treat:
            r1_c1, r1_c2 = st.columns(2)
            with r1_c1:
                t_date = st.date_input("처리 일자 (Date)", datetime.date.today(), key="t_date_main")
            with r1_c2:
                t_well = st.text_input("웰 위치 (Well Position)*", placeholder="예: A1, B2", key="t_well_main")

            t_cell = st.text_input("세포/오가노이드 정보", key="t_cell_main")

            r2_c1, r2_c2 = st.columns(2)
            with r2_c1:
                t_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key="t_analysis_main")
            t_analysis_val = st.session_state.get("t_analysis_main", "미진행")

            with r2_c2:
                if t_analysis_val == "미진행":
                    t_basal = st.selectbox("Basal Media", options=get_recipe_options(), key="t_basal_main")
                else:
                    t_basal = "-"
                    st.text_input("Basal Media", value="-", disabled=True, key="t_basal_main_disabled")

            if t_analysis_val == "미진행":
                num_t_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key="t_num_pairs_main")
                t_comps, t_concs = [], []
                for i in range(0, int(num_t_pairs), 2):
                    pair_cols = st.columns([2, 1, 2, 1])
                    with pair_cols[0]:
                        c_val = st.text_input(f"물질 #{i+1}", key=f"t_c_main_{i}")
                    with pair_cols[1]:
                        n_val = st.text_input(f"농도 #{i+1}", key=f"t_n_main_{i}")
                    if c_val.strip():
                        t_comps.append(c_val.strip())
                        t_concs.append(n_val.strip())

                    if i + 1 < int(num_t_pairs):
                        with pair_cols[2]:
                            c2_val = st.text_input(f"물질 #{i+2}", key=f"t_c_main_{i+1}")
                        with pair_cols[3]:
                            n2_val = st.text_input(f"농도 #{i+2}", key=f"t_n_main_{i+1}")
                        if c2_val.strip():
                            t_comps.append(c2_val.strip())
                            t_concs.append(n2_val.strip())
            else:
                t_comps = [f"분석 진행 ({t_analysis_val})"]
                t_concs = [""]

            t_note = st.text_input("비고", key="t_note_main")
            t_file = st.file_uploader("📷 사진 첨부", type=["png", "jpg", "jpeg"], key="t_file_upload_main")

            if st.button("처리 내역 및 사진 저장", use_container_width=True, type="primary", key="btn_t_main_save"):
                if t_well.strip() and t_comps:
                    wells = [w.strip().upper() for w in t_well.split(",") if w.strip()]
                    combined_compounds = ", ".join(t_comps)
                    combined_concs = ", ".join(t_concs)
                    img_b64 = file_to_base64(t_file)
                    comb_note = build_combined_note(t_basal, t_note, img_b64)

                    for w in wells:
                        # [수정] 8개 인자 일치
                        db.add_treatment(
                            selected_plate['id'], w, str(t_date),
                            combined_compounds, combined_concs, t_cell.strip(), comb_note, t_analysis
                        )
                    st.success(f"{len(wells)}개 웰 기록 완료!")
                    st.rerun()
                else:
                    st.error("웰 위치와 물질명을 확인해 주세요.")[cite: 1]

            st.markdown("---")
            st.subheader("📋 전체 물질 처리 이력 관리")

            if treatments:
                batch_col1, batch_col2 = st.columns(2)
                with batch_col1:
                    batch_update_btn = st.button("💾 선택한 항목 일괄 저장", type="primary", use_container_width=True)
                with batch_col2:
                    batch_delete_btn = st.button("🗑️ 선택한 항목 일괄 삭제", type="secondary", use_container_width=True)

                st.markdown("")
                list_cols = st.columns(2)
                to_delete_ids = []
                to_update_data = []

                for idx, item in enumerate(treatments):
                    with list_cols[idx % 2]:
                        b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)
                        img_flag = "📷 " if cur_img_b64 else ""
                        formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                        analysis_lbl = item.get('analysis_status', '미진행')

                        with st.expander(f"{img_flag}📍 Well [{item['well_position']}] | 📅 {item['treatment_date']} | 🧬 {item.get('cell_info', '-')} ({analysis_lbl})"):
                            is_selected = st.checkbox("선택 (일괄 처리용)", key=f"chk_select_{item['id']}")

                            try:
                                default_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                            except:
                                default_d = datetime.date.today()

                            r1_c1, r1_c2 = st.columns(2)
                            with r1_c1:
                                e_date = st.date_input("처리 일자", value=default_d, key=f"t_e_date_{item['id']}")
                            with r1_c2:
                                e_pos = st.text_input("웰 위치", value=item['well_position'], key=f"t_e_pos_{item['id']}")

                            e_cell = st.text_input("세포 정보", value=item['cell_info'] if item['cell_info'] else "", key=f"t_e_cell_{item['id']}")
                            e_cur_analysis = item.get('analysis_status', '미진행')
                            e_a_idx = ANALYSIS_OPTIONS.index(e_cur_analysis) if e_cur_analysis in ANALYSIS_OPTIONS else 0

                            r2_c1, r2_c2 = st.columns(2)
                            with r2_c1:
                                e_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, index=e_a_idx, key=f"t_e_analysis_{item['id']}")
                            e_cur_s_analysis = st.session_state.get(f"t_e_analysis_{item['id']}", e_cur_analysis)

                            with r2_c2:
                                if e_cur_s_analysis == "미진행":
                                    e_b_opts = get_recipe_options(b_media_val)
                                    e_b_idx = e_b_opts.index(b_media_val) if b_media_val in e_b_opts else 0
                                    e_basal = st.selectbox("Basal Media", options=e_b_opts, index=e_b_idx, key=f"t_e_basal_{item['id']}")
                                else:
                                    e_basal = "-"
                                    st.text_input("Basal Media", value="-", disabled=True, key=f"t_e_basal_disabled_{item['id']}")

                            if e_cur_s_analysis == "미진행":
                                e_existing_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                                e_existing_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                                e_num_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=max(1, len(e_existing_comps)), key=f"t_e_num_pairs_{item['id']}")

                                e_comps, e_concs = [], []
                                for sub_idx in range(0, int(e_num_pairs), 2):
                                    pair_cols = st.columns([2, 1, 2, 1])
                                    def_c = e_existing_comps[sub_idx] if sub_idx < len(e_existing_comps) else ""
                                    def_n = e_existing_concs[sub_idx] if sub_idx < len(e_existing_concs) else ""

                                    with pair_cols[0]:
                                        c_val = st.text_input(f"물질 #{sub_idx+1}", value=def_c, key=f"t_e_c_{item['id']}_{sub_idx}")
                                    with pair_cols[1]:
                                        n_val = st.text_input(f"농도 #{sub_idx+1}", value=def_n, key=f"t_e_n_{item['id']}_{sub_idx}")
                                    if c_val.strip():
                                        e_comps.append(c_val.strip())
                                        e_concs.append(n_val.strip())

                                    if sub_idx + 1 < int(e_num_pairs):
                                        def_c2 = e_existing_comps[sub_idx+1] if sub_idx+1 < len(e_existing_comps) else ""
                                        def_n2 = e_existing_concs[sub_idx+1] if sub_idx+1 < len(e_existing_concs) else ""
                                        with pair_cols[2]:
                                            c2_val = st.text_input(f"물질 #{sub_idx+2}", value=def_c2, key=f"t_e_c_{item['id']}_{sub_idx+1}")
                                        with pair_cols[3]:
                                            n2_val = st.text_input(f"농도 #{sub_idx+2}", value=def_n2, key=f"t_e_n_{item['id']}_{sub_idx+1}")
                                        if c2_val.strip():
                                            e_comps.append(c2_val.strip())
                                            e_concs.append(n2_val.strip())
                                e_comp = ", ".join(e_comps)
                                e_conc = ", ".join(e_concs)
                            else:
                                e_comp = f"분석 진행 ({e_cur_s_analysis})"
                                e_conc = ""

                            e_note = st.text_input("비고", value=pure_note_val, key=f"t_e_note_{item['id']}")
                            if cur_img_b64:
                                display_image_from_b64(cur_img_b64, caption="등록된 이미지")
                                del_img = st.checkbox("사진 삭제", key=f"chk_del_t_{item['id']}")
                            else:
                                del_img = False

                            new_img = st.file_uploader("사진 교체/추가", type=["png", "jpg", "jpeg"], key=f"f_e_{item['id']}")

                            btn_c1, btn_c2 = st.columns(2)
                            with btn_c1:
                                if st.button("💾 개별 저장", key=f"btn_t_update_{item['id']}", use_container_width=True):
                                    final_img_b64 = cur_img_b64
                                    if del_img:
                                        final_img_b64 = None
                                    if new_img is not None:
                                        final_img_b64 = file_to_base64(new_img)

                                    comb_note = build_combined_note(e_basal, e_note, final_img_b64)
                                    # [수정] 8개 인자 일치
                                    db.update_treatment(
                                        item['id'], e_pos.strip().upper(), str(e_date),
                                        e_comp.strip(), e_conc.strip(), e_cell.strip(), comb_note, e_analysis
                                    )
                                    st.toast("수정되었습니다!", icon="✅")
                                    st.rerun()
                            with btn_c2:
                                if st.button("🗑️ 개별 삭제", key=f"btn_t_del_{item['id']}", type="secondary", use_container_width=True):
                                    db.delete_treatment(item['id'])
                                    st.toast("삭제되었습니다.", icon="🗑️")
                                    st.rerun()

                            if is_selected:
                                final_img_b64 = cur_img_b64
                                if del_img:
                                    final_img_b64 = None
                                if new_img is not None:
                                    final_img_b64 = file_to_base64(new_img)

                                comb_note = build_combined_note(e_basal, e_note, final_img_b64)
                                to_update_data.append({
                                    'id': item['id'], 'pos': e_pos.strip().upper(), 'date': str(e_date),
                                    'comp': e_comp.strip(), 'conc': e_conc.strip(), 'cell': e_cell.strip(),
                                    'note': comb_note, 'analysis': e_analysis
                                })
                                to_delete_ids.append(item['id'])

                if batch_update_btn:
                    if to_update_data:
                        for d in to_update_data:
                            # [수정] 8개 인자 일치
                            db.update_treatment(
                                d['id'], d['pos'], d['date'],
                                d['comp'], d['conc'], d['cell'], d['note'], d['analysis']
                            )
                        st.success(f"선택된 {len(to_update_data)}개 항목 일괄 수정 완료!")
                        st.rerun()
                    else:
                        st.warning("수정(체크)된 항목이 없습니다.")

                if batch_delete_btn:
                    if to_delete_ids:
                        for d_id in to_delete_ids:
                            db.delete_treatment(d_id)
                        st.success(f"선택된 {len(to_delete_ids)}개 항목 일괄 삭제 완료!")
                        st.rerun()
                    else:
                        st.warning("삭제(체크)된 항목이 없습니다.")
            else:
                st.caption("아직 처리된 내역이 없습니다.")

        # ======================================================================
        # [TAB 4] 사진 비교 시각화
        # ======================================================================
        with tab_compare:
            st.caption("💡 등록된 현미경 사진들을 시간 흐름 또는 조건별로 비교합니다.")[cite: 1]
            treatments_with_img = []
            for t in treatments:
                b_media, pure_note, img_b64 = parse_note_basal_image(t)
                if img_b64:
                    t_copy = dict(t)
                    t_copy['parsed_basal'] = b_media
                    t_copy['parsed_note'] = pure_note
                    t_copy['img_b64'] = img_b64
                    treatments_with_img.append(t_copy)

            if not treatments_with_img:
                st.warning("🖼️ 현재 플레이트에 등록된 현미경 사진이 없습니다.")
            else:
                compare_mode = st.radio("📌 비교 방식", ["📅 날짜별 변화 비교", "🧪 조건별 결과 비교"], horizontal=True)
                grid_cols_count = st.slider("📐 한 줄에 표시할 사진 개수", min_value=2, max_value=6, value=3)

                if compare_mode.startswith("📅"):
                    all_wells_with_img = sorted(list(set([t['well_position'] for t in treatments_with_img])))
                    selected_compare_well = st.selectbox("🎯 비교할 Well 선택", all_wells_with_img)
                    well_img_list = sorted([t for t in treatments_with_img if t['well_position'] == selected_compare_well], key=lambda x: x['treatment_date'])

                    img_cols = st.columns(grid_cols_count)
                    for idx, t_item in enumerate(well_img_list):
                        with img_cols[idx % grid_cols_count]:
                            st.markdown(f"**📅 {t_item['treatment_date']}**")
                            display_image_from_b64(t_item['img_b64'], caption=f"{t_item['treatment_date']}")
                else:
                    all_dates_with_img = sorted(list(set([t['treatment_date'] for t in treatments_with_img])))
                    selected_compare_date = st.selectbox("📅 비교할 날짜 선택", all_dates_with_img)
                    date_img_list = sorted([t for t in treatments_with_img if t['treatment_date'] == selected_compare_date], key=lambda x: x['well_position'])

                    img_cols = st.columns(grid_cols_count)
                    for idx, t_item in enumerate(date_img_list):
                        with img_cols[idx % grid_cols_count]:
                            st.markdown(f"**📍 Well {t_item['well_position']}**")
                            display_image_from_b64(t_item['img_b64'], caption=f"Well {t_item['well_position']}")

        # ======================================================================
        # [TAB 5] 연구 데일리 로그
        # ======================================================================
        with tab_log:
            st.caption(f"💡 현재 프로젝트(**{selected_proj['name']}**)의 관찰 일지 기록")[cite: 1]
            with st.container(border=True):
                st.markdown("##### 📝 새 데일리 로그 작성")
                log_date = st.date_input("로그 일자", datetime.date.today(), key="daily_log_date_input")
                log_content = st.text_area("내용", key="daily_log_content_input")
                if st.button("로그 추가", use_container_width=True, type="primary", key="btn_add_log"):
                    if log_content.strip():
                        db.add_daily_log(selected_proj['id'], str(log_date), log_content.strip())
                        st.success("등록되었습니다.")
                        st.rerun()

            st.markdown("---")
            logs = db.get_daily_logs(selected_proj['id'])
            if logs:
                log_cols = st.columns(2)
                for idx, log in enumerate(logs):
                    with log_cols[idx % 2]:
                        with st.container(border=True):
                            st.markdown(f"**📅 {log['log_date']}**")
                            st.info(log['content'])
                            if st.button("🗑️ 삭제", key=f"btn_del_log_{log['id']}", use_container_width=True):
                                db.delete_daily_log(log['id'])
                                st.rerun()
            else:
                st.caption("아직 등록된 로그가 없습니다.")
