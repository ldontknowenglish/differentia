import streamlit as st
import pandas as pd
import db
import style

st.set_page_config(page_title="Experiment Flow", page_icon="🕒", layout="wide")
style.set_narrow_layout()
st.title("🕒 실험 물질 처리 흐름")
st.caption("프로젝트를 선택하면 날짜순으로 물질 처리와 Daily Log가 한 흐름으로 정렬됩니다.")

db.init_db()
projects=db.get_projects()
if not projects:
    st.warning("프로젝트가 없습니다.")
    st.stop()

proj_map={f"[{p['group_name'] or '기본'}] {p['name']}":p for p in projects}
label=st.selectbox("📌 프로젝트",list(proj_map.keys()))
proj=proj_map[label]

treatments=db.get_treatments_by_project(proj["id"])
logs=db.get_daily_logs(proj["id"])

items=[]
for t in treatments:
    items.append({
        "date":str(t["treatment_date"]),
        "kind":"🧪",
        "plate":t["plate_name"],
        "well":t["well_position"],
        "compound":t["compound_name"],
        "concentration":t["concentration"] or "",
        "note":t["note"] or ""
    })
for l in logs:
    items.append({
        "date":str(l["log_date"]),
        "kind":"📝",
        "plate":"",
        "well":"",
        "compound":"Daily Log",
        "concentration":"",
        "note":l["content"] or ""
    })

if not items:
    st.info("아직 기록이 없습니다.")
    st.stop()

df=pd.DataFrame(items)
df["date_dt"]=pd.to_datetime(df["date"],errors="coerce")
df=df.sort_values(["date_dt","plate","well","compound"],ascending=[True,True,True,True])

unique_dates=df["date"].nunique()
c1,c2,c3=st.columns(3)
c1.metric("기록 수",len(df))
c2.metric("실험 날짜",unique_dates)
c3.metric("사용 물질",df.loc[df["compound"]!="Daily Log","compound"].nunique())

st.divider()

# compact horizontal timeline
for d, group in df.groupby("date",sort=True):
    st.markdown(f"### 📅 {d}")
    for _,r in group.iterrows():
        if r["kind"]=="🧪":
            concentration=f" · {r['concentration']}" if r["concentration"] else ""
            note=f" · {r['note']}" if r["note"] else ""
            st.markdown(
                f"""<div style="display:flex;gap:8px;align-items:center;margin:3px 0;
                padding:7px 10px;border-left:4px solid #3b82f6;background:#f8fafc;
                font-size:13px;">
                <b style="min-width:28px">{r['well']}</b>
                <b>{r['compound']}</b><span>{concentration}</span>
                <span style="color:#64748b">{r['plate']}{note}</span>
                </div>""",unsafe_allow_html=True)
        else:
            st.markdown(
                f"""<div style="margin:3px 0;padding:7px 10px;border-left:4px solid #10b981;
                background:#f8fafc;font-size:13px;"><b>📝 Daily Log</b> {r['note']}</div>""",
                unsafe_allow_html=True)

st.divider()
st.subheader("📊 날짜 × 물질 요약")
compound_df=df[df["compound"]!="Daily Log"].copy()
if not compound_df.empty:
    summary=(compound_df.groupby(["date","compound"])
             .agg(Well=("well",lambda x:", ".join(sorted(set(x)))),
                  Plate=("plate",lambda x:", ".join(sorted(set(x)))))
             .reset_index()
             .sort_values(["date","compound"]))
    summary.columns=["날짜","물질","Well","Plate"]
    st.dataframe(summary,hide_index=True,use_container_width=True)
else:
    st.info("물질 처리 기록이 없습니다.")
