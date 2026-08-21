import base64
import streamlit as st

# ======================================================================
# 1. 헬퍼(보조) 함수 정의
# ======================================================================

def extract_image_data(item):
    """
    treatment 아이템에서 base64 이미지 문자열을 추출합니다.
    (키 이름이 'image_data', 'image_b64', 'image' 등 다양한 상황에 대비)
    """
    return item.get('image_data') or item.get('image_b64') or item.get('image')

def display_image_from_b64(b64_str, caption=""):
    """
    base64 이미지 문자열을 Streamlit st.image로 출력합니다.
    data:image/...;base64, 헤더가 포함되어 있어도 처리 가능하도록 작성했습니다.
    """
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=True)
    except Exception as e:
        st.error(f"이미지 로드 실패: {e}")

def parse_note_basal_image(item):
    """
    노트, 배지 정보 등을 파싱하는 함수입니다. (기존 데이터 구조에 맞게 변경 가능)
    """
    basal = item.get('basal_media', '')
    note = item.get('note', '')
    img = extract_image_data(item)
    return basal, note, img

def format_compound_summary(compound_name, concentration):
    """
    화합물 및 농도 정보를 깔끔하게 포맷팅합니다.
    """
    if compound_name and concentration:
        return f"{compound_name} ({concentration})"
    elif compound_name:
        return f"{compound_name}"
    return "화합물 정보 없음"


# ======================================================================
# 2. 테스트용 메인 데이터 준비 및 UI 탭 구성
# ======================================================================

st.set_page_config(layout="wide")

# (선택 사항) 테스트용 예시 데이터 - 실제 환경에서는 데이터베이스/세션 상태에서 받아온 treatments를 사용하세요.
if "treatments" not in st.session_state:
    # 테스트용 1x1 투명 PNG Base64 예시 데이터
    dummy_b64 = "iVBORw0KGgoAAAANSUEngine/iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    st.session_state.treatments = [
        {
            "well_position": "A1",
            "treatment_date": "2026-03-01",
            "cell_info": "iPSC-derived Organoid",
            "compound_name": "Compound A",
            "concentration": "10 uM",
            "note": "초기 배양 상태 양호",
            "image_data": dummy_b64
        },
        {
            "well_position": "A1",
            "treatment_date": "2026-03-05",
            "cell_info": "iPSC-derived Organoid",
            "compound_name": "Compound A",
            "concentration": "10 uM",
            "note": "혈관 형성 관찰됨",
            "image_data": dummy_b64
        },
        {
            "well_position": "B2",
            "treatment_date": "2026-03-01",
            "cell_info": "Intestinal Organoid",
            "compound_name": "Control",
            "concentration": "0 uM",
            "note": "-",
            "image_data": dummy_b64
        }
    ]

treatments = st.session_state.treatments

# 탭 생성
tab_main, tab_compare = st.tabs(["메인 화면", "📸 사진 비교"])


# ======================================================================
# 3. [TAB 4] 사진 비교 시각화 실행
# ======================================================================
with tab_compare:
    st.markdown("### 📸 사진 비교 시각화")
    st.caption("Well별로 등록된 사진을 날짜별/조건별로 모아 비교합니다.")
    
    if not treatments:
        st.info("등록된 데이터가 없습니다.")
    else:
        img_data = [t for t in treatments if extract_image_data(t)]
        
        if not img_data:
            st.warning("첨부된 사진 데이터가 없습니다.")
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
