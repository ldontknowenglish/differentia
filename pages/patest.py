import datetime
import io
import os
import pandas as pd
import plotly.express as px
import streamlit as st

# 1. Streamlit 페이지 설정
st.set_page_config(page_title="실험 데이터 엑셀 관리 및 분석", layout="wide")

# ==========================================
# 📁 엑셀 파일 입출력 헬퍼 함수
# ==========================================
EXCEL_DIR = "excel_data"
if not os.path.exists(EXCEL_DIR):
    os.makedirs(EXCEL_DIR)


def get_excel_filepath(batch_id, assay_name):
    """배치 ID와 검사명을 기반으로 안전한 엑셀 파일 경로 생성"""
    safe_batch = str(batch_id).replace("/", "_").replace("\\", "_")
    safe_assay = str(assay_name).replace(" ", "_")
    return os.path.join(EXCEL_DIR, f"{safe_batch}_{safe_assay}.xlsx")


def save_to_excel(batch_id, assay_name, df):
    """데이터프레임을 엑셀 파일로 저장"""
    filepath = get_excel_filepath(batch_id, assay_name)
    df.to_excel(filepath, index=False, engine="openpyxl")


def load_from_excel(batch_id, assay_name):
    """저장된 엑셀 파일 읽기"""
    filepath = get_excel_filepath(batch_id, assay_name)
    if os.path.exists(filepath):
        try:
            return pd.read_excel(filepath, engine="openpyxl")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def convert_df_to_excel_bytes(df):
    """다운로드용 엑셀 바이트 스트림 변환"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()


# ==========================================
# 🧫 [사이드바] 배치(Batch) 선택
# ==========================================
with st.sidebar:
    st.header("🧫 실험 배치(Batch) 설정")

    current_batch = st.text_input(
        "🧫 현재 작업 배치 ID / 플레이트명",
        value="Plate_Batch_01",
        help="예: Batch_2026_01, Plate_A1 등",
    )

    st.info(f"현재 선택된 배치: **{current_batch}**")


# ==========================================
# 📊 [메인 화면] 1. 통합 메타데이터 입력 구역
# ==========================================
st.title("🔬 실험 데이터 엑셀 저장 및 분석")

st.markdown("### 📋 공통 실험 메타데이터")
st.caption("배치 정보와 실험 날짜 관련 메타데이터를 통합하여 관리합니다.")

with st.container(border=True):
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.text_input("🧫 배치 ID (Batch)", value=current_batch, disabled=True)
    with col_m2:
        sample_day = st.text_input(
            "📅 샘플 시점 (Timepoint)", value="Day 7", help="예: Day 0, Day 7, Pass 2 등"
        )
    with col_m3:
        acq_date = st.date_input(
            "📅 샘플 획득일", datetime.date.today(), key="global_acq_date"
        )
    with col_m4:
        exp_date = st.date_input(
            "🧪 실험 진행일", datetime.date.today(), key="global_exp_date"
        )

st.divider()


# 엑셀 파일 또는 붙여넣은 텍스트 파싱 함수
def parse_input_data(uploaded_file, raw_text):
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                return pd.read_csv(uploaded_file)
            else:
                return pd.read_excel(uploaded_file, engine="openpyxl")
        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")
            return None
    elif raw_text and raw_text.strip():
        try:
            return pd.read_csv(io.StringIO(raw_text), sep="\t")
        except Exception as e:
            st.error(f"텍스트 파싱 오류: {e}")
            return None
    return None


# 데이터 입력 및 종합 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(
    ["🧫 Cell Count", "🧬 qPCR", "📊 FACS", "📈 배치 간 비교 분석"]
)


# 데이터 입력(좌) / 데이터 검토 및 저장(우) / 엑셀 이력 관리(하단) UI 함수
def render_analysis_tab(assay_name, example_text, is_cell_count=False):
    st.subheader(f"{assay_name} 데이터 작업")

    col_left, col_right = st.columns([1, 1.2])

    with col_left:
        st.markdown("##### 📥 1. 데이터 가져오기")

        file_upload = st.file_uploader(
            "엑셀/CSV 파일 업로드",
            type=["xlsx", "xls", "csv"],
            key=f"file_{assay_name}",
        )
        text_upload = st.text_area(
            "엑셀/Prism 복사-붙여넣기",
            value=example_text,
            height=140,
            key=f"txt_{assay_name}",
        )

        attachments = st.file_uploader(
            "관련 사진/원시 데이터 첨부",
            accept_multiple_files=True,
            key=f"attach_{assay_name}",
        )
        if attachments:
            st.caption(f"📎 총 {len(attachments)}개 파일 첨부됨")

        df_parsed = parse_input_data(file_upload, text_upload)

    with col_right:
        st.markdown("##### ✏️ 2. 신규 데이터 검토 및 수정 / 삭제")

        if df_parsed is not None:
            st.caption(
                "💡 **수정/삭제**: 셀 값을 수정하거나 행 선택 후 `Del`키를 누르고 엑셀로 저장하세요."
            )

            df_working = df_parsed.copy()

            # Cell Count인 경우 1차, 2차 수치 기반 평균 자동 계산
            if is_cell_count:
                if (
                    "Count_1st" in df_working.columns
                    and "Count_2nd" in df_working.columns
                ):
                    df_working["Count_1st"] = pd.to_numeric(
                        df_working["Count_1st"], errors="coerce"
                    )
                    df_working["Count_2nd"] = pd.to_numeric(
                        df_working["Count_2nd"], errors="coerce"
                    )
                    df_working["Count_Mean"] = (
                        df_working[["Count_1st", "Count_2nd"]].mean(axis=1).round(3)
                    )

            # 데이터 편집기
            edited_df = st.data_editor(
                df_working,
                num_rows="dynamic",
                key=f"edit_{assay_name}",
                use_container_width=True,
            )

            if st.button(
                f"💾 [{assay_name}] 엑셀 파일로 저장",
                key=f"btn_save_{assay_name}",
                type="primary",
            ):
                save_to_excel(current_batch, assay_name, edited_df)
                st.toast(
                    f"[{current_batch}] {assay_name} 데이터가 엑셀 파일로 저장되었습니다!",
                    icon="📂",
                )
                st.rerun()
        else:
            st.info(
                "👈 왼쪽에서 데이터를 입력하거나 파일을 올리면, 이곳에 수정 및 삭제 가능한 편집기 테이블이 나타납니다."
            )

    st.divider()

    # 3. 엑셀 저장 이력 조회 및 수정/삭제/다운로드
    st.markdown(f"#### 📜 [{current_batch}] 저장된 엑셀 데이터 관리")

    saved_df = load_from_excel(current_batch, assay_name)

    if not saved_df.empty:
        st.caption(
            "💡 현재 로컬 엑셀 파일에 저장되어 있는 데이터입니다. 수정한 후 '엑셀 파일 업데이트'를 누르면 파일이 갱신됩니다."
        )

        updated_db_df = st.data_editor(
            saved_df,
            num_rows="dynamic",
            key=f"excel_edit_{assay_name}",
            use_container_width=True,
        )

        col_btn1, col_btn2 = st.columns([1, 1])

        with col_btn1:
            if st.button(
                f"🔄 [{assay_name}] 엑셀 파일 업데이트",
                key=f"btn_update_{assay_name}",
            ):
                save_to_excel(current_batch, assay_name, updated_db_df)
                st.toast("엑셀 파일이 성공적으로 갱신되었습니다!", icon="🔄")
                st.rerun()

        with col_btn2:
            excel_bytes = convert_df_to_excel_bytes(updated_db_df)
            st.download_button(
                label=f"📥 [{assay_name}] 엑셀 파일 다운로드 (.xlsx)",
                data=excel_bytes,
                file_name=f"{current_batch}_{assay_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"btn_dl_{assay_name}",
            )
    else:
        st.caption(
            f"현재 선택된 배치({current_batch})에 저장된 {assay_name} 엑셀 파일이 없습니다."
        )


# --- 탭 1: Cell Count ---
with tab1:
    render_analysis_tab(
        "Cell Count",
        "Sample\tCount_1st\tCount_2nd\tViability_pct\nControl\t1.20\t1.24\t95.4\nGroup_A\t2.40\t2.60\t92.1\nGroup_B\t3.00\t3.20\t88.7",
        is_cell_count=True,
    )

# --- 탭 2: qPCR ---
with tab2:
    render_analysis_tab(
        "qPCR",
        "Gene\tRelative_Expression\nGAPDH\t1.00\nVEGF\t2.45\nCD31\t4.12",
    )

# --- 탭 3: FACS ---
with tab3:
    render_analysis_tab(
        "FACS",
        "Marker\tPos_Pct\nCD31\t72.4\nCD34\t34.1\nFitc_Neg\t98.2",
    )


# ==========================================
# 📈 [탭 4] 배치 간 비교 분석
# ==========================================
with tab4:
    st.subheader("📈 저장된 엑셀 파일 기반 배치 간 비교 분석")
    st.caption("저장된 엑셀 파일들을 탐색하여 데이터(Cell Count, qPCR, FACS)를 비교 시각화합니다.")

    # 저장된 모든 엑셀 파일 목록에서 배치 ID 수집
    existing_files = os.listdir(EXCEL_DIR) if os.path.exists(EXCEL_DIR) else []
    all_saved_batches = sorted(
        list(set([f.split("_")[0] for f in existing_files if f.endswith(".xlsx")]))
    )

    if not all_saved_batches:
        st.warning(
            "저장된 엑셀 파일 데이터가 없습니다. 먼저 데이터를 저장해 주세요."
        )
    else:
        selected_batches = st.multiselect(
            "🔍 비교 분석할 배치를 선택하세요:",
            options=all_saved_batches,
            default=all_saved_batches,
            key="multi_batch_select",
        )

        if not selected_batches:
            st.info("비교할 배치를 1개 이상 선택해 주세요.")
        else:
            st.divider()

            def get_combined_excel_data(assay_name):
                combined_list = []
                for b_id in selected_batches:
                    df = load_from_excel(b_id, assay_name)
                    if not df.empty:
                        df_copy = df.copy()
                        df_copy.insert(0, "Batch_ID", b_id)
                        combined_list.append(df_copy)
                if combined_list:
                    return pd.concat(combined_list, ignore_index=True)
                return pd.DataFrame()

            # --- 1. Cell Count 비교 분석 ---
            st.markdown("### 🧫 1. Cell Count 배치 비교")
            cc_combined = get_combined_excel_data("Cell Count")

            if not cc_combined.empty:
                col_cc_graph, col_cc_table = st.columns([3, 2])

                with col_cc_graph:
                    target_col = (
                        "Count_Mean"
                        if "Count_Mean" in cc_combined.columns
                        else "Count_1st"
                    )

                    if target_col in cc_combined.columns:
                        cc_combined[target_col] = pd.to_numeric(
                            cc_combined[target_col], errors="coerce"
                        )

                        fig_cc = px.bar(
                            cc_combined,
                            x="Sample"
                            if "Sample" in cc_combined.columns
                            else cc_combined.index,
                            y=target_col,
                            color="Batch_ID",
                            barmode="group",
                            title=f"배치별 세포 농도/수치 비교 ({target_col})",
                            text_auto=True,
                        )
                        st.plotly_chart(fig_cc, use_container_width=True)

                with col_cc_table:
                    st.markdown("**통합 Cell Count 데이터**")
                    st.dataframe(cc_combined, use_container_width=True)
            else:
                st.caption("선택한 배치에 저장된 Cell Count 엑셀 데이터가 없습니다.")

            st.divider()

            # --- 2. qPCR 비교 분석 ---
            st.markdown("### 🧬 2. qPCR 상대 발현량 비교")
            qpcr_combined = get_combined_excel_data("qPCR")

            if not qpcr_combined.empty:
                col_qp_graph, col_qp_table = st.columns([3, 2])

                with col_qp_graph:
                    if (
                        "Relative_Expression" in qpcr_combined.columns
                        and "Gene" in qpcr_combined.columns
                    ):
                        qpcr_combined["Relative_Expression"] = pd.to_numeric(
                            qpcr_combined["Relative_Expression"], errors="coerce"
                        )

                        fig_qpcr = px.bar(
                            qpcr_combined,
                            x="Gene",
                            y="Relative_Expression",
                            color="Batch_ID",
                            barmode="group",
                            title="배치별 유전자 상대 발현량 비교",
                            text_auto=True,
                        )
                        st.plotly_chart(fig_qpcr, use_container_width=True)

                with col_qp_table:
                    st.markdown("**통합 qPCR 데이터**")
                    st.dataframe(qpcr_combined, use_container_width=True)
            else:
                st.caption("선택한 배치에 저장된 qPCR 엑셀 데이터가 없습니다.")

            st.divider()

            # --- 3. FACS 비교 분석 ---
            st.markdown("### 📊 3. FACS 마커 양성 비율 비교")
            facs_combined = get_combined_excel_data("FACS")

            if not facs_combined.empty:
                col_fc_graph, col_fc_table = st.columns([3, 2])

                with col_fc_graph:
                    if (
                        "Pos_Pct" in facs_combined.columns
                        and "Marker" in facs_combined.columns
                    ):
                        facs_combined["Pos_Pct"] = pd.to_numeric(
                            facs_combined["Pos_Pct"], errors="coerce"
                        )

                        fig_facs = px.bar(
                            facs_combined,
                            x="Marker",
                            y="Pos_Pct",
                            color="Batch_ID",
                            barmode="group",
                            title="배치별 FACS 마커 양성 비율 (%) 비교",
                            text_auto=True,
                        )
                        st.plotly_chart(fig_facs, use_container_width=True)

                with col_fc_table:
                    st.markdown("**통합 FACS 데이터**")
                    st.dataframe(facs_combined, use_container_width=True)
            else:
                st.caption("선택한 배치에 저장된 FACS 엑셀 데이터가 없습니다.")
