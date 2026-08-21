

# ======================================================================
# [TAB 4] 사진 비교
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
                                    st.caption(f"🧪 {format_compound_summary(item['compound_name'], item['concentration'])}")
                                    if n: st.caption(f"📝 {n}")
                                    
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
                                    st.caption(f"🧪 {format_compound_summary(item['compound_name'], item['concentration'])}")
