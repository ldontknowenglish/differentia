import streamlit as st

def set_narrow_layout(max_width_px: int = 1100):
    """
    layout="wide" 로 인해 화면이 지나치게 가로로 넓게 늘어나는 문제를 줄이기 위한 공통 스타일.
    페이지 컨텐츠의 최대 가로폭을 제한하고 가운데 정렬합니다.
    st.set_page_config(...) 바로 다음 줄에서 호출해서 사용합니다.
    """
    st.markdown(
        f"""
        <style>
        .block-container {{
            max-width: {max_width_px}px;
            margin-left: auto;
            margin-right: auto;
            padding-left: 2.5rem;
            padding-right: 2.5rem;
        }}
        /* 2단(좌/우) 카드 레이아웃에서 각 칼럼 내부 요소가 카드 폭을 넘지 않도록 */
        div[data-testid="column"] {{
            min-width: 0;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
