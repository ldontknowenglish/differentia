import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import base64
import db
import style

st.set_page_config(page_title="Plates & Wells Visualizer", page_icon="🧫", layout="wide")
style.set_narrow_layout()
st.title("🧫 시각화 및 물질 처리 관리")

# ======================================================================
# [이미지 및 데이터 파싱 헬퍼 함수]
# ======================================================================
def file_to_base64(uploaded_file):
    """업로드된 이미지 파일을 Base64 문자열로 변환"""
    if uploaded_file is None:
        return None
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode('utf-8')

def extract_image_data(item):
    """item에서 이미지 base64 데이터 추출 (DB 컬럼 또는 note 파싱)"""
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
    
    # note에서 Media 태그와 IMG_DATA 태그 제거
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
    if basal and basal.strip():
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

def generate_dynamic_lineage_dot(treatments):
    """사용자가 입력한 treatments 데이터의 cell_info와 날짜 순서를 분석해 Graphviz DOT 생성"""
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
    """물질명과 농도 문자열을 1:1 매칭하여 '물질 농도' 형태로 정형화 (예: egf 10ng/ml, fgf 100ng/ml)"""
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


db.init_db()
projects = db.get_projects()

if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다. 먼저 **'1. Experiments(프로젝트 관리)'** 메뉴에서 프로젝트를 생성해 주세요.")
else:
    proj_map = {f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID: {p['id']})": p for p in projects}
    options = list(proj_map.keys())

    if "selected_plate_proj_label" not in st.session_state or st.session_state.selected_plate_proj_label not in options:
        st.session_state.selected_plate_proj_label = options[0]

    # === [상단 2열 레이아웃: Left 프로젝트 선택 | Right 작업 대상 플레이트 선택] ===
    col_proj, col_plate = st.columns([1, 1], gap="large")

    with col_proj:
        selected_label = st.selectbox("📌 프로젝트 선택", options=options, key="selected_plate_proj_label")
        selected_proj = proj_map[selected_label]

        st.markdown(
            f"""
            <div style="padding:10px 14px; border-left: 6px solid {selected_proj['color_code']}; background-color: #f8fafc; border-radius: 6px; margin-top: 4px;">
                <p style="margin:0; color:#0f172a; font-weight:bold; font-size:15px;">{selected_proj['name']}</p>
                <p style="margin:2px 0 0 0; color:#475569; font-size:13px;"><b>그룹:</b> {selected_proj['group_name']} | <b>설명:</b> {selected_proj['description'] if selected_proj['description'] else '없음'}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    plates = db.get_plates(selected_proj['id'])

    with col_plate:
        if plates:
            plate_dict = {f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)": pl for pl in plates}
            c_pl1, c_pl2 = st.columns([3, 1])
            with c_pl1:
                selected_plate_name = st.selectbox("🧫 작업 대상 플레이트 선택", list(plate_dict.keys()), key="selected_plate_select")
                selected_plate = plate_dict[selected_plate_name]
            with c_pl2:
                st.write(" ")
                st.write(" ")
                if st.button("🗑️ 삭제", type="secondary", use_container_width=True, key="btn_del_plate_top"):
                    db.delete_plate(selected_plate['id'])
                    st.toast("플레이트가 휴지통으로 이동되었습니다. (📥 복구 가능)", icon="🗑️")
                    st.rerun()
        else:
            st.info("💡 선택된 프로젝트에 등록된 플레이트가 없습니다. 아래에서 새 규격 플레이트를 만들어 주세요.")
            selected_plate = None

    PLATE_PRESETS = {
        "96-Well Plate (8 x 12)": (8, 12),
        "48-Well Plate (6 x 8)": (6, 8),
        "24-Well Plate (4 x 6)": (4, 6),
        "12-Well Plate (3 x 4)": (3, 4),
        "6-Well Plate (2 x 3)": (2, 3),
        "⚙️ 사용자 지정 (Custom)": "custom"
    }

    with st.expander("➕ 새 규격 플레이트 생성", expanded=not bool(plates)):
        with st.form("add_plate_form", clear_on_submit=True):
            p_cols1, p_cols2 = st.columns([3, 2])
            with p_cols1:
                plate_name = st.text_input("플레이트 이름*", placeholder="예: 96-Well Plate #1 (오가노이드 배양)")
            with p_cols2:
                selected_preset_label = st.selectbox("🧫 플레이트 표준 규격 선택*", list(PLATE_PRESETS.keys()))

            if PLATE_PRESETS[selected_preset_label] == "custom":
                c1, c2 = st.columns(2)
                with c1:
                    p_rows = st.number_input("행 개수 (Rows)", min_value=1, max_value=16, value=8)
                with c2:
                    p_cols = st.number_input("열 개수 (Cols)", min_value=1, max_value=24, value=12)
            else:
                p_rows, p_cols = PLATE_PRESETS[selected_preset_label]
                st.caption(f"💡 선택된 규격: **{p_rows} 행 x {p_cols} 열** (총 {p_rows * p_cols} Wells)")

            p_submit = st.form_submit_button("플레이트 추가", use_container_width=True)
            if p_submit:
                if plate_name.strip():
                    db.add_plate(selected_proj['id'], plate_name.strip(), p_rows, p_cols)
                    st.success(f"'{plate_name}' ({p_rows}x{p_cols} Well) 플레이트가 생성되었습니다.")
                    st.rerun()
                else:
                    st.error("플레이트 이름을 입력해 주세요.")

    if selected_plate:
        treatments = db.get_treatments_by_plate(selected_plate['id'])
        
        # 4개 탭 구성 (사진 비교 탭 추가)
        tab_view, tab_tree, tab_treat, tab_compare = st.tabs([
            "🔴 Plotly 원형 Well Plate 시각화 & 편집", 
            "🌳 사용자 데이터 기반 계통도", 
            "📝 날짜별 물질/세포 처리 입력 및 전체 관리",
            "📸 날짜별 & 조건별 사진 비교 시각화"
        ])

        # ======================================================================
        # [TAB 1] Plotly 시각화 및 편집
        # ======================================================================
        with tab_view:
            st.subheader("🔴 규격별 Plotly 2D 원형 Well Plate 인터랙티브 시각화 & 편집")
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
                    color_by = st.radio("🎨 색상 기준", ["주요 물질별", "처리 유무별"], horizontal=True, key="v_color_radio")

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
                unique_compounds = sorted(list(set([t['compound_name'].split(',')[0].strip() for t in treatments if t.get('compound_name')]))) if treatments else []
                compound_color_map = {comp: palette[i % len(palette)] for i, comp in enumerate(unique_compounds)}

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
                            main_comp = item['compound_name'].split(',')[0].strip() if item.get('compound_name') else "기타"
                            color = compound_color_map.get(main_comp, "#3B82F6") if color_by == "주요 물질별" else "#10B981"
                            
                            has_img = "📷 사진 유" if extract_image_data(item) else ""
                            comp_short = main_comp[:5]
                            text_labels.append(f"<b>{pos}</b><br>{comp_short}")
                            
                            basal_text = get_basal_media(item)
                            treatment_summary = format_compound_summary(item['compound_name'], item['concentration'])
                            hover_html = (
                                f"<b>[Well {pos}]</b> {has_img}<br>"
                                f"🥛 <b>Basal Media:</b> {basal_text}<br>"
                                f"🧪 <b>처리 조건:</b> {treatment_summary}<br>"
                                f"📅 <b>일자:</b> {item['treatment_date']}<br>"
                                f"🧫 <b>세포:</b> {item.get('cell_info', '-')}"
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
                    plot_bgcolor='#f1f5f9', paper_bgcolor='#ffffff', height=max(420, rows * 55), margin=dict(l=40, r=40, t=50, b=40)
                )

                plotly_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode=["points", "box", "lasso"])

                if unique_compounds and color_by == "주요 물질별":
                    st.markdown("##### 🏷️ 주요 물질별 색상 범례")
                    leg_cols = st.columns(min(len(unique_compounds), 3))
                    for idx, (comp, c_color) in enumerate(compound_color_map.items()):
                        with leg_cols[idx % 3]:
                            st.markdown(
                                f"""<div style="display:flex; align-items:center; background:#f8fafc; padding:4px 8px; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:6px;">
                                    <div style="width:12px; height:12px; background-color:{c_color}; border-radius:50%; margin-right:6px; border:1px solid #1e293b;"></div>
                                    <span style="font-size:12px; font-weight:bold; color:#0f172a;">{comp}</span>
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
                                    with st.expander(f"📅 {item['treatment_date']} | 🧪 {formatted_cond}", expanded=True):
                                        try:
                                            def_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                                        except:
                                            def_d = datetime.date.today()

                                        b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)

                                        mod_d = st.date_input("처리 일자", value=def_d, key=f"s_date_{item['id']}")
                                        mod_pos = st.text_input("웰 위치", value=item['well_position'], key=f"s_pos_{item['id']}")
                                        mod_basal = st.text_input("Basal Media", value=b_media_val, placeholder="예: mTeSR1", key=f"s_basal_{item['id']}")
                                        mod_comp = st.text_input("처리 물질", value=item['compound_name'], key=f"s_comp_{item['id']}")
                                        mod_conc = st.text_input("농도", value=item['concentration'] if item['concentration'] else "", key=f"s_conc_{item['id']}")
                                        mod_cell = st.text_input("세포 정보", value=item.get('cell_info', ''), key=f"s_cell_{item['id']}")
                                        mod_note = st.text_input("비고 / 상세 조건", value=pure_note_val, key=f"s_note_{item['id']}")

                                        # --- 이미지 관리 ---
                                        st.caption("📷 **현미경 / 결과 사진 관리**")
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
                                                db.update_treatment(
                                                    item['id'], mod_pos.strip().upper(), str(mod_d),
                                                    mod_comp.strip(), mod_conc.strip(), mod_cell.strip(), comb_note
                                                )
                                                st.toast("수정 사항이 성공적으로 저장되었습니다!", icon="✅")
                                                st.rerun()
                                        with b_del:
                                            if st.button("🗑️ 삭제", key=f"btn_s_del_{item['id']}", type="secondary", use_container_width=True):
                                                db.delete_treatment(item['id'])
                                                st.toast("삭제되었습니다.", icon="🗑️")
                                                st.rerun()

                                with st.expander(f"➕ Well [{pos}]에 추가 처리 및 사진 작성", expanded=False):
                                    with st.form(key=f"add_extra_{pos}"):
                                        ex_d = st.date_input("처리 일자", datetime.date.today(), key=f"ex_d_{pos}")
                                        ex_basal = st.text_input("Basal Media", placeholder="예: mTeSR1", key=f"ex_basal_{pos}")
                                        ex_comp = st.text_input("처리 물질명*", placeholder="예: VEGF, FGF2", key=f"ex_comp_{pos}")
                                        ex_conc = st.text_input("농도", placeholder="예: 50 ng/mL", key=f"ex_conc_{pos}")
                                        ex_cell = st.text_input("세포 정보", placeholder="예: iPSC", key=f"ex_cell_{pos}")
                                        ex_note = st.text_input("비고", placeholder="상세 조건", key=f"ex_note_{pos}")
                                        ex_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"ex_file_{pos}")

                                        if st.form_submit_button(f"💾 Well [{pos}] 추가 저장", use_container_width=True):
                                            if ex_comp.strip():
                                                img_b64 = file_to_base64(ex_file)
                                                comb_note = build_combined_note(ex_basal, ex_note, img_b64)
                                                db.add_treatment(
                                                    selected_plate['id'], pos, str(ex_d),
                                                    ex_comp.strip(), ex_conc.strip(), ex_cell.strip(), comb_note
                                                )
                                                st.toast(f"Well [{pos}] 추가 처리가 저장되었습니다!", icon="✅")
                                                st.rerun()
                                            else:
                                                st.error("처리 물질명을 입력해 주세요.")
                            else:
                                st.markdown(f"##### ➕ Well [{pos}] 신규 물질 처리 및 사진 작성")
                                st.caption("선택하신 Well은 현재 미처리 상태입니다. 신규 조건과 사진을 등록해 주세요.")

                                with st.form(key=f"add_empty_form_{pos}"):
                                    e_col1, e_col2 = st.columns(2)
                                    with e_col1:
                                        e_d = st.date_input("처리 일자", datetime.date.today(), key=f"e_d_{pos}")
                                        e_basal = st.text_input("Basal Media", placeholder="예: mTeSR1", key=f"e_basal_{pos}")
                                    with e_col2:
                                        e_cell = st.text_input("세포/오가노이드 정보", placeholder="예: DE, HIO", key=f"e_cell_{pos}")
                                        e_note = st.text_input("비고 / 상세 조건", placeholder="예: Daily media change", key=f"e_note_{pos}")

                                    st.caption("🧪 **처리 물질 및 농도**")
                                    num_e_items = st.number_input("입력할 물질 개수", min_value=1, max_value=10, value=2, key=f"e_num_{pos}")
                                    
                                    e_comps, e_concs = [], []
                                    for idx in range(int(num_e_items)):
                                        m1, m2 = st.columns([2, 1])
                                        with m1:
                                            c_val = st.text_input("물질", placeholder="예: VEGF" if idx==0 else "추가 물질 입력", key=f"e_c_{pos}_{idx}")
                                        with m2:
                                            n_val = st.text_input("농도", placeholder="예: 50 ng/mL" if idx==0 else "추가 농도 입력", key=f"e_n_{pos}_{idx}")
                                        if c_val.strip():
                                            e_comps.append(c_val.strip())
                                            e_concs.append(n_val.strip())

                                    e_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"e_file_{pos}")

                                    if st.form_submit_button(f"💾 Well [{pos}] 처리 저장", use_container_width=True, type="primary"):
                                        if e_comps:
                                            comb_comp = ", ".join(e_comps)
                                            comb_conc = ", ".join(e_concs)
                                            img_b64 = file_to_base64(e_file)
                                            comb_note = build_combined_note(e_basal, e_note, img_b64)
                                            
                                            db.add_treatment(
                                                selected_plate['id'], pos, str(e_d),
                                                comb_comp, comb_conc, e_cell.strip(), comb_note
                                            )
                                            st.success(f"✅ Well [{pos}] 처리가 저장되었습니다!")
                                            st.rerun()
                                        else:
                                            st.error("최소 하나 이상의 물질명을 입력해 주세요.")

                        else:
                            st.success(f"🎯 총 **{len(selected_wells)}개** Well 선택됨: `{', '.join(selected_wells)}`")
                            tab_sub_batch, tab_sub_info = st.tabs(["✏️ 선택 Well 일괄 물질 처리", "📝 선택 Well 개별 수정/조회"])

                            with tab_sub_batch:
                                st.caption("💡 선택된 모든 Well에 동일한 배지 및 물질 처리를 일괄 저장합니다.")
                                
                                with st.form("batch_treatment_form", clear_on_submit=False):
                                    b_col1, b_col2 = st.columns(2)
                                    with b_col1:
                                        b_date = st.date_input("처리 일자", datetime.date.today(), key="batch_date")
                                        b_basal = st.text_input("Basal Media", placeholder="예: mTeSR1", key="batch_basal")
                                    with b_col2:
                                        b_cell = st.text_input("세포/오가노이드 정보", placeholder="예: DE, HIO", key="batch_cell")
                                        b_note = st.text_input("비고 / 상세 조건", placeholder="예: Medium change", key="batch_note")
                                    
                                    st.caption("🧪 **처리 물질 및 농도**")
                                    num_b_items = st.number_input("입력할 물질 개수", min_value=1, max_value=10, value=2, key="batch_num_items")
                                    
                                    b_comps, b_concs = [], []
                                    for idx in range(int(num_b_items)):
                                        m1, m2 = st.columns([2, 1])
                                        with m1:
                                            c_val = st.text_input("물질", placeholder="예: VEGF" if idx==0 else "추가 물질 입력", key=f"batch_c_{idx}")
                                        with m2:
                                            n_val = st.text_input("농도", placeholder="예: 50 ng/mL" if idx==0 else "추가 농도 입력", key=f"batch_n_{idx}")
                                        if c_val.strip():
                                            b_comps.append(c_val.strip())
                                            b_concs.append(n_val.strip())

                                    b_file = st.file_uploader("📷 현미경 사진 일괄 첨부 (선택)", type=["png", "jpg", "jpeg"], key="batch_file")

                                    if st.form_submit_button(f"💾 선택한 {len(selected_wells)}개 Well에 일괄 저장", use_container_width=True, type="primary"):
                                        if b_comps:
                                            combined_compounds = ", ".join(b_comps)
                                            combined_concs = ", ".join(b_concs)
                                            img_b64 = file_to_base64(b_file)
                                            comb_note = build_combined_note(b_basal, b_note, img_b64)
                                            
                                            for w in selected_wells:
                                                db.add_treatment(
                                                    selected_plate['id'], w, str(b_date),
                                                    combined_compounds, combined_concs, b_cell.strip(), comb_note
                                                )
                                            st.success(f"✅ {len(selected_wells)}개 Well에 일괄 처리 저장 완료!")
                                            st.rerun()
                                        else:
                                            st.error("적어도 하나 이상의 처리 물질명을 입력해 주세요.")

                            with tab_sub_info:
                                for pos in selected_wells:
                                    if pos in well_all_map:
                                        items = well_all_map[pos]
                                        st.markdown(f"**📍 Well {pos}** ({len(items)}건 이력)")
                                        for item in items:
                                            formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                                            with st.expander(f"📅 {item['treatment_date']} | 🧪 {formatted_cond}", expanded=False):
                                                b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)
                                                if cur_img_b64:
                                                    display_image_from_b64(cur_img_b64, caption=f"Well {pos} 사진")
                                    else:
                                        st.markdown(f"**📍 Well {pos}** (미처리)")

                    else:
                        st.info("💡 왼쪽 차트에서 Well을 클릭하거나 마우스로 영역을 드래그(Box/Lasso)하세요.")

                # 2) 행/열 배치 요약 탭
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
                            well_count = len(row_treatments)
                        else:
                            basal_str, cond_str, cell_str, well_count = "-", "미처리 (Empty)", "-", 0
                        
                        row_summary.append({
                            "행": f"Row {r_label}", "처리 수": f"{well_count}/{cols}",
                            "Basal Media": basal_str, "실험 조건": cond_str, "세포 정보": cell_str
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
                            well_count = len(col_treatments)
                        else:
                            basal_str, cond_str, cell_str, well_count = "-", "미처리 (Empty)", "-", 0
                        
                        col_summary.append({
                            "열": f"Col {c_idx}", "처리 수": f"{well_count}/{rows}",
                            "Basal Media": basal_str, "실험 조건": cond_str, "세포 정보": cell_str
                        })

                    sub_summary_t1, sub_summary_t2 = st.tabs(["📌 Row (행) 기준 요약", "📌 Column (열) 기준 요약"])
                    with sub_summary_t1: st.dataframe(pd.DataFrame(row_summary), use_container_width=True, hide_index=True)
                    with sub_summary_t2: st.dataframe(pd.DataFrame(col_summary), use_container_width=True, hide_index=True)

        # ======================================================================
        # [TAB 2] 계통도 탭
        # ======================================================================
        with tab_tree:
            st.subheader("🌳 작성 데이터 기반 자동 생성 계통도 (Lineage Tree)")
            st.caption("💡 작성하신 **`세포/오가노이드 정보`**와 **`처리 일자`**의 순서를 자동으로 분석하여 가로형 계통도로 시각화합니다.")
            
            dot_code = generate_dynamic_lineage_dot(treatments)
            if dot_code:
                st.graphviz_chart(dot_code, use_container_width=True)
            else:
                st.info("💡 계통도를 그릴 세포 정보 데이터가 없습니다.")

        # ======================================================================
        # [TAB 3] 물질/세포 처리 입력 및 전체 이력 관리
        # ======================================================================
        with tab_treat:
            st.subheader("📝 웰(Well) 별 날짜/배지/물질 처리 및 사진 기록 추가")
            
            with st.form("add_treatment_form", clear_on_submit=False):
                col_t1, col_t2 = st.columns([1.2, 1.8])
                with col_t1:
                    t_date = st.date_input("처리 일자 (Date)", datetime.date.today())
                    t_well = st.text_input("웰 위치 (Well Position)*", placeholder="예: A1, B2 또는 A1,A2,A3")
                    t_basal = st.text_input("Basal Media (기본 배지)", placeholder="예: mTeSR1, DMEM/F12")
                    t_cell = st.text_input("세포/오가노이드 정보", placeholder="예: iPSC, DE, HIO")
                    t_note = st.text_input("비고 / 상세 조건", placeholder="예: Medium change")
                
                with col_t2:
                    st.caption("🧪 **처리 물질 및 농도 입력**")
                    num_t_items = st.number_input("입력할 물질 개수", min_value=1, max_value=10, value=2, key="t_num_items")
                    
                    t_comps, t_concs = [], []
                    for idx in range(int(num_t_items)):
                        c_col1, c_col2 = st.columns([2, 1])
                        with c_col1:
                            c_val = st.text_input("물질", placeholder="예: VEGF" if idx==0 else "추가 물질 입력", key=f"t_c_{idx}")
                        with c_col2:
                            n_val = st.text_input("농도", placeholder="예: 50 ng/mL" if idx==0 else "추가 농도 입력", key=f"t_n_{idx}")
                        if c_val.strip():
                            t_comps.append(c_val.strip())
                            t_concs.append(n_val.strip())

                    t_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key="t_file_upload")

                t_submit = st.form_submit_button("처리 내역 및 사진 저장", use_container_width=True, type="primary")
                if t_submit:
                    if t_well.strip() and t_comps:
                        wells = [w.strip().upper() for w in t_well.split(",") if w.strip()]
                        combined_compounds = ", ".join(t_comps)
                        combined_concs = ", ".join(t_concs)
                        img_b64 = file_to_base64(t_file)
                        comb_note = build_combined_note(t_basal, t_note, img_b64)
                        
                        for w in wells:
                            db.add_treatment(
                                selected_plate['id'], w, str(t_date),
                                combined_compounds, combined_concs, t_cell.strip(), comb_note
                            )
                        st.success(f"{len(wells)}개 웰({', '.join(wells)})에 기록 완료!")
                        st.rerun()
                    else:
                        st.error("웰 위치와 최소 하나 이상의 물질명을 필수 입력해 주세요.")

            st.markdown("---")
            st.subheader("📋 전체 물질 처리 이력 관리 (수정/삭제/사진관리)")
            if treatments:
                list_cols = st.columns(2)
                for idx, item in enumerate(treatments):
                    with list_cols[idx % 2]:
                        b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)
                        img_flag = "📷 " if cur_img_b64 else ""
                        formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                        with st.expander(f"{img_flag}📍 Well [{item['well_position']}] | 📅 {item['treatment_date']} | 🧪 {formatted_cond}"):
                            try:
                                default_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                            except:
                                default_d = datetime.date.today()

                            e_date = st.date_input("처리 일자", value=default_d, key=f"t_e_date_{item['id']}")
                            e_pos = st.text_input("웰 위치", value=item['well_position'], key=f"t_e_pos_{item['id']}")
                            e_basal = st.text_input("Basal Media", value=b_media_val, key=f"t_e_basal_{item['id']}")
                            e_comp = st.text_input("물질/약물 조합", value=item['compound_name'], key=f"t_e_comp_{item['id']}")
                            e_conc = st.text_input("처리 농도", value=item['concentration'] if item['concentration'] else "", key=f"t_e_conc_{item['id']}")
                            e_cell = st.text_input("세포 정보", value=item['cell_info'] if item['cell_info'] else "", key=f"t_e_cell_{item['id']}")
                            e_note = st.text_input("비고 / 상세 조건", value=pure_note_val, key=f"t_e_note_{item['id']}")

                            if cur_img_b64:
                                display_image_from_b64(cur_img_b64, caption="등록된 이미지")
                                del_img = st.checkbox("사진 삭제", key=f"chk_del_t_{item['id']}")
                            else:
                                del_img = False

                            new_img = st.file_uploader("사진 교체/추가", type=["png", "jpg", "jpeg"], key=f"f_e_{item['id']}")

                            btn_c1, btn_c2 = st.columns(2)
                            with btn_c1:
                                if st.button("💾 저장", key=f"btn_t_update_{item['id']}", use_container_width=True):
                                    final_img_b64 = cur_img_b64
                                    if del_img:
                                        final_img_b64 = None
                                    if new_img is not None:
                                        final_img_b64 = file_to_base64(new_img)

                                    comb_note = build_combined_note(e_basal, e_note, final_img_b64)
                                    db.update_treatment(
                                        item['id'], e_pos.strip().upper(), str(e_date),
                                        e_comp.strip(), e_conc.strip(), e_cell.strip(), comb_note
                                    )
                                    st.toast("수정되었습니다!", icon="✅")
                                    st.rerun()
                            with btn_c2:
                                if st.button("🗑️ 삭제", key=f"btn_t_del_{item['id']}", type="secondary", use_container_width=True):
                                    db.delete_treatment(item['id'])
                                    st.toast("삭제되었습니다.", icon="🗑️")
                                    st.rerun()
            else:
                st.caption("아직 처리된 내역이 없습니다.")

        # ======================================================================
        # [TAB 4] 날짜별 및 조건별 사진 비교 시각화 (신규 기능)
        # ======================================================================
        with tab_compare:
            st.subheader("📸 날짜별 및 조건별 현미경/결과 사진 비교 시각화")
            st.caption("💡 등록된 현미경 사진들을 시간 흐름(날짜별) 또는 동일 일자의 조건별로 나란히 비교할 수 있습니다.")

            # 이미지가 존재하는 처리 내역만 필터링
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
                st.warning("🖼️ 현재 플레이트에 등록된 현미경 사진이 없습니다. **'1D 원형 Well Plate 편집'** 또는 **'날짜별 물질/세포 처리 입력'** 탭에서 사진을 업로드해 주세요.")
            else:
                compare_mode = st.radio(
                    "📌 비교 보기 방식 선택",
                    ["📅 1. 날짜별 변화 비교 (동일 Well/조건의 시계열 변화)", "🧪 2. 조건별 결과 비교 (동일 날짜의 Well/조건 간 비교)"],
                    horizontal=True
                )

                st.markdown("---")
                grid_cols_count = st.slider("📐 한 줄에 표시할 사진 개수 (열 조정)", min_value=2, max_value=6, value=3)

                # --- [모드 1: 날짜별 변화 비교] ---
                if compare_mode.startswith("📅"):
                    all_wells_with_img = sorted(list(set([t['well_position'] for t in treatments_with_img])))
                    
                    c_sel1, c_sel2 = st.columns([1, 2])
                    with c_sel1:
                        selected_compare_well = st.selectbox("🎯 비교할 Well 선택", all_wells_with_img)

                    # 선택된 Well의 날짜순 이미지 데이터
                    well_img_list = [t for t in treatments_with_img if t['well_position'] == selected_compare_well]
                    well_img_list = sorted(well_img_list, key=lambda x: x['treatment_date'])

                    st.markdown(f"##### 🧫 Well [{selected_compare_well}] 날짜별 사진 변화 ({len(well_img_list)}장)")

                    img_cols = st.columns(grid_cols_count)
                    for idx, t_item in enumerate(well_img_list):
                        with img_cols[idx % grid_cols_count]:
                            formatted_cond = format_compound_summary(t_item['compound_name'], t_item['concentration'])
                            st.markdown(
                                f"""
                                <div style="border: 1px solid #cbd5e1; padding: 8px; border-radius: 8px; background-color: #f8fafc; margin-bottom: 12px;">
                                    <p style="margin:0; font-weight:bold; color:#1e293b; font-size:14px;">📅 {t_item['treatment_date']}</p>
                                    <p style="margin:2px 0; color:#3b82f6; font-size:12px;"><b>🧪 조건:</b> {formatted_cond}</p>
                                    <p style="margin:0; color:#64748b; font-size:11px;"><b>🥛 배지:</b> {t_item['parsed_basal']} | <b>🧫 세포:</b> {t_item.get('cell_info','-')}</p>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            display_image_from_b64(t_item['img_b64'], caption=f"{t_item['treatment_date']} - {selected_compare_well}")
                            if t_item['parsed_note']:
                                st.caption(f"📝 {t_item['parsed_note']}")

                # --- [모드 2: 조건별 결과 비교] ---
                else:
                    all_dates_with_img = sorted(list(set([t['treatment_date'] for t in treatments_with_img])))
                    
                    c_sel1, c_sel2 = st.columns([1, 2])
                    with c_sel1:
                        selected_compare_date = st.selectbox("📅 비교할 날짜 선택", all_dates_with_img)

                    # 선택된 날짜의 Well별 이미지 데이터
                    date_img_list = [t for t in treatments_with_img if t['treatment_date'] == selected_compare_date]
                    date_img_list = sorted(date_img_list, key=lambda x: x['well_position'])

                    st.markdown(f"##### 📅 [{selected_compare_date}] 각 Well/조건별 사진 비교 ({len(date_img_list)}장)")

                    img_cols = st.columns(grid_cols_count)
                    for idx, t_item in enumerate(date_img_list):
                        with img_cols[idx % grid_cols_count]:
                            formatted_cond = format_compound_summary(t_item['compound_name'], t_item['concentration'])
                            st.markdown(
                                f"""
                                <div style="border: 1px solid #cbd5e1; padding: 8px; border-radius: 8px; background-color: #f8fafc; margin-bottom: 12px;">
                                    <p style="margin:0; font-weight:bold; color:#0f172a; font-size:14px;">📍 Well {t_item['well_position']}</p>
                                    <p style="margin:2px 0; color:#059669; font-size:12px;"><b>🧪 조건:</b> {formatted_cond}</p>
                                    <p style="margin:0; color:#64748b; font-size:11px;"><b>🥛 배지:</b> {t_item['parsed_basal']} | <b>🧫 세포:</b> {t_item.get('cell_info','-')}</p>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            display_image_from_b64(t_item['img_b64'], caption=f"Well {t_item['well_position']} ({formatted_cond})")
                            if t_item['parsed_note']:
                                st.caption(f"📝 {t_item['parsed_note']}")