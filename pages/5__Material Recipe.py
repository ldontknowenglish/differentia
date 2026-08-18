# ---------------------------------------------------------
# TAB 2: 레시피 조회 및 관리
# ---------------------------------------------------------
with tab2:
    st.subheader("등록된 Material Recipe 목록")
    
    recipes_df = db.get_all_recipes()
    
    if not recipes_df:
        st.info("등록된 레시피가 없습니다. '새 레시피 등록' 탭에서 생성해 주세요.")
    else:
        # DB 내 카테고리 필터
        all_categories = ["전체보기"] + sorted(list(set([r.get('category', '미분류') for r in recipes_df if r.get('category')])))
        selected_filter = st.selectbox("🏷️ 카테고리별 필터링", all_categories, key="recipe_filter_box")
        
        st.markdown("---")
        
        filtered_recipes = recipes_df if selected_filter == "전체보기" else [r for r in recipes_df if r.get('category') == selected_filter]
        
        if not filtered_recipes:
            st.warning(f"'{selected_filter}' 카테고리에 해당하는 레시피가 없습니다.")
        
        for row in filtered_recipes:
            recipe_id = row['recipe_id']
            cat_tag = row.get('category') or '미분류'
            prep_date = row.get('prepared_date') or str(row.get('created_at', ''))[:10]
            description = row.get('description') or "설명 없음"
            
            expander_title = f"🧪 [{cat_tag}] **{row['recipe_name']}** (📅 조제일: {prep_date}) - {description}"
            
            with st.expander(expander_title):
                # 수정 모드 상태 키 관리 (세션 스테이트 활용)
                edit_mode_key = f"edit_mode_{recipe_id}"
                if edit_mode_key not in st.session_state:
                    st.session_state[edit_mode_key] = False

                # ---------------------------------------------------------
                # [모드 A] 일반 조회 모드
                # ---------------------------------------------------------
                if not st.session_state[edit_mode_key]:
                    details_df = db.get_recipe_details(recipe_id, as_df=True)
                    
                    st.markdown(f"**카테고리:** `{cat_tag}` | **조제일:** `{prep_date}`")
                    st.markdown("**구성 물질 목록:**")
                    
                    if not details_df.empty:
                        st.dataframe(
                            details_df.rename(columns={
                                "material_name": "물질명 (Material)",
                                "manufacturer": "제조사 (Manufacturer)",
                                "cat_no": "Catalog No.",
                                "amount": "용량/농도"
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.caption("등록된 물질 정보가 없습니다.")
                    
                    st.markdown("")
                    # 버튼 레이아웃 (수정 / 삭제)
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        if st.button("✏️ 레시피 수정하기", key=f"btn_turn_edit_{recipe_id}", use_container_width=True):
                            st.session_state[edit_mode_key] = True
                            st.rerun()
                    with col_btn2:
                        if st.button(f"🗑️ '{row['recipe_name']}' 레시피 삭제", key=f"delete_recipe_{recipe_id}", use_container_width=True):
                            db.delete_recipe(recipe_id)
                            st.warning("레시피가 휴지통으로 이동되었습니다.")
                            st.rerun()

                # ---------------------------------------------------------
                # [모드 B] 수정 모드
                # ---------------------------------------------------------
                else:
                    st.markdown("### ✏️ 레시피 수정 모드")
                    
                    # 1. 기본 정보 수정 입력창
                    edit_name = st.text_input("레시피/배지 이름", value=row['recipe_name'], key=f"edit_name_{recipe_id}")
                    
                    # 카테고리 옵션 구성
                    cat_options = st.session_state.custom_categories if st.session_state.custom_categories else ["미분류"]
                    current_cat_idx = cat_options.index(cat_tag) if cat_tag in cat_options else 0
                    edit_category = st.selectbox("분류 (카테고리)", cat_options, index=current_cat_idx, key=f"edit_cat_{recipe_id}")
                    
                    # 조제 날짜 파싱
                    try:
                        parsed_date_obj = datetime.datetime.strptime(prep_date, "%Y-%m-%d").date()
                    except:
                        parsed_date_obj = datetime.date.today()
                    edit_date = st.date_input("조제/만든 날짜", value=parsed_date_obj, key=f"edit_date_{recipe_id}")
                    
                    edit_desc = st.text_input("설명 / 비고", value=row.get('description', ''), key=f"edit_desc_{recipe_id}")
                    
                    st.markdown("---")
                    st.markdown("**구성 물질 및 용량 수정**")
                    
                    # 기존 상세 성분 데이터를 세션이나 임시 키로 로드
                    edit_items_key = f"edit_items_{recipe_id}"
                    if edit_items_key not in st.session_state:
                        raw_details = db.get_recipe_details(recipe_id, as_df=False)
                        st.session_state[edit_items_key] = [
                            {
                                "material_name": d.get("material_name", ""),
                                "manufacturer": d.get("manufacturer", ""),
                                "cat_no": d.get("cat_no", ""),
                                "amount": d.get("amount", "")
                            } for d in raw_details
                        ]
                    
                    # 수정 중인 성분 리스트 렌더링
                    updated_edit_items = []
                    for e_idx, e_item in enumerate(st.session_state[edit_items_key]):
                        ec1, ec2, ec3, ec4, ec5 = st.columns([2.5, 2, 2, 2, 0.8])
                        with ec1:
                            e_mat = st.text_input(f"물질명 #{e_idx+1}", value=e_item.get("material_name", ""), key=f"edit_mat_{recipe_id}_{e_idx}")
                        with ec2:
                            e_mfg = st.text_input(f"제조사 #{e_idx+1}", value=e_item.get("manufacturer", ""), key=f"edit_mfg_{recipe_id}_{e_idx}")
                        with ec3:
                            e_cat = st.text_input(f"Cat No. #{e_idx+1}", value=e_item.get("cat_no", ""), key=f"edit_catnum_{recipe_id}_{e_idx}")
                        with ec4:
                            e_amt = st.text_input(f"용량/농도 #{e_idx+1}", value=e_item.get("amount", ""), key=f"edit_amt_{recipe_id}_{e_idx}")
                        with ec5:
                            st.write(" ")
                            st.write(" ")
                            if st.button("🗑️", key=f"edit_del_item_{recipe_id}_{e_idx}"):
                                st.session_state[edit_items_key].pop(e_idx)
                                st.rerun()
                                
                        if e_mat:
                            updated_edit_items.append({
                                "material_name": e_mat,
                                "manufacturer": e_mfg,
                                "cat_no": e_cat,
                                "amount": e_amt
                            })
                    
                    # 성분 행 추가 버튼
                    if st.button("➕ 물질 성분 추가", key=f"edit_add_row_{recipe_id}"):
                        st.session_state[edit_items_key].append({"material_name": "", "manufacturer": "", "cat_no": "", "amount": ""})
                        st.rerun()
                        
                    st.markdown("---")
                    col_save_mod, col_cancel_mod = st.columns([1, 1])
                    with col_save_mod:
                        if st.button("💾 수정 사항 저장", type="primary", key=f"btn_save_edit_{recipe_id}", use_container_width=True):
                            if not edit_name:
                                st.error("레시피 이름을 입력해 주세요.")
                            elif not updated_edit_items:
                                st.error("최소 하나 이상의 구성 물질을 입력해 주세요.")
                            else:
                                # 1. 기존 레시피 아이템들을 모두 삭제 후 새로 삽입하거나 업데이트 처리
                                # 여기서는 깔끔하게 기존 recipe_items를 삭제하고 새로 추가하는 방식을 쓰기 위해 DB 함수 활용 또는 직접 쿼리 실행
                                conn = db.get_connection()
                                cursor = conn.cursor()
                                # 메인 레시피 정보 업데이트
                                cursor.execute("""
                                    UPDATE material_recipes 
                                    SET recipe_name = ?, category = ?, prepared_date = ?, description = ?
                                    WHERE recipe_id = ?
                                """, (edit_name, edit_category, edit_date.strftime("%Y-%m-%d"), edit_desc, recipe_id))
                                
                                # 기존 상세 아이템 삭제 후 새 아이템 재삽입
                                cursor.execute("DELETE FROM recipe_items WHERE recipe_id = ?", (recipe_id,))
                                for item in updated_edit_items:
                                    cursor.execute("""
                                        INSERT INTO recipe_items (recipe_id, material_name, manufacturer, cat_no, amount) 
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (
                                        recipe_id, 
                                        item.get('material_name', ''), 
                                        item.get('manufacturer', ''), 
                                        item.get('cat_no', ''), 
                                        item.get('amount', '')
                                    ))
                                conn.commit()
                                conn.close()
                                
                                # 세션 상태 청소 및 모드 복귀
                                del st.session_state[edit_items_key]
                                st.session_state[edit_mode_key] = False
                                st.success("레시피가 성공적으로 수정되었습니다!")
                                st.rerun()
                                
                    with col_cancel_mod:
                        if st.button("❌ 취소", key=f"btn_cancel_edit_{recipe_id}", use_container_width=True):
                            if edit_items_key in st.session_state:
                                del st.session_state[edit_items_key]
                            st.session_state[edit_mode_key] = False
                            st.rerun()
