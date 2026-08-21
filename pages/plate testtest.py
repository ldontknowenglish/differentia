                with edit_main_tab1:
                    all_well_positions = [f"{r}{c}" for r in row_labels for c in range(1, cols + 1)]

                    if "last_dragged_signature" not in st.session_state:
                        st.session_state["last_dragged_signature"] = None

                    dragged_wells = []
                    if plotly_event and "selection" in plotly_event and plotly_event["selection"].get("points"):
                        for pt in plotly_event["selection"]["points"]:
                            if "customdata" in pt:
                                val = pt["customdata"]
                                if isinstance(val, (list, tuple)) and len(val) > 0:
                                    dragged_wells.append(str(val[0]))
                                elif val:
                                    dragged_wells.append(str(val))
                            elif "point_index" in pt:
                                dragged_wells.append(well_names[pt["point_index"]])

                    current_sig = ",".join(sorted(dragged_wells)) if dragged_wells else None
                    if current_sig != st.session_state["last_dragged_signature"]:
                        st.session_state["last_dragged_signature"] = current_sig
                        if dragged_wells:
                            st.session_state["selected_wells_multiselect"] = dragged_wells

                    selected_wells = st.multiselect(
                        "📌 대상 Well 선택 (차트에서 클릭/드래그 시 자동 선택)",
                        options=all_well_positions,
                        key="selected_wells_multiselect"
                    )

                    if selected_wells:
                        # ======================================================================
                        # [CASE 1] 단일 Well 선택 시
                        # ======================================================================
                        if len(selected_wells) == 1:
                            pos = selected_wells[0]
                            st.success(f"🎯 **Well [{pos}]** 가 선택되었습니다.")

                            if pos in well_all_map:
                                items = well_all_map[pos]
                                st.markdown(f"##### 📝 Well [{pos}] 기존 처리 이력 ({len(items)}건)")
                                
                                for item in items:
                                    formatted_cond = format_compound_summary(item['compound_name'], item['concentration'])
                                    with st.expander(f"📅 {item['treatment_date']} | 🧬 {item.get('cell_info', '-')} | 🧪 {formatted_cond}", expanded=True):
                                        try:
                                            def_d = datetime.datetime.strptime(item['treatment_date'], "%Y-%m-%d").date()
                                        except:
                                            def_d = datetime.date.today()

                                        b_media_val, pure_note_val, cur_img_b64 = parse_note_basal_image(item)

                                        r1_c1, r1_c2 = st.columns(2)
                                        with r1_c1:
                                            mod_d = st.date_input("처리 일자", value=def_d, key=f"s_date_{item['id']}")
                                        with r1_c2:
                                            mod_pos = st.text_input("웰 위치", value=item['well_position'], key=f"s_pos_{item['id']}")
                                        
                                        mod_cell = st.text_input("세포 정보", value=item.get('cell_info', ''), key=f"s_cell_{item['id']}")
                                        
                                        cur_analysis = item.get('analysis_status', '미진행')
                                        a_idx = ANALYSIS_OPTIONS.index(cur_analysis) if cur_analysis in ANALYSIS_OPTIONS else 0
                                        
                                        r2_c1, r2_c2 = st.columns(2)
                                        with r2_c1:
                                            mod_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, index=a_idx, key=f"s_analysis_{item['id']}")
                                        
                                        cur_s_analysis = st.session_state.get(f"s_analysis_{item['id']}", cur_analysis)
                                        
                                        with r2_c2:
                                            if cur_s_analysis == "미진행":
                                                b_opts = get_recipe_options(b_media_val)
                                                b_idx = b_opts.index(b_media_val) if b_media_val in b_opts else 0
                                                mod_basal = st.selectbox("Basal Media (레시피 선택)", options=b_opts, index=b_idx, key=f"s_basal_{item['id']}")
                                            else:
                                                mod_basal = "-"
                                                st.text_input("Basal Media", value="-", disabled=True, key=f"s_basal_disabled_{item['id']}")

                                        if cur_s_analysis == "미진행":
                                            st.caption("🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**")
                                            existing_comps = [c.strip() for c in str(item['compound_name']).split(',') if c.strip()]
                                            existing_concs = [c.strip() for c in str(item['concentration']).split(',')] if item['concentration'] else []
                                            
                                            num_s_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=max(1, len(existing_comps)), key=f"s_num_pairs_{item['id']}")
                                            
                                            s_comps, s_concs = [], []
                                            for i in range(0, int(num_s_pairs), 2):
                                                pair_cols = st.columns([2, 1, 2, 1])
                                                
                                                def_c1 = existing_comps[i] if i < len(existing_comps) else ""
                                                def_n1 = existing_concs[i] if i < len(existing_concs) else ""
                                                with pair_cols[0]:
                                                    c1_val = st.text_input(f"물질 #{i+1}", value=def_c1, placeholder="예: VEGF", key=f"s_c_{item['id']}_{i}")
                                                with pair_cols[1]:
                                                    n1_val = st.text_input(f"농도 #{i+1}", value=def_n1, placeholder="예: 50 ng/mL", key=f"s_n_{item['id']}_{i}")
                                                if c1_val.strip():
                                                    s_comps.append(c1_val.strip())
                                                    s_concs.append(n1_val.strip())
                                                    
                                                if i + 1 < int(num_s_pairs):
                                                    def_c2 = existing_comps[i+1] if i+1 < len(existing_comps) else ""
                                                    def_n2 = existing_concs[i+1] if i+1 < len(existing_concs) else ""
                                                    with pair_cols[2]:
                                                        c2_val = st.text_input(f"물질 #{i+2}", value=def_c2, placeholder="예: FGF", key=f"s_c_{item['id']}_{i+1}")
                                                    with pair_cols[3]:
                                                        n2_val = st.text_input(f"농도 #{i+2}", value=def_n2, placeholder="예: 10 ng/mL", key=f"s_n_{item['id']}_{i+1}")
                                                    if c2_val.strip():
                                                        s_comps.append(c2_val.strip())
                                                        s_concs.append(n2_val.strip())
                                            mod_comp = ", ".join(s_comps)
                                            mod_conc = ", ".join(s_concs)
                                        else:
                                            mod_comp = f"분석 진행 ({cur_s_analysis})"
                                            mod_conc = ""
                                            st.info(f"🔬 **{cur_s_analysis}** 분석 모드입니다.")

                                        mod_note = st.text_input("비고 / 상세 조건", value=pure_note_val, key=f"s_note_{item['id']}")

                                        st.caption("📷 **현미경 / 결과 사진 관리**")
                                        if cur_img_b64:
                                            display_image_from_b64(cur_img_b64, caption=f"Well {pos} 등록 사진")
                                            del_img = st.checkbox("🗑️ 저장된 사진 삭제", key=f"chk_del_img_{item['id']}")
                                        else:
                                            del_img = False

                                        new_img_file = st.file_uploader("새 현미경 사진 첨부/교체", type=["png", "jpg", "jpeg"], key=f"file_s_{item['id']}")

                                        b_save, b_del = st.columns(2)
                                        with b_save:
                                            if st.button("💾 저장", key=f"btn_s_save_{item['id']}", type="primary", use_container_width=True):
                                                final_img_b64 = cur_img_b64
                                                if del_img:
                                                    final_img_b64 = None
                                                if new_img_file is not None:
                                                    final_img_b64 = file_to_base64(new_img_file)

                                                comb_note = build_combined_note(mod_basal, mod_note, final_img_b64)
                                                db.update_treatment(
                                                    item['id'], mod_pos.strip().upper(), str(mod_d),
                                                    mod_comp.strip(), mod_conc.strip(), mod_cell.strip(), comb_note, mod_analysis
                                                )
                                                st.toast("수정 사항이 성공적으로 저장되었습니다!", icon="✅")
                                                st.rerun()
                                        with b_del:
                                            if st.button("🗑️ 삭제", key=f"btn_s_del_{item['id']}", type="secondary", use_container_width=True):
                                                db.delete_treatment(item['id'])
                                                st.toast("삭제되었습니다.", icon="🗑️")
                                                st.rerun()

                                with st.expander(f"➕ Well [{pos}]에 추가 처리 및 사진 작성", expanded=False):
                                    r1_c1, r1_c2 = st.columns(2)
                                    with r1_c1:
                                        ex_d = st.date_input("처리 일자", datetime.date.today(), key=f"ex_d_{pos}")
                                    with r1_c2:
                                        st.text_input("웰 위치", value=pos, disabled=True, key=f"ex_pos_{pos}")

                                    ex_cell = st.text_input("세포 정보", placeholder="예: iPSC", key=f"ex_cell_{pos}")
                                    
                                    r2_c1, r2_c2 = st.columns(2)
                                    with r2_c1:
                                        ex_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key=f"ex_analysis_{pos}")
                                    
                                    ex_analysis_val = st.session_state.get(f"ex_analysis_{pos}", "미진행")
                                    
                                    with r2_c2:
                                        if ex_analysis_val == "미진행":
                                            ex_basal = st.selectbox("Basal Media (레시피 선택)", options=get_recipe_options(), key=f"ex_basal_{pos}")
                                        else:
                                            ex_basal = "-"
                                            st.text_input("Basal Media", value="-", disabled=True, key=f"ex_basal_disabled_{pos}")

                                    if ex_analysis_val == "미진행":
                                        st.caption("🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**")
                                        num_ex_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key=f"ex_num_pairs_{pos}")
                                        
                                        ex_comps, ex_concs = [], []
                                        for i in range(0, int(num_ex_pairs), 2):
                                            pair_cols = st.columns([2, 1, 2, 1])
                                            with pair_cols[0]:
                                                c1_val = st.text_input(f"물질 #{i+1}", placeholder="예: VEGF", key=f"ex_c_{pos}_{i}")
                                            with pair_cols[1]:
                                                n1_val = st.text_input(f"농도 #{i+1}", placeholder="예: 50 ng/mL", key=f"ex_n_{pos}_{i}")
                                            if c1_val.strip():
                                                ex_comps.append(c1_val.strip())
                                                ex_concs.append(n1_val.strip())
                                                
                                            if i + 1 < int(num_ex_pairs):
                                                with pair_cols[2]:
                                                    c2_val = st.text_input(f"물질 #{i+2}", placeholder="추가 물질", key=f"ex_c_{pos}_{i+1}")
                                                with pair_cols[3]:
                                                    n2_val = st.text_input(f"농도 #{i+2}", placeholder="추가 농도", key=f"ex_n_{pos}_{i+1}")
                                                if c2_val.strip():
                                                    ex_comps.append(c2_val.strip())
                                                    ex_concs.append(n2_val.strip())
                                        ex_comp_str = ", ".join(ex_comps)
                                        ex_conc_str = ", ".join(ex_concs)
                                    else:
                                        ex_comp_str = f"분석 진행 ({ex_analysis_val})"
                                        ex_conc_str = ""
                                        st.info(f"🔬 **{ex_analysis_val}** 분석 모드입니다.")

                                    ex_note = st.text_input("비고", placeholder="상세 조건", key=f"ex_note_{pos}")
                                    ex_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"ex_file_{pos}")

                                    if st.button(f"💾 Well [{pos}] 추가 저장", key=f"btn_ex_save_{pos}", use_container_width=True, type="primary"):
                                        if ex_analysis_val != "미진행" or ex_comp_str.strip():
                                            img_b64 = file_to_base64(ex_file)
                                            comb_note = build_combined_note(ex_basal, ex_note, img_b64)
                                            db.add_treatment(
                                                selected_plate['id'], pos, str(ex_d),
                                                ex_comp_str, ex_conc_str, ex_cell.strip(), comb_note, ex_analysis
                                            )
                                            st.toast(f"Well [{pos}] 추가 처리가 저장되었습니다!", icon="✅")
                                            st.rerun()
                                        else:
                                            st.error("처리 물질명을 입력해 주세요.")
                            else:
                                st.markdown(f"##### ➕ Well [{pos}] 신규 물질 처리 및 사진 작성")
                                st.caption("선택하신 Well은 현재 미처리 상태입니다.")

                                r1_c1, r1_c2 = st.columns(2)
                                with r1_c1:
                                    e_d = st.date_input("처리 일자", datetime.date.today(), key=f"e_d_{pos}")
                                with r1_c2:
                                    st.text_input("웰 위치", value=pos, disabled=True, key=f"e_pos_{pos}")

                                e_cell = st.text_input("세포/오가노이드 정보", placeholder="예: DE, HIO", key=f"e_cell_{pos}")

                                r2_c1, r2_c2 = st.columns(2)
                                with r2_c1:
                                    e_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key=f"e_analysis_{pos}")
                                with r2_c2:
                                    e_analysis_val = st.session_state.get(f"e_analysis_{pos}", "미진행")
                                    if e_analysis_val == "미진행":
                                        e_basal = st.selectbox("Basal Media (레시피 선택)", options=get_recipe_options(), key=f"e_basal_{pos}")
                                    else:
                                        e_basal = "-"
                                        st.text_input("Basal Media", value="-", disabled=True, key=f"e_basal_disabled_{pos}")

                                if e_analysis_val == "미진행":
                                    st.caption("🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**")
                                    num_e_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key=f"e_num_pairs_{pos}")
                                    
                                    e_comps, e_concs = [], []
                                    for i in range(0, int(num_e_pairs), 2):
                                        pair_cols = st.columns([2, 1, 2, 1])
                                        with pair_cols[0]:
                                            c_val = st.text_input(f"물질 #{i+1}", placeholder="예: VEGF", key=f"e_c_{pos}_{i}")
                                        with pair_cols[1]:
                                            n_val = st.text_input(f"농도 #{i+1}", placeholder="예: 50 ng/mL", key=f"e_n_{pos}_{i}")
                                        if c_val.strip():
                                            e_comps.append(c_val.strip())
                                            e_concs.append(n_val.strip())
                                            
                                        if i + 1 < int(num_e_pairs):
                                            with pair_cols[2]:
                                                c2_val = st.text_input(f"물질 #{i+2}", placeholder="추가 물질", key=f"e_c_{pos}_{i+1}")
                                            with pair_cols[3]:
                                                n2_val = st.text_input(f"농도 #{i+2}", placeholder="추가 농도", key=f"e_n_{pos}_{i+1}")
                                            if c2_val.strip():
                                                e_comps.append(c2_val.strip())
                                                e_concs.append(n2_val.strip())
                                else:
                                    e_basal = "-"
                                    e_comps = [f"분석 진행 ({e_analysis_val})"]
                                    e_concs = [""]
                                    st.info(f"🔬 **{e_analysis_val}** 분석 모드입니다.")

                                e_note = st.text_input("비고 / 상세 조건", placeholder="예: Daily media change", key=f"e_note_{pos}")
                                e_file = st.file_uploader("📷 현미경 사진 첨부 (선택)", type=["png", "jpg", "jpeg"], key=f"e_file_{pos}")

                                if st.button(f"💾 Well [{pos}] 처리 저장", key=f"btn_empty_save_{pos}", use_container_width=True, type="primary"):
                                    if e_comps:
                                        comb_comp = ", ".join(e_comps)
                                        comb_conc = ", ".join(e_concs)
                                        img_b64 = file_to_base64(e_file)
                                        comb_note = build_combined_note(e_basal, e_note, img_b64)
                                        
                                        db.add_treatment(
                                            selected_plate['id'], pos, str(e_d),
                                            comb_comp, comb_conc, e_cell.strip(), comb_note, e_analysis
                                        )
                                        st.success(f"✅ Well [{pos}] 처리가 저장되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error("최소 하나 이상의 물질명을 입력해 주세요.")

                        # ======================================================================
                        # [CASE 2] 다중 Well 선택 시 (2개 이상)
                        # ======================================================================
                        else:
                            st.info(f"🎯 총 **{len(selected_wells)}개**의 Well이 선택되었습니다.")

                            # 1) 선택된 Well들의 현재 실험 조건 요약 표시
                            st.markdown("##### 📋 선택된 Well 목록 및 현재 조건 요약")
                            
                            batch_summary = []
                            for pos in selected_wells:
                                if pos in well_last_map:
                                    item = well_last_map[pos]
                                    basal_txt = get_basal_media(item)
                                    cond_txt = format_compound_summary(item.get('compound_name', ''), item.get('concentration', ''))
                                    cell_txt = item.get('cell_info', '-') or '-'
                                    analysis_txt = item.get('analysis_status', '미진행') or '미진행'
                                    date_txt = item.get('treatment_date', '-')
                                    has_img = "📷 유" if extract_image_data(item) else "무"
                                else:
                                    basal_txt, cond_txt, cell_txt, analysis_txt, date_txt, has_img = "-", "미처리 (Empty)", "-", "-", "-", "무"

                                batch_summary.append({
                                    "Well": pos,
                                    "최신일자": date_txt,
                                    "세포 정보": cell_txt,
                                    "분석 상태": analysis_txt,
                                    "Basal Media": basal_txt,
                                    "처리 조건 (물질 및 농도)": cond_txt,
                                    "사진": has_img
                                })

                            st.dataframe(pd.DataFrame(batch_summary), use_container_width=True, hide_index=True)

                            # 2) 선택한 Well 일괄 편집 Form
                            with st.expander("⚡ 선택한 Well 정보 일괄 입력 / 등록", expanded=True):
                                st.caption("💡 아래에서 입력한 조건이 선택된 모든 Well에 **동일하게 일괄 적용/신규 등록**됩니다.")

                                b_d = st.date_input("처리 일자", datetime.date.today(), key="b_date_input")
                                b_cell = st.text_input("세포/오가노이드 정보", placeholder="예: DE, HIO (선택)", key="b_cell_input")

                                bc1, bc2 = st.columns(2)
                                with bc1:
                                    b_analysis = st.selectbox("🔬 분석진행 상태", options=ANALYSIS_OPTIONS, key="b_analysis_select")
                                with bc2:
                                    b_analysis_val = st.session_state.get("b_analysis_select", "미진행")
                                    if b_analysis_val == "미진행":
                                        b_basal = st.selectbox("Basal Media (레시피 선택)", options=get_recipe_options(), key="b_basal_select")
                                    else:
                                        b_basal = "-"
                                        st.text_input("Basal Media", value="-", disabled=True, key="b_basal_disabled")

                                if b_analysis_val == "미진행":
                                    st.caption("🧪 **처리 물질 및 농도 (2쌍씩 같은 열 관리)**")
                                    num_b_pairs = st.number_input("입력할 물질 쌍 개수", min_value=1, max_value=10, value=2, key="b_num_pairs_input")

                                    b_comps, b_concs = [], []
                                    for i in range(0, int(num_b_pairs), 2):
                                        pair_cols = st.columns([2, 1, 2, 1])
                                        with pair_cols[0]:
                                            c_val = st.text_input(f"물질 #{i+1}", placeholder="예: VEGF", key=f"b_c_{i}")
                                        with pair_cols[1]:
                                            n_val = st.text_input(f"농도 #{i+1}", placeholder="예: 50 ng/mL", key=f"b_n_{i}")
                                        if c_val.strip():
                                            b_comps.append(c_val.strip())
                                            b_concs.append(n_val.strip())

                                        if i + 1 < int(num_b_pairs):
                                            with pair_cols[2]:
                                                c2_val = st.text_input(f"물질 #{i+2}", placeholder="추가 물질", key=f"b_c_{i+1}")
                                            with pair_cols[3]:
                                                n2_val = st.text_input(f"농도 #{i+2}", placeholder="추가 농도", key=f"b_n_{i+1}")
                                            if c2_val.strip():
                                                b_comps.append(c2_val.strip())
                                                b_concs.append(n2_val.strip())
                                    
                                    comb_b_comp = ", ".join(b_comps)
                                    comb_b_conc = ", ".join(b_concs)
                                else:
                                    b_basal = "-"
                                    comb_b_comp = f"분석 진행 ({b_analysis_val})"
                                    comb_b_conc = ""
                                    st.info(f"🔬 **{b_analysis_val}** 분석 모드로 일괄 적용됩니다.")

                                b_note = st.text_input("비고 / 상세 조건", placeholder="예: 일괄 매체 교체", key="b_note_input")
                                b_file = st.file_uploader("📷 현미경 사진 일괄 첨부 (선택)", type=["png", "jpg", "jpeg"], key="b_file_input")

                                if st.button(f"💾 {len(selected_wells)}개 Well 일괄 저장", key="btn_batch_save_all", type="primary", use_container_width=True):
                                    if b_analysis_val != "미진행" or comb_b_comp.strip():
                                        img_b64 = file_to_base64(b_file)
                                        comb_note = build_combined_note(b_basal, b_note, img_b64)

                                        for pos in selected_wells:
                                            db.add_treatment(
                                                selected_plate['id'], pos, str(b_d),
                                                comb_b_comp, comb_b_conc, b_cell.strip(), comb_note, b_analysis
                                            )
                                        st.success(f"✅ {len(selected_wells)}개 Well에 처리가 일괄 저장되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error("처리 물질명을 입력하거나 분석진행 상태를 선택해 주세요.")

                            # 3) 선택한 Well 일괄 삭제
                            with st.expander("🗑️ 선택된 Well 이력 일괄 삭제", expanded=False):
                                st.warning("⚠️ 지정한 Well에 등록된 모든 처리 이력이 일괄 삭제됩니다.")
                                wells_to_delete = st.multiselect(
                                    "삭제할 Well 선택",
                                    options=selected_wells,
                                    default=selected_wells,
                                    key="batch_delete_wells_select"
                                )
                                if st.button("🚨 선택한 Well의 모든 이력 삭제", key="btn_batch_delete_wells", type="secondary", use_container_width=True):
                                    if wells_to_delete:
                                        for pos in wells_to_delete:
                                            if hasattr(db, 'delete_well_treatments'):
                                                db.delete_well_treatments(selected_plate['id'], pos)
                                            elif hasattr(db, 'delete_treatment'):
                                                for item in well_all_map.get(pos, []):
                                                    db.delete_treatment(item['id'])
                                        st.success(f"✅ {len(wells_to_delete)}개 Well의 이력이 일괄 삭제되었습니다.")
                                        st.rerun()
                                    else:
                                        st.error("삭제할 Well을 선택해 주세요.")
