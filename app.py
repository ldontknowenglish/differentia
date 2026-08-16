import streamlit as st
import db
import style

st.set_page_config(
    page_title="오가노이드/연구노트 & Well 시각화 시스템",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)
style.set_narrow_layout()

db.init_db()

st.title("🧪 연구노트 & Standardized Circle Well Plate 시각화 시스템 (v6.2)")
st.markdown("""
### 🔬 이번 업데이트 핵심: 2단 그리드 보기 + 휴지통(복구) 기능 추가

1. **📥 휴지통(Trash) 기능 신규 추가**
   - 프로젝트/플레이트/처리 내역/Daily Log를 삭제하면 즉시 영구 삭제되지 않고 **휴지통**으로 이동합니다.
   - 왼쪽 메뉴의 **'6 Trash(휴지통)'** 페이지에서 실수로 지운 항목을 언제든지 **♻️ 복구**할 수 있고, 필요 시 **❌ 영구 삭제**도 가능합니다.

2. **🗂️ 2단 그리드(2-Column) 레이아웃 적용**
   - Well 처리 이력, 전체 처리 내역 관리, Daily Log 목록을 세로로 길게 한 줄씩 보던 방식에서 **한 화면에 2개씩 나란히** 보이도록 개선해 스크롤을 줄이고 비교가 쉬워졌습니다.

3. **처리 내역 수정(Edit) 및 삭제(Delete) 기능 연동**
   - 웰 시각화 탭 및 물질 처리 이력 탭에서 각 처리 기록별로 **수정(💾) 및 삭제(🗑️)** 버튼을 배치하여 오기입된 데이터를 즉시 변경하거나 휴지통으로 이동할 수 있습니다.

4. **표준 규격 멀티웰 플레이트 프리셋 탑재 (6, 12, 24, 48, 96 Well)**
   - 플레이트 생성 시 표준 규격을 드롭다운에서 선택하여 즉시 배양판을 생성할 수 있습니다.

5. **Plotly 기반 동적 원형 웰(Circle Marker) 시각화 연동**
   - 선택된 규격에 맞춰 웰 크기와 레이아웃이 자동 조정되며, 마우스 호버로 상세 내용을 확인합니다.
""")

projects = db.get_projects()
groups = set([p["group_name"] for p in projects if p["group_name"]])
trash_count = db.get_trash_count()

col1, col2, col3, col4 = st.columns(4)
col1.metric("총 프로젝트 수", len(projects))
col2.metric("등록된 그룹 수", len(groups))
col3.metric("데이터 관리 기능", "수정/삭제/복구 지원")
col4.metric("🗑️ 휴지통 항목 수", trash_count)

if trash_count > 0:
    st.info(f"📥 휴지통에 복구 대기 중인 항목이 **{trash_count}건** 있습니다. 왼쪽 메뉴의 **'6 Trash(휴지통)'** 페이지에서 확인하세요.")
