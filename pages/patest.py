import io
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="실험 데이터 입력 및 시각화", layout="wide")
st.title("🔬 실험 데이터 입력 (Cell Count / qPCR / FACS)")

st.write(
    "엑셀이나 Prism의 셀 영역을 복사(`Ctrl+C`)한 뒤, 아래 텍스트 상자에 붙여넣기(`Ctrl+V`)하세요."
)


# 1. 텍스트 데이터를 DataFrame으로 변환하는 함수
def parse_pasted_data(raw_text):
    if not raw_text.strip():
        return None
    try:
        # 엑셀 복사 시 기본 구분자는 탭(\t)입니다.
        df = pd.read_csv(io.StringIO(raw_text), sep="\t")
        return df
    except Exception as e:
        st.error(f"데이터 파싱 오류: {e}")
        return None


# 2. 실험 유형별 탭 구성
tab1, tab2, tab3 = st.tabs(["🧫 Cell Count", "🧬 qPCR", "📊 FACS"])

# -------------------------------------------------------------------
# TAB 1: Cell Count
# -------------------------------------------------------------------
with tab1:
    st.subheader("Cell Count 데이터")

    example_cell = "Sample\tConcentration_M_mL\tViability_pct\nControl\t1.2\t95.4\nGroup_A\t2.5\t92.1\nGroup_B\t3.1\t88.7"

    raw_cell = st.text_area(
        "붙여넣기 영역 (Cell Count)",
        value=example_cell,
        height=120,
        key="cell_input",
    )
    df_cell = parse_pasted_data(raw_cell)

    if df_cell is not None:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.write("▼ **수정 가능한 테이블**")
            edited_cell = st.data_editor(
                df_cell, num_rows="dynamic", key="edit_cell"
            )

        with col2:
            st.write("▼ **시각화 미리보기**")
            numeric_cols = edited_cell.select_dtypes(
                include=["float", "int"]
            ).columns.tolist()
            if numeric_cols:
                target_col = st.selectbox(
                    "Y축 항목 선택", numeric_cols, key="cell_y"
                )
                fig = px.bar(
                    edited_cell,
                    x=edited_cell.columns[0],
                    y=target_col,
                    text_auto=True,
                    title=f"Cell Count: {target_col}",
                )
                st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------------
# TAB 2: qPCR
# -------------------------------------------------------------------
with tab2:
    st.subheader("qPCR 데이터")

    example_qpcr = "Sample\tGene\tRelative_Expression\nControl\tGAPDH\t1.00\nControl\tTarget_A\t1.02\nGroup_1\tGAPDH\t0.98\nGroup_1\tTarget_A\t3.45\nGroup_2\tGAPDH\t1.01\nGroup_2\tTarget_A\t0.42"

    raw_qpcr = st.text_area(
        "붙여넣기 영역 (qPCR)",
        value=example_qpcr,
        height=150,
        key="qpcr_input",
    )
    df_qpcr = parse_pasted_data(raw_qpcr)

    if df_qpcr is not None:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.write("▼ **수정 가능한 테이블**")
            edited_qpcr = st.data_editor(
                df_qpcr, num_rows="dynamic", key="edit_qpcr"
            )

        with col2:
            st.write("▼ **상대적 발현량 비교**")
            cols = edited_qpcr.columns.tolist()
            if len(cols) >= 3:
                fig = px.bar(
                    edited_qpcr,
                    x=cols[0],
                    y=cols[2],
                    color=cols[1],
                    barmode="group",
                    title="qPCR Relative Expression ($2^{-\\Delta\\Delta Ct}$)",
                )
                st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------------
# TAB 3: FACS
# -------------------------------------------------------------------
with tab3:
    st.subheader("FACS / Flow Cytometry 데이터")

    example_facs = "Sample\tMarker\tPos_Pct\tMFI\nControl\tCD31\t2.1\t150\nControl\tCD34\t1.5\t120\nStained_1\tCD31\t68.4\t4500\nStained_1\tCD34\t42.1\t2800"

    raw_facs = st.text_area(
        "붙여넣기 영역 (FACS)",
        value=example_facs,
        height=130,
        key="facs_input",
    )
    df_facs = parse_pasted_data(raw_facs)

    if df_facs is not None:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.write("▼ **수정 가능한 테이블**")
            edited_facs = st.data_editor(
                df_facs, num_rows="dynamic", key="edit_facs"
            )

        with col2:
            metric_choice = st.radio(
                "표시 지표 선택", ["Pos_Pct (%)", "MFI"], horizontal=True
            )
            target_metric = "Pos_Pct" if "Pct" in metric_choice else "MFI"

            if target_metric in edited_facs.columns:
                fig = px.bar(
                    edited_facs,
                    x="Sample",
                    y=target_metric,
                    color="Marker"
                    if "Marker" in edited_facs.columns
                    else None,
                    barmode="group",
                    title=f"FACS: {metric_choice}",
                )
                st.plotly_chart(fig, use_container_width=True)
