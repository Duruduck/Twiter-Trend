"""
content_fetcher.py
URL → 제목 + 본문 텍스트 추출
지원: 일반 웹페이지, 뉴스, 블로그 (BeautifulSoup)
"""
import re
import requests
from bs4 import BeautifulSoup


TWITTER_DOMAINS = ("twitter.com", "x.com", "t.co")


def _is_twitter_url(url: str) -> bool:
    return any(d in url for d in TWITTER_DOMAINS)


def _prompt_twitter_text(url: str) -> dict:
    """트위터 URL 감지 시 사용자에게 텍스트 직접 입력 요청."""
    print("\n" + "─" * 50)
    print("🐦 트위터/X URL이 감지됐어요.")
    print("   로그인 없이는 트윗 내용을 가져올 수 없어서,")
    print("   트윗 텍스트를 직접 붙여넣어 주세요.")
    print("─" * 50)
    print("트윗 내용 입력 후 Enter 두 번:")

    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)

    text = " ".join(lines).strip()
    if not text:
        print("⚠️  내용이 없어서 URL을 주제로 사용합니다.")
        text = url

    return {"title": text[:50], "text": text, "source": url}


def fetch_content(url: str) -> dict:
    """
    URL에서 제목 + 본문 텍스트 추출.
    트위터/X URL은 텍스트 직접 입력으로 처리.
    반환: {title, text, source}
    """
    if _is_twitter_url(url):
        return _prompt_twitter_text(url)

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding

        soup = BeautifulSoup(resp.text, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "advertisement", "iframe"]):
            tag.decompose()

        # 제목 추출
        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        # 본문 추출 (article 우선, 없으면 body 전체)
        article = soup.find("article") or soup.find("main") or soup.find("body")
        text = article.get_text(separator=" ", strip=True) if article else ""

        # 공백 정리
        text = re.sub(r"\s+", " ", text).strip()

        # 토큰 절약: 3000자로 제한
        if len(text) > 3000:
            text = text[:3000] + "..."

        return {"title": title or url, "text": text, "source": url}

    except Exception as e:
        print(f"  ⚠️  URL 수집 실패: {e} — URL을 주제로 대체합니다.")
        return {"title": url, "text": url, "source": url}
