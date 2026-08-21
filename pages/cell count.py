import datetime
import io
import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Cell Count 엑셀 관리 시스템", layout="wide")

# ==========================================
# 📁 엑셀 저장 및 로드 헬퍼 함수
# ==========================================
EXCEL_DIR = "excel_data"
if not os.path.exists(EXCEL_DIR):
    os.makedirs(EXCEL_DIR)


def get_excel_filepath(batch_id, assay_name):
    safe_batch = str(batch_id).replace("/", "_").replace("\\", "_")
    safe_assay = str(assay_name).replace(" ", "_")
    return os.path.join(EXCEL_DIR, f"{safe_batch}_{safe_assay}.xlsx")


def save_to_excel(batch_id, assay_name, df):
    filepath = get_excel_filepath(batch_id, assay_name)
    df.to_excel(filepath, index=False, engine="openpyxl")


def load_from_excel(batch_id, assay_name):
    filepath = get_excel_filepath(batch_id, assay_name)
    if os.path.exists(filepath):
        try:
            return pd.read_excel(filepath, engine="openpyxl")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def convert_df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cell_Count")
    return output.getvalue()


# ==========================================
# 🧫 이미지 기반 Cell Count 자동 계산 함수
# ==========================================
def calculate_cell_count_metrics(df, default_seeding):
    """
    1. seeding density
    2. counted well
    3. condition
    4. 1st count
    5. 2nd count
    6. average (자동계산)
    7. 실제 1 well (자동계산)
    8. 증가율 (자동계산)
    """
    df_calc = df.copy()

    # 필수 열 유효성 확보
    if "seeding density" not in df_calc.columns:
        df_calc["seeding density"] = default_seeding
    else:
        df_calc["seeding density"] = pd.to_numeric(
            df_calc["seeding density"], errors="coerce"
        ).fillna(default_seeding)

    if "counted well" not in df_calc.columns:
        df_calc["counted well"] = 1
    else:
        df_calc["counted well"] = pd.to_numeric(
            df_calc["counted well"], errors="coerce"
        ).fillna(1)

    df_calc["1st count"] = pd.to_numeric(
        df_calc["1st count"], errors="coerce"
    ).fillna(0)
    df_calc["2nd count"] = pd.to_numeric(
        df_calc["2nd count"], errors="coerce"
    ).fillna(0)

    # 1. average 계산 ((1st + 2nd) / 2)
    df_calc["average"] = (
        (df_calc["1st count"] + df_calc["2nd count"]) / 2
    ).round(3)

    # 2. 실제 1 well 계산 (average / counted well)
    df_calc["실제 1 well"] = (
        df_calc["average"] / df_calc["counted well"]
    ).round(3)

    # 3. 증가율 계산 (실제 1 well / seeding density)
    df_calc["증가율"] = (
        df_calc["실제 1 well"] / df_calc["seeding density"]
    ).round(2)

    # 요청된 순서대로 열 정렬
    ordered_cols = [
        "seeding density",
        "counted well",
        "condition",
        "1st count",
        "2nd count",
        "average",
        "실제 1 well",
        "증가율",
    ]

    # 사용자 정의 추가 컬럼이 있을 경우 뒤에 유지
    extra_cols = [c for c in df_calc.columns if c not in ordered_cols]
    return df_calc[ordered_cols + extra_cols]


# ==========================================
# 📊 [메인 화면]
# ==========================================
st.title("🧫 Cell Count 규격 데이터 관리")

# 상단 메타데이터 입력
with st.container(border=True):
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        current_batch = st.text_input(
            "🧫 배치 ID / 플레이트명", value="DE_5_D3_protocol_test"
        )
    with col_m2:
        seeding_density = st.number_input(
            "🌱 기본 Seeding Density (x10^6)",
            value=0.6,
            step=0.1,
            format="%.2f",
        )
    with col_m3:
        sample_day = st.text_input("📅 샘플 시점 (Timepoint)", value="Day 3")

st.divider()

col_left, col_right = st.columns([1, 1.3])

with col_left:
    st.markdown("##### 📥 1. 신규 Cell Count 데이터 입력")
    st.caption("기초 데이터 또는 엑셀 복사/붙여넣기를 통해 데이터를 입력하세요.")

    default_tsv = "condition\tcounted well\t1st count\t2nd count\nwells\t5\t1.60\t1.86\nnew\t7\t0.094\t0.14\nD+N\t2\t4.05\t3.082"
    raw_text = st.text_area(
        "엑셀/Prism 붙여넣기 (Tab으로 구분)", value=default_tsv, height=150
    )

    uploaded_file = st.file_uploader(
        "또는 엑셀/CSV 파일 업로드", type=["xlsx", "xls", "csv"]
    )

    # 데이터 파싱
    df_parsed = None
    if uploaded_file is not None:
        try:
            df_parsed = (
                pd.read_csv(uploaded_file)
                if uploaded_file.name.endswith(".csv")
                else pd.read_excel(uploaded_file, engine="openpyxl")
            )
        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")
    elif raw_text and raw_text.strip():
        try:
            df_parsed = pd.read_csv(io.StringIO(raw_text), sep="\t")
        except Exception as e:
            st.error(f"텍스트 파싱 오류: {e}")

with col_right:
    st.markdown("##### ✏️ 2. 데이터 자동 계산 검토 및 엑셀 저장")

    if df_parsed is not None:
        # 이미지 계산 수식 자동 적용
        df_calculated = calculate_cell_count_metrics(
            df_parsed, seeding_density
        )

        st.caption(
            "💡 **`1st count`**, **`2nd count`**, **`counted well`**을 수정하면 **`average`**, **`실제 1 well`**, **`증가율`**이 자동 계산됩니다."
        )

        edited_df = st.data_editor(
            df_calculated,
            num_rows="dynamic",
            use_container_width=True,
            key="cell_count_editor",
        )

        if st.button(
            "💾 Cell Count 데이터 엑셀 파일 저장", type="primary"
        ):
            # 수식 실시간 재계산 후 저장
            final_df = calculate_cell_count_metrics(edited_df, seeding_density)
            save_to_excel(current_batch, "Cell_Count", final_df)
            st.toast("엑셀 파일이 성공적으로 저장되었습니다!", icon="📂")
            st.rerun()

st.divider()

# ==========================================
# 📜 3. 저장된 엑셀 파일 이력 관리 및 다운로드
# ==========================================
st.markdown(f"#### 📜 [{current_batch}] 저장된 Cell Count 엑셀 이력")

saved_df = load_from_excel(current_batch, "Cell_Count")

if not saved_df.empty:
    updated_saved_df = st.data_editor(
        saved_df,
        num_rows="dynamic",
        use_container_width=True,
        key="saved_excel_editor",
    )

    col_b1, col_b2 = st.columns([1, 1])
    with col_b1:
        if st.button("🔄 엑셀 파일 수정사항 업데이트"):
            re_calculated_df = calculate_cell_count_metrics(
                updated_saved_df, seeding_density
            )
            save_to_excel(current_batch, "Cell_Count", re_calculated_df)
            st.toast("엑셀 파일이 업데이트되었습니다!", icon="🔄")
            st.rerun()

    with col_b2:
        excel_data = convert_df_to_excel_bytes(updated_saved_df)
        st.download_button(
            label="📥 엑셀 파일 다운로드 (.xlsx)",
            data=excel_data,
            file_name=f"{current_batch}_Cell_Count.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("현재 저장된 Cell Count 엑셀 파일이 없습니다.")
