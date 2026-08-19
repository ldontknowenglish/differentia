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
# 🧫 [사이드바] 프로젝트 및 배치(Batch) 선택
# ==========================================
projects = db.get_projects()

with st.sidebar:
    st.header("🧫 실험 배치(Batch) 선택")

    if not projects:
        st.warning("⚠️ 등록된 프로젝트가 없습니다. 프로젝트를 먼저 생성해 주세요.")
        current_batch = "미지정"
    else:
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


# ==========================================
# 📊 [메인 화면] 1. 통합 메타데이터 입력 구역
# ==========================================
st.title("🔬 실험 데이터 입력 및 배치 분석")

st.markdown("### 📋 공통 실험 메타데이터 (한번에 관리)")
st.caption("배치 정보와 실험 날짜 관련 메타데이터를 통합하여 한곳에서 관리합니다.")

with st.container(border=True):
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.text_input("🧫 배치 ID (Batch)", value=current_batch, disabled=True)
    with col_m2:
        sample_day = st.text_input("📅 샘플 시점 (Timepoint)", value="Day 7", help="예: Day 0, Day 7, Pass 2 등")
    with col_m3:
        acq_date = st.date_input("📅 샘플 획득일", datetime.date.today(), key="global_acq_date")
    with col_m4:
        exp_date = st.date_input("🧪 실험 진행일", datetime.date.today(), key="global_exp_date")

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


# [개편된 레이아웃] 데이터 입력(좌) / 데이터 수정·삭제(우) UI 랜더링 함수
def render_analysis_tab(assay_name, example_text, is_cell_count=False):
    st.subheader(f"{assay_name} 데이터 작업")

    col_left, col_right = st.columns([1, 1.2])

    with col_left:
        st.markdown("##### 📥 1. 데이터 가져오기")
        
        file_upload = st.file_uploader(
            f"엑셀/CSV 파일 업로드", type=["xlsx", "xls", "csv"], key=f"file_{assay_name}"
        )
        text_upload = st.text_area(
            "엑셀/Prism 복사-붙여넣기", value=example_text, height=140, key=f"txt_{assay_name}"
        )

        attachments = st.file_uploader(
            f"관련 사진/원시 데이터 첨부",
            accept_multiple_files=True,
            key=f"attach_{assay_name}",
        )
        if attachments:
            st.caption(f"📎 총 {len(attachments)}개 파일 첨부됨")

        df_parsed = parse_input_data(file_upload, text_upload)

    with col_right:
        st.markdown("##### ✏️ 2. 신규 데이터 검토 및 수정 / 삭제")
        
        if df_parsed is not None:
            st.caption("💡 **수정/삭제**: 셀 값을 직접 수정하거나 행 선택 후 `Del`키로 삭제 후 DB에 저장하세요.")

            df_working = df_parsed.copy()

            # Cell Count인 경우 1차, 2차 수치 기반 평균 자동 계산
            if is_cell_count:
                if "Count_1st" in df_working.columns and "Count_2nd" in df_working.columns:
                    df_working["Count_1st"] = pd.to_numeric(df_working["Count_1st"], errors="coerce")
                    df_working["Count_2nd"] = pd.to_numeric(df_working["Count_2nd"], errors="coerce")
                    df_working["Count_Mean"] = df_working[["Count_1st", "Count_2nd"]].mean(axis=1).round(3)

            # 사용자 지정 폼 형태 그대로 편집기 표시 (불필요한 메타데이터 컬럼 미포함)
            edited_df = st.data_editor(
                df_working, 
                num_rows="dynamic", 
                key=f"edit_{assay_name}",
                use_container_width=True
            )

            if st.button(f"💾 [{assay_name}] 데이터 DB 저장", key=f"btn_save_{assay_name}", type="primary"):
                # 작성한 폼 형태 그대로 DB에 저장
                db.save_analysis_data(current_batch, assay_name, edited_df)
                st.success(f"[{current_batch}] 배치의 {assay_name} 데이터가 성공적으로 저장되었습니다!")
        else:
            st.info("👈 왼쪽에서 데이터를 입력하거나 파일을 업로드하면, 이곳에 편집 테이블이 활성화됩니다.")

    st.divider()

    # 3. DB 저장 이력 조회 및 수정/삭제 (입력 폼과 동일한 구조 유지)
    st.markdown(f"#### 📜 [{current_batch}] 저장된 데이터 이력 관리")
    st.caption("💡 작성했던 데이터 폼 규격 그대로 저장된 이력입니다. 수정 후 아래 업데이트 버튼을 누르세요.")
    
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
            st.success("데이터베이스가 성공적으로 업데이트되었습니다!")
            st.rerun()
    else:
        st.caption(f"현재 선택된 배치({current_batch})에 저장된 {assay_name} 데이터가 없습니다.")


# --- 탭 1: Cell Count (1차, 2차, 평균 수치 관리 규격 적용) ---
with tab1:
    render_analysis_tab(
        "Cell Count",
        "Sample\tCount_1st\tCount_2nd\tViability_pct\nControl\t1.20\t1.24\t95.4\nGroup_A\t2.40\t2.60\t92.1\nGroup_B\t3.00\t3.20\t88.7",
        is_cell_count=True
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

    all_plates = []
    for proj in projects:
        p_list = db.get_plates(proj["id"])
        for pl in p_list:
            if pl["name"] not in all_plates:
                all_plates.append(pl["name"])

    if not all_plates:
        st.warning("등록된 배치(플레이트) 데이터가 없습니다.")
    else:
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

            def get_combined_data(assay_name):
                combined_list = []
                for b_id in selected_batches:
                    df = db.get_analysis_data(b_id, assay_name)
                    if not df.empty:
                        df_copy = df.copy()
                        df_copy.insert(0, "Batch_ID", b_id)
                        combined_list.append(df_copy)
                if combined_list:
                    return pd.concat(combined_list, ignore_index=True)
                return pd.DataFrame()

            # --- 1. Cell Count 비교 분석 ---
            st.markdown("### 🧫 1. Cell Count 배치 비교")
            cc_combined = get_combined_data("Cell Count")

            if not cc_combined.empty:
                col_cc_graph, col_cc_table = st.columns([3, 2])
                
                with col_cc_graph:
                    # 평균값(Count_Mean) 우선 시각화
                    target_col = "Count_Mean" if "Count_Mean" in cc_combined.columns else "Count_1st"
                    
                    if target_col in cc_combined.columns:
                        cc_combined[target_col] = pd.to_numeric(cc_combined[target_col], errors="coerce")
                        
                        fig_cc = px.bar(
                            cc_combined,
                            x="Sample" if "Sample" in cc_combined.columns else cc_combined.index,
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
