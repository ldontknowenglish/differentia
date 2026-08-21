                                            with pair_cols[2]:
                                                c_val2 = st.text_input(f"물질 #{i+2}", placeholder="추가 물질", key=f"e_c_{pos}_{i+1}")
                                            with pair_cols[3]:
                                                n_val2 = st.text_input(f"농도 #{i+2}", placeholder="추가 농도", key=f"e_n_{pos}_{i+1}")
                                            if c_val2.strip():
                                                e_comps.append(c_val2.strip())
                                                e_concs.append(n_val2.strip())
                                    e_comp_str = ", ".join(e_comps)
                                    e_conc_str = ", ".join(e_concs)
                                else:
                                    e_comp_str = f"분석 진행 ({e_analysis_val})"
                                    e_conc_str = ""
                                    st.info(f"🔬 **{e_analysis_val}** 분석 모드입니다.")

                                e_note = st.text_input("비고", placeholder="상세 조건", key=f"e_note_{pos}")
                                e_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"e_file_{pos}")

                                if st.button("💾 저장", key=f"btn_e_save_{pos}", use_container_width=True, type="primary"):
                                    if e_analysis_val != "미진행" or e_comp_str.strip():
                                        img_b64 = file_to_base64(e_file)
                                        comb_note = build_combined_note(e_basal, e_note, img_b64)
                                        db.add_treatment(
                                            selected_plate['id'], pos, str(e_d),
                                            e_comp_str, e_conc_str, e_cell.strip(), comb_note, e_analysis
                                        )
                                        st.toast(f"Well [{pos}] 신규 처리가 저장되었습니다!", icon="✅")
                                        st.rerun()
                                    else:
                                        st.error("처리 물질명을 입력해 주세요.")
                        else:
                            st.info(f"🎯 **{len(selected_wells)}개의 Well**이 선택되었습니다. 다중 선택 모드입니다.")
                            with st.form("multi_edit_form", clear_on_submit=True):
                                st.markdown("##### ➕ 선택된 모든 Well에 동일한 처리 추가")
                                m_d = st.date_input("처리 일자", datetime.date.today())
                                m_cell = st.text_input("세포/오가노이드 정보", placeholder="예: iPSC")
                                
                                m_r2_c1, m_r2_c2 = st.columns(2)
                                with m_r2_c1:
                                    m_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS)
                                with m_r2_c2:
                                    m_basal_ph = st.empty()
                                    m_basal = "-"
                                    
                                st.caption("🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**")
                                num_m_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2)
                                
                                m_comps, m_concs = [], []
                                for i in range(0, int(num_m_pairs), 2):
                                    pair_cols = st.columns([2, 1, 2, 1])
                                    with pair_cols[0]:
                                        c_val = st.text_input(f"물질 #{i+1}", placeholder="예: VEGF", key=f"m_c_{i}")
                                    with pair_cols[1]:
                                        n_val = st.text_input(f"농도 #{i+1}", placeholder="예: 50 ng/mL", key=f"m_n_{i}")
                                    if c_val.strip():
                                        m_comps.append(c_val.strip())
                                        m_concs.append(n_val.strip())
                                        
                                    if i + 1 < int(num_m_pairs):
                                        with pair_cols[2]:
                                            c_val2 = st.text_input(f"물질 #{i+2}", placeholder="추가 물질", key=f"m_c_{i+1}")
                                        with pair_cols[3]:
                                            n_val2 = st.text_input(f"농도 #{i+2}", placeholder="추가 농도", key=f"m_n_{i+1}")
                                        if c_val2.strip():
                                            m_comps.append(c_val2.strip())
                                            m_concs.append(n_val2.strip())
                                            
                                m_comp_str = ", ".join(m_comps)
                                m_conc_str = ", ".join(m_concs)
                                m_note = st.text_input("비고", placeholder="공통 비고")
                                m_file = st.file_uploader("📷 공통 사진 첨부 (선택)", type=["png", "jpg", "jpeg"])
                                
                                m_submit = st.form_submit_button("일괄 추가 저장", use_container_width=True)
                                
                                if m_submit:
                                    img_b64 = file_to_base64(m_file)
                                    for pos in selected_wells:
                                        comb_note = build_combined_note(m_basal, m_note, img_b64)
                                        db.add_treatment(
                                            selected_plate['id'], pos, str(m_d),
                                            m_comp_str, m_conc_str, m_cell.strip(), comb_note, m_analysis
                                        )
                                    st.success(f"{len(selected_wells)}개의 Well에 처리가 일괄 추가되었습니다!")
                                    st.rerun()

                    else:
                        st.info("👈 왼쪽 차트에서 편집할 Well을 선택하세요. (클릭 또는 박스/올가미 선택)")

                with edit_main_tab2:
                    st.markdown(f"##### 📊 {selected_plate['name']} 요약")
                    if not treatments:
                        st.info("데이터가 없습니다.")
                    else:
                        df = pd.DataFrame(treatments)
                        df['treatment_date'] = pd.to_datetime(df['treatment_date']).dt.strftime('%Y-%m-%d')
                        if selected_date != "전체 날짜 (최신 상태)":
                            df = df[df['treatment_date'] == selected_date]
                        
                        if df.empty:
                            st.warning(f"{selected_date}에 해당하는 데이터가 없습니다.")
                        else:
                            df_latest = df.sort_values('treatment_date', ascending=False).groupby('well_position').first().reset_index()
                            df_latest['row'] = df_latest['well_position'].apply(lambda x: x[0])
                            df_latest['col'] = df_latest['well_position'].apply(lambda x: int(x[1:]))
                            
                            pivot = df_latest.pivot(index='row', columns='col', values='cell_info').fillna('-')
                            # Ensure all rows and cols are present in pivot table
                            for r in row_labels:
                                if r not in pivot.index:
                                    pivot.loc[r] = '-'
                            for c in range(1, cols + 1):
                                if c not in pivot.columns:
                                    pivot[c] = '-'
                            pivot = pivot.sort_index().sort_index(axis=1)
                            
                            st.dataframe(pivot, use_container_width=True)

        # ======================================================================
        # [TAB 2] 계통도 (Lineage Tree)
        # ======================================================================
        with tab_tree:
            st.markdown("### 🌳 세포 분화 계통도 (Lineage Tree)")
            st.caption("각 Well에서 세포(Cell Info)가 날짜 흐름에 따라 어떻게 변화했는지 추적합니다.")
            
            if not treatments:
                st.info("계통도를 생성할 처리 데이터가 없습니다.")
            else:
                dot_source = generate_dynamic_lineage_dot(treatments)
                if dot_source:
                    st.graphviz_chart(dot_source, use_container_width=True)
                else:
                    st.warning("계통도를 구성할 유효한 세포 정보(Cell Info) 변경 내역이 없습니다.")

        # ======================================================================
        # [TAB 3] 테이블 보기 & 관리
        # ======================================================================
        with tab_treat:
            st.markdown("### 📝 처리 내역 상세 테이블")
            
            if not treatments:
                st.info("등록된 처리 내역이 없습니다.")
            else:
                df = pd.DataFrame(treatments)
                df = df.sort_values(by=['treatment_date', 'well_position'], ascending=[False, True]).reset_index(drop=True)
                
                # 테이블 표시를 위해 컬럼 재구성 및 정제
                display_df = pd.DataFrame()
                display_df['일자'] = df['treatment_date']
                display_df['Well'] = df['well_position']
                display_df['세포 정보'] = df['cell_info']
                display_df['분석 진행'] = df['analysis_status'].fillna('미진행')
                
                # Basal Media, 복합 물질 포맷팅, Note(이미지 제외)
                basal_list = []
                comp_list = []
                note_list = []
                img_list = []
                
                for idx, row in df.iterrows():
                    b, n, i = parse_note_basal_image(row)
                    basal_list.append(b)
                    note_list.append(n)
                    img_list.append("📷 있음" if i else "없음")
                    
                    if row.get('analysis_status') and row['analysis_status'] != '미진행':
                        comp_list.append(f"[{row['analysis_status']}]")
                    else:
                        comp_list.append(format_compound_summary(row['compound_name'], row['concentration']))
                        
                display_df['Basal Media'] = basal_list
                display_df['처리 조건 (물질 농도)'] = comp_list
                display_df['비고'] = note_list
                display_df['사진 첨부'] = img_list
                
                st.dataframe(display_df, use_container_width=True)
                
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 CSV 데이터 다운로드",
                    data=csv,
                    file_name=f"{selected_plate['name']}_treatments.csv",
                    mime="text/csv",
                )

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
