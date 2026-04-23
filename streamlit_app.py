"""
백화점 경쟁사 행사 AI 분석 시스템 — Streamlit 버전
Streamlit Cloud 배포용 (app.py 수정 없이 동일 기능 제공)
"""
import os, json, base64, io, re
from datetime import datetime
import streamlit as st
import anthropic
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── API 키 설정 (Secrets → 환경변수 → 사이드바 입력 순서) ──
def get_api_key():
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM = "당신은 백화점 MD 경쟁분석 전문가입니다. 이미지에서 행사 정보를 추출해 JSON으로만 응답하세요. 마크다운 없이 순수 JSON만 출력하세요."


def extract_events(cl, uploaded_files, store_name):
    if not uploaded_files:
        return []
    content = []
    for f in uploaded_files:
        data = base64.b64encode(f.read()).decode()
        mime = f.type or "image/jpeg"
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
        f.seek(0)
    content.append({"type": "text", "text": f"""이 이미지들은 {store_name} 카카오채널 스크린샷입니다.
모든 행사·팝업·사은혜택·이벤트를 추출하세요.
JSON 형식: {{"events":[{{"category":"상품군","name":"행사명","detail":"내용","period":"기간","type":"유형"}}]}}"""})
    resp = cl.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=2000,
        system=SYSTEM, messages=[{"role": "user", "content": content}]
    )
    raw = re.sub(r"```json?\n?", "", resp.content[0].text).replace("```", "").strip()
    return json.loads(raw).get("events", [])


def compare(cl, lotte, hyundai):
    lt = "\n".join([f"[{e['category']}] {e['name']}: {e['detail']}" for e in lotte])
    ht = "\n".join([f"[{e['category']}] {e['name']}: {e['detail']}" for e in hyundai])
    prompt = f"""롯데백화점 대구점과 더현대 대구 행사를 비교 분석하세요.

롯데:\n{lt}\n\n더현대:\n{ht}

JSON 형식으로만 응답:
{{"categories":[{{"category":"상품군","lotte":"롯데내용","hyundai":"현대내용","winner":"롯데|더현대|비슷","point":"한줄포인트"}}],
"lotte_strength":["강점1","강점2","강점3"],
"hyundai_strength":["강점1","강점2","강점3"],
"insight":["MD 전략 제언1","제언2","제언3","제언4"]}}

상품군: 패션/스포츠·레저/뷰티/식품F&B/리빙가구/팝업스토어/사은혜택/문화이벤트
insight는 롯데 영업기획팀 입장의 실전 전략 제언으로 작성"""
    resp = cl.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = re.sub(r"```json?\n?", "", resp.content[0].text).replace("```", "").strip()
    return json.loads(raw)


def build_excel(data):
    wb = Workbook()

    def th(c, bg="1A1A2E", fc="FFFFFF", sz=10):
        c.fill = PatternFill("solid", start_color=bg)
        c.font = Font(bold=True, color=fc, name="맑은 고딕", size=sz)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        s = Side(border_style="thin", color="CCCCCC")
        c.border = Border(left=s, right=s, top=s, bottom=s)

    def td(c, bg="FFFFFF", fc="111111", bold=False, center=False):
        c.fill = PatternFill("solid", start_color=bg)
        c.font = Font(bold=bold, color=fc, name="맑은 고딕", size=9)
        c.alignment = Alignment(horizontal="center" if center else "left", vertical="center", wrap_text=True)
        s = Side(border_style="thin", color="E0E0E0")
        c.border = Border(left=s, right=s, top=s, bottom=s)

    ws1 = wb.active; ws1.title = "상품군별 비교"; ws1.sheet_view.showGridLines = False
    ws1.merge_cells("A1:E1")
    c = ws1["A1"]; c.value = f"롯데 vs 더현대 행사 비교 ({data.get('analyzed_at', '')})"; th(c, sz=12)
    ws1.row_dimensions[1].height = 26
    for i, (h, w) in enumerate([("상품군", 14), ("롯데백화점", 36), ("더현대 대구", 36), ("우세", 10), ("비교포인트", 32)], 1):
        ws1.column_dimensions[get_column_letter(i)].width = w
        th(ws1.cell(row=2, column=i, value=h))
    for r, cat in enumerate(data.get("categories", []), 3):
        ws1.row_dimensions[r].height = 42
        bg = "FAFAFA" if r % 2 == 0 else "FFFFFF"
        w = cat.get("winner", "비슷"); wfc = "C00020" if w == "롯데" else ("003087" if w == "더현대" else "555555")
        for ci, v in enumerate([cat.get("category"), cat.get("lotte", "—"), cat.get("hyundai", "—"), w, cat.get("point", "")], 1):
            td(ws1.cell(row=r, column=ci, value=v), bg=bg, bold=(ci == 1 or ci == 4), fc=wfc if ci == 4 else "111111", center=(ci == 1 or ci == 4))

    ws2 = wb.create_sheet("롯데 행사 상세"); ws2.sheet_view.showGridLines = False
    ws2.merge_cells("A1:E1"); c = ws2["A1"]; c.value = "롯데백화점 대구점 행사 전체"; th(c, bg="E8002D", sz=12); ws2.row_dimensions[1].height = 24
    for i, (h, w) in enumerate([("카테고리", 12), ("행사명", 28), ("내용", 42), ("기간", 14), ("유형", 10)], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w; th(ws2.cell(row=2, column=i, value=h), bg="C00020")
    for r, ev in enumerate(data.get("lotte_events", []), 3):
        bg = "FFF5F5" if r % 2 == 0 else "FFFFFF"
        for ci, k in enumerate(["category", "name", "detail", "period", "type"], 1):
            td(ws2.cell(row=r, column=ci, value=ev.get(k, "")), bg=bg)
        ws2.row_dimensions[r].height = 36

    ws3 = wb.create_sheet("더현대 행사 상세"); ws3.sheet_view.showGridLines = False
    ws3.merge_cells("A1:E1"); c = ws3["A1"]; c.value = "더현대 대구 행사 전체"; th(c, bg="003087", sz=12); ws3.row_dimensions[1].height = 24
    for i, (h, w) in enumerate([("카테고리", 12), ("행사명", 28), ("내용", 42), ("기간", 14), ("유형", 10)], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w; th(ws3.cell(row=2, column=i, value=h), bg="003087")
    for r, ev in enumerate(data.get("hyundai_events", []), 3):
        bg = "F0F4FF" if r % 2 == 0 else "FFFFFF"
        for ci, k in enumerate(["category", "name", "detail", "period", "type"], 1):
            td(ws3.cell(row=r, column=ci, value=ev.get(k, "")), bg=bg)
        ws3.row_dimensions[r].height = 36

    ws4 = wb.create_sheet("AI 분석"); ws4.sheet_view.showGridLines = False
    ws4.column_dimensions["A"].width = 18; ws4.column_dimensions["B"].width = 60
    ws4.merge_cells("A1:B1"); c = ws4["A1"]; c.value = "AI 경쟁 분석 — MD 전략 제언"; th(c, sz=12); ws4.row_dimensions[1].height = 24
    row = 2
    for title, items, bg, fc in [
        ("롯데 강점", data.get("lotte_strength", []), "FCE4E4", "C00020"),
        ("더현대 강점", data.get("hyundai_strength", []), "E4EBF9", "003087"),
        ("MD 전략 제언", data.get("insight", []), "FFFDE7", "856404"),
    ]:
        th(ws4.cell(row=row, column=1, value=title), bg=fc)
        ws4.cell(row=row, column=2).fill = PatternFill("solid", start_color=fc)
        ws4.row_dimensions[row].height = 20; row += 1
        for item in items:
            td(ws4.cell(row=row, column=2, value=f"• {item}"), bg=bg)
            ws4.cell(row=row, column=1).fill = PatternFill("solid", start_color=bg)
            ws4.row_dimensions[row].height = 30; row += 1
        row += 1

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="백화점 행사 AI 분석", page_icon="🏬", layout="wide")

st.markdown("""
<style>
[data-testid="stHeader"] {background:#111}
.store-lotte {color:#e8002d; font-weight:700}
.store-hyundai {color:#003087; font-weight:700}
</style>
""", unsafe_allow_html=True)

# 사이드바에서 API 키 입력
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    preset_key = get_api_key()
    api_key = st.text_input(
        "Anthropic API Key",
        value=preset_key,
        type="password",
        placeholder="sk-ant-...",
        help="console.anthropic.com 에서 발급한 API 키를 입력하세요.",
    )
    if api_key:
        st.success("API 키 설정됨", icon="✅")
    else:
        st.warning("API 키를 입력해주세요.", icon="⚠️")

st.markdown("## 🏬 백화점 행사 AI 분석")
st.caption("롯데백화점 대구점 vs 더현대 대구 — 카카오채널 스크린샷 비교 분석")

col_l, col_h = st.columns(2)
with col_l:
    st.markdown("### 🔴 롯데백화점 대구점")
    lotte_files = st.file_uploader(
        "카카오채널 스크린샷 업로드 (최대 10장)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="lotte",
    )
    if lotte_files:
        cols = st.columns(min(len(lotte_files), 5))
        for i, f in enumerate(lotte_files[:10]):
            cols[i % 5].image(f, width=80)

with col_h:
    st.markdown("### 🔵 더현대 대구")
    hyundai_files = st.file_uploader(
        "카카오채널 스크린샷 업로드 (최대 10장)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="hyundai",
    )
    if hyundai_files:
        cols = st.columns(min(len(hyundai_files), 5))
        for i, f in enumerate(hyundai_files[:10]):
            cols[i % 5].image(f, width=80)

st.divider()

if st.button("🤖 AI 분석 시작", type="primary", use_container_width=True):
    if not lotte_files and not hyundai_files:
        st.error("이미지를 최소 한 장 이상 업로드해주세요.")
    elif not api_key:
        st.error("왼쪽 사이드바에 Anthropic API 키를 입력해주세요.")
    else:
        cl = anthropic.Anthropic(api_key=api_key)
        with st.spinner("이미지 분석 중... (20~40초 소요)"):
            try:
                lotte_ev = extract_events(cl, lotte_files[:10], "롯데백화점 대구점")
                hyundai_ev = extract_events(cl, hyundai_files[:10], "더현대 대구")
                result = compare(cl, lotte_ev, hyundai_ev)
                result["lotte_events"] = lotte_ev
                result["hyundai_events"] = hyundai_ev
                result["analyzed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state["result"] = result
            except Exception as e:
                st.error(f"분석 실패: {e}")

if "result" in st.session_state:
    result = st.session_state["result"]

    st.subheader("📊 상품군별 비교표")
    categories = result.get("categories", [])
    if categories:
        rows = []
        for c in categories:
            w = c.get("winner", "비슷")
            badge = "🔴 롯데 우세" if w == "롯데" else ("🔵 더현대 우세" if w == "더현대" else "⚪ 비슷")
            rows.append({
                "상품군": c.get("category", ""),
                "롯데백화점": c.get("lotte", "—"),
                "더현대 대구": c.get("hyundai", "—"),
                "우세": badge,
                "비교 포인트": c.get("point", ""),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("🧠 AI 경쟁 분석")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**🔴 롯데 강점**")
        for x in result.get("lotte_strength", []):
            st.markdown(f"— {x}")
    with c2:
        st.markdown("**🔵 더현대 강점**")
        for x in result.get("hyundai_strength", []):
            st.markdown(f"— {x}")
    with c3:
        st.markdown("**⚡ MD 전략 제언**")
        for x in result.get("insight", []):
            st.markdown(f"— {x}")

    st.divider()
    excel_buf = build_excel(result)
    fname = f"백화점행사비교_{datetime.now().strftime('%Y%m%d')}.xlsx"
    st.download_button(
        label="📥 Excel 다운로드",
        data=excel_buf,
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
