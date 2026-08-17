import streamlit as st
import pandas as pd
import datetime
import calendar
import db
import style

# --- 페이지 설정 및 디자인 서식 적용 ---
st.set_page_config(page_title="실험 달력 관리", page_icon="📅", layout="wide")

if hasattr(style, "apply_custom_style"):
    style.apply_custom_style()

st.title("📅 전체 연구노트 월별 통합 실험 달력")

# 헬퍼 함수 정의
def extract_image_data(item):
    if not item:
        return None
    if item.get('image_data'):
        return item['image_data']
    note = str(item.get('note', ''))
    if '[IMG_DATA:' in note and ']' in note:
        start = note.find('[IMG_DATA:') + len('[IMG_DATA:')
        end = note.rfind(']')
        if start < end:
            return note[start:end].strip()
    return None

def parse_note_basal_image(item):
    if not item:
        return "", "", None
    basal = item.get('basal_media', '-')
    if basal == "-":
        basal = ""
    
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

db.init_db()
projects = db.get_projects()

if not projects:
    st.warning("⚠️ 등록된 프로젝트가 없습니다.")
else:
    all_treatments = []
    
    for p in projects:
        plates = db.get_plates(p['id'])
        if plates:
            plate_name_map = {pl['id']: pl['name'] for pl in plates}
            for pl in plates:
                plate_treatments = db.get_treatments_by_plate(pl['id'])
                for t in plate_treatments:
                    t['project_name'] = p['name']
                    t['plate_name'] = plate_name_map.get(t['plate_id'], '기본 플레이트')
                    all_treatments.append(t)

    # --- 사이드바 조회 설정 영역 ---
    with st.sidebar:
        st.markdown("### ⚙️ 조회 설정")
        today = datetime.date.today()
        
        sel_year = st.number_input("연도 선택", min_value=2020, max_value=2035, value=today.year)
        sel_month = st.selectbox("월 선택", list(range(1, 13)), index=today.month - 1)
        
        month_cal = calendar.monthcalendar(sel_year, sel_month)

        week_options = []
        for w_idx, week in enumerate(month_cal):
            valid_days = [d for d in week if d != 0]
            if valid_days:
                week_options.append((w_idx, f"{sel_year}년 {sel_month}월 {w_idx + 1}주차 ({valid_days[0]}일 ~ {valid_days[-1]}일)"))

        selected_week_idx, selected_week_label = st.selectbox(
            "🔎 확대할 주(Week) 선택", 
            options=week_options, 
            format_func=lambda x: x[1]
        )

    # --- 달력 로직 구현부 ---
    st.caption("💡 동일한 세포 오가노이드 정보 및 플레이트/조건을 가진 항목들은 하나의 대표 실험 항목으로 묶여 표시됩니다.")

    # 데이터 그룹화 처리 (날짜별 맵핑)
    treatment_date_map = {}
    if all_treatments:
        for t in all_treatments:
            d_str = t['treatment_date']
            if not d_str:
                continue
            
            if d_str not in treatment_date_map:
                treatment_date_map[d_str] = []
            
            treatment_date_map[d_str].append(t)

    # 💡 데이터 그룹화: 동일 플레이트, 세포, 배지 조건 내부에서 각 well별 (물질, 농도) 쌍을 수집
    grouped_date_map = {}
    for d_str, items in treatment_date_map.items():
        merged_dict = {}
        for item in items:
            plate_n = item.get('plate_name', '')
            cell_info = item.get('cell_info', '-').strip() if item.get('cell_info') else '-'
            comp_name = item.get('compound_name', '기타')
            conc = item.get('concentration', '-')
            basal_media = item.get('basal_media', '-')
            
            group_key = (plate_n, cell_info, basal_media)
            
            if group_key not in merged_dict:
                merged_dict[group_key] = item.copy()
                merged_dict[group_key]['treatments_set'] = {(comp_name, conc)}
            else:
                merged_dict[group_key]['treatments_set'].add((comp_name, conc))
                    
        # 집합 형태를 리스트로 변환
        processed_items = []
        for g_key, val in merged_dict.items():
            val['treatments_list'] = list(val['treatments_set'])
            processed_items.append(val)
            
        grouped_date_map[d_str] = processed_items

    # 전체 통계 계산 (그룹화된 묶음 건수 기준)
    month_treatment_count = sum(
        len(v) for k, v in grouped_date_map.items() 
        if k.startswith(f"{sel_year}-{sel_month:02d}")
    )
    
    st.markdown(
        f"""
        <div style="padding:10px; background-color:#f0fdf4; border-left:4px solid #16a34a; border-radius:6px; margin-top:10px; margin-bottom:15px;">
            <span style="font-size:14px; color:#15803d; font-weight:bold;">📊 {sel_year}년 {sel_month}월 연구노트 통합 통계</span><br>
            <span style="font-size:13px; color:#166534;">동일 조건 통합 기준 총 <b>{month_treatment_count}건</b>의 실험 그룹이 진행되었습니다.</span>
        </div>
        """, unsafe_allow_html=True
    )

    st.markdown(f"### 📍 {selected_week_label} (달력 칸 내부 확장 보기)")

    week_days = ["월 (Mon)", "화 (Tue)", "수 (Wed)", "목 (Thu)", "금 (Fri)", "토 (Sat)", "일 (Sun)"]
    cols = st.columns(7)
    for idx, day_name in enumerate(week_days):
        cols[idx].markdown(f"<div style='text-align:center; font-weight:bold; color:#475569; padding:4px; background:#f1f5f9; border-radius:4px;'>{day_name}</div>", unsafe_allow_html=True)

    for w_idx, week in enumerate(month_cal):
        is_target_week = (w_idx == selected_week_idx)
        w_cols = st.columns(7)
        
        for day_idx, day_num in enumerate(week):
            with w_cols[day_idx]:
                if day_num == 0:
                    st.markdown("<div style='min-height:90px;'></div>", unsafe_allow_html=True)
                else:
                    cur_date_str = f"{sel_year}-{sel_month:02d}-{day_num:02d}"
                    is_today = (cur_date_str == str(today))
                    date_bg = "#eff6ff" if is_today else "#ffffff"
                    date_border = "#3b82f6" if is_today else "#cbd5e1"

                    date_items = grouped_date_map.get(cur_date_str, [])
                    
                    cell_min_height = "420px" if is_target_week else "110px"
                    content_max_height = "350px" if is_target_week else "70px"
                    
                    badge_html = f"<span style='float:right; font-size:10px; background:#3b82f6; color:white; padding:1px 5px; border-radius:10px;'>{len(date_items)}건</span>" if date_items else ""

                    body_html = ""
                    if date_items:
                        for item in date_items:
                            _, _, img_b64 = parse_note_basal_image(item)
                            plate_n = item.get('plate_name', '')
                            cell_info = item.get('cell_info', '-')
                            basal_media = item.get('basal_media', '-')
                            if not basal_media:
                                basal_media = '-'
                            
                            t_list = item.get('treatments_list', [('기타', '-')])
                            
                            formatted_treatments = []
                            for c_name, c_conc in t_list:
                                if c_conc and c_conc != '-':
                                    formatted_treatments.append(f"{c_name} : {c_conc}")
                                else:
                                    formatted_treatments.append(f"{c_name}")
                            comp_conc_str = " , ".join(formatted_treatments)
                            
                            has_img = "📷" if img_b64 else ""
                            
                            analysis_status = item.get('analysis_status', '미진행')
                            if not analysis_status:
                                analysis_status = '미진행'
                            
                            analysis_badge = ""
                            if analysis_status == "완료":
                                analysis_badge = f'<br><div style="margin-top:3px;"><span style="color:white; background:#10b981; font-size:8px; padding:1px 4px; border-radius:3px;">🔬 분석: {analysis_status}</span></div>'
                            elif analysis_status == "진행중":
                                analysis_badge = f'<br><div style="margin-top:3px;"><span style="color:white; background:#f59e0b; font-size:8px; padding:1px 4px; border-radius:3px;">🔬 분석: {analysis_status}</span></div>'
                            elif analysis_status != "미진행":
                                analysis_badge = f'<br><div style="margin-top:3px;"><span style="color:#64748b; background:#e2e8f0; font-size:8px; padding:1px 4px; border-radius:3px;">🔬 분석: {analysis_status}</span></div>'
                            
                            if is_target_week:
                                body_html += f'<div style="font-size:10px; background:#f8fafc; border-left:3px solid #10b981; padding:5px; margin-bottom:5px; border-radius:3px; color:#334155;"><b>📂 {plate_n}</b> {has_img}<br><span style="color:#059669; font-size:9px;">🧬 세포: {cell_info}</span><br><span style="color:#d97706; font-size:9px;">🧪 배지: {basal_media}</span><br><span style="color:#0284c7; font-size:9px;">💊 {comp_conc_str}</span>{analysis_badge}</div>'
                            else:
                                cell_short = cell_info[:6] if cell_info else "-"
                                basal_short = basal_media[:6] if basal_media != '-' else "-"
                                
                                status_text_short = f" ({analysis_status})" if analysis_status != "미진행" else ""
                                body_html += f'<div style="font-size:10px; background:#f8fafc; border-left:2px solid #10b981; padding:2px 4px; margin-bottom:3px; border-radius:2px; color:#334155;"><b>📂 {plate_n}</b> / {cell_short} / {basal_short} / {comp_conc_str} {has_img}{status_text_short}</div>'
                    else:
                        if is_target_week:
                            body_html = '<div style="font-size:10px; color:#94a3b8; text-align:center; height:100%; display:flex; align-items:center; justify-content:center; min-height:280px;">내역 없음</div>'
                        else:
                            body_html = '<div style="font-size:10px; color:#94a3b8; text-align:center; margin-top:30px;">내역 없음</div>'

                    border_style = f"2px solid #10b981" if is_target_week and date_items else f"1px solid {date_border}"
                    html_content = f'<div style="border: {border_style}; border-radius: 6px; padding: 6px; background-color: {date_bg}; min-height: {cell_min_height}; margin-top: 4px; display: flex; flex-direction: column;"><div style="font-size:12px; font-weight:bold; color:#1e293b; border-bottom:1px solid #f1f5f9; margin-bottom:4px; padding-bottom:2px; flex-shrink: 0;">{day_num}일 {badge_html}</div><div style="max-height: {content_max_height}; overflow-y: auto; padding-right: 2px; flex-grow: 1;">{body_html}</div></div>'
                    
                    st.markdown(html_content, unsafe_allow_html=True)