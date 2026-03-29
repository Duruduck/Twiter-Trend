"""
image_fetcher.py
주제 키워드 → 관련 이미지 자동 수집

우선순위:
  1. Bing Image Search API  (BING_IMAGE_KEY 있을 때, 월 1,000건 무료)
  2. Google Custom Search   (GOOGLE_CSE_KEY + GOOGLE_CSE_ID 있을 때, 일 100건 무료)
  3. URL의 og:image 썸네일 (URL 입력일 때)
  4. Pexels 스톡 이미지    (PEXELS_API_KEY 있을 때)
  5. 폴백 없음 → None 반환 (색상 배경 사용)
"""
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ─── 공개 API ────────────────────────────────────────────────

def fetch_image(
    keywords: list,
    output_dir: Path,
    source_url: str = "",
    pexels_key: str = "",
) -> Path | None:
    """
    키워드로 이미지를 자동 수집해서 output_dir/photo.jpg로 저장.

    Args:
        keywords:   스크립트 keywords 리스트 (예: ['서인영', '유튜브', '복귀'])
        output_dir: 저장 디렉터리
        source_url: 원본 URL (og:image 시도용, 선택)
        pexels_key: Pexels API 키 (선택)

    Returns:
        Path or None
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "photo.jpg"
    query = " ".join(keywords[:3]) if keywords else "news"

    # 1. Bing Image Search
    bing_key = os.environ.get("BING_IMAGE_KEY", "")
    if bing_key:
        path = _fetch_bing(query, dest, bing_key)
        if path:
            print(f"  → 이미지 수집 (Bing): {path.name}")
            return path

    # 2. Google Custom Search
    google_key = os.environ.get("GOOGLE_CSE_KEY", "")
    google_cse = os.environ.get("GOOGLE_CSE_ID", "")
    if google_key and google_cse:
        path = _fetch_google(query, dest, google_key, google_cse)
        if path:
            print(f"  → 이미지 수집 (Google): {path.name}")
            return path

    # 3. og:image (URL 있을 때)
    if source_url and _is_normal_url(source_url):
        path = _fetch_og_image(source_url, dest)
        if path:
            print(f"  → 이미지 수집 (og:image): {path.name}")
            return path

    # 4. Pexels 스톡 이미지
    if pexels_key:
        path = _fetch_pexels_image(query, dest, pexels_key)
        if path:
            print(f"  → 이미지 수집 (Pexels): {path.name}")
            return path

    print("  ⚠️  이미지 수집 실패 — 색상 배경으로 대체")
    return None


# ─── Bing Image Search ───────────────────────────────────────

def _fetch_bing(query: str, dest: Path, api_key: str) -> Path | None:
    """
    Bing Image Search API v7
    https://learn.microsoft.com/en-us/bing/search-apis/bing-image-search
    무료: 월 1,000건 (Azure 계정 필요)
    """
    try:
        resp = requests.get(
            "https://api.bing.microsoft.com/v7.0/images/search",
            headers={"Ocp-Apim-Subscription-Key": api_key},
            params={
                "q": query,
                "count": 5,
                "imageType": "Photo",
                "safeSearch": "Moderate",
                "mkt": "ko-KR",
            },
            timeout=10,
        )
        resp.raise_for_status()
        images = resp.json().get("value", [])
        for img in images:
            url = img.get("contentUrl", "")
            if url and _download_image(url, dest):
                return dest
    except Exception as e:
        print(f"  ⚠️  Bing 오류: {e}")
    return None


# ─── Google Custom Search ────────────────────────────────────

def _fetch_google(query: str, dest: Path, api_key: str, cse_id: str) -> Path | None:
    """
    Google Custom Search JSON API
    https://developers.google.com/custom-search/v1/overview
    무료: 일 100건 (Google Cloud Console 필요)
    """
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cse_id,
                "q": query,
                "searchType": "image",
                "num": 5,
                "gl": "kr",
                "lr": "lang_ko",
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        for item in items:
            url = item.get("link", "")
            if url and _download_image(url, dest):
                return dest
    except Exception as e:
        print(f"  ⚠️  Google CSE 오류: {e}")
    return None


# ─── og:image 추출 ───────────────────────────────────────────

def _fetch_og_image(url: str, dest: Path) -> Path | None:
    """웹페이지 og:image 메타태그에서 대표 이미지 추출."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # og:image → twitter:image → 첫 번째 큰 img 순서로 시도
        candidates = []
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            if prop in ("og:image", "twitter:image"):
                content = tag.get("content", "")
                if content:
                    candidates.append(content)

        # 상대 URL → 절대 URL 변환
        from urllib.parse import urljoin
        candidates = [urljoin(url, c) for c in candidates]

        for img_url in candidates:
            if _download_image(img_url, dest):
                return dest

    except Exception as e:
        print(f"  ⚠️  og:image 오류: {e}")
    return None


# ─── Pexels 스톡 이미지 ──────────────────────────────────────

def _fetch_pexels_image(query: str, dest: Path, api_key: str) -> Path | None:
    """Pexels Photo Search API — 세로형 이미지 우선."""
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={
                "query": query,
                "per_page": 5,
                "orientation": "portrait",
            },
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        for photo in photos:
            url = photo.get("src", {}).get("large", "")
            if url and _download_image(url, dest):
                return dest
    except Exception as e:
        print(f"  ⚠️  Pexels 이미지 오류: {e}")
    return None


# ─── 공통 유틸 ───────────────────────────────────────────────

def _download_image(url: str, dest: Path) -> bool:
    """이미지 URL → 파일 저장. 성공하면 True."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if not any(t in content_type for t in ("image/", "jpeg", "png", "webp")):
            return False

        raw = b"".join(resp.iter_content(chunk_size=8192))
        if len(raw) < 5000:   # 5KB 미만은 아이콘/픽셀 등 제외
            return False

        # webp → jpg 변환 시도 (ffmpeg 사용)
        if "webp" in content_type:
            tmp = dest.with_suffix(".webp")
            tmp.write_bytes(raw)
            import subprocess
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(tmp), str(dest)],
                capture_output=True
            )
            tmp.unlink(missing_ok=True)
            return result.returncode == 0

        dest.write_bytes(raw)
        return True

    except Exception:
        return False


def _is_normal_url(url: str) -> bool:
    """트위터/X URL이 아닌 일반 웹페이지 URL인지 확인."""
    twitter_domains = ("twitter.com", "x.com", "t.co")
    return not any(d in url for d in twitter_domains)
