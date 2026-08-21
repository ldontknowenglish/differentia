import base64
import streamlit as st

# ======================================================================
# 1. 헬퍼(보조) 함수 정의
# ======================================================================

def extract_image_data(item):
    """treatment 아이템에서 base64 이미지 문자열을 추출합니다."""
    return item.get('image_data') or item.get('image_b64') or item.get('image')

def display_image_from_b64(b64_str, caption=""):
    """base64 이미지 문자열을 Streamlit st.image로 안전하게 출력합니다."""
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=True)
    except Exception as e:
        st.error(f"이미지 로드 실패: {e}")

def parse_note_basal_image(item):
    """노트, 배지 정보 등을 파싱하는 함수입니다."""
    basal = item.get('basal_media', '')
    note = item.get('note', '')
    img = extract_image_data(item)
    return basal, note, img

def format_compound_summary(compound_name, concentration):
    """화합물 및 농도 정보를 포맷팅합니다."""
    if compound_name and concentration:
        return f"{compound_name} ({concentration})"
    elif compound_name:
        return f"{compound_name}"
    return "화합물 정보 없음"


# ======================================================================
# 2. 테스트용 메인 데이터 준비
# ======================================================================
        with tab_compare:
            st.caption("💡 등록된 현미경 사진들을 시간 흐름(날짜별) 또는 동일 일자의 조건별로 나란히 비교할 수 있습니다.")

            treatments_with_img = []
            for t in treatments:
                b_media, pure_note, img_b64 = parse_note_basal_image(t)
                if img_b64:
                    t_copy = dict(t)
                    t_copy['parsed_basal'] = b_media
                    t_copy['parsed_note'] = pure_note
                    t_copy['img_b64'] = img_b64
                    treatments_with_img.append(t_copy)

            if not treatments_with_img:
                st.warning("🖼️ 현재 플레이트에 등록된 현미경 사진이 없습니다.")
            else:
                compare_mode = st.radio(
                    "📌 비교 보기 방식 선택",
                    ["📅 1. 날짜별 변화 비교 (동일 Well/조건의 시계열 변화)", "🧪 2. 조건별 결과 비교 (동일 날짜의 Well/조건 간 비교)"],
                    horizontal=True
                )

                st.markdown("---")
                grid_cols_count = st.slider("📐 한 줄에 표시할 사진 개수 (열 조정)", min_value=2, max_value=6, value=3)

                if compare_mode.startswith("📅"):
                    all_wells_with_img = sorted(list(set([t['well_position'] for t in treatments_with_img])))
                    
                    c_sel1, c_sel2 = st.columns([1, 2])
                    with c_sel1:
                        selected_compare_well = st.selectbox("🎯 비교할 Well 선택", all_wells_with_img)

                    well_img_list = [t for t in treatments_with_img if t['well_position'] == selected_compare_well]
                    well_img_list = sorted(well_img_list, key=lambda x: x['treatment_date'])

                    st.markdown(f"##### 🧫 Well [{selected_compare_well}] 날짜별 사진 변화 ({len(well_img_list)}장)")

                    img_cols = st.columns(grid_cols_count)
                    for idx, t_item in enumerate(well_img_list):
                        with img_cols[idx % grid_cols_count]:
                            formatted_cond = format_compound_summary(t_item['compound_name'], t_item['concentration'])
                            analysis_tag = t_item.get('analysis_status', '미진행')
                            st.markdown(
                                f"""
                                <div style="border: 1px solid #cbd5e1; padding: 8px; border-radius: 8px; background-color: #f8fafc; margin-bottom: 12px;">
                                    <p style="margin:0; font-weight:bold; color:#1e293b; font-size:14px;">📅 {t_item['treatment_date']}</p>
                                    <p style="margin:2px 0; color:#3b82f6; font-size:12px;"><b>🧬 세포:</b> {t_item.get('cell_info','-')} | <b>🔬 분석:</b> {analysis_tag}</p>
                                    <p style="margin:0; color:#64748b; font-size:11px;"><b>🧪 조건:</b> {formatted_cond} | <b>🥛 배지:</b> {t_item['parsed_basal']}</p>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            display_image_from_b64(t_item['img_b64'], caption=f"{t_item['treatment_date']} - {selected_compare_well}")
                            if t_item['parsed_note']:
                                st.caption(f"📝 {t_item['parsed_note']}")

                else:
                    all_dates_with_img = sorted(list(set([t['treatment_date'] for t in treatments_with_img])))
                    
                    c_sel1, c_sel2 = st.columns([1, 2])
                    with c_sel1:
                        selected_compare_date = st.selectbox("📅 비교할 날짜 선택", all_dates_with_img)

                    date_img_list = [t for t in treatments_with_img if t['treatment_date'] == selected_compare_date]
                    date_img_list = sorted(date_img_list, key=lambda x: x['well_position'])

                    st.markdown(f"##### 📅 [{selected_compare_date}] 각 Well/조건별 사진 비교 ({len(date_img_list)}장)")

                    img_cols = st.columns(grid_cols_count)
                    for idx, t_item in enumerate(date_img_list):
                        with img_cols[idx % grid_cols_count]:
                            formatted_cond = format_compound_summary(t_item['compound_name'], t_item['concentration'])
                            analysis_tag = t_item.get('analysis_status', '미진행')
                            st.markdown(
                                f"""
                                <div style="border: 1px solid #cbd5e1; padding: 8px; border-radius: 8px; background-color: #f8fafc; margin-bottom: 12px;">
                                    <p style="margin:0; font-weight:bold; color:#0f172a; font-size:14px;">📍 Well {t_item['well_position']}</p>
                                    <p style="margin:2px 0; color:#059669; font-size:12px;"><b>🧬 세포:</b> {t_item.get('cell_info','-')} | <b>🔬 분석:</b> {analysis_tag}</p>
                                    <p style="margin:0; color:#64748b; font-size:11px;"><b>🧪 조건:</b> {formatted_cond} | <b>🥛 배지:</b> {t_item['parsed_basal']}</p>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            display_image_from_b64(t_item['img_b64'], caption=f"Well {t_item['well_position']} ({formatted_cond})")
                            if t_item['parsed_note']:
                                st.caption(f"📝 {t_item['parsed_note']}")
                            
                            
                            
            


# ======================================================================
# 3. 👈 [왼쪽 사이드바] 프로젝트 선택 UI
# ======================================================================

with st.sidebar:
    st.header("📂 프로젝트 선택")
    
    # 등록된 프로젝트 목록 추출 (중복 제거)
    project_list = sorted(list(set([t.get('project_name', '기타/미지정') for t in all_treatments])))
    
    # 전체 선택 옵션 추가
    selected_project = st.selectbox(
        "비교할 프로젝트를 선택하세요:",
        options=["전체 프로젝트"] + project_list
    )
    
    st.divider()
    st.caption("🔍 필터 옵션을 선택하면 해당 프로젝트의 사진 데이터만 필터링되어 비교 화면에 표시됩니다.")

# 데이터 필터링 적용
if selected_project == "전체 프로젝트":
    treatments = all_treatments
else:
    treatments = [t for t in all_treatments if t.get('project_name', '기타/미지정') == selected_project]


# ======================================================================
# 4. [메인 영역] 탭 구성 및 사진 비교 시각화
# ======================================================================

tab_main, tab_compare = st.tabs(["메인 화면", "📸 사진 비교"])

with tab_compare:
    st.markdown(f"### 📸 사진 비교 시각화 (`{selected_project}`)")
    st.caption("Well별로 등록된 사진을 날짜별/조건별로 모아 비교합니다.")
    
    if not treatments:
        st.info("선택한 프로젝트에 등록된 데이터가 없습니다.")
    else:
        img_data = [t for t in treatments if extract_image_data(t)]
        
        if not img_data:
            st.warning("선택한 프로젝트에 첨부된 사진 데이터가 없습니다.")
        else:
            compare_mode = st.radio("보기 모드", ["날짜별 그룹화", "Well별 그룹화"], horizontal=True)
            
            if compare_mode == "날짜별 그룹화":
                dates = sorted(list(set([t['treatment_date'] for t in img_data])), reverse=True)
                for d in dates:
                    st.markdown(f"#### 📅 {d}")
                    items_on_date = [t for t in img_data if t['treatment_date'] == d]
                    
                    cols_per_row = 4
                    for i in range(0, len(items_on_date), cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j in range(cols_per_row):
                            if i + j < len(items_on_date):
                                item = items_on_date[i + j]
                                img_b64 = extract_image_data(item)
                                with cols[j]:
                                    b, n, _ = parse_note_basal_image(item)
                                    caption = f"[{item['well_position']}] {item.get('cell_info', '')}"
                                    display_image_from_b64(img_b64, caption=caption)
                                    st.caption(f"🧪 {format_compound_summary(item.get('compound_name'), item.get('concentration'))}")
                                    if n: 
                                        st.caption(f"📝 {n}")
                                    
            else: # Well별 그룹화
                wells = sorted(list(set([t['well_position'] for t in img_data])))
                for w in wells:
                    st.markdown(f"#### 🧫 Well [{w}]")
                    items_in_well = sorted([t for t in img_data if t['well_position'] == w], key=lambda x: x['treatment_date'])
                    
                    cols_per_row = 4
                    for i in range(0, len(items_in_well), cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j in range(cols_per_row):
                            if i + j < len(items_in_well):
                                item = items_in_well[i + j]
                                img_b64 = extract_image_data(item)
                                with cols[j]:
                                    b, n, _ = parse_note_basal_image(item)
                                    caption = f"📅 {item['treatment_date']}"
                                    display_image_from_b64(img_b64, caption=caption)
                                    st.caption(f"🧬 {item.get('cell_info', '')}")
                                    st.caption(f"🧪 {format_compound_summary(item.get('compound_name'), item.get('concentration'))}")
                                    if n: 
                                        st.caption(f"📝 {n}")
