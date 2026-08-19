import io
import pandas as pd
import plotly.express as px
import streamlit as st

# DB 모듈 임포트
import db

st.set_page_config(page_title="실험 데이터 관리", layout="wide")

# DB 및 관련 테이블 초기화
db.init_db()
db.init_analysis_tables()

# ==========================================
# 🧫 [사이드바] 배치(Batch) 선택 및 정보 설정
# ==========================================
import streamlit as st
import db

# 1. DB 초기화 및 프로젝트 목록 조회
db.init_db()
projects = db.get_projects()

with st.sidebar:
    st.header("🧫 실험 배치(Batch) 선택")

    # DB에 등록된 프로젝트가 없는 경우 처리
    if not projects:
        st.warning("⚠️ 등록된 프로젝트가 없습니다. 프로젝트를 먼저 생성해 주세요.")
        current_batch = "미지정"
    else:
        # 프로젝트 선택 드롭다운 생성 (2__Well_Plates.py 방식 적용)
        proj_map = {
            f"[{p['group_name'] if p['group_name'] else '기본'}] {p['name']} (ID: {p['id']})": p 
            for p in projects
        }
        proj_options = list(proj_map.keys())

        if (
            "selected_plate_proj_label" not in st.session_state 
            or st.session_state.selected_plate_proj_label not in proj_options
        ):
            st.session_state.selected_plate_proj_label = proj_options[0]

        selected_proj_label = st.selectbox(
            "📌 프로젝트 선택",
            options=proj_options,
            key="selected_plate_proj_label",
        )
        selected_proj = proj_map[selected_proj_label]

        # 프로젝트 하위의 플레이트(배치) 목록 가져오기
        plates = db.get_plates(selected_proj['id'])

        if plates:
            plate_dict = {
                f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)": pl 
                for pl in plates
            }
            selected_plate_name = st.selectbox(
                "🧫 작업 대상 플레이트(배치) 선택",
                options=list(plate_dict.keys()),
                key="selected_plate_select",
            )
            selected_plate = plate_dict[selected_plate_name]
            current_batch = selected_plate['name']
        else:
            st.info("💡 해당 프로젝트에 등록된 플레이트가 없습니다.")
            current_batch = "플레이트 없음"

    st.divider()

    # 선택 요약 정보 표시
    st.info(
        f"""
    **현재 선택된 배치 요약**
    - **ID / 플레이트**: `{current_batch}`
    - **종류**: {cell_type}
    - **단계**: {culture_stage}
    - **배지**: {media_condition}
    """
    )


# ==========================================
# 📊 [메인 화면] 선택된 배치 기반 데이터 작업
# ==========================================
st.title("🔬 실험 데이터 입력 및 분석")

# 상단에 현재 배치 상태 표시 카드
col_b1, col_b2, col_b3 = st.columns(3)
col_b1.metric("선택된 배치 ID", current_batch)
col_b2.metric("세포/오가노이드", cell_type)
col_b3.metric("배양 단계", culture_stage)

st.caption(f"💡 현재 입력하는 데이터는 **[{current_batch}]** 배치에 자동으로 귀속됩니다.")

st.divider()


# 파싱 함수
def parse_pasted_data(raw_text):
    if not raw_text or not raw_text.strip():
        return None
    try:
        return pd.read_csv(io.StringIO(raw_text), sep="\t")
    except Exception as e:
        st.error(f"파싱 오류: {e}")
        return None


# 데이터 입력 탭 (Cell Count / qPCR / FACS)
tab1, tab2, tab3 = st.tabs(["🧫 Cell Count", "🧬 qPCR", "📊 FACS"])

# 1. Cell Count 탭
with tab1:
    st.subheader(f"Cell Count 데이터 입력 ({current_batch})")

    example_cell = "Sample\tConcentration_M_mL\tViability_pct\nControl\t1.2\t95.4\nGroup_A\t2.5\t92.1\nGroup_B\t3.1\t88.7"
    raw_cell = st.text_area(
        "엑셀/Prism 데이터 붙여넣기", value=example_cell, height=120, key="txt_cell"
    )
    df_cell = parse_pasted_data(raw_cell)

    if df_cell is not None:
        # 데이터프레임 맨 앞에 배치 ID 칼럼 자동 추가
        df_cell.insert(0, "Batch_ID", current_batch)
        edited_cell = st.data_editor(df_cell, num_rows="dynamic", key="edit_cell")

        if st.button("💾 이 배치의 데이터 DB 저장", key="save_cell"):
            # DB 함수 연결
            db.save_analysis_data(current_batch, "Cell Count", edited_cell)
            st.success(
                f"[{current_batch}] 배치의 Cell Count 데이터가 성공적으로 DB에 저장되었습니다!"
            )

    st.divider()
    # DB 저장 데이터 이력 조회
    st.markdown(f"#### 📜 [{current_batch}] DB 저장된 Cell Count 이력")
    saved_cell_df = db.get_analysis_data(current_batch, "Cell Count")
    if not saved_cell_df.empty:
        st.dataframe(saved_cell_df, use_container_width=True)
    else:
        st.caption("저장된 Cell Count 데이터가 없습니다.")

# 2. qPCR 탭
with tab2:
    st.subheader(f"qPCR 데이터 입력 ({current_batch})")

    example_qpcr = "Gene\tRelative_Expression\nGAPDH\t1.00\nVEGF\t2.45\nCD31\t4.12"
    raw_qpcr = st.text_area(
        "qPCR 데이터 붙여넣기", value=example_qpcr, height=120, key="txt_qpcr"
    )
    df_qpcr = parse_pasted_data(raw_qpcr)

    if df_qpcr is not None:
        df_qpcr.insert(0, "Batch_ID", current_batch)
        edited_qpcr = st.data_editor(df_qpcr, num_rows="dynamic", key="edit_qpcr")

        if st.button("💾 qPCR 데이터 DB 저장", key="save_qpcr"):
            db.save_analysis_data(current_batch, "qPCR", edited_qpcr)
            st.success(
                f"[{current_batch}] 배치의 qPCR 데이터가 DB에 저장되었습니다!"
            )

    st.divider()
    st.markdown(f"#### 📜 [{current_batch}] DB 저장된 qPCR 이력")
    saved_qpcr_df = db.get_analysis_data(current_batch, "qPCR")
    if not saved_qpcr_df.empty:
        st.dataframe(saved_qpcr_df, use_container_width=True)
    else:
        st.caption("저장된 qPCR 데이터가 없습니다.")

# 3. FACS 탭
with tab3:
    st.subheader(f"FACS 데이터 입력 ({current_batch})")

    example_facs = "Marker\tPos_Pct\nCD31\t72.4\nCD34\t34.1"
    raw_facs = st.text_area(
        "FACS 데이터 붙여넣기", value=example_facs, height=120, key="txt_facs"
    )
    df_facs = parse_pasted_data(raw_facs)

    if df_facs is not None:
        df_facs.insert(0, "Batch_ID", current_batch)
        edited_facs = st.data_editor(df_facs, num_rows="dynamic", key="edit_facs")

        if st.button("💾 FACS 데이터 DB 저장", key="save_facs"):
            db.save_analysis_data(current_batch, "FACS", edited_facs)
            st.success(
                f"[{current_batch}] 배치의 FACS 데이터가 DB에 저장되었습니다!"
            )

    st.divider()
    st.markdown(f"#### 📜 [{current_batch}] DB 저장된 FACS 이력")
    saved_facs_df = db.get_analysis_data(current_batch, "FACS")
    if not saved_facs_df.empty:
        st.dataframe(saved_facs_df, use_container_width=True)
    else:
        st.caption("저장된 FACS 데이터가 없습니다.")
