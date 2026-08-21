import base64
import datetime
import db
import pandas as pd
import plotly.graph_objects as go
import style
import streamlit as st

# --- 1. 페이지 설정 및 디자인 서식 적용 ---
st.set_page_config(
    page_title="연구 프로젝트 관리", page_icon="🧪", layout="wide"
)

# 화면 전체 레이아웃을 좌측 밀착(Left-aligned)시키는 Custom CSS
st.markdown(
    """
    <style>
        /* 메인 컨테이너의 좌측 여백을 최소화하고 왼쪽으로 정렬 */
        .main .block-container {
            padding-left: 1.5rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
            margin-left: 0 !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

if hasattr(style, "apply_custom_style"):
  style.apply_custom_style()


st.title("🧫 시각화 및 세포 오가노이드 처리 관리")


# ======================================================================
# [이미지 및 데이터 파싱 헬퍼 함수]
# ======================================================================
def file_to_base64(uploaded_file):
  """업로드된 이미지 파일을 Base64 문자열로 변환"""
  if uploaded_file is None:
    return None
  bytes_data = uploaded_file.getvalue()
  return base64.b64encode(bytes_data).decode("utf-8")


def extract_image_data(item):
  """item에서 이미지 base64 데이터 추출 (DB 컬럼 또는 note 파싱)"""
  if not item:
    return None
  if item.get("image_data"):
    return item["image_data"]
  note = str(item.get("note", ""))
  if "[IMG_DATA:" in note and "]" in note:
    start = note.find("[IMG_DATA:") + len("[IMG_DATA:")
    end = note.rfind("]")
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

  raw_note = str(item.get("note", ""))
  img_data = extract_image_data(item)

  # note에서 Media 태그와 IMG_DATA 태그 제거
  pure_note = raw_note
  if "[Media:" in pure_note and "]" in pure_note:
    m_start = pure_note.find("[Media:")
    m_end = pure_note.find("]", m_start)
    if m_end != -1:
      pure_note = (pure_note[:m_start] + pure_note[m_end + 1 :]).strip()

  if "[IMG_DATA:" in pure_note and "]" in pure_note:
    i_start = pure_note.find("[IMG_DATA:")
    i_end = pure_note.rfind("]")
    if i_end != -1:
      pure_note = (pure_note[:i_start] + pure_note[i_end + 1 :]).strip()

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
    st.image(
        img_bytes,
        caption=caption,
        use_container_width=True if width is None else False,
        width=width,
    )
  except Exception:
    st.caption("⚠️ 이미지를 로드할 수 없습니다.")


def get_basal_media(item):
  """Basal Media 정보를 안전하게 추출"""
  if not item:
    return "-"
  if (
      item.get("basal_media")
      and str(item["basal_media"]).strip()
      and str(item["basal_media"]).strip() != "-"
  ):
    return str(item["basal_media"]).strip()
  note = str(item.get("note", ""))
  if "[Media:" in note and "]" in note:
    start = note.find("[Media:") + len("[Media:")
    end = note.find("]", start)
    if end != -1:
      extracted = note[start:end].strip()
      if extracted:
        return extracted
  return "-"


def get_recipe_options(current_val=""):
  """Material Recipe DB에서 저장된 레시피 목록을 추출하여 드롭다운 옵션 생성"""
  options = ["-"]
  if hasattr(db, "get_all_recipes"):
    recipes = db.get_all_recipes()
    if isinstance(recipes, list):
      for r in recipes:
        name = (
            r.get("recipe_name")
            if isinstance(r, dict)
            else getattr(r, "recipe_name", None)
        )
        if name and name not in options:
          options.append(name)
    elif (
        isinstance(recipes, pd.DataFrame)
        and not recipes.empty
        and "recipe_name" in recipes.columns
    ):
      for name in recipes["recipe_name"].dropna().unique():
        if name and name not in options:
          options.append(str(name))

  if current_val and current_val != "-" and current_val not in options:
    options.append(current_val)

  return options


def generate_dynamic_lineage_dot(treatments):
  """사용자가 입력한 treatments 데이터의 cell_info와 날짜 순서를 분석해 Graphviz DOT 생성"""
  if not treatments:
    return None

  df = pd.DataFrame(treatments)
  if "cell_info" not in df.columns:
    return None

  df = df[df["cell_info"].notnull() & (df["cell_info"].str.strip() != "")]
  if df.empty:
    return None

  df = df.sort_values(by=["well_position", "treatment_date"])

  nodes = set()
  edges = set()

  for well, group in df.groupby("well_position"):
    cell_history = []
    for _, row in group.iterrows():
      c_info = str(row["cell_info"]).strip()
      t_date = str(row["treatment_date"]).strip()
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
      '    node [shape=box, style="filled,rounded", fillcolor="#f8fafc",'
      ' color="#3b82f6", fontname="Malgun Gothic, sans-serif", fontsize=9,'
      ' height=0.28, margin="0.1,0.05"];',
      '    edge [color="#64748b", arrowhead=normal, arrowsize=0.6, penwidth=1.2,'
      ' fontname="Malgun Gothic, sans-serif", fontsize=8];',
  ]

  for node in nodes:
    clean_node = node.replace('"', '\\"')
    dot_lines.append(f'    "{clean_node}" [label="{clean_node}"];')

  for src, dst, transition_date in edges:
    clean_src = src.replace('"', '\\"')
    clean_dst = dst.replace('"', '\\"')
    clean_date = transition_date.replace('"', '\\"')
    dot_lines.append(
        f'    "{clean_src}" -> "{clean_dst}" [label=" {clean_date} ",'
        ' fontcolor="#475569"];'
    )

  dot_lines.append("}")
  return "\n".join(dot_lines)


def format_compound_summary(comp_str, conc_str):
  """물질명과 농도 문자열을 1:1 매칭하여 '물질 농도' 형태로 정형화"""
  if not comp_str:
    return "-"

  comps = [c.strip() for c in str(comp_str).split(",") if c.strip()]
  concs = [c.strip() for c in str(conc_str).split(",")] if conc_str else []

  paired = []
  for i, comp in enumerate(comps):
    conc = concs[i] if i < len(concs) and concs[i] else ""
    if conc:
      paired.append(f"{comp} {conc}")
    else:
      paired.append(comp)

  return ", ".join(paired)


# 분석 진행 옵션 리스트 정의
ANALYSIS_OPTIONS = [
    "미진행",
    "단일세포 전사체 (scRNA-seq)",
    "면역형광 염색 (IF / Confocal)",
    "Flow Cytometry (FACS)",
    "Western Blot / PCR",
    "기타 분석",
]

PLATE_PRESETS = {
    "96-Well Plate (8 x 12)": (8, 12),
    "48-Well Plate (6 x 8)": (6, 8),
    "24-Well Plate (4 x 6)": (4, 6),
    "12-Well Plate (3 x 4)": (3, 4),
    "6-Well Plate (2 x 3)": (2, 3),
    "⚙️ 사용자 지정 (Custom)": "custom",
}

db.init_db()
projects = db.get_projects()

if not projects:
  st.warning(
      "⚠️ 등록된 프로젝트가 없습니다. 먼저 **'1. Experiments(프로젝트"
      " 관리)'** 메뉴에서 프로젝트를 생성해 주세요."
  )
else:
  proj_map = {
      f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID:"
      f" {p['id']})": p
      for p in projects
  }
  options = list(proj_map.keys())

  if (
      "selected_plate_proj_label" not in st.session_state
      or st.session_state.selected_plate_proj_label not in options
  ):
    st.session_state.selected_plate_proj_label = options[0]

  # === [사이드바 설정 영역: 프로젝트 선택, 플레이트 선택 및 생성] ===
  with st.sidebar:
    st.markdown("### 🗂️ 프로젝트 및 플레이트 관리")

    selected_label = st.selectbox(
        "📌 프로젝트 선택",
        options=options,
        key="selected_plate_proj_label",
    )
    selected_proj = proj_map[selected_label]

    st.markdown(
        f"""
            <div style="padding:10px 14px; border-left: 6px solid {selected_proj['color_code']}; background-color: #f8fafc; border-radius: 6px; margin-top: 4px; margin-bottom: 15px;">
                <p style="margin:0; color:#0f172a; font-weight:bold; font-size:14px;">{selected_proj['name']}</p>
                <p style="margin:2px 0 0 0; color:#475569; font-size:12px;"><b>그룹:</b> {selected_proj['group_name']} | <b>설명:</b> {selected_proj['description'] if selected_proj['description'] else '없음'}</p>
            </div>
            """,
        unsafe_allow_html=True,
    )

    plates = db.get_plates(selected_proj["id"])

    if plates:
      plate_dict = {
          f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)": pl for pl in plates
      }
      selected_plate_name = st.selectbox(
          "🧫 작업 대상 플레이트 선택",
          list(plate_dict.keys()),
          key="selected_plate_select",
      )
      selected_plate = plate_dict[selected_plate_name]

      if st.button(
          "🗑️ 선택 플레이트 삭제",
          type="secondary",
          use_container_width=True,
          key="btn_del_plate_top",
      ):
        db.delete_plate(selected_plate["id"])
        st.toast("플레이트가 휴지통으로 이동되었습니다.", icon="🗑️")
        st.rerun()
    else:
      st.info(
          "💡 선택된 프로젝트에 등록된 플레이트가 없습니다. 아래에서"
          " 생성해 주세요."
      )
      selected_plate = None

    st.markdown("---")
    with st.expander("➕ 새 규격 플레이트 생성", expanded=not bool(plates)):
      with st.form("add_plate_form", clear_on_submit=True):
        plate_name = st.text_input(
            "플레이트 이름*", placeholder="예: 96-Well Plate #1"
        )
        selected_preset_label = st.selectbox(
            "🧫 플레이트 표준 규격 선택*", list(PLATE_PRESETS.keys())
        )

        if PLATE_PRESETS[selected_preset_label] == "custom":
          p_rows = st.number_input(
              "행 개수 (Rows)", min_value=1, max_value=16, value=8
          )
          p_cols = st.number_input(
              "열 개수 (Cols)", min_value=1, max_value=24, value=12
          )
        else:
          p_rows, p_cols = PLATE_PRESETS[selected_preset_label]
          st.caption(f"💡 선택된 규격: **{p_rows} 행 x {p_cols} 열**")

        p_submit = st.form_submit_button(
            "플레이트 추가", use_container_width=True
        )
        if p_submit:
          if plate_name.strip():
            db.add_plate(
                selected_proj["id"], plate_name.strip(), p_rows, p_cols
            )
            st.success(f"'{plate_name}' 플레이트 생성 완료!")
            st.rerun()
          else:
            st.error("플레이트 이름을 입력해 주세요.")

  if selected_plate:
    treatments = db.get_treatments_by_plate(selected_plate["id"])

    # 4개 탭 구성 (사진 비교 탭 포함)
    tab_view, tab_tree, tab_treat, tab_compare = st.tabs([
        "🔴 Well Plate 시각화 & 편집",
        "🌳 사용자 데이터 기반 계통도",
        "📝 날짜별 물질/세포 처리 입력 및 전체 관리",
        "📸 날짜별 & 조건별 사진 비교 시각화",
    ])

    # ======================================================================
    # [TAB 1] Plotly 시각화 및 편집
    # ======================================================================
    with tab_view:
      st.info(
          "💡 **왼쪽 차트**의 Well을 **클릭**하거나"
          " **드래그(Box/Lasso)**하면 **오른쪽 편집 창**에서 바로 수정, 사진"
          " 첨부 및 신규 처리를 할 수 있습니다."
      )

      left_col, right_col = st.columns([5.5, 6.5], gap="large")

      rows = selected_plate["rows"]
      cols = selected_plate["cols"]
      total_wells = rows * cols
      row_labels = [chr(65 + i) for i in range(rows)]
      dates_available = (
          sorted(list(set([t["treatment_date"] for t in treatments])))
          if treatments
          else []
      )

      with left_col:
        st.markdown("##### 🧫 플레이트 배치 시각화")
        col_v1, col_v2 = st.columns([1.2, 1.8])
        with col_v1:
          selected_date = st.selectbox(
              "📅 조회 날짜",
              options=["전체 날짜 (최신 상태)"] + dates_available,
              key="v_date_select",
          )
        with col_v2:
          color_by = st.radio(
              "🎨 색상 기준",
              ["세포 정보별", "처리 유무별"],
              horizontal=True,
              key="v_color_radio",
          )

        well_last_map = {}
        well_all_map = {}
        for t in treatments:
          if (
              selected_date == "전체 날짜 (최신 상태)"
              or t["treatment_date"] == selected_date
          ):
            pos = t["well_position"].upper()
            if pos not in well_all_map:
              well_all_map[pos] = []
            well_all_map[pos].append(t)
            well_last_map[pos] = t

        palette = [
            "#3B82F6",
            "#10B981",
            "#F59E0B",
            "#EF4444",
            "#8B5CF6",
            "#EC4899",
            "#14B8A6",
            "#6366F1",
            "#F97316",
            "#06B6D4",
        ]
        unique_cells = (
            sorted(
                list(
                    set([
                        t.get("cell_info", "").strip()
                        for t in treatments
                        if t.get("cell_info")
                    ])
                )
            )
            if treatments
            else []
        )
        cell_color_map = {
            cell: palette[i % len(palette)]
            for i, cell in enumerate(unique_cells)
        }

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
        (
            x_vals,
            y_vals,
            well_names,
            marker_colors,
            hover_texts,
            text_labels,
        ) = ([], [], [], [], [], [])

        for r_idx, r_label in enumerate(row_labels):
          for c in range(1, cols + 1):
            pos = f"{r_label}{c}"
            x_vals.append(c)
            y_vals.append(rows - r_idx)
            well_names.append(pos)

            if pos in well_last_map:
              item = well_last_map[pos]
              cell_name = (
                  item.get("cell_info", "").strip()
                  if item.get("cell_info")
                  else "기타"
              )

              if color_by == "세포 정보별":
                color = cell_color_map.get(cell_name, "#3B82F6")
              else:
                color = "#10B981"

              has_img = "📷 사진 유" if extract_image_data(item) else ""
              cell_short = cell_name[:6] if cell_name else "미지정"

              analysis_val = (
                  item.get("analysis_status", "-")
                  if item.get("analysis_status")
                  else "미진행"
              )
              analysis_badge = "🔬" if analysis_val != "미진행" else ""

              text_labels.append(
                  f"<b>{pos}</b><br>{cell_short}{' ' + analysis_badge if analysis_badge else ''}"
              )

              basal_text = get_basal_media(item)
              treatment_summary = format_compound_summary(
                  item["compound_name"], item["concentration"]
              )

              hover_html = (
                  f"<b>[Well {pos}]</b> {has_img}<br>🧫 <b>세포 정보:</b>"
                  f" {item.get('cell_info', '-')}<br>🔬 <b>분석 진행:</b>"
                  f" {analysis_val}<br>🥛 <b>Basal Media:</b>"
                  f" {basal_text}<br>🧪 <b>처리 조건:</b>"
                  f" {treatment_summary}<br>📅 <b>일자:</b>"
                  f" {item['treatment_date']}"
              )
              hover_texts.append(hover_html)
            else:
              color = "#FFFFFF"
              text_labels.append(f"<span style='color:#94a3b8;'>{pos}</span>")
              hover_texts.append(f"<b>[Well {pos}]</b><br>처리 내역 없음 (Empty)")

            marker_colors.append(color)

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers+text",
                customdata=well_names,
                marker=dict(
                    size=marker_size,
                    symbol="circle",
                    color=marker_colors,
                    line=dict(width=2, color="#334155"),
                ),
                text=text_labels,
                textposition="middle center",
                textfont=dict(size=font_size, color="black"),
                hoverinfo="text",
                hovertext=hover_texts,
                showlegend=False,
            )
        )

        fig.update_layout(
            title=dict(
                text=f"🧫 {selected_plate['name']}",
                x=0.5,
                font=dict(size=16),
            ),
            dragmode="select",
            clickmode="event+select",
            xaxis=dict(
                title="Column",
                tickmode="array",
                tickvals=list(range(1, cols + 1)),
                range=[0.3, cols + 0.7],
                zeroline=False,
                fixedrange=True,
            ),
            yaxis=dict(
                title="Row",
                tickmode="array",
                tickvals=[rows - i for i in range(rows)],
                ticktext=row_labels,
                range=[0.3, rows + 0.7],
                zeroline=False,
                fixedrange=True,
            ),
            plot_bgcolor="#f1f5f9",
            paper_bgcolor="#ffffff",
            height=max(420, rows * 55),
            margin=dict(l=20, r=20, t=40, b=20),
        )

        plotly_event = st.plotly_chart(
            fig,
            use_container_width=True,
            on_select="rerun",
            selection_mode=["points", "box", "lasso"],
        )

        if unique_cells and color_by == "세포 정보별":
          st.markdown("##### 🏷️ 세포 정보별 색상 범례")
          leg_cols = st.columns(min(len(unique_cells), 3))
          for idx, (cell_item, c_color) in enumerate(cell_color_map.items()):
            with leg_cols[idx % 3]:
              st.markdown(
                  f"""<div style="display:flex; align-items:center; background:#f8fafc; padding:4px 8px; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:6px;">
                                    <div style="width:12px; height:12px; background-color:{c_color}; border-radius:50%; margin-right:6px; border:1px solid #1e293b;"></div>
                                    <span style="font-size:12px; font-weight:bold; color:#0f172a;">{cell_item}</span>
                                </div>""",
                  unsafe_allow_html=True,
              )

      with right_col:
        edit_main_tab1, edit_main_tab2 = st.tabs(
            ["✏️ 선택 Well 편집 & 사진 첨부", "📊 행/열 배치 요약 표"]
        )

        with edit_main_tab1:
          all_well_positions = [
              f"{r}{c}" for r in row_labels for c in range(1, cols + 1)
          ]

          if "last_dragged_signature" not in st.session_state:
            st.session_state["last_dragged_signature"] = None

          dragged_wells = []
          if (
              plotly_event
              and "selection" in plotly_event
              and plotly_event["selection"].get("points")
          ):
            for pt in plotly_event["selection"]["points"]:
              if "customdata" in pt:
                val = pt["customdata"]
                if isinstance(val, (list, tuple)) and len(val) > 0:
                  dragged_wells.append(str(val[0]))
                elif val:
                  dragged_wells.append(str(val))
              elif "point_index" in pt:
                dragged_wells.append(well_names[pt["point_index"]])

          current_sig = (
              ",".join(sorted(dragged_wells)) if dragged_wells else None
          )
          if current_sig != st.session_state["last_dragged_signature"]:
            st.session_state["last_dragged_signature"] = current_sig
            if dragged_wells:
              st.session_state["selected_wells_multiselect"] = dragged_wells

          selected_wells = st.multiselect(
              "📌 대상 Well 선택 (차트에서 클릭/드래그 시 자동 선택)",
              options=all_well_positions,
              key="selected_wells_multiselect",
          )

          if selected_wells:
            if len(selected_wells) == 1:
              pos = selected_wells[0]
              st.success(f"🎯 **Well [{pos}]** 가 선택되었습니다.")

              if pos in well_all_map:
                items = well_all_map[pos]
                st.markdown(
                    f"##### 📝 Well [{pos}] 기존 처리 이력 ({len(items)}건)"
                )

                for item in items:
                  formatted_cond = format_compound_summary(
                      item["compound_name"], item["concentration"]
                  )
                  with st.expander(
                      f"📅 {item['treatment_date']} | 🧬"
                      f" {item.get('cell_info', '-')} | 🧪 {formatted_cond}",
                      expanded=True,
                  ):
                    try:
                      def_d = datetime.datetime.strptime(
                          item["treatment_date"], "%Y-%m-%d"
                      ).date()
                    except Exception:
                      def_d = datetime.date.today()

                    b_media_val, pure_note_val, cur_img_b64 = (
                        parse_note_basal_image(item)
                    )

                    r1_c1, r1_c2 = st.columns(2)
                    with r1_c1:
                      mod_d = st.date_input(
                          "처리 일자",
                          value=def_d,
                          key=f"s_date_{item['id']}",
                      )
                    with r1_c2:
                      mod_pos = st.text_input(
                          "웰 위치",
                          value=item["well_position"],
                          key=f"s_pos_{item['id']}",
                      )

                    mod_cell = st.text_input(
                        "세포 정보",
                        value=item.get("cell_info", ""),
                        key=f"s_cell_{item['id']}",
                    )

                    cur_analysis = item.get("analysis_status", "미진행")
                    a_idx = (
                        ANALYSIS_OPTIONS.index(cur_analysis)
                        if cur_analysis in ANALYSIS_OPTIONS
                        else 0
                    )

                    r2_c1, r2_c2 = st.columns(2)
                    with r2_c1:
                      mod_analysis = st.selectbox(
                          "🔬 분석진행 상태",
                          options=ANALYSIS_OPTIONS,
                          index=a_idx,
                          key=f"s_analysis_{item['id']}",
                      )

                    cur_s_analysis = st.session_state.get(
                        f"s_analysis_{item['id']}", cur_analysis
                    )

                    with r2_c2:
                      if cur_s_analysis == "미진행":
                        b_opts = get_recipe_options(b_media_val)
                        b_idx = (
                            b_opts.index(b_media_val)
                            if b_media_val in b_opts
                            else 0
                        )
                        mod_basal = st.selectbox(
                            "Basal Media (레시피 선택)",
                            options=b_opts,
                            index=b_idx,
                            key=f"s_basal_{item['id']}",
                        )
                      else:
                        mod_basal = "-"
                        st.text_input(
                            "Basal Media",
                            value="-",
                            disabled=True,
                            key=f"s_basal_disabled_{item['id']}",
                        )

                    if cur_s_analysis == "미진행":
                      st.caption(
                          "🧪 **처리 물질 및 농도 (2쌍씩 같은 열"
                          " 관리)**"
                      )
                      existing_comps = [
                          c.strip()
                          for c in str(item["compound_name"]).split(",")
                          if c.strip()
                      ]
                      existing_concs = (
                          [
                              c.strip()
                              for c in str(item["concentration"]).split(",")
                          ]
                          if item["concentration"]
                          else []
                      )

                      num_s_pairs = st.number_input(
                          "입력할 물질 쌍 개수",
                          min_value=1,
                          max_value=10,
                          value=max(1, len(existing_comps)),
                          key=f"s_num_pairs_{item['id']}",
                      )

                      s_comps, s_concs = [], []
                      for i in range(0, int(num_s_pairs), 2):
                        pair_cols = st.columns([2, 1, 2, 1])

                        def_c1 = (
                            existing_comps[i]
                            if i < len(existing_comps)
                            else ""
                        )
                        def_n1 = (
                            existing_concs[i]
                            if i < len(existing_concs)
                            else ""
                        )
                        with pair_cols[0]:
                          c1_val = st.text_input(
                              f"물질 #{i+1}",
                              value=def_c1,
                              placeholder="예: VEGF",
                              key=f"s_c_{item['id']}_{i}",
                          )
                        with pair_cols[1]:
                          n1_val = st.text_input(
                              f"농도 #{i+1}",
                              value=def_n1,
                              placeholder="예: 50 ng/mL",
                              key=f"s_n_{item['id']}_{i}",
                          )
                        if c1_val.strip():
                          s_comps.append(c1_val.strip())
                          s_concs.append(n1_val.strip())

                        if i + 1 < int(num_s_pairs):
                          def_c2 = (
                              existing_comps[i + 1]
                              if i + 1 < len(existing_comps)
                              else ""
                          )
                          def_n2 = (
                              existing_concs[i + 1]
                              if i + 1 < len(existing_concs)
                              else ""
                          )
                          with pair_cols[2]:
                            c2_val = st.text_input(
                                f"물질 #{i+2}",
                                value=def_c2,
                                placeholder="예: FGF",
                                key=f"s_c_{item['id']}_{i+1}",
                            )
                          with pair_cols[3]:
                            n2_val = st.text_input(
                                f"농도 #{i+2}",
                                value=def_n2,
                                placeholder="예: 10 ng/mL",
                                key=f"s_n_{item['id']}_{i+1}",
                            )
                          if c2_val.strip():
                            s_comps.append(c2_val.strip())
                            s_concs.append(n2_val.strip())
                      mod_comp = ", ".join(s_comps)
                      mod_conc = ", ".join(s_concs)
                    else:
                      mod_comp = f"분석 진행 ({cur_s_analysis})"
                      mod_conc = ""
                      st.info(f"🔬 **{cur_s_analysis}** 분석 모드입니다.")

                    mod_note = st.text_input(
                        "비고 / 상세 조건",
                        value=pure_note_val,
                        key=f"s_note_{item['id']}",
                    )

                    st.caption("📷 **현미경 / 결과 사진 관리**")
                    if cur_img_b64:
                      display_image_from_b64(
                          cur_img_b64, caption=f"Well {pos} 등록 사진"
                      )
                      del_img = st.checkbox(
                          "🗑️ 저장된 사진 삭제",
                          key=f"chk_del_img_{item['id']}",
                      )
                    else:
                      del_img = False

                    new_img_file = st.file_uploader(
                        "새 현미경 사진 첨부/교체",
                        type=["png", "jpg", "jpeg"],
                        key=f"file_s_{item['id']}",
                    )

                    b_save, b_del = st.columns(2)
                    with b_save:
                      if st.button(
                          "💾 저장",
                          key=f"btn_s_save_{item['id']}",
                          type="primary",
                          use_container_width=True,
                      ):
                        final_img_b64 = cur_img_b64
                        if del_img:
                          final_img_b64 = None
                        if new_img_file is not None:
                          final_img_b64 = file_to_base64(new_img_file)

                        comb_note = build_combined_note(
                            mod_basal, mod_note, final_img_b64
                        )
                        db.update_treatment(
                            item["id"],
                            mod_pos.strip().upper(),
                            str(mod_d),
                            mod_comp.strip(),
                            mod_conc.strip(),
                            mod_cell.strip(),
                            comb_note,
                            mod_analysis,
                        )
                        st.toast(
                            "수정 사항이 성공적으로 저장되었습니다!", icon="✅"
                        )
                        st.rerun()
                    with b_del:
                      if st.button(
                          "🗑️ 삭제",
                          key=f"btn_s_del_{item['id']}",
                          type="secondary",
                          use_container_width=True,
                      ):
                        db.delete_treatment(item["id"])
                        st.toast("삭제되었습니다.", icon="🗑️")
                        st.rerun()

                with st.expander(
                    f"➕ Well [{pos}]에 추가 처리 및 사진 작성",
                    expanded=False,
                ):
                  r1_c1, r1_c2 = st.columns(2)
                  with r1_c1:
                    ex_d = st.date_input(
                        "처리 일자", datetime.date.today(), key=f"ex_d_{pos}"
                    )
                  with r1_c2:
                    st.text_input(
                        "웰 위치", value=pos, disabled=True, key=f"ex_pos_{pos}"
                    )

                  ex_cell = st.text_input(
                      "세포 정보", placeholder="예: iPSC", key=f"ex_cell_{pos}"
                  )

                  r2_c1, r2_c2 = st.columns(2)
                  with r2_c1:
                    ex_analysis = st.selectbox(
                        "🔬 분석진행 상태",
                        options=ANALYSIS_OPTIONS,
                        key=f"ex_analysis_{pos}",
                    )

                  ex_analysis_val = st.session_state.get(
                      f"ex_analysis_{pos}", "미진행"
                  )

                  with r2_c2:
                    if ex_analysis_val == "미진행":
                      ex_basal = st.selectbox(
                          "Basal Media (레시피 선택)",
                          options=get_recipe_options(),
                          key=f"ex_basal_{pos}",
                      )
                    else:
                      ex_basal = "-"
                      st.text_input(
                          "Basal Media",
                          value="-",
                          disabled=True,
                          key=f"ex_basal_disabled_{pos}",
                      )

                  if ex_analysis_val == "미진행":
                    st.caption(
                        "🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**"
                    )
                    num_ex_pairs = st.number_input(
                        "입력할 물질 쌍 개수",
                        min_value=1,
                        max_value=10,
                        value=2,
                        key=f"ex_num_pairs_{pos}",
                    )

                    ex_comps, ex_concs = [], []
                    for i in range(0, int(num_ex_pairs), 2):
                      pair_cols = st.columns([2, 1, 2, 1])
                      with pair_cols[0]:
                        c1_val = st.text_input(
                            f"물질 #{i+1}",
                            placeholder="예: VEGF",
                            key=f"ex_c_{pos}_{i}",
                        )
                      with pair_cols[1]:
                        n1_val = st.text_input(
                            f"농도 #{i+1}",
                            placeholder="예: 50 ng/mL",
                            key=f"ex_n_{pos}_{i}",
                        )
                      if c1_val.strip():
                        ex_comps.append(c1_val.strip())
                        ex_concs.append(n1_val.strip())

                      if i + 1 < int(num_ex_pairs):
                        with pair_cols[2]:
                          c2_val = st.text_input(
                              f"물질 #{i+2}",
                              placeholder="추가 물질",
                              key=f"ex_c_{pos}_{i+1}",
                          )
                        with pair_cols[3]:
                          n2_val = st.text_input(
                              f"농도 #{i+2}",
                              placeholder="추가 농도",
                              key=f"ex_n_{pos}_{i+1}",
                          )
                        if c2_val.strip():
                          ex_comps.append(c2_val.strip())
                          ex_concs.append(n2_val.strip())
                    ex_comp_str = ", ".join(ex_comps)
                    ex_conc_str = ", ".join(ex_concs)
                  else:
                    ex_comp_str = f"분석 진행 ({ex_analysis_val})"
                    ex_conc_str = ""
                    st.info(f"🔬 **{ex_analysis_val}** 분석 모드입니다.")

                  ex_note = st.text_input(
                      "비고", placeholder="상세 조건", key=f"ex_note_{pos}"
                  )
                  ex_file = st.file_uploader(
                      "📷 현미경 사진 첨부 (선택)",
                      type=["png", "jpg", "jpeg"],
                      key=f"ex_file_{pos}",
                  )

                  if st.button(
                      f"💾 Well [{pos}] 추가 저장",
                      key=f"btn_ex_save_{pos}",
                      use_container_width=True,
                      type="primary",
                  ):
                    if ex_analysis_val != "미진행" or ex_comp_str.strip():
                      img_b64 = file_to_base64(ex_file)
                      comb_note = build_combined_note(
                          ex_basal, ex_note, img_b64
                      )
                      db.add_treatment(
                          selected_plate["id"],
                          pos,
                          str(ex_d),
                          ex_comp_str,
                          ex_conc_str,
                          ex_cell.strip(),
                          comb_note,
                          ex_analysis,
                      )
                      st.toast(
                          f"Well [{pos}] 추가 처리가 저장되었습니다!",
                          icon="✅",
                      )
                      st.rerun()
                    else:
                      st.error("처리 물질명을 입력해 주세요.")
              else:
                st.markdown(f"##### ➕ Well [{pos}] 신규 물질 처리 및 사진 작성")
                st.caption("선택하신 Well은 현재 미처리 상태입니다.")

                r1_c1, r1_c2 = st.columns(2)
                with r1_c1:
                  e_d = st.date_input(
                      "처리 일자", datetime.date.today(), key=f"e_d_{pos}"
                  )
                with r1_c2:
                  st.text_input(
                      "웰 위치", value=pos, disabled=True, key=f"e_pos_{pos}"
                  )

                e_cell = st.text_input(
                    "세포/오가노이드 정보",
                    placeholder="예: DE, HIO",
                    key=f"e_cell_{pos}",
                )

                r2_c1, r2_c2 = st.columns(2)
                with r2_c1:
                  e_analysis = st.selectbox(
                      "🔬 분석진행 상태",
                      options=ANALYSIS_OPTIONS,
                      key=f"e_analysis_{pos}",
                  )
                with r2_c2:
                  e_analysis_val = st.session_state.get(
                      f"e_analysis_{pos}", "미진행"
                  )
                  if e_analysis_val == "미진행":
                    e_basal = st.selectbox(
                        "Basal Media (레시피 선택)",
                        options=get_recipe_options(),
                        key=f"e_basal_{pos}",
                    )
                  else:
                    e_basal = "-"
                    st.text_input(
                        "Basal Media",
                        value="-",
                        disabled=True,
                        key=f"e_basal_disabled_{pos}",
                    )

                if e_analysis_val == "미진행":
                  st.caption("🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**")
                  num_e_pairs = st.number_input(
                      "입력할 물질 쌍 개수",
                      min_value=1,
                      max_value=10,
                      value=2,
                      key=f"e_num_pairs_{pos}",
                  )

                  e_comps, e_concs = [], []
                  for i in range(0, int(num_e_pairs), 2):
                    pair_cols = st.columns([2, 1, 2, 1])
                    with pair_cols[0]:
                      c_val = st.text_input(
                          f"물질 #{i+1}",
                          placeholder="예: VEGF",
                          key=f"e_c_{pos}_{i}",
                      )
                    with pair_cols[1]:
                      n_val = st.text_input(
                          f"농도 #{i+1}",
                          placeholder="예: 50 ng/mL",
                          key=f"e_n_{pos}_{i}",
                      )
                    if c_val.strip():
                      e_comps.append(c_val.strip())
                      e_concs.append(n_val.strip())

                    if i + 1 < int(num_e_pairs):
                      with pair_cols[2]:
                        c2_val = st.text_input(
                            f"물질 #{i+2}",
                            placeholder="추가 물질",
                            key=f"e_c_{pos}_{i+1}",
                        )
                      with pair_cols[3]:
                        n2_val = st.text_input(
                            f"농도 #{i+2}",
                            placeholder="추가 농도",
                            key=f"e_n_{pos}_{i+1}",
                        )
                      if c2_val.strip():
                        e_comps.append(c2_val.strip())
                        e_concs.append(n2_val.strip())
                  e_comp_str = ", ".join(e_comps)
                  e_conc_str = ", ".join(e_concs)
                else:
                  e_comp_str = f"분석 진행 ({e_analysis_val})"
                  e_conc_str = ""
                  st.info(f"🔬 **{e_analysis_val}** 분석 모드입니다.")

                e_note = st.text_input(
                    "비고 / 상세 조건",
                    placeholder="예: Daily media change",
                    key=f"e_note_{pos}",
                )
                e_file = st.file_uploader(
                    "📷 현미경 사진 첨부 (선택)",
                    type=["png", "jpg", "jpeg"],
                    key=f"e_file_{pos}",
                )

                if st.button(
                    f"💾 Well [{pos}] 일괄 저장",
                    key=f"btn_e_save_{pos}",
                    type="primary",
                    use_container_width=True,
                ):
                  if e_analysis_val != "미진행" or e_comp_str.strip():
                    img_b64 = file_to_base64(e_file)
                    comb_note = build_combined_note(e_basal, e_note, img_b64)
                    db.add_treatment(
                        selected_plate["id"],
                        pos,
                        str(e_d),
                        e_comp_str,
                        e_conc_str,
                        e_cell.strip(),
                        comb_note,
                        e_analysis,
                    )
                    st.toast(
                        f"Well [{pos}] 처리가 저장되었습니다!", icon="✅"
                    )
                    st.rerun()
                  else:
                    st.error("처리 물질명을 입력해 주세요.")
            else:
              # 다중 선택(Multiple Wells Selected)
              st.info(
                  f"⚡ 총 **{len(selected_wells)}개**의 Well"
                  " [ "
                  + ", ".join(selected_wells)
                  + " ] 이 다중 선택되었습니다."
              )

              m_d = st.date_input(
                  "일괄 적용 일자",
                  datetime.date.today(),
                  key="multi_date_input",
              )
              m_cell = st.text_input(
                  "일괄 세포 정보",
                  placeholder="예: hPSC-Derived Organoids",
                  key="multi_cell_input",
              )

              m_c1, m_c2 = st.columns(2)
              with m_c1:
                m_analysis = st.selectbox(
                    "🔬 일괄 분석진행 상태",
                    options=ANALYSIS_OPTIONS,
                    key="multi_analysis_select",
                )
              with m_c2:
                m_analysis_val = st.session_state.get(
                    "multi_analysis_select", "미진행"
                )
                if m_analysis_val == "미진행":
                  m_basal = st.selectbox(
                      "Basal Media (레시피 선택)",
                      options=get_recipe_options(),
                      key="multi_basal_select",
                  )
                else:
                  m_basal = "-"
                  st.text_input(
                      "Basal Media",
                      value="-",
                      disabled=True,
                      key="multi_basal_disabled",
                  )

              if m_analysis_val == "미진행":
                st.caption(
                    "🧪 **일괄 처리 물질 및 농도 (2쌍씩 같은 열 관리)**"
                )
                num_m_pairs = st.number_input(
                    "입력할 물질 쌍 개수",
                    min_value=1,
                    max_value=10,
                    value=2,
                    key="multi_num_pairs",
                )

                m_comps, m_concs = [], []
                for i in range(0, int(num_m_pairs), 2):
                  pair_cols = st.columns([2, 1, 2, 1])
                  with pair_cols[0]:
                    c_val = st.text_input(
                        f"물질 #{i+1}",
                        placeholder="예: BMP4",
                        key=f"m_c_{i}",
                    )
                  with pair_cols[1]:
                    n_val = st.text_input(
                        f"농도 #{i+1}",
                        placeholder="예: 10 ng/mL",
                        key=f"m_n_{i}",
                    )
                  if c_val.strip():
                    m_comps.append(c_val.strip())
                    m_concs.append(n_val.strip())

                  if i + 1 < int(num_m_pairs):
                    with pair_cols[2]:
                      c2_val = st.text_input(
                          f"물질 #{i+2}",
                          placeholder="추가 물질",
                          key=f"m_c_{i+1}",
                      )
                    with pair_cols[3]:
                      n2_val = st.text_input(
                          f"농도 #{i+2}",
                          placeholder="추가 농도",
                          key=f"m_n_{i+1}",
                      )
                    if c2_val.strip():
                      m_comps.append(c2_val.strip())
                      m_concs.append(n2_val.strip())
                m_comp_str = ", ".join(m_comps)
                m_conc_str = ", ".join(m_concs)
              else:
                m_comp_str = f"분석 진행 ({m_analysis_val})"
                m_conc_str = ""
                st.info(f"🔬 **{m_analysis_val}** 일괄 분석 모드입니다.")

              m_note = st.text_input(
                  "일괄 비고",
                  placeholder="예: Batch media exchange",
                  key="multi_note_input",
              )
              m_file = st.file_uploader(
                  "📷 공통 현미경 사진 첨부 (선택)",
                  type=["png", "jpg", "jpeg"],
                  key="multi_file_input",
              )

              if st.button(
                  f"⚡ 선택한 {len(selected_wells)}개 Well에 일괄 저장",
                  type="primary",
                  use_container_width=True,
                  key="btn_multi_save",
              ):
                if m_analysis_val != "미진행" or m_comp_str.strip():
                  img_b64 = file_to_base64(m_file)
                  comb_note = build_combined_note(m_basal, m_note, img_b64)
                  for target_pos in selected_wells:
                    db.add_treatment(
                        selected_plate["id"],
                        target_pos,
                        str(m_d),
                        m_comp_str,
                        m_conc_str,
                        m_cell.strip(),
                        comb_note,
                        m_analysis,
                    )
                  st.toast(
                      f"{len(selected_wells)}개 Well 일괄 저장이 completed!",
                      icon="✅",
                  )
                  st.rerun()
                else:
                  st.error("처리 물질명을 입력해 주세요.")
          else:
            st.info(
                "👈 왼쪽 시각화 차트에서 편집을 원하시는 **Well을 클릭하거나"
                " 드래그**해 주세요."
            )

        with edit_main_tab2:
          st.markdown("##### 📊 행 / 열별 조건 요약 매트릭스")
          if treatments:
            df_t = pd.DataFrame(treatments)
            df_t["row"] = df_t["well_position"].apply(
                lambda x: str(x)[0].upper() if str(x) else ""
            )
            df_t["col"] = df_t["well_position"].apply(
                lambda x: str(x)[1:] if len(str(x)) > 1 else ""
            )

            pivot_df = df_t.pivot_table(
                index="row",
                columns="col",
                values="cell_info",
                aggfunc=lambda x: " / ".join(
                    set([str(v) for v in x if str(v).strip()])
                ),
            ).fillna("-")
            st.dataframe(pivot_df, use_container_width=True)
          else:
            st.caption("등록된 처리 데이터가 없습니다.")

    # ======================================================================
    # [TAB 2] 계통도 시각화
    # ======================================================================
    with tab_tree:
      st.markdown("### 🌳 사용자 데이터 기반 오가노이드 분화 계통도")
      st.caption(
          "입력하신 날짜별 '세포 정보'의 변경 이력을 추적하여 분화 및 처리"
          " 흐름도를 자동으로 시각화합니다."
      )

      dot_code = generate_dynamic_lineage_dot(treatments)
      if dot_code:
        st.graphviz_chart(dot_code)
      else:
        st.info(
            "💡 세포 정보 및 처리 날짜 이력이 충분하지 않아 계통도를 생성할"
            " 수 없습니다. [탭 3]에서 세포 정보와 날짜별 처리를 입력해 주세요."
        )

    # ======================================================================
    # [TAB 3] 데이터 입력 및 전체 테이블 관리
    # ======================================================================
    with tab_treat:
      st.markdown("### 📝 날짜별 물질/세포 처리 입력 및 전체 내역 관리")

      t_tab1, t_tab2 = st.tabs(["➕ 신규 처리 내역 등록", "📋 전체 처리 내역 조회 및 수정"])

      with t_tab1:
        with st.form("add_treatment_form", clear_on_submit=True):
          f_c1, f_c2 = st.columns(2)
          with f_c1:
            t_date = st.date_input("처리 일자*", datetime.date.today())
          with f_c2:
            t_well = st.text_input(
                "Well 위치* (예: A1, B2 또는 A1-A6 범위)", placeholder="예: A1"
            )

          t_cell = st.text_input(
              "세포/오가노이드 정보",
              placeholder="예: Human Intestinal Organoid (HIO)",
          )

          f_c3, f_c4 = st.columns(2)
          with f_c3:
            t_analysis = st.selectbox(
                "🔬 분석진행 상태", options=ANALYSIS_OPTIONS
            )
          with f_c4:
            t_basal = st.selectbox(
                "Basal Media (레시피 선택)", options=get_recipe_options()
            )

          st.caption("🧪 **처리 물질 및 농도 입력 (2쌍씩 같은 열 관리)**")
          num_f_pairs = st.number_input(
              "입력할 물질 쌍 개수", min_value=1, max_value=10, value=2
          )

          f_comps, f_concs = [], []
          for i in range(0, int(num_f_pairs), 2):
            pair_cols = st.columns([2, 1, 2, 1])
            with pair_cols[0]:
              c_val = st.text_input(
                  f"물질 #{i+1}", placeholder="예: EGF", key=f"form_c_{i}"
              )
            with pair_cols[1]:
              n_val = st.text_input(
                  f"농도 #{i+1}", placeholder="예: 50 ng/mL", key=f"form_n_{i}"
              )
            if c_val.strip():
              f_comps.append(c_val.strip())
              f_concs.append(n_val.strip())

            if i + 1 < int(num_f_pairs):
              with pair_cols[2]:
                c2_val = st.text_input(
                    f"물질 #{i+2}",
                    placeholder="추가 물질",
                    key=f"form_c_{i+1}",
                )
              with pair_cols[3]:
                n2_val = st.text_input(
                    f"농도 #{i+2}",
                    placeholder="추가 농도",
                    key=f"form_n_{i+1}",
                )
              if c2_val.strip():
                f_comps.append(c2_val.strip())
                f_concs.append(n2_val.strip())

          t_comp_str = ", ".join(f_comps)
          t_conc_str = ", ".join(f_concs)

          t_note = st.text_input("비고 / 상세 조건", placeholder="기타 특이사항 입력")
          t_file = st.file_uploader(
              "📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"]
          )

          f_submit = st.form_submit_button(
              "처리 내역 저장", use_container_width=True
          )
          if f_submit:
            if t_well.strip():
              img_b64 = file_to_base64(t_file)
              comb_note = build_combined_note(t_basal, t_note, img_b64)

              # 범위 처리 지원 (예: A1-A6)
              raw_well = t_well.strip().upper()
              if "-" in raw_well:
                parts = raw_well.split("-")
                start_w, end_w = parts[0].strip(), parts[1].strip()
                r_start, c_start = start_w[0], int(start_w[1:])
                r_end, c_end = end_w[0], int(end_w[1:])

                wells_to_add = []
                for r in range(ord(r_start), ord(r_end) + 1):
                  for c in range(c_start, c_end + 1):
                    wells_to_add.append(f"{chr(r)}{c}")

                for w_pos in wells_to_add:
                  db.add_treatment(
                      selected_plate["id"],
                      w_pos,
                      str(t_date),
                      t_comp_str,
                      t_conc_str,
                      t_cell.strip(),
                      comb_note,
                      t_analysis,
                  )
                st.success(
                    f"총 {len(wells_to_add)}개 Well ({raw_well}) 일괄 저장 완료!"
                )
              else:
                db.add_treatment(
                    selected_plate["id"],
                    raw_well,
                    str(t_date),
                    t_comp_str,
                    t_conc_str,
                    t_cell.strip(),
                    comb_note,
                    t_analysis,
                )
                st.success(f"Well [{raw_well}] 처리 내역 저장 완료!")
              st.rerun()
            else:
              st.error("Well 위치를 입력해 주세요.")

      with t_tab2:
        if treatments:
          df_treat = pd.DataFrame(treatments)

          # 표시용 정리
          df_display = df_treat.copy()
          df_display["Basal Media"] = df_display.apply(get_basal_media, axis=1)
          df_display["사진 유무"] = df_display.apply(
              lambda x: "📷 유" if extract_image_data(x) else "무", axis=1
          )
          df_display["처리 물질 요약"] = df_display.apply(
              lambda x: format_compound_summary(
                  x["compound_name"], x["concentration"]
              ),
              axis=1,
          )

          cols_show = [
              "id",
              "treatment_date",
              "well_position",
              "cell_info",
              "analysis_status",
              "Basal Media",
              "처리 물질 요약",
              "사진 유무",
          ]
          st.dataframe(
              df_display[cols_show], use_container_width=True, hide_index=True
          )

          with st.expander("🗑️ 특정 처리 내역 ID 기준 개별 삭제"):
            del_id = st.number_input("삭제할 레코드 ID", min_value=1, step=1)
            if st.button("내역 삭제", type="secondary"):
              db.delete_treatment(del_id)
              st.toast(f"ID {del_id} 삭제 완료", icon="🗑️")
              st.rerun()
        else:
          st.info("등록된 처리 내역이 없습니다.")

    # ======================================================================
    # [TAB 4] 날짜별 & 조건별 사진 비교 시각화
    # ======================================================================
    with tab_compare:
      st.markdown("### 📸 날짜별 & 조건별 사진 비교 시각화")
      st.caption(
          "등록된 현미경 이미지 데이터를 날짜 흐름 및 처리 조건별로 한눈에"
          " 비교 분석합니다."
      )

      # 이미지 데이터가 존재하는 처리 내역만 추출
      img_treatments = [t for t in treatments if extract_image_data(t)]

      if not img_treatments:
        st.info(
            "💡 현재 등록된 현미경/결과 사진이 없습니다. [탭 1] 또는 [탭 3]에서"
            " Well별 사진을 등록해 주세요."
        )
      else:
        comp_mode = st.radio(
            "🔎 비교 시각화 방식 선택",
            ["📅 특정 Well의 날짜별 시계열 변화 비교", "🧪 동일 날짜 내 Well/조건별 비교"],
            horizontal=True,
        )

        if "특정 Well" in comp_mode:
          img_wells = sorted(
              list(set([t["well_position"].upper() for t in img_treatments]))
          )
          sel_well_img = st.selectbox(
              "🎯 대상 Well 선택", options=img_wells, key="sel_well_img_comp"
          )

          well_imgs = [
              t
              for t in img_treatments
              if t["well_position"].upper() == sel_well_img
          ]
          well_imgs = sorted(well_imgs, key=lambda x: x["treatment_date"])

          st.markdown(
              f"##### 📈 Well [{sel_well_img}] 시계열 현미경 관찰 이력"
              f" ({len(well_imgs)}건)"
          )

          img_cols = st.columns(min(len(well_imgs), 4))
          for idx, item in enumerate(well_imgs):
            col_target = img_cols[idx % 4]
            b64_data = extract_image_data(item)
            basal_txt = get_basal_media(item)
            cond_txt = format_compound_summary(
                item["compound_name"], item["concentration"]
            )

            with col_target:
              st.markdown(
                  f"**📅 {item['treatment_date']}**<br><span"
                  " style='font-size:12px; color:#475569;'>"
                  f"🧬 {item.get('cell_info', '-')}<br>🥛 {basal_txt}<br>🧪"
                  f" {cond_txt}</span>",
                  unsafe_allow_html=True,
              )
              display_image_from_b64(
                  b64_data, caption=f"{sel_well_img} ({item['treatment_date']})"
              )
              st.markdown("---")

        else:
          img_dates = sorted(
              list(set([t["treatment_date"] for t in img_treatments]))
          )
          sel_date_img = st.selectbox(
              "📅 관찰 일자 선택", options=img_dates, key="sel_date_img_comp"
          )

          date_imgs = [
              t for t in img_treatments if t["treatment_date"] == sel_date_img
          ]
          date_imgs = sorted(date_imgs, key=lambda x: x["well_position"])

          st.markdown(
              f"##### 🧫 {sel_date_img} 기준 Well별 현미경 비교 ({len(date_imgs)}건)"
          )

          img_cols = st.columns(min(len(date_imgs), 4))
          for idx, item in enumerate(date_imgs):
            col_target = img_cols[idx % 4]
            b64_data = extract_image_data(item)
            basal_txt = get_basal_media(item)
            cond_txt = format_compound_summary(
                item["compound_name"], item["concentration"]
            )

            with col_target:
              st.markdown(
                  f"**🎯 Well [{item['well_position']}]**<br><span"
                  " style='font-size:12px; color:#475569;'>"
                  f"🧬 {item.get('cell_info', '-')}<br>🥛 {basal_txt}<br>🧪"
                  f" {cond_txt}</span>",
                  unsafe_allow_html=True,
              )
              display_image_from_b64(
                  b64_data, caption=f"Well {item['well_position']}"
              )
              st.markdown("---")
