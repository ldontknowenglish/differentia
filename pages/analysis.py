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

st.set_page_config(layout="wide")

# 예시 데이터 (실제 프로젝트 환경에서는 DB 또는 세션 상태에서 가져옵니다)
if "treatments" not in st.session_state:
    dummy_b64 = "iVBORw0KGgoAAAANSUEngine/iVBORw0KGgoAAAANSUEngine/iVBORw0KGgoAAAANSUEngine/iVBORw0KGgoAAAANSUEngine"
    st.session_state.treatments = [
        {
            "project_name": "혈관 오가노이드 성숙도 실험",
            "well_position": "A1",
            "treatment_date": "2026-03-01",
            "cell_info": "iPSC-derived ECs",
            "compound_name": "VEGF",
            "concentration": "50 ng/mL",
            "note": "초기 배양 양호",
            "image_data": dummy_b64
        },
        {
            "project_name": "혈관 오가노이드 성숙도 실험",
            "well_position": "A1",
            "treatment_date": "2026-03-05",
            "cell_info": "iPSC-derived ECs",
            "compound_name": "VEGF",
            "concentration": "50 ng/mL",
            "note": "혈관 공통 구조 형성",
            "image_data": dummy_b64
        },
        {
            "project_name": "장 오가노이드 QC 스크리닝",
            "well_position": "B2",
            "treatment_date": "2026-03-01",
            "cell_info": "Intestinal Organoid",
            "compound_name": "Control",
            "concentration": "0 uM",
            "note": "-",
            "image_data": dummy_b64
        }
    ]

all_treatments = st.session_state.treatments

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
