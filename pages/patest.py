import io
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="실험 데이터 관리", layout="wide")

# ==========================================
# 🧫 [사이드바] 배치(Batch) 선택 및 정보 설정
# ==========================================
with st.sidebar:
    st.header("🧫 실험 배치(Batch) 선택")

    # 세션 상태에 기본 배치 목록 저장
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
    if not raw_text.strip():
        return None
    try:
        return pd.read_csv(io.StringIO(raw_text), sep="\t")
    except Exception as e:
        st.error(f"파싱 오류: {e}")
        return None


# 데이터 입력 탭 (Cell Count / qPCR / FACS)
tab1, tab2, tab3 = st.tabs(["🧫 Cell Count", "🧬 qPCR", "📊 FACS"])

with tab1:
    st.subheader(f"Cell Count 데이터 입력 ({current_batch})")

    example_cell = "Sample\tConcentration_M_mL\tViability_pct\nControl\t1.2\t95.4\nGroup_A\t2.5\t92.1\nGroup_B\t3.1\t88.7"
    raw_cell = st.text_area(
        "엑셀/Prism 데이터 붙여넣기", value=example_cell, height=120
    )
    df_cell = parse_pasted_data(raw_cell)

    if df_cell is not None:
        # 데이터프레임 맨 앞에 배치 ID 칼럼 자동 추가
        df_cell.insert(0, "Batch_ID", current_batch)

        edited_cell = st.data_editor(df_cell, num_rows="dynamic")

        if st.button("💾 이 배치의 데이터 DB 저장", key="save_cell"):
            st.success(
                f"[{current_batch}] 배치의 Cell Count 데이터가 성공적으로 저장되었습니다!"
            )
