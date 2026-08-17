import streamlit as st
import datetime
import db
import style

st.set_page_config(page_title="Daily Log", page_icon="📅", layout="wide")
style.apply_custom_style()

st.title("📅 연구 데일리 로그")
st.caption("프로젝트별 관찰 일지 및 연구 기록을 일자별로 관리합니다.")

db.init_db()
projects = db.get_projects()

if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다.")
else:
    proj_map = {f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID: {p['id']})": p for p in projects}
    options = list(proj_map.keys())

    if "selected_log_proj_label" not in st.session_state or st.session_state.selected_log_proj_label not in options:
        st.session_state.selected_log_proj_label = options[0]

    # 프로젝트 선택 영역
    col_proj, _ = st.columns([1, 1], gap="large")
    with col_proj:
        selected_label = st.selectbox("📌 프로젝트 선택", options=options, key="selected_log_proj_label")
        selected_proj = proj_map[selected_label]

    st.markdown("---")

    # 입력 폼 컨테이너 통일
    with st.container(border=True):
        st.markdown("##### 📝 새 데일리 로그 작성")
        with st.form("add_log_form", clear_on_submit=True):
            log_date = st.date_input("로그 일자", datetime.date.today())
            log_content = st.text_area("연구 관찰 및 기록 내용", placeholder="오늘의 관찰 결과, 세포 상태, 비고 사항 기록")
            submitted = st.form_submit_button("로그 추가", use_container_width=True, type="primary")
            if submitted:
                if log_content.strip():
                    db.add_daily_log(selected_proj['id'], str(log_date), log_content.strip())
                    st.success("데일리 로그가 등록되었습니다.")
                    st.rerun()

    st.markdown("---")
    logs = db.get_daily_logs(selected_proj['id'])
    if logs:
        st.caption(f"💡 총 {len(logs)}건 · 2개씩 나란히 표시됩니다.")
        log_cols = st.columns(2)
        for idx, log in enumerate(logs):
            with log_cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"**📅 {log['log_date']}**")
                    st.info(log['content'])
                    if st.button("🗑️ 휴지통으로 이동", key=f"btn_del_log_{log['id']}", use_container_width=True):
                        db.delete_daily_log(log['id'])
                        st.toast("로그가 휴지통으로 이동되었습니다.", icon="🗑️")
                        st.rerun()
    else:
        st.caption("아직 등록된 로그가 없습니다.")
