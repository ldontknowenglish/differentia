import base64
import datetime
import streamlit as st
import pandas as pd
import db  # DB 모듈 호출

# 페이지 기본 설정
st.set_page_config(page_title="사진 비교 시각화", page_icon="📸", layout="wide")

# DB 초기화
if hasattr(db, 'init_db'):
    db.init_db()

# ======================================================================
# 1. 헬퍼(보조) 함수 정의
# ======================================================================

def extract_image_data(item):
    """treatment 아이템에서 base64 이미지 문자열을 추출합니다."""
    if not item:
        return None
    if item.get('image_data'):
        return item['image_data']
    if item.get('image_b64'):
        return item['image_b64']
    if item.get('image'):
        return item['image']
    
    # DB note에 [IMG_DATA:...] 형태로 저장된 경우 파싱
    note = str(item.get('note', ''))
    if '[IMG_DATA:' in note and ']' in note:
        start = note.find('[IMG_DATA:') + len('[IMG_DATA:')
        end = note.rfind(']')
        if start < end:
            return note[start:end].strip()
    return None

def get_basal_media(item):
    """Basal Media 정보를 안전하게 추출"""
    if not item:
        return "-"
    if item.get('basal_media') and str(item['basal_media']).strip() and str(item['basal_media']).strip() != '-':
        return str(item['basal_media']).strip()
    note = str(item.get('note', ''))
    if '[Media:' in note and ']' in note:
        start = note.find('[Media:') + len('[Media:')
        end = note.find(']', start)
        if end != -1:
            extracted = note[start:end].strip()
            if extracted:
                return extracted
    return "-"

def parse_note_basal_image(item):
    """노트, 배지 정보, 이미지를 분리 파싱하는 함수입니다."""
    if not item:
        return "-", "", None
    basal = get_basal_media(item)
    raw_note = str(item.get('note', ''))
    img_data = extract_image_data(item)
    
    pure_note = raw_note
    if '[Media:' in pure_note and ']' in pure_note:
        m_start = pure_note.find('[Media:')
        m_end = pure_note.find(']', m_start)
        if m_end != -1:
            pure_note = (pure_note[:m_start] + pure_note[m_end+1:]).strip()
            
    if '[IMG_DATA:' in pure_note and ']' in pure_note:
        i_start = pure_note.find('[IMG_DATA:')
        i_end = pure_note.rfind(']')
        if i_end != -1:
            pure_note = (pure_note[:i_start] + pure_note[i_end+1:]).strip()
            
    return basal, pure_note.strip(), img_data

def format_compound_summary(compound_name, concentration):
    """화합물 및 농도 정보를 포맷팅합니다."""
    if compound_name and concentration and concentration != "-":
        return f"{compound_name} ({concentration})"
    elif compound_name:
        return f"{compound_name}"
    return "화합물 정보 없음"

def display_image_from_b64(b64_str, caption=""):
    """base64 이미지 문자열을 Streamlit st.image로 안전하게 출력합니다."""
    if not b64_str:
        return
    try:
        if "," in str(b64_str):
            b64_str = str(b64_str).split(",")[1]
        img_bytes = base64.b64decode(b64_str)
        st.image(img_bytes, caption=caption, use_container_width=True)
    except Exception as e:
        st.caption("⚠️ 이미지를 로드할 수 없습니다.")

# ======================================================================
# 2. DB에서 프로젝트 및 Plate 데이터 가져오기
# ======================================================================

projects = db.get_projects()

if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다. 프로젝트를 먼저 등록해 주세요.")
    st.stop()

proj_map = {f"[{p.get('group_name', '기본')}] {p['name']} (ID: {p['id']})": p for p in projects}

# ======================================================================
# 3. 👈 [왼쪽 사이드바] 프로젝트 및 Well Plate 선택 UI
# ======================================================================

with st.sidebar:
    st.header("📂 프로젝트 및 플레이트 선택")
    
    selected_proj_label = st.selectbox("📌 프로젝트 선택:", list(proj_map.keys()))
    selected_proj = proj_map[selected_proj_label]
    
    # 해당 프로젝트에 속한 플레이트(Well Plate 설정) 가져오기
    plates = db.get_plates(selected_proj['id'])
    
    if plates:
        plate_map = {f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)": pl for pl in plates}
        selected_plate_label = st.selectbox("🧫 플레이트 선택:", list(plate_map.keys()))
        selected_plate = plate_map[selected_plate_label]
        
        # 선택된 플레이트의 treatment 데이터 가져오기
        treatments = db.get_treatments_by_plate(selected_plate['id'])
    else:
        st.info("선택된 프로젝트에 생성된 Well Plate가 없습니다.")
        selected_plate = None
        treatments = []

    st.divider()
    st.caption("🔍 선택된 프로젝트/플레이트의 실제 실험 사진만 필터링되어 비교 화면에 표시됩니다.")

# ======================================================================
# 4. [메인 영역] 탭 구성 및 사진 비교 시각화
# ======================================================================

tab_main, tab_compare = st.tabs(["🏠 메인 화면", "📸 사진 비교"])

with tab_main:
    st.title("🧪 실험 데이터 관리 시스템")
    if selected_plate:
        st.success(f"현재 선택된 플레이트: **{selected_plate['name']}** (규격: {selected_plate['rows']} x {selected_plate['cols']})")
        st.info(f"총 **{len(treatments)}건**의 실험(Treatment) 데이터가 등록되어 있습니다.")
    else:
        st.warning("사이드바에서 작업할 플레이트를 선택하세요.")

with tab_compare:
    plate_title = selected_plate['name'] if selected_plate else '선택 안 됨'
    st.markdown(f"### 📸 사진 비교 시각화 (`{selected_proj['name']}` - `{plate_title}`)")
    st.caption("Well별로 등록된 사진을 날짜별/조건별로 모아 비교합니다.")
    
    if not treatments:
        st.info("선택한 플레이트에 등록된 실험 데이터가 없습니다.")
    else:
        # 이미지가 포함된 treatment 데이터만 필터링
        img_data = []
        for t in treatments:
            img_b64 = extract_image_data(t)
            if img_b64:
                t_copy = dict(t)
                t_copy['image_data'] = img_b64
                img_data.append(t_copy)
        
        if not img_data:
            st.warning("선택한 플레이트에 첨부된 현미경/실험 사진 데이터가 없습니다.")
        else:
            compare_mode = st.radio("보기 모드", ["날짜별 그룹화", "Well별 그룹화"], horizontal=True)
            st.divider()
            
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
                                img_b64 = item['image_data']
                                with cols[j]:
                                    b_media, pure_note, _ = parse_note_basal_image(item)
                                    caption = f"[{item['well_position']}] {item.get('cell_info', '')}"
                                    display_image_from_b64(img_b64, caption=caption)
                                    st.caption(f"🧪 {format_compound_summary(item.get('compound_name'), item.get('concentration'))}")
                                    if b_media and b_media != "-":
                                        st.caption(f"🥛 {b_media}")
                                    if pure_note: 
                                        st.caption(f"📝 {pure_note}")
                                        
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
                                img_b64 = item['image_data']
                                with cols[j]:
                                    b_media, pure_note, _ = parse_note_basal_image(item)
                                    caption = f"📅 {item['treatment_date']}"
                                    display_image_from_b64(img_b64, caption=caption)
                                    st.caption(f"🧬 {item.get('cell_info', '')}")
                                    st.caption(f"🧪 {format_compound_summary(item.get('compound_name'), item.get('concentration'))}")
                                    if b_media and b_media != "-":
                                        st.caption(f"🥛 {b_media}")
                                    if pure_note: 
                                        st.caption(f"📝 {pure_note}")
