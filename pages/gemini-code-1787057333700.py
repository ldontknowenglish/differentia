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

if hasattr(db, 'get_all_categories'):
    db_cats = db.get_all_categories()
    for cat in db_cats:
        if cat and cat not in st.session_state.custom_categories:
            st.session_state.custom_categories.append(cat)

# 기존 DB 등록 항목 목록 로드 (자동완성/추천용)
def get_master_lists():
    mat_list, mfg_list, cat_list = [], [], []
    if hasattr(db, 'get_all_recipe_items_master'):
        raw_items = db.get_all_recipe_items_master()
        mat_list = sorted(list(set([i['material_name'] for i in raw_items if i.get('material_name')])))
        mfg_list = sorted(list(set([i['manufacturer'] for i in raw_items if i.get('manufacturer')])))
        cat_list = sorted(list(set([i['cat_no'] for i in raw_items if i.get('cat_no')])))
    return mat_list, mfg_list, cat_list

master_mats, master_mfgs, master_cats = get_master_lists()

tab1, tab2 = st.tabs(["➕ 새 레시피 등록", "🔍 레시피 조회 및 관리"])

# ---------------------------------------------------------
# TAB 1: 새 레시피 등록
# ---------------------------------------------------------
with tab1:
    st.subheader("새로운 Material Recipe 작성")
    
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

    st.markdown("---")
    st.write("##### 🧪 구성 물질, 제조사, Cat No. 및 용량 설정")
    st.caption("💡 한 행에서 입력 혹은 기존 데이터 기반 선택이 가능합니다.")

    # 초기 기본 세션 아이템 데이터 설정
    if "recipe_items" not in st.session_state:
        st.session_state.recipe_items = [
            {"material_name": "RPMI1640", "manufacturer": "Gibco", "cat_no": "11875093", "amount": "500 mL"},
            {"material_name": "L-glutamine", "manufacturer": "Gibco", "cat_no": "25030081", "amount": "1%"},
        ]

    updated_items = []
    
    # 헤더 행 표시
    h1, h2, h3, h4, h5 = st.columns([2.5, 2.0, 2.0, 1.8, 0.5])
    h1.caption("**물질명 (Material)**")
    h2.caption("**제조사 (Manufacturer)**")
    h3.caption("**Cat No.**")
    h4.caption("**용량 / 농도**")
    h5.caption("")

    # 물질 목록 한 줄(Single Row) 배치
    for idx, item in enumerate(st.session_state.recipe_items):
        c1, c2, c3, c4, c5 = st.columns([2.5, 2.0, 2.0, 1.8, 0.5])
        
        # 1. 물질명 (직접 입력 및 빠른 선택)
        with c1:
            val_mat = item.get("material_name", "")
            mat_input = st.text_input(
                f"mat_{idx}", 
                value=val_mat, 
                key=f"mat_input_{idx}", 
                label_visibility="collapsed",
                placeholder="예: RPMI1640"
            )
            if master_mats:
                sel_m = st.selectbox("선택", ["기존 DB 항목 선택..."] + master_mats, key=f"mat_quick_{idx}", label_visibility="collapsed")
                if sel_m != "기존 DB 항목 선택...":
                    mat_input = sel_m

        # 2. 제조사
        with c2:
            val_mfg = item.get("manufacturer", "")
            mfg_input = st.text_input(
                f"mfg_{idx}", 
                value=val_mfg, 
                key=f"mfg_input_{idx}", 
                label_visibility="collapsed",
                placeholder="예: Gibco"
            )
            if master_mfgs:
                sel_mfg = st.selectbox("선택", ["기존 DB 항목 선택..."] + master_mfgs, key=f"mfg_quick_{idx}", label_visibility="collapsed")
                if sel_mfg != "기존 DB 항목 선택...":
                    mfg_input = sel_mfg

        # 3. Cat No.
        with c3:
            val_cat = item.get("cat_no", "")
            cat_input = st.text_input(
                f"cat_{idx}", 
                value=val_cat, 
                key=f"cat_input_{idx}", 
                label_visibility="collapsed",
                placeholder="예: 11875093"
            )
            if master_cats:
                sel_c = st.selectbox("선택", ["기존 DB 항목 선택..."] + master_cats, key=f"cat_quick_{idx}", label_visibility="collapsed")
                if sel_c != "기존 DB 항목 선택...":
                    cat_input = sel_c

        # 4. 용량/농도
        with c4:
            val_amt = item.get("amount", "")
            amt_input = st.text_input(
                f"amt_{idx}", 
                value=val_amt, 
                key=f"amt_input_{idx}", 
                label_visibility="collapsed",
                placeholder="예: 500 mL / 10 mM"
            )

        # 5. 삭제 버튼
        with c5:
            if st.button("🗑️", key=f"del_btn_{idx}"):
                st.session_state.recipe_items.pop(idx)
                st.rerun()

        if mat_input:
            updated_items.append({
                "material_name": mat_input,
                "manufacturer": mfg_input,
                "cat_no": cat_input,
                "amount": amt_input
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
            
            st.success(f"[{category}] '{recipe_name}' 레시피가 성공적으로 저장되었습니다!")
            st.session_state.recipe_items = [{"material_name": "", "manufacturer": "", "cat_no": "", "amount": ""}]
            st.rerun()

# ---------------------------------------------------------
# TAB 2: 레시피 조회 및 관리
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
        
        for row in filtered_recipes:
            recipe_id = row['recipe_id']
            cat_tag = row.get('category') or '미분류'
            prep_date = row.get('prepared_date') or str(row.get('created_at', ''))[:10]
            description = row.get('description') or "설명 없음"
            
            expander_title = f"🧪 [{cat_tag}] **{row['recipe_name']}** (📅 조제일: {prep_date}) - {description}"
            
            with st.expander(expander_title):
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
                
                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn2:
                    if st.button(f"🗑️ '{row['recipe_name']}' 레시피 삭제", key=f"delete_recipe_{recipe_id}", use_container_width=True):
                        db.delete_recipe(recipe_id)
                        st.warning("레시피가 휴지통으로 이동되었습니다.")
                        st.rerun()