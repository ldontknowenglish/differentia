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
with st.sidebar:
    st.header("🧫 실험 배치(Batch) 선택")

    # DB에 기존 등록된 Plate 정보를 가져와 배치 목록으로 활용
    projects = db.get_projects()

    if "batch_list" not in st.session_state:
        st.session_state["batch_list"] = [
            "Batch_20260819_01",
            "Batch_20260815_02",
            "Batch_20260801_03",
        ]

    # 1. 배치 ID 선택 (새 배치 추가 옵션 포함)
    selected_batch = st.selectbox(
        "작업할 배치(Batch ID)를 선택하세요",
        options=st.session_state["batch_list"] + ["➕ 새 배치 직접 등록"],
    )

    # 1-1. 새 배치 등록 로직
    if selected_batch == "➕ 새 배치 직접 등록":
        new_batch_id = st.text_input(
            "새 배치 ID 입력", placeholder="예: Batch_20260820_01"
        )
        if st.button("배치 추가"):
            if (
                new_batch_id
                and new_batch_id not in st.session_state["batch_list"]
            ):
                st.session_state["batch_list"].append(new_batch_id)
                st.success(f"'{new_batch_id}' 등록 완료!")
                st.rerun()
        current_batch = new_batch_id if new_batch_id else "미지정"
    else:
        current_batch = selected_batch

    st.divider()

    # 2. 선택한 배치의 조건 설정 (필요 시 세부 선택)
    st.subheader("📋 배치 시작 조건")

    cell_type = st.selectbox(
        "세포 / 오가노이드 종류",
        [
            "Blood Vessel Organoid",
            "Intestinal Assembloid",
            "iPSC-derived Line",
            "Primary Cell Line",
        ],
    )

    culture_stage = st.text_input("배양/분화 단계", value="Day 0 (Seeding)")

    media_condition = st.selectbox(
        "배지 조건 (Media Condition)",
        [
            "Chemically Defined (Animal-Free)",
            "Growth Factor High",
            "Standard Medium",
        ],
    )

    # 선택 요약 정보 표시
    st.info(
        f"""
    **현재 선택된 배치 요약**
    - **ID**: `{current_batch}`
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
