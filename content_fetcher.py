"""
content_fetcher.py

역할 1: URL → 본문 텍스트 추출
역할 2: 주제 키워드 → 뉴스/웹 검색 결과 수집

검색 소스 (API 키 있는 것만 자동 활성화):
  - 네이버 뉴스: NAVER_CLIENT_ID + NAVER_CLIENT_SECRET
  - Google CSE:  GOOGLE_CSE_KEY + GOOGLE_CSE_ID
  - Bing 검색:   BING_SEARCH_KEY
  - 폴백:        네이버 뉴스 RSS (무료, 키 불필요)
"""
import os
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TWITTER_DOMAINS = ("twitter.com", "x.com", "t.co")


def fetch_content(url: str) -> dict:
    """URL → {title, text, source}"""
    if _is_twitter_url(url):
        return _prompt_twitter_text(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()
        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)
        article = soup.find("article") or soup.find("main") or soup.find("body")
        text = article.get_text(separator=" ", strip=True) if article else ""
        text = re.sub(r"\s+", " ", text).strip()[:3000]
        return {"title": title or url, "text": text, "source": url}
    except Exception as e:
        print(f"  ⚠️  URL 수집 실패: {e}")
        return {"title": url, "text": url, "source": url}


def _is_twitter_url(url: str) -> bool:
    return any(d in url for d in TWITTER_DOMAINS)


def _prompt_twitter_text(url: str) -> dict:
    print("\n" + "─" * 50)
    print("트위터/X URL이 감지됐어요.")
    print("트윗 텍스트를 직접 붙여넣어 주세요.")
    print("─" * 50)
    print("입력 후 빈 줄에서 Enter:")
    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)
    text = " ".join(lines).strip() or url
    return {"title": text[:50], "text": text, "source": url}


def fetch_topic_context(topic: str, max_results: int = 5) -> dict:
    """
    주제 키워드 → 뉴스 + 웹 검색 결과 종합.
    반환: {news, web, combined_text, sources_used}
    """
    news, web, sources_used = [], [], []

    naver_id     = os.environ.get("NAVER_CLIENT_ID", "")
    naver_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if naver_id and naver_secret:
        result = _search_naver_news(topic, naver_id, naver_secret, max_results)
        if result:
            news.extend(result)
            sources_used.append("naver_api")
            print(f"  → 네이버 뉴스 {len(result)}건")

    google_key = os.environ.get("GOOGLE_CSE_KEY", "")
    google_cse = os.environ.get("GOOGLE_CSE_ID", "")
    if google_key and google_cse:
        result = _search_google(topic, google_key, google_cse, max_results)
        if result:
            web.extend(result)
            sources_used.append("google")
            print(f"  → Google {len(result)}건")

    bing_key = os.environ.get("BING_SEARCH_KEY", "")
    if bing_key:
        result = _search_bing(topic, bing_key, max_results)
        if result:
            web.extend(result)
            sources_used.append("bing")
            print(f"  → Bing {len(result)}건")

    if not news:
        result = _search_naver_rss(topic, max_results)
        if result:
            news.extend(result)
            sources_used.append("naver_rss")
            print(f"  → 네이버 RSS {len(result)}건")

    return {
        "news":          news,
        "web":           web,
        "combined_text": _build_combined_text(topic, news, web),
        "sources_used":  sources_used,
    }


def _search_naver_news(topic, client_id, client_secret, max_results):
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
            params={"query": topic, "display": max_results, "sort": "date"},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            {
                "title":       re.sub(r"<[^>]+>", "", item.get("title", "")),
                "description": re.sub(r"<[^>]+>", "", item.get("description", "")),
                "url":         item.get("link", ""),
            }
            for item in resp.json().get("items", [])
        ]
    except Exception as e:
        print(f"  ⚠️  네이버 뉴스 API 실패: {e}")
        return []


def _search_naver_rss(topic, max_results):
    try:
        url  = f"https://news.naver.com/search/results.nhn?query={quote(topic)}&type=1"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for item in soup.select(".news_area")[:max_results]:
            title_tag = item.select_one(".news_tit")
            desc_tag  = item.select_one(".dsc_wrap")
            if title_tag:
                results.append({
                    "title":       title_tag.get_text(strip=True),
                    "description": desc_tag.get_text(strip=True) if desc_tag else "",
                    "url":         title_tag.get("href", ""),
                })
        return results
    except Exception as e:
        print(f"  ⚠️  네이버 RSS 실패: {e}")
        return []


def _search_google(topic, api_key, cse_id, max_results):
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cse_id, "q": topic,
                    "num": max_results, "gl": "kr", "lr": "lang_ko"},
            timeout=10,
        )
        resp.raise_for_status()
        return [{"title": i.get("title",""), "snippet": i.get("snippet",""), "url": i.get("link","")}
                for i in resp.json().get("items", [])]
    except Exception as e:
        print(f"  ⚠️  Google CSE 실패: {e}")
        return []


def _search_bing(topic, api_key, max_results):
    try:
        resp = requests.get(
            "https://api.bing.microsoft.com/v7.0/search",
            headers={"Ocp-Apim-Subscription-Key": api_key},
            params={"q": topic, "count": max_results, "mkt": "ko-KR"},
            timeout=10,
        )
        resp.raise_for_status()
        return [{"title": i.get("name",""), "snippet": i.get("snippet",""), "url": i.get("url","")}
                for i in resp.json().get("webPages", {}).get("value", [])]
    except Exception as e:
        print(f"  ⚠️  Bing 검색 실패: {e}")
        return []


def _build_combined_text(topic, news, web):
    parts = [f"[주제]\n{topic}\n"]
    if news:
        parts.append("[뉴스]")
        for i, n in enumerate(news[:5], 1):
            parts.append(f"{i}. {n['title']}")
            if n.get("description"):
                parts.append(f"   {n['description'][:150]}")
    if web:
        parts.append("\n[웹 검색 결과]")
        for i, w in enumerate(web[:5], 1):
            parts.append(f"{i}. {w['title']}")
            if w.get("snippet"):
                parts.append(f"   {w['snippet'][:150]}")
    return "\n".join(parts)
