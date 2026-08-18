import streamlit as st
import pandas as pd
import db
import style

# --- 1. 페이지 설정 및 디자인 서식 적용 ---
st.set_page_config(page_title="연구 프로젝트 관리", page_icon="🧪", layout="wide")

# 화면 전체 레이아웃을 좌측 밀착(Left-aligned)시키는 Custom CSS
st.markdown("""
    <style>
        /* 메인 컨테이너의 좌측 여백을 최소화하고 왼쪽으로 정렬 */
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

st.title("🧪 연구 프로젝트")
st.caption("새 연구 프로젝트를 생성하고 그룹별로 분류/검색하며, Plate 및 Well별 처리 흐름을 상세 조회합니다.")

# DB 초기화 및 데이터 로드
db.init_db()
projects = db.get_projects()

# --- 2. Session State 초기화 (사이드바 드롭다운 관리용) ---
if "group_options" not in st.session_state:
    existing_groups = sorted(list(set([p["group_name"] for p in projects if p.get("group_name")])))
    default_groups = ["기본 연구"]
    st.session_state.group_options = list(dict.fromkeys(default_groups + existing_groups))

if "name_presets" not in st.session_state:
    st.session_state.name_presets = ["분화"]

# =========================================================
# 사이드바: 새 프로젝트 생성 & 드롭다운 관리
# =========================================================
with st.sidebar:
    st.header("➕ 새 프로젝트")
    
    # 1) 카테고리 / 그룹 선택
    group_select_list = st.session_state.group_options + ["➕ 직접 입력"]
    selected_group_opt = st.selectbox("📁 그룹 / 카테고리 선택", group_select_list)
    group_init_val = "" if selected_group_opt == "➕ 직접 입력" else selected_group_opt
    p_group = st.text_input("카테고리 명칭 (필요시 수정 가능)", value=group_init_val, placeholder="예: 장 상피 모델")

    # 2) 프로젝트명 선택
    name_select_list = st.session_state.name_presets + ["➕ 직접 입력"]
    selected_name_opt = st.selectbox("🧪 프로젝트명 선택", name_select_list)
    name_init_val = "" if selected_name_opt == "➕ 직접 입력" else selected_name_opt
    p_name = st.text_input("프로젝트명 (필요시 수정 가능)*", value=name_init_val, placeholder="예: HIO-Vessel Co-culture")

    # 3) 드롭다운 항목 관리 (삭제)
    with st.expander("⚙️ 드롭다운 항목 삭제/관리"):
        del_target = st.radio("삭제할 드롭다운 항목 종류", ["카테고리 항목", "프로젝트명 프리셋"], horizontal=True)
        if del_target == "카테고리 항목":
            if st.session_state.group_options:
                item_to_del = st.selectbox("삭제할 카테고리 선택", st.session_state.group_options, key="del_cat_sb")
                if st.button("🗑️ 선택한 카테고리 항목 삭제", use_container_width=True):
                    st.session_state.group_options.remove(item_to_del)
                    st.toast(f"'{item_to_del}' 항목이 삭제되었습니다.")
                    st.rerun()
            else:
                st.caption("삭제할 카테고리 항목이 없습니다.")
        else:
            if st.session_state.name_presets:
                item_to_del = st.selectbox("삭제할 프로젝트명 선택", st.session_state.name_presets, key="del_name_sb")
                if st.button("🗑️ 선택한 프로젝트명 항목 삭제", use_container_width=True):
                    st.session_state.name_presets.remove(item_to_del)
                    st.toast(f"'{item_to_del}' 항목이 삭제되었습니다.")
                    st.rerun()
            else:
                st.caption("삭제할 프로젝트명 항목이 없습니다.")

    st.divider()

    # 4) 색상 프리셋 시각화
    color_map = {
        "#3B82F6": "🔵 파랑",
        "#10B981": "🟢 초록",
        "#F59E0B": "🟠 주황",
        "#EF4444": "🔴 빨강",
        "#8B5CF6": "🟣 보라",
        "#EC4899": "🩷 핑크",
        "#6B7280": "🔘 회색"
    }
    
    selected_preset = st.radio(
        "🎨 색상 프리셋 선택",
        options=list(color_map.keys()),
        format_func=lambda c: color_map[c],
        horizontal=True,
        index=0
    )

    swatch_html = "".join([
        f'<div style="display:inline-block; width:20px; height:20px; background-color:{c}; border-radius:4px; margin-right:6px; vertical-align:middle; border: {"2px solid #0f172a" if c == selected_preset else "1px solid #cbd5e1"};"></div>'
        for c in color_map.keys()
    ])
    st.markdown(f'<div style="margin-bottom:12px; font-size:13px; color:#475569;"><b>컬러 팔레트 미리보기:</b> {swatch_html}</div>', unsafe_allow_html=True)

    p_color = st.color_picker("색상 커스텀 지정", value=selected_preset)
    p_desc = st.text_area("설명", placeholder="프로젝트 목적 및 실험 조건 작성")

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
        else:
            st.error("프로젝트명을 입력하거나 선택해 주세요.")

# =========================================================
# 메인 영역: 좌/우 화면 분할 (좌측: 목록 및 필터 / 우측: 상세 분석)
# =========================================================
if not projects:
    st.info("왼쪽 사이드바에서 프로젝트를 먼저 생성해 주세요.")
    st.stop()

groups = sorted({p["group_name"] for p in projects if p["group_name"]})

# 메인 화면을 좌/우 [1 : 2.5] 비율로 분할
col_left, col_right = st.columns([1, 2.5], gap="large")

# ---------------------------------------------------------
# [좌측 영역] 검색, 필터 및 프로젝트 카드 목록
# ---------------------------------------------------------
with col_left:
    st.subheader("📁 프로젝트 선택")
    
    selected_group = st.selectbox("📁 그룹 필터", ["전체"] + groups)
    search_kw = st.text_input("🔍 검색", placeholder="프로젝트명 / 설명 입력")

    filtered = []
    for p in projects:
        if selected_group != "전체" and p["group_name"] != selected_group:
            continue
        if search_kw.strip():
            kw = search_kw.strip().lower()
            if kw not in (p["name"] or "").lower() and kw not in (p["description"] or "").lower():
                continue
        filtered.append(p)

    if not filtered:
        st.warning("일치하는 프로젝트가 없습니다.")
    else:
        st.caption(f"💡 총 {len(filtered)}개의 프로젝트")

        # 세션 내 선택된 프로젝트 ID 보장
        if "selected_project_id" not in st.session_state or st.session_state.selected_project_id not in [p["id"] for p in filtered]:
            st.session_state.selected_project_id = filtered[0]["id"]

        # 프로젝트 목록을 좌측 카드 세로형 리스트로 표시
        for p in filtered:
            is_selected = (p["id"] == st.session_state.selected_project_id)
            with st.container(border=True):
                border_style = f"border-left: 5px solid {p['color_code']};"
                st.markdown(
                    f"""
                    <div style="{border_style} padding-left: 8px; margin-bottom: 6px;">
                        <div style="display:flex; align-items:center; justify-content:space-between;">
                            <span style="font-size:15px; font-weight:bold; color:#0f172a;">{p['name']}</span>
                            <span style="background-color:{p['color_code']}; padding:2px 7px; border-radius:10px; color:#fff; font-size:10px; font-weight:bold;">
                                {p['group_name'] or '기본'}
                            </span>
                        </div>
                        <div style="font-size:12px; color:#64748b; margin-top:4px;">{p['description'] or '설명 없음'}</div>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                btn_label = "✅ 현재 선택됨" if is_selected else "📌 상세 보기"
                if st.button(btn_label, key=f"btn_select_{p['id']}", use_container_width=True, disabled=is_selected):
                    st.session_state.selected_project_id = p["id"]
                    st.rerun()

# ---------------------------------------------------------
# [우측 영역] 선택된 프로젝트의 상세 정보 (Metrics 및 탭)
# ---------------------------------------------------------
with col_right:
    if filtered:
        proj = next(p for p in filtered if p["id"] == st.session_state.selected_project_id)

        # 타이틀
        st.subheader(f"📊 [{proj['group_name'] or '기본'}] {proj['name']} 실험 요약")

        # 1) Metrics 카드
        plates = db.get_plates(proj["id"])
        treatments = db.get_treatments_by_project(proj["id"])
        logs = db.get_daily_logs(proj["id"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Plate 수", f"{len(plates)}개")
        m2.metric("처리 기록", f"{len(treatments)}건")
        m3.metric("사용 Well 수", f"{len({(t['plate_id'], t['well_position']) for t in treatments})}개")
        m4.metric("실험 기록일", f"{len(set([t['treatment_date'] for t in treatments] + [l['log_date'] for l in logs]))}일")

        st.write("")

        # 2) 탭 메뉴 (Well별 보기 / 물질 처리 흐름 / 프로젝트 수정 및 삭제)
        tab1, tab2, tab3 = st.tabs(["🧫 Well별 한눈에 보기", "🕒 물질 처리 흐름", "⚙️ 프로젝트 수정/삭제"])

        # Tab 1: Well별 한눈에 보기
        with tab1:
            if not plates:
                st.info("등록된 Plate가 없습니다.")
            else:
                for plate in plates:
                    pt = [t for t in treatments if t["plate_id"] == plate["id"]]
                    with st.container(border=True):
                        st.markdown(f"**🧫 {plate['name']}** · {plate['rows']}×{plate['cols']} · 총 처리 {len(pt)}건")
                        if not pt:
                            st.caption("이 Plate에는 등록된 처리 기록이 없습니다.")
                            continue

                        grouped = {}
                        for t in pt:
                            grouped.setdefault(t["well_position"], []).append(t)

                        rows = []
                        for well, items in sorted(grouped.items()):
                            items = sorted(items, key=lambda x: x["treatment_date"])
                            flow = " → ".join(
                                f"{x['treatment_date'][5:]} {x['compound_name']}"
                                + (f" ({x['concentration']})" if x["concentration"] else "")
                                for x in items
                            )
                            last = items[-1]
                            rows.append({
                                "Well": well,
                                "처리 횟수": len(items),
                                "첫 처리일": items[0]["treatment_date"],
                                "최근 처리일": last["treatment_date"],
                                "처리 흐름": flow,
                                "세포/오가노이드": last["cell_info"] or "-",
                            })
                        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                        st.caption("💡 '처리 흐름'에서 각 Well에 날짜 순으로 어떤 물질이 처리됐는지 바로 확인할 수 있습니다.")

        # Tab 2: 물질 처리 흐름 (타임라인)
        with tab2:
            st.subheader("🗓️ 날짜순 실험 흐름")
            if not treatments and not logs:
                st.info("아직 기록된 실험 내역이 없습니다.")
            else:
                items = []
                for t in treatments:
                    items.append({
                        "date": str(t["treatment_date"]),
                        "type": "🧪 물질",
                        "plate": t["plate_name"],
                        "well": t["well_position"],
                        "detail": t["compound_name"],
                        "condition": t["concentration"] or "",
                        "note": t["note"] or ""
                    })
                for l in logs:
                    items.append({
                        "date": str(l["log_date"]),
                        "type": "📝 Daily Log",
                        "plate": "",
                        "well": "",
                        "detail": l["content"],
                        "condition": "",
                        "note": ""
                    })

                df = pd.DataFrame(items)
                df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.sort_values(["date_dt", "plate", "well", "detail"], ascending=[True, True, True, True])

                for d, group in df.groupby("date", sort=True):
                    st.markdown(f"#### 📅 {d}")
                    for _, r in group.iterrows():
                        if r["type"] == "🧪 물질":
                            loc = f"{r['plate']} · {r['well']}"
                            cond = f" ({r['condition']})" if r["condition"] else ""
                            note = f" - {r['note']}" if r["note"] else ""
                            st.markdown(
                                f"""
                                <div style="margin:4px 0; padding:8px 12px; border-left:4px solid #3b82f6; background:#f8fafc; font-size:13px; border-radius:4px;">
                                    <b>🧪 {r['detail']}</b>{cond}<br>
                                    <span style="color:#64748b;">위치: {loc}{note}</span>
                                </div>
                                """, unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                f"""
                                <div style="margin:4px 0; padding:8px 12px; border-left:4px solid #10b981; background:#f8fafc; font-size:13px; border-radius:4px;">
                                    <b>📝 Daily Log:</b> {r['detail']}
                                </div>
                                """, unsafe_allow_html=True
                            )

        # Tab 3: 프로젝트 수정 및 휴지통 이동
        with tab3:
            with st.container(border=True):
                st.subheader("⚙️ 프로젝트 정보 수정")
                edit_name = st.text_input("프로젝트명", value=proj["name"], key="edit_name_compact")
                edit_group = st.text_input("그룹명", value=proj["group_name"], key="edit_group_compact")
                edit_color = st.color_picker("색상", value=proj["color_code"], key="edit_color_compact")
                edit_desc = st.text_area("설명", value=proj["description"] or "", key="edit_desc_compact")
                
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("💾 변경사항 저장", use_container_width=True, type="primary"):
                    db.update_project(proj["id"], edit_name, edit_group, edit_color, edit_desc)
                    st.success("프로젝트 정보가 수정되었습니다.")
                    st.rerun()
                if col_btn2.button("🗑️ 휴지통으로 이동", use_container_width=True):
                    db.delete_project(proj["id"])
                    st.session_state.pop("selected_project_id", None)
                    st.toast("프로젝트가 휴지통으로 이동되었습니다. (📥 휴지통에서 복구 가능)", icon="🗑️")
                    st.rerun()
