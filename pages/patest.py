import datetime
import io
import pandas as pd
import plotly.express as px
import streamlit as st

# DB 모듈 임포트
import db

# 1. Streamlit 페이지 설정 (다른 Streamlit 동작 전에 가장 먼저 실행되어야 함)
st.set_page_config(page_title="실험 데이터 관리", layout="wide")

# 2. DB 및 관련 테이블 초기화
db.init_db()
db.init_analysis_tables()

# ==========================================
# 🧫 [사이드바] 배치(Batch) 선택 및 정보 설정
# ==========================================
db.init_db()
projects = db.get_projects()

with st.sidebar:
    st.header("🧫 실험 배치(Batch) 선택")

    # DB에 등록된 프로젝트가 없는 경우 처리
    if not projects:
        st.warning("⚠️ 등록된 프로젝트가 없습니다. 프로젝트를 먼저 생성해 주세요.")
        current_batch = "미지정"
        sample_day = "Day 0"
    else:
        # 프로젝트 선택
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

        # 플레이트(배치) 선택
        plates = db.get_plates(selected_proj["id"])

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
            current_batch = selected_plate["name"]
        else:
            st.info("💡 해당 프로젝트에 등록된 플레이트가 없습니다.")
            current_batch = "플레이트 없음"

    st.divider()

    # [수정 1 & 2] 배치 시작 조건 제거 및 몇 일차 샘플(Day) 입력 칸 추가
    st.subheader("📅 샘플 시점 설정")
    sample_day = st.text_input(
        "샘플 획득 시점 (Day/Timepoint)",
        value="Day 7",
        help="예: Day 0, Day 3, Day 14, Pass 2 등",
    )

    st.info(
        f"""
    **현재 선택 상태**
    - **플레이트**: `{current_batch}`
    - **샘플 시점**: `{sample_day}`
    """
    )


# ==========================================
# 📊 [메인 화면] 선택된 배치 기반 데이터 작업
# ==========================================
st.title("🔬 실험 데이터 입력 및 분석")

# 상단 현황 메트릭
col_b1, col_b2, col_b3 = st.columns(3)
col_b1.metric("선택된 배치 ID", current_batch)
col_b2.metric("샘플 획득 시점", sample_day)
col_b3.metric("오늘 날짜", datetime.date.today().strftime("%Y-%m-%d"))

st.caption(f"💡 데이터 입력 시 **[{current_batch}]** 배치와 **[{sample_day}]** 정보가 함께 기록됩니다.")
st.divider()


# [수정 3] 엑셀 파일 또는 붙여넣은 텍스트 파싱 함수
def parse_input_data(uploaded_file, raw_text):
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                return pd.read_csv(uploaded_file)
            else:
                return pd.read_excel(uploaded_file)
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
tab1, tab2, tab3, tab4 = st.tabs(["🧫 Cell Count", "🧬 qPCR", "📊 FACS", "📈 종합 결과 보고서"])


# 데이터 입력 공통 UI 랜더링 함수
def render_analysis_tab(assay_name, example_text):
    st.subheader(f"{assay_name} 데이터 입력 ({current_batch} / {sample_day})")

    # 1. 날짜 설정 (샘플 획득일 vs 실험 진행일)
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        acq_date = st.date_input(f"📅 샘플 획득일 ({assay_name})", datetime.date.today(), key=f"acq_{assay_name}")
    with col_d2:
        exp_date = st.date_input(f"🧪 실험 진행일 ({assay_name})", datetime.date.today(), key=f"exp_{assay_name}")

    # 2. 파일 업로드 및 붙여넣기 선택
    st.markdown("##### 📥 데이터 가져오기 (엑셀 Upload 또는 텍스트 붙여넣기)")
    col_in1, col_in2 = st.columns([1, 1])

    with col_in1:
        file_upload = st.file_uploader(
            f"엑셀/CSV 파일 업로드 ({assay_name})", type=["xlsx", "xls", "csv"], key=f"file_{assay_name}"
        )
    with col_in2:
        text_upload = st.text_area(
            "엑셀/Prism 복사-붙여넣기", value=example_text, height=100, key=f"txt_{assay_name}"
        )

    df_parsed = parse_input_data(file_upload, text_upload)

    # 3. 사진 및 이미지/파일 첨부
    st.markdown("##### 📎 증빙 사진 및 원본 파일 첨부")
    attachments = st.file_uploader(
        f"관련 사진/원시 데이터 파일 첨부 ({assay_name})",
        accept_multiple_files=True,
        key=f"attach_{assay_name}",
    )
    if attachments:
        st.caption(f"총 {len(attachments)}개 파일 첨부됨")

    # 4. 데이터 편집 및 키 데이터 정리
    if df_parsed is not None:
        st.markdown("##### ✏️ 키 데이터 검토 및 수정/삭제")
        st.caption("아래 테이블에서 셀 값을 직접 수정하거나 행을 추가/삭제(Del 키)할 수 있습니다.")

        # 공통 메타데이터 열 삽입
        df_working = df_parsed.copy()
        if "Batch_ID" not in df_working.columns:
            df_working.insert(0, "Batch_ID", current_batch)
            df_working.insert(1, "Timepoint", sample_day)
            df_working.insert(2, "샘플획득일", acq_date.strftime("%Y-%m-%d"))
            df_working.insert(3, "실험진행일", exp_date.strftime("%Y-%m-%d"))

        # 행 수정 및 삭제가 가능한 Data Editor
        edited_df = st.data_editor(df_working, num_rows="dynamic", key=f"edit_{assay_name}")

        if st.button(f"💾 [{assay_name}] 데이터 DB 저장", key=f"btn_save_{assay_name}"):
            db.save_analysis_data(current_batch, assay_name, edited_df)
            st.success(f"[{current_batch}] 배치의 {assay_name} 데이터가 DB에 저장되었습니다!")

    st.divider()

    # 5. DB 저장 이력 조회 및 수정/삭제
    st.markdown(f"#### 📜 [{current_batch}] DB 저장된 {assay_name} 이력")
    saved_df = db.get_analysis_data(current_batch, assay_name)

    if not saved_df.empty:
        updated_db_df = st.data_editor(
            saved_df,
            num_rows="dynamic",
            key=f"db_edit_{assay_name}",
            use_container_width=True,
        )
        if st.button(f"🔄 [{assay_name}] DB 변경사항 업데이트", key=f"btn_update_{assay_name}"):
            db.save_analysis_data(current_batch, assay_name, updated_db_df)
            st.success("DB 내용이 업데이트되었습니다.")
    else:
        st.caption(f"저장된 {assay_name} 데이터가 없습니다.")


# --- 탭 1: Cell Count ---
with tab1:
    render_analysis_tab(
        "Cell Count",
        "Sample\tConcentration_M_mL\tViability_pct\nControl\t1.2\t95.4\nGroup_A\t2.5\t92.1\nGroup_B\t3.1\t88.7",
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


# [수정 4] 해당 플레이트의 실험 결과를 한눈에 보는 종합 요약 탭
with tab4:
    st.subheader(f"📈 [{current_batch}] 플레이트 실험 결과 종합 보고서")
    st.caption("현재 플레이트에 기록된 모든 실험 데이터를 한눈에 확인합니다.")

    cc_df = db.get_analysis_data(current_batch, "Cell Count")
    qpcr_df = db.get_analysis_data(current_batch, "qPCR")
    facs_df = db.get_analysis_data(current_batch, "FACS")

    # 요약 메트릭 카운트
    sum_col1, sum_col2, sum_col3 = st.columns(3)
    sum_col1.metric("Cell Count 레코드", f"{len(cc_df)}건")
    sum_col2.metric("qPCR 레코드", f"{len(qpcr_df)}건")
    sum_col3.metric("FACS 레코드", f"{len(facs_df)}건")

    st.divider()

    # 종합 결과 아코디언/확장형 뷰
    with st.expander("🧫 Cell Count 종합 데이터", expanded=True):
        if not cc_df.empty:
            st.dataframe(cc_df, use_container_width=True)
        else:
            st.info("등록된 Cell Count 데이터가 없습니다.")

    with st.expander("🧬 qPCR 종합 데이터", expanded=True):
        if not qpcr_df.empty:
            st.dataframe(qpcr_df, use_container_width=True)
        else:
            st.info("등록된 qPCR 데이터가 없습니다.")

    with st.expander("📊 FACS 종합 데이터", expanded=True):
        if not facs_df.empty:
            st.dataframe(facs_df, use_container_width=True)
        else:
            st.info("등록된 FACS 데이터가 없습니다.")
