# app.py
import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import time

JST = timezone(timedelta(hours=9))
st.set_page_config(page_title="場所ニュース（Google News / 自動クエリ）", page_icon="📰", layout="wide")

# -------- utils
def xdaysago(x: int = 0) -> str:
    """JST基準で x 日前（x<0は未来）のYYYY-MM-DD"""
    return (datetime.now(JST).date() - timedelta(days=x)).isoformat()

def _published_to_jst(entry):
    try:
        tt = entry.get("published_parsed")
        if not tt: return None
        epoch = time.mktime(tt)
        dt_utc = datetime.utcfromtimestamp(epoch).replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(JST)
    except Exception:
        return None

def google_news_to_table(rss_url: str, limit: int = 50) -> pd.DataFrame:
    fp = feedparser.parse(rss_url)
    rows, seen = [], set()
    for e in fp.entries[:limit]:
        link = e.get("link", "")
        if not link or link in seen: continue
        seen.add(link)
        title = e.get("title", "")
        src = e.get("source", {})
        source = src.get("title") if isinstance(src, dict) else ""
        published_jst = _published_to_jst(e)
        rows.append({
            "title": title,
            "source": source,
            "published_jst": published_jst.strftime("%Y-%m-%d %H:%M") if published_jst else "",
            "link": link,
        })
    return pd.DataFrame(rows)

# -------- query builder
EVENT_TERMS = "イベント OR 開催 OR オープン OR 祭り OR 体験会 OR フェス OR 展示会 OR 展"

def build_query(place: str) -> str:
    """（場所名）AND（イベント語のOR束）を自動生成"""
    place = place.strip()
    return f'({place}) AND ({EVENT_TERMS})'

def q_to_tb(place: str, add: str = "") -> tuple[pd.DataFrame, str, str]:
    """昨日+今日を対象にRSS取得。DF, 実URL, 実クエリを返す"""
    yesterday = xdaysago(1)   # 昨日
    tomorrow = xdaysago(-1)   # 明日（before用）
    query = build_query(place)
    # ご指定フォーマット: after:{yesterday}+before:{tomorrow}+{query}
    q_param = f"after:{yesterday}+before:{tomorrow}+{quote_plus(query)}"
    rss_url = f"https://news.google.com/rss/search?q={q_param}&hl=ja&gl=JP&ceid=JP:ja{add}"
    df = google_news_to_table(rss_url).iloc[:20]
    return df, rss_url, query

# -------- UI
st.title("📰 場所ニュース")
st.caption("駅名/地名 → そこに関連したイベント関連ニュースを表示")

with st.sidebar:
    place = st.text_input("駅名・地名（例：渋谷駅 / 東京駅 / 京都市）", value="渋谷駅")
    max_rows = st.slider("表示件数", 10, 50, 20, 5)
    run = st.button("検索する")

if run:
    if not place.strip():
        st.warning("駅名・地名を入力してください。")
        st.stop()

    df, rss_url, actual_query = q_to_tb(place)

    if df.empty:
        st.info("関連ニュースが見つかりませんでした。地名を広域（区/市/県）にするなどお試しください。")
        st.stop()

    df = df.head(max_rows)

    st.subheader("関連記事")
    for _, row in df.iterrows():
        with st.container(border=True):
            title_line = f"**[{row['title']}]({row['link']})**"
            if row['source']:
                title_line += f" · {row['source']}"
            st.markdown(title_line)
            if row['published_jst']:
                st.write(f"🕒 {row['published_jst']}（JST）")

    with st.expander("表で見る"):
        st.dataframe(df.rename(columns={
            "title": "タイトル", "source": "媒体", "published_jst": "公開(JST)", "link": "リンク"
        }), use_container_width=True)

    st.markdown("**実際に使用したRSS URL**")
    st.code(rss_url, language="text")
    
else:
    st.info("サイドバーに駅名（または地名）を入れて検索してください。検索語は自動でイベント関連語を含む形に組み立てます。")
