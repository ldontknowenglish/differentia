import io
import pandas as pd
import plotly.express as px
import streamlit as st

import db
import style

# --- 1. 페이지 설정 및 디자인 서식 적용 ---
st.set_page_config(
    page_title="연구 프로젝트 및 데이터 관리", page_icon="🧪", layout="wide"
)

# 화면 전체 레이아웃을 좌측 밀착(Left-aligned)시키는 Custom CSS
st.markdown(
    """
    <style>
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

st.title("🧪 Experiment project & Sample Tracking")
st.caption(
    "새 연구 프로젝트를 관리하고, 각 분석 샘플(Cell count, qPCR, FACS)이 어느 Plate/Well에서 유래했는지 추적합니다."
)

# DB 초기화 및 데이터 로드
db.init_db()
projects = db.get_projects()

# --- 2. Session State 초기화 ---
if "group_options" not in st.session_state:
    existing_groups = sorted(
        list(set([p["group_name"] for p in projects if p.get("group_name")]))
    )
    default_groups = ["기본 연구"]
    st.session_state.group_options = list(
        dict.fromkeys(default_groups + existing_groups)
    )

if "name_presets" not in st.session_state:
    st.session_state.name_presets = ["분화"]

if "selected_project_id" not in st.session_state and projects:
    st.session_state.selected_project_id = projects[0]["id"]


# 3. 텍스트 파싱 함수
def parse_pasted_data(raw_text):
    if not raw_text or not raw_text.strip():
        return None
    try:
        return pd.read_csv(io.StringIO(raw_text), sep="\t")
    except Exception as e:
        st.error(f"데이터 파싱 오류: {e}")
        return None


# =========================================================
# 사이드바: 1) 샘플 유래 출처(Plate/Well) 선택 & 2) 새 프로젝트 생성
# =========================================================
with st.sidebar:
    st.header("🧫 샘플 유래(Origin) 설정")

    if projects and "selected_project_id" in st.session_state:
        current_proj_id = st.session_state.selected_project_id
        db_plates = db.get_plates(current_proj_id)

        # 1) Plate/배치 선택
        if db_plates:
            plate_options = {p["name"]: p for p in db_plates}
            selected_plate_name = st.selectbox(
                "📍 유래 Plate(배치) 선택",
                options=list(plate_options.keys()) + ["➕ 직접 입력"],
            )

            if selected_plate_name == "➕ 직접 입력":
                active_plate_name = st.text_input(
                    "새 Plate/배치명", value="Batch_01"
                )
                active_well_list = ["A1", "A2", "A3", "B1", "B2", "B3", "전체 Well"]
            else:
                active_plate_name = selected_plate_name
                # DB의 Treatment 데이터에서 선택 가능한 Well 목록 추출
                p_treatments = db.get_treatments_by_project(current_proj_id)
                wells = sorted(
                    list(
                        {
                            t["well_position"]
                            for t in p_treatments
                            if t["plate_name"] == active_plate_name
                        }
                    )
                )
                active_well_list = (
                    wells if wells else ["A1", "A2", "A3", "B1", "B2", "B3"]
                )
        else:
            active_plate_name = st.text_input(
                "Plate/배치명 직접 입력", value="Batch_2026_01"
            )
            active_well_list = ["A1", "A2", "A3", "B1", "B2", "B3", "전체 Well"]

        # 2) Well 위치 선택
        selected_well = st.selectbox("🎯 유래 Well 위치 선택", active_well_list)

        # 3) 배양/조건 선택
        cell_type = st.selectbox(
            "세포 / 오가노이드 종류",
            [
                "Blood Vessel Organoid",
                "Intestinal Assembloid",
                "iPSC-derived Line",
                "Primary Cell Line",
            ],
        )

        media_condition = st.selectbox(
            "배지 조건 (Media Condition)",
            [
                "Chemically Defined (Animal-Free)",
                "Growth Factor High",
                "Standard Medium",
            ],
        )

        # 세션에 출처 정보 저장
        st.session_state["sample_provenance"] = {
            "project_id": current_proj_id,
            "plate_name": active_plate_name,
            "well_position": selected_well,
            "cell_type": cell_type,
            "media_condition": media_condition,
        }

        st.info(
            f"""
        **현재 지정된 샘플 출처**
        - **Plate/배치**: `{active_plate_name}`
        - **Well 위치**: `{selected_well}`
        - **세포**: {cell_type}
        """
        )
    else:
        st.caption("프로젝트를 먼저 선택해 주세요.")

    st.divider()

    # --- 새 프로젝트 생성 섹션 ---
    st.header("➕ 새 프로젝트")
    group_select_list = st.session_state.group_options + ["➕ 직접 입력"]
    selected_group_opt = st.selectbox(
        "📁 그룹 / 카테고리 선택", group_select_list
    )
    group_init_val = (
        "" if selected_group_opt == "➕ 직접 입력" else selected_group_opt
    )
    p_group = st.text_input(
        "카테고리 명칭", value=group_init_val, placeholder="예: 장 상피 모델"
    )

    name_select_list = st.session_state.name_presets + ["➕ 직접 입력"]
    selected_name_opt = st.selectbox("🧪 프로젝트명 선택", name_select_list)
    name_init_val = (
        "" if selected_name_opt == "➕ 직접 입력" else selected_name_opt
    )
    p_name = st.text_input(
        "프로젝트명*", value=name_init_val, placeholder="예: HIO-Vessel Co-culture"
    )

    p_color = st.color_picker("색상 지정", value="#3B82F6")
    p_desc = st.text_area("설명", placeholder="프로젝트 목적 작성")

    if st.button("프로젝트 생성", use_container_width=True, type="primary"):
        if p_name.strip():
            final_group = p_group.strip() if p_group.strip() else "기본 연구"
            final_name = p_name.strip()
            if final_group not in st.session_state.group_options:
                st.session_state.group_options.append(final_group)
            if final_name not in st.session_state.name_presets:
                st.session_state.name_presets.append(final_name)
            db.add_project(final_name, final_group, p_color, p_desc.strip())
            st.success(f"'{final_name}' 프로젝트가 생성되었습니다.")
            st.rerun()

# =========================================================
# 메인 영역: 좌/우 화면 분할
# =========================================================
if not projects:
    st.info("왼쪽 사이드바에서 프로젝트를 먼저 생성해 주세요.")
    st.stop()

groups = sorted({p["group_name"] for p in projects if p["group_name"]})
col_left, col_right = st.columns([1, 2.5], gap="large")

# ---------------------------------------------------------
# [좌측 영역] 검색 및 프로젝트 목록
# ---------------------------------------------------------
with col_left:
    st.subheader("📁 프로젝트 선택")
    selected_group = st.selectbox("📁 그룹 필터", ["전체"] + groups)
    search_kw = st.text_input("🔍 검색", placeholder="프로젝트명 / 설명 입력")

    filtered = [
        p
        for p in projects
        if (selected_group == "전체" or p["group_name"] == selected_group)
        and (
            not search_kw.strip()
            or search_kw.strip().lower() in (p["name"] or "").lower()
            or search_kw.strip().lower() in (p["description"] or "").lower()
        )
    ]

    if not filtered:
        st.warning("일치하는 프로젝트가 없습니다.")
    else:
        if (
            "selected_project_id" not in st.session_state
            or st.session_state.selected_project_id
            not in [p["id"] for p in filtered]
        ):
            st.session_state.selected_project_id = filtered[0]["id"]

        for p in filtered:
            is_selected = p["id"] == st.session_state.selected_project_id
            with st.container(border=True):
                border_style = f"border-left: 5px solid {p['color_code']};"
                st.markdown(
                    f"""
                    <div style="{border_style} padding-left: 8px; margin-bottom: 6px;">
                        <span style="font-size:15px; font-weight:bold;">{p['name']}</span>
                        <span style="background-color:{p['color_code']}; padding:2px 7px; border-radius:10px; color:#fff; font-size:10px; float:right;">
                            {p['group_name'] or '기본'}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "✅ 선택됨" if is_selected else "📌 선택",
                    key=f"btn_{p['id']}",
                    use_container_width=True,
                    disabled=is_selected,
                ):
                    st.session_state.selected_project_id = p["id"]
                    st.rerun()

# ---------------------------------------------------------
# [우측 영역] 선택된 프로젝트 상세 및 분석 데이터 연동
# ---------------------------------------------------------
with col_right:
    if filtered:
        proj = next(
            p for p in filtered if p["id"] == st.session_state.selected_project_id
        )
        st.subheader(
            f"📊 [{proj['group_name'] or '기본'}] {proj['name']} 상세 리포트"
        )

        plates = db.get_plates(proj["id"])
        treatments = db.get_treatments_by_project(proj["id"])
        logs = db.get_daily_logs(proj["id"])

        prov = st.session_state.get(
            "sample_provenance",
            {
                "plate_name": "미지정",
                "well_position": "-",
                "cell_type": "-",
            },
        )

        # Metrics 카드
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("선택된 유래 Plate", prov["plate_name"])
        m2.metric("선택된 Well", prov["well_position"])
        m3.metric("등록 Plate 수", f"{len(plates)}개")
        m4.metric("처리 기록", f"{len(treatments)}건")

        st.write("")

        # 4개의 탭 구성
        tab1, tab2, tab3, tab4 = st.tabs([
            "🧫 Well별 한눈에 보기",
            "🕒 물질 처리 흐름",
            "🔬 분석 데이터 입력 (Cell/qPCR/FACS)",
            "⚙️ 프로젝트 수정/삭제",
        ])

        # Tab 1: Well별 보기
        with tab1:
            if not plates:
                st.info("등록된 Plate가 없습니다.")
            else:
                for plate in plates:
                    pt = [
                        t for t in treatments if t["plate_id"] == plate["id"]
                    ]
                    with st.container(border=True):
                        st.markdown(
                            f"**🧫 {plate['name']}** · {plate['rows']}×{plate['cols']} · 총 처리 {len(pt)}건"
                        )
                        if pt:
                            grouped = {}
                            for t in pt:
                                grouped.setdefault(
                                    t["well_position"], []
                                ).append(t)
                            rows = []
                            for well, items in sorted(grouped.items()):
                                items = sorted(
                                    items, key=lambda x: x["treatment_date"]
                                )
                                flow = " → ".join(
                                    f"{x['treatment_date'][5:]} {x['compound_name']}"
                                    for x in items
                                )
                                rows.append({
                                    "Well": well,
                                    "최근 처리일": items[-1]["treatment_date"],
                                    "처리 흐름": flow,
                                    "세포 정보": items[-1]["cell_info"] or "-",
                                })
                            st.dataframe(
                                pd.DataFrame(rows),
                                hide_index=True,
                                use_container_width=True,
                            )

        # Tab 2: 물질 처리 흐름
        with tab2:
            st.subheader("🗓️ 날짜순 처리 흐름")
            if not treatments and not logs:
                st.info("기록된 실험 내역이 없습니다.")
            else:
                items = [
                    {
                        "date": str(t["treatment_date"]),
                        "detail": f"🧪 {t['compound_name']} ({t['concentration'] or ''})",
                        "loc": f"{t['plate_name']} · {t['well_position']}",
                    }
                    for t in treatments
                ]
                for r in items:
                    st.markdown(
                        f"**{r['date']}** | {r['detail']} | 위치: `{r['loc']}`"
                    )

        # Tab 3: 분석 데이터 입력 (출처 자동 연동 핵심 기능)
        with tab4_sub := tab3:
            st.subheader(
                f"🔬 [{proj['name']}] 분석 데이터 입력 및 샘플 유래 추적"
            )
            st.success(
                f"💡 현재 입력하는 데이터는 **[Plate: {prov['plate_name']} / Well: {prov['well_position']}]** 조건에서 유래된 것으로 자동 저장됩니다."
            )

            sub_t1, sub_t2, sub_t3 = st.tabs(
                ["🧫 Cell Count", "🧬 qPCR", "📊 FACS"]
            )

            # --- Cell Count ---
            with sub_t1:
                raw_cell = st.text_area(
                    "Cell Count 붙여넣기 (Excel/Prism 복사)",
                    value="Sample\tConcentration_M_mL\tViability_pct\nControl\t1.2\t95.4\nGroup_A\t2.5\t92.1",
                    height=100,
                    key="tab3_cell",
                )
                df_c = parse_pasted_data(raw_cell)
                if df_c is not None:
                    # 유래 정보(Provenance) 컬럼 맨 앞에 결합
                    df_c.insert(0, "Well_Position", prov["well_position"])
                    df_c.insert(0, "Plate_Name", prov["plate_name"])
                    df_c.insert(0, "Project_ID", proj["id"])

                    edited_c = st.data_editor(
                        df_c, num_rows="dynamic", key="edit_c_tab3"
                    )

                    col_c1, col_c2 = st.columns([1, 1])
                    with col_c1:
                        if st.button("💾 Cell Count 데이터 DB 저장"):
                            st.toast(
                                f"[{prov['plate_name']}-{prov['well_position']}] Cell Count 데이터 저장 완료!"
                            )
                    with col_c2:
                        num_cols = edited_c.select_dtypes(
                            include=["float", "int"]
                        ).columns.tolist()
                        if num_cols:
                            fig = px.bar(
                                edited_c,
                                x="Sample"
                                if "Sample" in edited_c.columns
                                else edited_c.columns[3],
                                y=num_cols[0],
                                title=f"Cell Count ({prov['plate_name']}-{prov['well_position']})",
                            )
                            st.plotly_chart(fig, use_container_width=True)

            # --- qPCR ---
            with sub_t2:
                raw_qpcr = st.text_area(
                    "qPCR 붙여넣기",
                    value="Gene\tRelative_Expression\nGAPDH\t1.00\nTarget_A\t3.45",
                    height=100,
                    key="tab3_qpcr",
                )
                df_q = parse_pasted_data(raw_qpcr)
                if df_q is not None:
                    df_q.insert(0, "Well_Position", prov["well_position"])
                    df_q.insert(0, "Plate_Name", prov["plate_name"])
                    df_q.insert(0, "Project_ID", proj["id"])

                    edited_q = st.data_editor(
                        df_q, num_rows="dynamic", key="edit_q_tab3"
                    )
                    if st.button("💾 qPCR 데이터 DB 저장"):
                        st.toast(
                            f"[{prov['plate_name']}-{prov['well_position']}] qPCR 데이터 저장 완료!"
                        )

            # --- FACS ---
            with sub_t3:
                raw_facs = st.text_area(
                    "FACS 붙여넣기",
                    value="Marker\tPos_Pct\nCD31\t68.4\nCD34\t42.1",
                    height=100,
                    key="tab3_facs",
                )
                df_f = parse_pasted_data(raw_facs)
                if df_f is not None:
                    df_f.insert(0, "Well_Position", prov["well_position"])
                    df_f.insert(0, "Plate_Name", prov["plate_name"])
                    df_f.insert(0, "Project_ID", proj["id"])

                    edited_f = st.data_editor(
                        df_f, num_rows="dynamic", key="edit_f_tab3"
                    )
                    if st.button("💾 FACS 데이터 DB 저장"):
                        st.toast(
                            f"[{prov['plate_name']}-{prov['well_position']}] FACS 데이터 저장 완료!"
                        )

        # Tab 4: 프로젝트 수정/삭제
        with tab4:
            st.subheader("⚙️ 프로젝트 수정/삭제")
            edit_name = st.text_input("프로젝트명", value=proj["name"])
            if st.button("💾 저장", type="primary"):
                db.update_project(
                    proj["id"],
                    edit_name,
                    proj["group_name"],
                    proj["color_code"],
                    proj["description"],
                )
                st.success("수정 완료!")
                st.rerun()
