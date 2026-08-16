import streamlit as st
import pandas as pd
import db
import style

st.set_page_config(page_title="프로젝트 관리", page_icon="🧪", layout="wide")
style.set_narrow_layout()
st.title("🧪 연구 프로젝트")

db.init_db()
projects = db.get_projects()

# --- Session State를 활용한 드롭다운 목록 초기화 ---
if "group_options" not in st.session_state:
    existing_groups = sorted(list(set([p["group_name"] for p in projects if p.get("group_name")])))
    default_groups = ["기본 연구"]
    st.session_state.group_options = list(dict.fromkeys(default_groups + existing_groups))

if "name_presets" not in st.session_state:
    st.session_state.name_presets = [
        "분화"
    ]

with st.sidebar:
    st.header("➕ 새 프로젝트")
    
    # 1. 카테고리 / 그룹 드롭다운 선택 및 수정
    group_select_list = st.session_state.group_options + ["➕ 직접 입력"]
    selected_group_opt = st.selectbox("📁 그룹 / 카테고리 선택", group_select_list)
    group_init_val = "" if selected_group_opt == "➕ 직접 입력" else selected_group_opt
    p_group = st.text_input("카테고리 명칭 (필요시 수정 가능)", value=group_init_val, placeholder="예: 장 상피 모델")

    # 2. 프로젝트명 드롭다운 선택 및 수정
    name_select_list = st.session_state.name_presets + ["➕ 직접 입력"]
    selected_name_opt = st.selectbox("🧪 프로젝트명 선택", name_select_list)
    name_init_val = "" if selected_name_opt == "➕ 직접 입력" else selected_name_opt
    p_name = st.text_input("프로젝트명 (필요시 수정 가능)*", value=name_init_val, placeholder="예: HIO-Vessel Co-culture")

    # --- [신규] 드롭다운 항목 관리 (삭제) 영역 ---
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

    # 3. 색상 프리셋 시각화 (라디오 버튼 아이콘 + HTML 컬러 칩 팔레트)
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
            
            # 신규 등록된 항목이면 Session State에 자동으로 추가
            if final_group not in st.session_state.group_options:
                st.session_state.group_options.append(final_group)
            if final_name not in st.session_state.name_presets:
                st.session_state.name_presets.append(final_name)
                
            db.add_project(final_name, final_group, p_color, p_desc.strip())
            st.success(f"'{final_name}' 프로젝트가 생성되었습니다.")
            st.rerun()
        else:
            st.error("프로젝트명을 입력하거나 선택해 주세요.")

if not projects:
    st.info("왼쪽에서 프로젝트를 먼저 만들어 주세요.")
    st.stop()

# compact project list
groups = sorted({p["group_name"] for p in projects if p["group_name"]})
c1, c2 = st.columns([1, 2])
with c1:
    selected_group = st.selectbox("그룹 필터", ["전체"] + groups)
with c2:
    search_kw = st.text_input("🔍 검색", placeholder="프로젝트명 / 설명")

filtered = []
for p in projects:
    if selected_group != "전체" and p["group_name"] != selected_group:
        continue
    if search_kw.strip():
        kw = search_kw.strip().lower()
        if kw not in (p["name"] or "").lower() and kw not in (p["description"] or "").lower():
            continue
    filtered.append(p)

labels = [f"[{p['group_name'] or '기본'}] {p['name']}" for p in filtered]
if not labels:
    st.info("검색 결과가 없습니다.")
    st.stop()

if "selected_project_id" not in st.session_state or st.session_state.selected_project_id not in [p["id"] for p in filtered]:
    st.session_state.selected_project_id = filtered[0]["id"]

selected_id = st.selectbox(
    "📌 상세히 볼 실험",
    [p["id"] for p in filtered],
    index=[p["id"] for p in filtered].index(st.session_state.selected_project_id),
    format_func=lambda pid: next(f"[{p['group_name'] or '기본'}] {p['name']}" for p in filtered if p["id"] == pid)
)
st.session_state.selected_project_id = selected_id
proj = next(p for p in filtered if p["id"] == selected_id)

# compact project header
st.markdown(
    f"""<div style="border-left:6px solid {proj['color_code']};padding:8px 12px;
    background:#f8fafc;border-radius:6px;margin:8px 0 12px;">
    <b style="font-size:20px">{proj['name']}</b>
    <span style="margin-left:10px;color:#64748b">{proj['group_name']}</span>
    <div style="font-size:12px;color:#64748b">{proj['description'] or '설명 없음'}</div>
    </div>""", unsafe_allow_html=True)

plates = db.get_plates(proj["id"])
treatments = db.get_treatments_by_project(proj["id"])
logs = db.get_daily_logs(proj["id"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Plate", len(plates))
m2.metric("처리 기록", len(treatments))
m3.metric("사용 Well", len({(t["plate_id"], t["well_position"]) for t in treatments}))
m4.metric("실험 기록일", len(set([t["treatment_date"] for t in treatments] + [l["log_date"] for l in logs])))

st.divider()

tab1, tab2, tab3 = st.tabs(["🧫 Well별 한눈에 보기", "🕒 물질 처리 흐름", "⚙️ 프로젝트 수정/삭제"])

with tab1:
    if not plates:
        st.info("등록된 Plate가 없습니다.")
    else:
        for plate in plates:
            pt = [t for t in treatments if t["plate_id"] == plate["id"]]
            st.markdown(f"**🧫 {plate['name']}**  · {plate['rows']}×{plate['cols']} · 처리 {len(pt)}건")
            if not pt:
                st.caption("처리 기록 없음")
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
                    "첫 처리": items[0]["treatment_date"],
                    "최근 처리": last["treatment_date"],
                    "처리 흐름": flow,
                    "세포/오가노이드": last["cell_info"] or "",
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption("💡 '처리 흐름'에서 각 Well에 날짜 순으로 어떤 물질이 처리됐는지 바로 확인할 수 있습니다.")

with tab2:
    st.subheader("날짜순 실험 흐름")
    if not treatments and not logs:
        st.info("아직 실험 기록이 없습니다.")
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
            st.markdown(f"### 📅 {d}")
            for _, r in group.iterrows():
                if r["type"] == "🧪 물질":
                    loc = f"{r['plate']} · {r['well']}"
                    cond = f" · {r['condition']}" if r["condition"] else ""
                    note = f" · {r['note']}" if r["note"] else ""
                    st.markdown(
                        f"""<div style="margin:3px 0;padding:6px 10px;border-left:4px solid #3b82f6;
                        background:#f8fafc;font-size:13px;">
                        <b>{r['detail']}</b>{cond}<br>
                        <span style="color:#64748b">{loc}{note}</span>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"""<div style="margin:3px 0;padding:6px 10px;border-left:4px solid #10b981;
                        background:#f8fafc;font-size:13px;"><b>📝 Daily Log</b> {r['detail']}</div>""",
                        unsafe_allow_html=True)

with tab3:
    with st.expander("프로젝트 정보 수정", expanded=False):
        edit_name = st.text_input("프로젝트명", value=proj["name"], key="edit_name_compact")
        edit_group = st.text_input("그룹명", value=proj["group_name"], key="edit_group_compact")
        edit_color = st.color_picker("색상", value=proj["color_code"], key="edit_color_compact")
        edit_desc = st.text_area("설명", value=proj["description"] or "", key="edit_desc_compact")
        a, b = st.columns(2)
        if a.button("💾 저장", use_container_width=True):
            db.update_project(proj["id"], edit_name, edit_group, edit_color, edit_desc)
            st.rerun()
        if b.button("🗑️ 휴지통으로 이동", type="primary", use_container_width=True):
            db.delete_project(proj["id"])
            st.session_state.pop("selected_project_id", None)
            st.toast("프로젝트가 휴지통으로 이동되었습니다. (📥 휴지통에서 복구 가능)", icon="🗑️")
            st.rerun()
