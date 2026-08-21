   else:
                            st.markdown(f"##### 📋 선택된 Well 목록 ({len(selected_wells)}개)")
                            st.caption("여러 개의 Well이 동시 선택되었습니다. 일괄 삭제 등을 진행할 수 있습니다.")
                            
                            with st.expander("🗑️ 선택된 Well 이력 일괄 삭제", expanded=False):
                                st.warning("⚠️ 지정한 Well에 등록된 모든 처리 이력이 삭제됩니다.")
                                wells_to_delete = st.multiselect(
                                    "삭제할 Well 선택",
                                    options=selected_wells,
                                    default=selected_wells,
                                    key="batch_delete_wells_select"
                                )
                                if st.button("🚨 선택한 Well의 모든 이력 삭제", key="btn_batch_delete_wells", type="secondary"):
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
