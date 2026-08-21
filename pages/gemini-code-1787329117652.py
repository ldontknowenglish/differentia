# ======================================================================
        # [TAB 0] 전체 실험 중인 플레이트 대시보드 (모든 프로젝트 대상)
        # ======================================================================
        with tab_overview:
            st.markdown("### 🧪 전체 프로젝트의 실험 중인 플레이트 목록")
            st.caption("모든 웰의 분석이 완료된 플레이트는 제외되며, 현재 분석 및 실험이 진행 중인 플레이트만 표시됩니다.")

            # 1. 모든 프로젝트 및 플레이트 전수 조회
            active_plates = []
            all_projects = db.get_projects()
            
            for proj in all_projects:
                proj_plates = db.get_plates(proj['id'])
                for pl in proj_plates:
                    pl_treatments = db.get_treatments_by_plate(pl['id'])
                    total_cap = pl['rows'] * pl['cols']
                    
                    # 분석 완료된 Well 추출 (analysis_status가 존재하고 '미진행'이 아닌 경우)
                    completed_wells = set([
                        t.get('well_position') for t in pl_treatments 
                        if t.get('analysis_status') and t.get('analysis_status') != '미진행'
                    ])
                    
                    # 모든 웰의 분석이 완료된 플레이트(completed_wells 개수 == total_cap)는 제외
                    if len(completed_wells) < total_cap:
                        active_plates.append({
                            'project': proj,
                            'plate': pl,
                            'treatments': pl_treatments,
                            'total_cap': total_cap,
                            'completed_count': len(completed_wells)
                        })

            # 2. 진행 중인 플레이트 목록 출력
            if not active_plates:
                st.info("💡 현재 진행 중인 실험 플레이트가 없습니다. (모든 플레이트의 분석이 완료되었거나 등록된 플레이트가 없습니다.)")
            else:
                grid_cols = st.columns(3)
                for idx, item in enumerate(active_plates):
                    proj = item['project']
                    pl = item['plate']
                    pl_treatments = item['treatments']
                    total_cap = item['total_cap']
                    completed_count = item['completed_count']
                    
                    # 세포 정보 모음
                    cells = sorted(list(set([t.get('cell_info', '').strip() for t in pl_treatments if t.get('cell_info')])))
                    cell_display = ", ".join(cells) if cells else "미지정 (세포 정보 없음)"
                    
                    # 작업 제목/최신 처리 정보 요약
                    if pl_treatments:
                        latest_treat = max(pl_treatments, key=lambda x: str(x.get('treatment_date', '')))
                        latest_date = latest_treat.get('treatment_date', '-')
                        _, pure_note, _ = parse_note_basal_image(latest_treat)
                        
                        task_title = pure_note if pure_note else format_compound_summary(latest_treat.get('compound_name'), latest_treat.get('concentration'))
                        if not task_title or task_title == "-":
                            task_title = f"최근 처리 진행 ({latest_treat.get('analysis_status', '기본')})"
                    else:
                        latest_date = "기록 없음"
                        task_title = "작업 기록 없음"

                    well_count = len(set([t.get('well_position') for t in pl_treatments]))

                    # 사이드바 프로젝트/플레이트 옵션 선택용 키 생성
                    proj_label = f"[{proj['group_name'] if proj['group_name'] else '기본'}] {proj['name']} (ID: {proj['id']})"
                    pl_key = f"{pl['name']} ({pl['rows']}x{pl['cols']} Wells)"

                    col_idx = idx % 3
                    with grid_cols[col_idx]:
                        st.markdown(
                            f"""
                            <div style="border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 12px;">
                                <div style="font-size:12px; color:{proj['color_code']}; font-weight:bold; margin-bottom:4px;">📁 프로젝트: {proj['name']}</div>
                                <div class="plate-card-header">🧫 {pl['name']}</div>
                                <div class="plate-card-sub"><b>📌 규격:</b> {pl['rows']}x{pl['cols']} ({total_cap} Wells)</div>
                                <div class="plate-card-sub"><b>🧬 사용 세포:</b> <span style="color:#2563eb; font-weight:600;">{cell_display}</span></div>
                                <div class="plate-card-sub"><b>📋 최근 조건:</b> {task_title}</div>
                                <div class="plate-card-sub"><b>🔬 분석 진행률:</b> <span style="color:#059669; font-weight:bold;">{completed_count}/{total_cap} Wells 완료</span></div>
                                <div class="plate-card-sub"><b>📅 최근 작업일:</b> {latest_date} ({well_count}/{total_cap} Wells 처리됨)</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        # 카드 클릭 시 해당 프로젝트 및 플레이트로 대시보드 상태 변경 후 이동
                        if st.button(f"🔍 [{pl['name']}] 편집하러 가기", key=f"btn_goto_pl_{pl['id']}", use_container_width=True, type="primary"):
                            st.session_state.selected_plate_proj_label = proj_label
                            st.session_state.selected_plate_select = pl_key
                            st.toast(f"'{proj['name']}' 프로젝트의 '{pl['name']}' 플레이트로 이동합니다.", icon="🧫")
                            st.rerun()