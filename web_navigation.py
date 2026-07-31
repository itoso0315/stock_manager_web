import streamlit as st


def render_sidebar_navigation():
    """ファイル名に依存しないWebアプリのナビゲーションを表示する。"""
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.page_link("web_app.py", label="My Stock", icon="📊")
        st.page_link(
            "pages/technical_analysis.py",
            label="technical analysis",
            icon="📈",
        )
