import datetime
import pandas as pd
import streamlit as st
import db
import style

st.set_page_config(page_title="Material Recipe", page_icon="🧪", layout="wide")

# 앱 스타일 및 DB 초기화
if hasattr(style, 'apply_custom_style'):
    style.apply_custom_style()

if hasattr(db, 'init_recipe_db'):
    db.init_recipe_db()

st.title("🧪 Material Recipe (물질/배지 레시피 관리)")
st.caption("각종 배지 및 시약 조제법과 구성 물질의 Catalog No.(Cat No.), 제조사를 관리합니다.")

# ---------------------------------------------------------
# 세션 스테이트: 카테고리 항목 동적 관리
# ---------------------------------------------------------
DEFAULT_CATEGORIES = ["공통 시약/버퍼"]

if "custom_categories" not in st.session_state:
    st.session_state.custom_categories = DEFAULT_CATEGORIES.copy()

# DB에 저장되어 있는 기존 카테고리 목록 병합
if hasattr(db, 'get_all_categories'):
    db_cats = db.get_all_categories()
    for cat in db_cats:
        if cat and cat not in st.session_state.custom_categories:
            st.session_state.custom_categories.append(cat)

# DB 내 기존 작성 물질/제조사/Cat No. 마스터 옵션 로드
def get_master_item_options():
    mat_set, mfg_set, cat_set = set(), set(), set()
    if hasattr(db, 'get_all_recipes'):
        recipes = db.get_all_recipes()
        for r in recipes:
            details = db.get_recipe_details(r['recipe_id'], as_df=False)
            for d in details:
                if d.get("material_name"): mat_set.add(d.get("material_name").strip())
                if d.get("manufacturer"): mfg_set.add(d.get("manufacturer").strip())
                if d.get("cat_no"): cat_set.add(d.get("cat_no").strip())
    return sorted(list(mat_set)), sorted(list(mfg_set)), sorted(list(cat_set))

master_mats, master_mfgs, master_cats = get_master_item_options()

# 💡 위젯 세션 키 완벽 제거 함수
def clear_all_recipe_widget_keys():
    keys_to_del = [
        k for k in st.session_state.keys() 
        if k.startswith(("mat_sel_key_", "mat_txt_key_", "mfg_sel_key_", "mfg_txt_key_", "cat_sel_key_", "cat_txt_key_", "amt_txt_key_"))
    ]
    for k in keys_to_del:
        del st.session_state[k]

tab1, tab2 = st.tabs(["➕ 새 레시피 등록", "🔍 레시피 조회 및 관리"])

# ---------------------------------------------------------
# TAB 1: 새 레시피 등록
# ---------------------------------------------------------
with tab1:
    st.subheader("새로운 Material Recipe 작성")
    
    all_existing_recipes = db.get_all_recipes()
    
    with st.expander("📋 **기존 작성 내역 불러오기 (템플릿 활용)**", expanded=False):
        if not all_existing_recipes:
            st.info("등록된 기존 레시피가 없습니다.")
        else:
            col_load1, col_load2 = st.columns([3, 1])
            with col_load1:
                recipe_options = {
                    f"[{r.get('category', '미분류')}] {r['recipe_name']} (조제일: {r.get('prepared_date', '')})": r['recipe_id']
                    for r in all_existing_recipes
                }
                selected_recipe_label = st.selectbox("불러올 기존 레시피 선택", list(recipe_options.keys()), key="select_existing_recipe_preset")
            
            with col_load2:
                st.write(" ")
                st.write(" ")
                if st.button("📥 레시피 가져오기", use_container_width=True, type="secondary"):
                    selected_id = recipe_options[selected_recipe_label]
                    fetched_details = db.get_recipe_details(selected_id, as_df=False)
                    
                    if fetched_details:
                        # 1. 이전 위젯 키들 완전 삭제
                        clear_all_recipe_widget_keys()
                        
                        # 2. 가져온 데이터로 목록 덮어쓰기 (기존 예시 완벽 제거)
                        st.session_state.recipe_items = [
                            {
                                "material_name": item.get("material_name", ""),
                                "manufacturer": item.get("manufacturer", ""),
                                "cat_no": item.get("cat_no", ""),
                                "amount": item.get("amount", "")
                            }
                            for item in fetched_details
                        ]
                        st.success(f"'{selected_recipe_label}' 레시피를 가져왔습니다!")
                        st.rerun()

    col1, col2, col3 = st.columns([2, 1.5, 1.5])
    with col1:
        recipe_name = st.text_input("레시피/배지 이름", placeholder="예: DE basal media")
    
    with col2:
        cat_options = st.session_state.custom_categories if st.session_state.custom_categories else ["미분류"]
        category = st.selectbox("분류 (카테고리)", cat_options, key="select_recipe_cat")

    with col3:
        prepared_date = st.date_input("조제/만든 날짜", value=datetime.date.today())

    description = st.text_input("설명 / 비고", placeholder="예: Definitive Endoderm 유도용 기초 배지 (10일 보관 가능)")

    with st.expander("⚙️ 카테고리 드롭다운 목록 관리 (추가 / 삭제)"):
        mgt_col1, mgt_col2 = st.columns([1, 1])
        
        with mgt_col1:
            st.markdown("**➕ 카테고리 추가**")
            c_add1, c_add2 = st.columns([3, 1])
            with c_add1:
                new_cat_name = st.text_input("추가할 카테고리명", key="expander_add_cat_input", label_visibility="collapsed", placeholder="새 카테고리명 입력")
            with c_add2:
                if st.button("추가", key="btn_add_cat"):
                    clean_cat = new_cat_name.strip()
                    if clean_cat and clean_cat not in st.session_state.custom_categories:
                        st.session_state.custom_categories.append(clean_cat)
                        st.success(f"'{clean_cat}' 추가됨")
                        st.rerun()
                    elif clean_cat in st.session_state.custom_categories:
                        st.warning("이미 존재합니다.")

        with mgt_col2:
            st.markdown("**🗑️ 카테고리 삭제**")
            if st.session_state.custom_categories:
                c_del1, c_del2 = st.columns([3, 1])
                with c_del1:
                    target_del_cat = st.selectbox("삭제할 카테고리", st.session_state.custom_categories, key="expander_del_cat_select", label_visibility="collapsed")
                with c_del2:
                    if st.button("삭제", key="btn_del_cat"):
                        st.session_state.custom_categories.remove(target_del_cat)
                        st.warning(f"'{target_del_cat}' 삭제됨")
                        st.rerun()
            else:
                st.caption("삭제할 카테고리가 없습니다.")

    st.markdown("---")
    st.write("##### 🧪 구성 물질, 제조사 및 Cat No. 설정")
    st.caption("💡 **추천 검색 기능**: 드롭다운 클릭 후 단어(예: `RP`)를 타이핑하면 관련 항목이 검색되며, 목록에 없을 경우 `➕ 직접 입력`을 선택해 작성할 수 있습니다.")

    # 💡 디폴트 예시 데이터를 제거하고 기본 1개 빈 항목만 생성되도록 변경
    if "recipe_items" not in st.session_state or not st.session_state.recipe_items:
        st.session_state.recipe_items = [
            {"material_name": "", "manufacturer": "", "cat_no": "", "amount": ""}
        ]

    # 테이블 헤더
    th1, th2, th3, th4, th5 = st.columns([2.5, 2.0, 2.0, 1.8, 0.5])
    th1.caption("**물질명 (Material)**")
    th2.caption("**제조사 (Manufacturer)**")
    th3.caption("**Cat No.**")
    th4.caption("**용량 / 농도**")
    th5.caption("")

    updated_items = []
    DIRECT_INPUT_OPT = "➕ 직접 입력 (목록에 없음)"

    for idx, item in enumerate(st.session_state.recipe_items):
        c1, c2, c3, c4, c5 = st.columns([2.5, 2.0, 2.0, 1.8, 0.5])
        
        # 1. 물질명 (Material Name)
        with c1:
            m_options = [DIRECT_INPUT_OPT] + master_mats
            cur_mat = item.get("material_name", "")
            mat_idx = m_options.index(cur_mat) if cur_mat in m_options else 0
            
            selected_mat = st.selectbox(
                f"mat_sel_{idx}",
                options=m_options,
                index=mat_idx,
                key=f"mat_sel_key_{idx}",
                label_visibility="collapsed"
            )
            
            if selected_mat == DIRECT_INPUT_OPT:
                mat_val = st.text_input(
                    f"mat_txt_{idx}",
                    value="" if cur_mat in master_mats else cur_mat,
                    key=f"mat_txt_key_{idx}",
                    label_visibility="collapsed",
                    placeholder="물질명 직접 입력"
                )
            else:
                mat_val = selected_mat

        # 2. 제조사 (Manufacturer)
        with c2:
            mfg_options = [DIRECT_INPUT_OPT] + master_mfgs
            cur_mfg = item.get("manufacturer", "")
            mfg_idx = mfg_options.index(cur_mfg) if cur_mfg in mfg_options else 0
            
            selected_mfg = st.selectbox(
                f"mfg_sel_{idx}",
                options=mfg_options,
                index=mfg_idx,
                key=f"mfg_sel_key_{idx}",
                label_visibility="collapsed"
            )
            
            if selected_mfg == DIRECT_INPUT_OPT:
                mfg_val = st.text_input(
                    f"mfg_txt_{idx}",
                    value="" if cur_mfg in master_mfgs else cur_mfg,
                    key=f"mfg_txt_key_{idx}",
                    label_visibility="collapsed",
                    placeholder="제조사 직접 입력"
                )
            else:
                mfg_val = selected_mfg

        # 3. Cat No.
        with c3:
            cat_options_list = [DIRECT_INPUT_OPT] + master_cats
            cur_cat = item.get("cat_no", "")
            cat_idx = cat_options_list.index(cur_cat) if cur_cat in cat_options_list else 0
            
            selected_cat = st.selectbox(
                f"cat_sel_{idx}",
                options=cat_options_list,
                index=cat_idx,
                key=f"cat_sel_key_{idx}",
                label_visibility="collapsed"
            )
            
            if selected_cat == DIRECT_INPUT_OPT:
                cat_val = st.text_input(
                    f"cat_txt_{idx}",
                    value="" if cur_cat in master_cats else cur_cat,
                    key=f"cat_txt_key_{idx}",
                    label_visibility="collapsed",
                    placeholder="Cat No. 직접 입력"
                )
            else:
                cat_val = selected_cat

        # 4. 용량/농도
        with c4:
            amt_val = st.text_input(
                f"amt_txt_{idx}",
                value=item.get("amount", ""),
                key=f"amt_txt_key_{idx}",
                label_visibility="collapsed",
                placeholder="예: 500 mL / 10 mM"
            )

        # 5. 삭제 버튼
        with c5:
            if st.button("🗑️", key=f"del_btn_{idx}"):
                clear_all_recipe_widget_keys()
                st.session_state.recipe_items.pop(idx)
                if not st.session_state.recipe_items:
                    st.session_state.recipe_items = [{"material_name": "", "manufacturer": "", "cat_no": "", "amount": ""}]
                st.rerun()

        if mat_val:
            updated_items.append({
                "material_name": mat_val,
                "manufacturer": mfg_val,
                "cat_no": cat_val,
                "amount": amt_val
            })

    col_add, _ = st.columns([1, 4])
    with col_add:
        if st.button("➕ 물질 항목 추가"):
            st.session_state.recipe_items.append({"material_name": "", "manufacturer": "", "cat_no": "", "amount": ""})
            st.rerun()

    st.markdown("---")
    if st.button("💾 레시피 DB에 저장", type="primary", use_container_width=True):
        if not recipe_name:
            st.error("레시피 이름을 입력해 주세요.")
        elif not category:
            st.error("카테고리를 선택해 주세요.")
        elif not updated_items:
            st.error("최소 하나 이상의 구성 물질을 입력해 주세요.")
        else:
            prep_date_str = prepared_date.strftime("%Y-%m-%d")
            db.save_material_recipe(recipe_name, category, prep_date_str, description, updated_items)
            
            clear_all_recipe_widget_keys()
            st.success(f"[{category}] '{recipe_name}' 레시피가 성공적으로 저장되었습니다!")
            st.session_state.recipe_items = [{"material_name": "", "manufacturer": "", "cat_no": "", "amount": ""}]
            st.rerun()

# ---------------------------------------------------------
# TAB 2: 레시피 조회, 수정 및 관리
# ---------------------------------------------------------
with tab2:
    st.subheader("등록된 Material Recipe 목록")
    
    recipes_df = db.get_all_recipes()
    
    if not recipes_df:
        st.info("등록된 레시피가 없습니다. '새 레시피 등록' 탭에서 생성해 주세요.")
    else:
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
                edit_mode_key = f"edit_mode_{recipe_id}"
                if edit_mode_key not in st.session_state:
                    st.session_state[edit_mode_key] = False

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

                else:
                    st.markdown("### ✏️ 레시피 수정 모드")
                    
                    edit_name = st.text_input("레시피/배지 이름", value=row['recipe_name'], key=f"edit_name_{recipe_id}")
                    
                    cat_options = st.session_state.custom_categories if st.session_state.custom_categories else ["미분류"]
                    current_cat_idx = cat_options.index(cat_tag) if cat_tag in cat_options else 0
                    edit_category = st.selectbox("분류 (카테고리)", cat_options, index=current_cat_idx, key=f"edit_cat_{recipe_id}")
                    
                    try:
                        parsed_date_obj = datetime.datetime.strptime(prep_date, "%Y-%m-%d").date()
                    except:
                        parsed_date_obj = datetime.date.today()
                    edit_date = st.date_input("조제/만든 날짜", value=parsed_date_obj, key=f"edit_date_{recipe_id}")
                    
                    edit_desc = st.text_input("설명 / 비고", value=row.get('description', ''), key=f"edit_desc_{recipe_id}")
                    
                    st.markdown("---")
                    st.markdown("**구성 물질 및 용량 수정**")
                    
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
                    
                    updated_edit_items = []
                    for e_idx, e_item in enumerate(st.session_state[edit_items_key]):
                        ec1, ec2, ec3, ec4, ec5 = st.columns([2.5, 2.0, 2.0, 1.8, 0.5])
                        with ec1:
                            e_mat = st.text_input(f"물질명 #{e_idx+1}", value=e_item.get("material_name", ""), key=f"edit_mat_{recipe_id}_{e_idx}", label_visibility="collapsed")
                        with ec2:
                            e_mfg = st.text_input(f"제조사 #{e_idx+1}", value=e_item.get("manufacturer", ""), key=f"edit_mfg_{recipe_id}_{e_idx}", label_visibility="collapsed")
                        with ec3:
                            e_cat = st.text_input(f"Cat No. #{e_idx+1}", value=e_item.get("cat_no", ""), key=f"edit_catnum_{recipe_id}_{e_idx}", label_visibility="collapsed")
                        with ec4:
                            e_amt = st.text_input(f"용량/농도 #{e_idx+1}", value=e_item.get("amount", ""), key=f"edit_amt_{recipe_id}_{e_idx}", label_visibility="collapsed")
                        with ec5:
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
                                conn = db.get_connection()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE material_recipes 
                                    SET recipe_name = ?, category = ?, prepared_date = ?, description = ?
                                    WHERE recipe_id = ?
                                """, (edit_name, edit_category, edit_date.strftime("%Y-%m-%d"), edit_desc, recipe_id))
                                
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