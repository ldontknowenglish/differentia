import datetime
import io
import pandas as pd
import plotly.express as px
import streamlit as st

# DB 모듈 임포트
import db

# 1. Streamlit 페이지 설정 (최상단 배치)
st.set_page_config(page_title="실험 데이터 관리 및 분석", layout="wide")

# 2. DB 및 관련 테이블 초기화
db.init_db()
db.init_analysis_tables()

# ==========================================
# 🧫 [사이드바] 배치(Batch) 선택 및 정보 설정
# ==========================================
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

    # 샘플 시점(Day) 입력
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
st.title("🔬 실험 데이터 입력 및 배치 분석")

# 상단 현황 메트릭
col_b1, col_b2, col_b3 = st.columns(3)
col_b1.metric("선택된 배치 ID", current_batch)
col_b2.metric("샘플 획득 시점", sample_day)
col_b3.metric("오늘 날짜", datetime.date.today().strftime("%Y-%m-%d"))

st.caption(f"💡 데이터 입력 시 **[{current_batch}]** 배치와 **[{sample_day}]** 정보가 함께 기록됩니다.")
st.divider()


# 엑셀 파일 또는 붙여넣은 텍스트 파싱 함수
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
tab1, tab2, tab3, tab4 = st.tabs(["🧫 Cell Count", "🧬 qPCR", "📊 FACS", "📈 배치 간 비교 분석 및 종합 보고서"])


# 데이터 입력 및 DB 이력 수정/삭제 공통 UI 함수
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

    # 4. 신규 데이터 검토 및 저장
    if df_parsed is not None:
        st.markdown("##### ✏️ 신규 키 데이터 검토 및 수정/삭제")
        st.caption("테이블 셀을 클릭하여 직접 수정하거나, 행을 선택하여 삭제(Del) 후 DB에 저장하세요.")

        df_working = df_parsed.copy()
        if "Batch_ID" not in df_working.columns:
            df_working.insert(0, "Batch_ID", current_batch)
            df_working.insert(1, "Timepoint", sample_day)
            df_working.insert(2, "샘플획득일", acq_date.strftime("%Y-%m-%d"))
            df_working.insert(3, "실험진행일", exp_date.strftime("%Y-%m-%d"))

        edited_df = st.data_editor(df_working, num_rows="dynamic", key=f"edit_{assay_name}")

        if st.button(f"💾 [{assay_name}] 데이터 DB 저장", key=f"btn_save_{assay_name}"):
            db.save_analysis_data(current_batch, assay_name, edited_df)
            st.success(f"[{current_batch}] 배치의 {assay_name} 데이터가 DB에 저장되었습니다!")

    st.divider()

    # 5. DB 저장 이력 조회, 수정 및 삭제
    st.markdown(f"#### 📜 [{current_batch}] DB 저장 데이터 관리 (수정 / 삭제)")
    st.caption("💡 **수정/삭제 방법**: 아래 테이블에서 값을 직접 편집하거나 삭제할 행을 클릭(Del 키)한 후 하단의 **'DB 변경사항 업데이트'** 버튼을 누르세요.")
    
    saved_df = db.get_analysis_data(current_batch, assay_name)

    if not saved_df.empty:
        updated_db_df = st.data_editor(
            saved_df,
            num_rows="dynamic",
            key=f"db_edit_{assay_name}",
            use_container_width=True,
        )
        
        col_act1, col_act2 = st.columns([1, 4])
        with col_act1:
            if st.button(f"🔄 [{assay_name}] DB 변경사항 업데이트", key=f"btn_update_{assay_name}"):
                db.save_analysis_data(current_batch, assay_name, updated_db_df)
                st.success("데이터베이스가 성공적으로 업데이트되었습니다!")
                st.rerun()
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


# ==========================================
# 📈 [탭 4] 배치 간 비교 분석 및 종합 보고서
# ==========================================
with tab4:
    st.subheader("📈 선택한 배치(플레이트) 간 비교 분석 및 종합 보고서")
    st.caption("여러 배치를 다중 선택하여 실험 데이터(Cell Count, qPCR, FACS)를 비교 시각화합니다.")

    # 전체 배치(플레이트) 목록 추출
    all_plates = []
    for proj in projects:
        p_list = db.get_plates(proj["id"])
        for pl in p_list:
            if pl["name"] not in all_plates:
                all_plates.append(pl["name"])

    if not all_plates:
        st.warning("등록된 배치(플레이트) 데이터가 없습니다.")
    else:
        # 다중 배치 선택 드롭다운
        default_selected = [current_batch] if current_batch in all_plates else [all_plates[0]]
        selected_batches = st.multiselect(
            "🔍 비교 분석할 배치(플레이트) 들을 선택하세요:",
            options=all_plates,
            default=default_selected,
            key="multi_batch_select",
        )

        if not selected_batches:
            st.info("비교할 배치를 1개 이상 선택해 주세요.")
        else:
            st.divider()

            # 선택된 배치들의 데이터 통합 로딩 함수
            def get_combined_data(assay_name):
                combined_list = []
                for b_id in selected_batches:
                    df = db.get_analysis_data(b_id, assay_name)
                    if not df.empty:
                        combined_list.append(df)
                if combined_list:
                    return pd.concat(combined_list, ignore_index=True)
                return pd.DataFrame()

            # --- 1. Cell Count 비교 분석 ---
            st.markdown("### 🧫 1. Cell Count 배치 비교")
            cc_combined = get_combined_data("Cell Count")

            if not cc_combined.empty:
                col_cc_graph, col_cc_table = st.columns([3, 2])
                
                with col_cc_graph:
                    # 수치형 변환
                    if "Concentration_M_mL" in cc_combined.columns:
                        cc_combined["Concentration_M_mL"] = pd.to_numeric(cc_combined["Concentration_M_mL"], errors="coerce")
                        
                        fig_cc = px.bar(
                            cc_combined,
                            x="Sample" if "Sample" in cc_combined.columns else cc_combined.index,
                            y="Concentration_M_mL",
                            color="Batch_ID",
                            barmode="group",
                            title="배치별 세포 농도 비교 (Concentration M/mL)",
                            text_auto=True,
                        )
                        st.plotly_chart(fig_cc, use_container_width=True)
                
                with col_cc_table:
                    st.markdown("**통합 Cell Count 데이터**")
                    st.dataframe(cc_combined, use_container_width=True)
            else:
                st.caption("선택한 배치에 등록된 Cell Count 데이터가 없습니다.")

            st.divider()

            # --- 2. qPCR 비교 분석 ---
            st.markdown("### 🧬 2. qPCR 상대 발현량 비교")
            qpcr_combined = get_combined_data("qPCR")

            if not qpcr_combined.empty:
                col_qp_graph, col_qp_table = st.columns([3, 2])

                with col_qp_graph:
                    if "Relative_Expression" in qpcr_combined.columns and "Gene" in qpcr_combined.columns:
                        qpcr_combined["Relative_Expression"] = pd.to_numeric(qpcr_combined["Relative_Expression"], errors="coerce")

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
                st.caption("선택한 배치에 등록된 qPCR 데이터가 없습니다.")

            st.divider()

            # --- 3. FACS 비교 분석 ---
            st.markdown("### 📊 3. FACS 마커 양성 비율 비교")
            facs_combined = get_combined_data("FACS")

            if not facs_combined.empty:
                col_fc_graph, col_fc_table = st.columns([3, 2])

                with col_fc_graph:
                    if "Pos_Pct" in facs_combined.columns and "Marker" in facs_combined.columns:
                        facs_combined["Pos_Pct"] = pd.to_numeric(facs_combined["Pos_Pct"], errors="coerce")

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
                st.caption("선택한 배치에 등록된 FACS 데이터가 없습니다.")
