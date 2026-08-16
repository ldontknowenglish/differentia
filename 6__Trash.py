import streamlit as st
import db
import style

st.set_page_config(page_title="휴지통", page_icon="🗑️", layout="wide")
style.set_narrow_layout()
st.title("🗑️ 휴지통 (Trash)")
st.caption("실수로 삭제한 항목을 여기서 확인하고 복구할 수 있습니다. '영구 삭제'를 누르기 전까지는 데이터가 안전하게 보관됩니다.")

db.init_db()

trash_projects = db.get_trash_projects()
trash_plates = db.get_trash_plates()
trash_treatments = db.get_trash_treatments()
trash_logs = db.get_trash_daily_logs()

total = len(trash_projects) + len(trash_plates) + len(trash_treatments) + len(trash_logs)

m1, m2, m3, m4 = st.columns(4)
m1.metric("삭제된 프로젝트", len(trash_projects))
m2.metric("삭제된 플레이트", len(trash_plates))
m3.metric("삭제된 처리 내역", len(trash_treatments))
m4.metric("삭제된 Daily Log", len(trash_logs))

st.divider()

if total == 0:
    st.info("💡 휴지통이 비어 있습니다.")
    st.stop()

tab_proj, tab_plate, tab_treat, tab_log = st.tabs([
    f"📁 프로젝트 ({len(trash_projects)})",
    f"🧫 플레이트 ({len(trash_plates)})",
    f"🧪 처리 내역 ({len(trash_treatments)})",
    f"📝 Daily Log ({len(trash_logs)})",
])

# -------------------------------------------------------------
# 프로젝트
# -------------------------------------------------------------
with tab_proj:
    if not trash_projects:
        st.caption("삭제된 프로젝트가 없습니다.")
    else:
        st.caption("💡 한 화면에서 보기 편하도록 2개씩 나란히 표시됩니다.")
        cols = st.columns(2)
        for idx, p in enumerate(trash_projects):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"**{p['name']}**  <span style='color:#64748b'>[{p['group_name']}]</span>", unsafe_allow_html=True)
                    st.caption(p['description'] or "설명 없음")
                    st.caption(f"🕒 삭제 시각: {p['deleted_at']}")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("♻️ 복구", key=f"restore_proj_{p['id']}", use_container_width=True):
                            db.restore_project(p['id'])
                            st.toast("프로젝트가 복구되었습니다.", icon="♻️")
                            st.rerun()
                    with b2:
                        if st.button("❌ 영구 삭제", key=f"perm_proj_{p['id']}", type="primary", use_container_width=True):
                            db.permanently_delete_project(p['id'])
                            st.toast("프로젝트가 영구적으로 삭제되었습니다.", icon="❌")
                            st.rerun()

# -------------------------------------------------------------
# 플레이트
# -------------------------------------------------------------
with tab_plate:
    if not trash_plates:
        st.caption("삭제된 플레이트가 없습니다.")
    else:
        st.caption("💡 한 화면에서 보기 편하도록 2개씩 나란히 표시됩니다.")
        cols = st.columns(2)
        for idx, pl in enumerate(trash_plates):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"**{pl['name']}**  ({pl['rows']}x{pl['cols']} Wells)")
                    st.caption(f"소속 프로젝트: {pl['project_name'] or '알 수 없음'}")
                    st.caption(f"🕒 삭제 시각: {pl['deleted_at']}")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("♻️ 복구", key=f"restore_plate_{pl['id']}", use_container_width=True):
                            db.restore_plate(pl['id'])
                            st.toast("플레이트가 복구되었습니다.", icon="♻️")
                            st.rerun()
                    with b2:
                        if st.button("❌ 영구 삭제", key=f"perm_plate_{pl['id']}", type="primary", use_container_width=True):
                            db.permanently_delete_plate(pl['id'])
                            st.toast("플레이트가 영구적으로 삭제되었습니다.", icon="❌")
                            st.rerun()

# -------------------------------------------------------------
# 처리 내역
# -------------------------------------------------------------
with tab_treat:
    if not trash_treatments:
        st.caption("삭제된 처리 내역이 없습니다.")
    else:
        st.caption("💡 한 화면에서 보기 편하도록 2개씩 나란히 표시됩니다.")
        cols = st.columns(2)
        for idx, t in enumerate(trash_treatments):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"**📍 Well [{t['well_position']}]** · 🧪 {t['compound_name']} ({t['concentration'] or '-'})")
                    st.caption(f"📅 {t['treatment_date']} · 🧫 {t['plate_name'] or '알 수 없음'} · 📁 {t['project_name'] or '알 수 없음'}")
                    if t['cell_info']:
                        st.caption(f"세포/오가노이드: {t['cell_info']}")
                    if t['note']:
                        st.caption(f"비고: {t['note']}")
                    st.caption(f"🕒 삭제 시각: {t['deleted_at']}")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("♻️ 복구", key=f"restore_treat_{t['id']}", use_container_width=True):
                            db.restore_treatment(t['id'])
                            st.toast("처리 내역이 복구되었습니다.", icon="♻️")
                            st.rerun()
                    with b2:
                        if st.button("❌ 영구 삭제", key=f"perm_treat_{t['id']}", type="primary", use_container_width=True):
                            db.permanently_delete_treatment(t['id'])
                            st.toast("처리 내역이 영구적으로 삭제되었습니다.", icon="❌")
                            st.rerun()

# -------------------------------------------------------------
# Daily Log
# -------------------------------------------------------------
with tab_log:
    if not trash_logs:
        st.caption("삭제된 Daily Log가 없습니다.")
    else:
        st.caption("💡 한 화면에서 보기 편하도록 2개씩 나란히 표시됩니다.")
        cols = st.columns(2)
        for idx, l in enumerate(trash_logs):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"**📅 {l['log_date']}**  <span style='color:#64748b'>[{l['project_name'] or '알 수 없음'}]</span>", unsafe_allow_html=True)
                    st.caption(l['content'])
                    st.caption(f"🕒 삭제 시각: {l['deleted_at']}")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("♻️ 복구", key=f"restore_log_{l['id']}", use_container_width=True):
                            db.restore_daily_log(l['id'])
                            st.toast("Daily Log가 복구되었습니다.", icon="♻️")
                            st.rerun()
                    with b2:
                        if st.button("❌ 영구 삭제", key=f"perm_log_{l['id']}", type="primary", use_container_width=True):
                            db.permanently_delete_daily_log(l['id'])
                            st.toast("Daily Log가 영구적으로 삭제되었습니다.", icon="❌")
                            st.rerun()

st.divider()
with st.expander("⚠️ 휴지통 전체 비우기 (모든 항목 영구 삭제)"):
    st.warning("이 작업은 되돌릴 수 없습니다. 휴지통에 있는 모든 항목이 영구적으로 삭제됩니다.")
    confirm = st.checkbox("정말로 휴지통을 비우겠습니다.")
    if st.button("🗑️ 휴지통 비우기", type="primary", disabled=not confirm):
        for p in trash_projects:
            db.permanently_delete_project(p['id'])
        for pl in trash_plates:
            db.permanently_delete_plate(pl['id'])
        for t in trash_treatments:
            db.permanently_delete_treatment(t['id'])
        for l in trash_logs:
            db.permanently_delete_daily_log(l['id'])
        st.toast("휴지통이 비워졌습니다.", icon="🗑️")
        st.rerun()
