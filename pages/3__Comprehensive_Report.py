import streamlit as st
import pandas as pd
import db
import style

st.set_page_config(page_title="Comprehensive Report",page_icon="📊",layout="wide")
style.set_narrow_layout()
st.title("📊 실험 종합 보기")
st.caption("가로로 긴 표 대신 Well별 처리 흐름과 날짜별 물질 흐름을 compact하게 보여줍니다.")

db.init_db()
projects=db.get_projects()
if not projects:
    st.warning("프로젝트가 없습니다.")
    st.stop()

proj_map={f"[{p['group_name'] or '기본'}] {p['name']}":p for p in projects}
label=st.selectbox("📌 프로젝트",list(proj_map.keys()))
proj=proj_map[label]
treatments=db.get_treatments_by_project(proj["id"])

if not treatments:
    st.info("물질 처리 기록이 없습니다.")
    st.stop()

df=pd.DataFrame([dict(x) for x in treatments])

c1,c2,c3=st.columns(3)
c1.metric("처리 기록",len(df))
c2.metric("사용 Well",df[["plate_id","well_position"]].drop_duplicates().shape[0])
c3.metric("사용 물질",df["compound_name"].nunique())

st.divider()
st.subheader("🧫 Well별 처리 흐름")
for plate, pg in df.groupby("plate_name",sort=True):
    st.markdown(f"**🧫 {plate}**")
    rows=[]
    for well, wg in pg.groupby("well_position",sort=True):
        wg=wg.sort_values("treatment_date")
        flow=" → ".join(
            f"{r['treatment_date'][5:]} {r['compound_name']}"
            + (f" ({r['concentration']})" if r["concentration"] else "")
            for _,r in wg.iterrows())
        rows.append({"Well":well,"처리 흐름":flow,"처리 횟수":len(wg)})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)

st.divider()
st.subheader("📅 날짜별 처리 물질")
date_summary=(df.assign(date_dt=pd.to_datetime(df["treatment_date"],errors="coerce"))
              .groupby(["treatment_date","compound_name"])
              .agg(Well=("well_position",lambda x:", ".join(sorted(set(x)))),
                   Plate=("plate_name",lambda x:", ".join(sorted(set(x)))))
              .reset_index()
              .sort_values(["treatment_date","compound_name"]))
date_summary.columns=["날짜","물질","Well","Plate"]
st.dataframe(date_summary,hide_index=True,use_container_width=True)

csv=date_summary.to_csv(index=False).encode("utf-8-sig")
st.download_button("📥 날짜별 처리 요약 CSV",csv,
                   file_name=f"{proj['name']}_timeline.csv",mime="text/csv")
