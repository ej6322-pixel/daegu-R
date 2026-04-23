import streamlit as st

st.set_page_config(page_title="테스트", layout="wide")

# 사이드바 테스트
api_key = st.sidebar.text_input("API Key", type="password")

if api_key:
    st.sidebar.success("✅ API 키 설정됨")
else:
    st.sidebar.warning("⚠️ API 키를 입력해주세요")

st.write("메인 콘텐츠")
st.write(f"API Key: {api_key if api_key else '입력되지 않음'}")
