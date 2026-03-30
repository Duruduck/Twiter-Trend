"""
notion_archiver.py
매일 오후 11시 자동 실행:
  트렌드 수집 + AI 스크립트 생성 → Notion 에 날짜 제목 페이지로 아카이븍

사용법:
  python notion_archiver.py              — 즉시 실행 (오늘 날짜 페이지 생성)
  python notion_archiver.py --date 2025-03-30  — 특정 날짜로 생성

필요 환경변수:
  NOTION_TOKEN          — Notion Integration 토큰 (https://www.notion.so/my-integrations)
  NOTION_PARENT_PAGE_ID — 상위 페이지 ID (TwiterTrend 페이지 ID)
  ANTHROPIC_API_KEY     — 스크립트 생성
  TWITTER_BEARER_TOKEN  — 트렌드 수집
"""
import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests

# 파이프라인 모듈 로드 (pipeline.py 와 같은 디렉토리에 있어야 함)
sys.path.insert(0, str(Path(__file__).parent))


# ═══════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Notion 일일 트렌드 아카이브")
    parser.add_argument("--date", type=str, default="",
                        help="아카이브 날짜 (YYYY-MM-DD, 기본: 오늘)")
    args = parser.parse_args()

    target_date = args.date or date.today().strftime("%Y-%m-%d")
    print(f"\n🗓️  Notion 아카이브 시작 — {target_date}")

    # 환경변수 확인
    notion_token = os.environ.get("NOTION_TOKEN", "")
    parent_id    = os.environ.get("NOTION_PARENT_PAGE_ID", "3336d03aed9180e482a4cb1c02f0d9e1")

    if not notion_token:
        print("⚠️  NOTION_TOKEN 환경변수가 없습니다.")
        print("   https://www.notion.so/my-integrations 에서 토큰을 발급하세요.")
        sys.exit(1)

    # 트렌드 수집
    print("\n[1/3] 트렌드 수집 중...")
    trends    = _fetch_trends_safe()
    timeline  = trends.get("timeline", [])
    trending  = trends.get("trending", [])

    # 스크립트 생성 (킸 주제 선택)
    print("\n[2/3] AI 스크립트 생성 중...")
    top_topic  = (timeline + trending)[0]["topic"] if (timeline or trending) else ""
    script     = _generate_script_safe(top_topic)

    # Notion 페이지 생성
    print("\n[3/3] Notion 페이지 생성 중...")
    page_url = create_daily_page(
        notion_token=notion_token,
        parent_id=parent_id,
        target_date=target_date,
        timeline=timeline,
        trending=trending,
        script=script,
        top_topic=top_topic,
    )
    print(f"\n✅ 아카이브 완료 → {page_url}")


# ═══════════════════════════════════════════════════════════
# Notion 페이지 생성
# ═══════════════════════════════════════════════════════════

def create_daily_page(
    notion_token: str,
    parent_id: str,
    target_date: str,
    timeline: list,
    trending: list,
    script: dict,
    top_topic: str,
) -> str:
    """
    Notion에 날짜 제목 페이지 생성.
    반환: 생성된 페이지 URL
    """
    headers = {
        "Authorization":  f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type":   "application/json",
    }

    # 페이지 제목 (YYYY-MM-DD 요일)
    dt       = datetime.strptime(target_date, "%Y-%m-%d")
    weekdays = ["(Mon)", "(Tue)", "(Wed)", "(Thu)", "(Fri)", "(Sat)", "(Sun)"]
    title    = f"{target_date} {weekdays[dt.weekday()]}"

    # 페이지 콘텐츠 블록 조립
    children = [
        # 타임라인 트렌드
        _heading2("🐦  내 팔로워 타임라인 Top 3"),
    ]
    if timeline:
        for t in timeline:
            children.append(_bullet(
                f"{t['rank']}. {t['topic']}  —  RT {t.get('rt_count', 0):,}  |"
                f"  트윗 {t.get('tweet_count', 0)}개"
            ))
    else:
        children.append(_bullet("(데이터 없음)"))

    children.append(_heading2("📈  대한민국 트렌딩 Top 3"))
    if trending:
        for t in trending:
            vol = f"{t.get('tweet_volume', 0):,}" if t.get("tweet_volume") else "—"
            children.append(_bullet(f"{t['rank']}. {t['topic']}  —  트윗 {vol}"))
    else:
        children.append(_bullet("(데이터 없음)"))

    # 주제 & 스크립트
    children.append(_heading2("📝  오늘의 주제 & 스크립트"))
    if top_topic:
        children.append(_paragraph(f"🎯 주제: {top_topic}"))
    if script:
        children.append(_paragraph(f"🎣 Hook: {script.get('hook', '')}"))
        body = script.get("body", [])
        for i, b in enumerate(body, 1):
            children.append(_bullet(f"Body {i}: {b}"))
        children.append(_paragraph(f"💬 Closer: {script.get('closer', '')}"))
        kws = ", ".join(f"#{k}" for k in script.get("keywords", []))
        if kws:
            children.append(_paragraph(f"🏷️ {kws}"))
    else:
        children.append(_paragraph("(스크립트 없음)"))

    # 쇼츠/트윗 결과 섹션 (파이프라인 실행 후 나중에 채울 수 있도록)
    children.append(_heading2("🎬  오늘의 쇼츠"))
    children.append(_paragraph("(파이프라인 실행 후 YouTube URL이 여기에 기록됩니다)"))

    children.append(_heading2("🐦  오늘의 트윗"))
    children.append(_paragraph("(파이프라인 실행 후 게시된 트윗 URL이 여기에 기록됩니다)"))

    # Notion API 호출
    payload = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
        "children": children,
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json=payload,
        timeout=15,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Notion 페이지 생성 실패: {resp.status_code} {resp.text[:200]}")

    page_id  = resp.json()["id"]
    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
    return page_url


def append_to_daily_page(
    notion_token: str,
    page_id: str,
    section: str,
    content: str,
):
    """
    이미 생성된 날짜 페이지에 크영 또는 ?어 URL 추가.
    pipeline.py 이 upload 후에 호출.

    Args:
        page_id:  날짜 페이지 ID
        section:  'youtube' 또는 'tweet'
        content:  추가할 URL 또는 텍스트
    """
    headers = {
        "Authorization":  f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type":   "application/json",
    }
    emoji = "🎬" if section == "youtube" else "🐦"
    block = {
        "children": [
            _paragraph(f"{emoji} {content}")
        ]
    }
    resp = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=headers,
        json=block,
        timeout=10,
    )
    return resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# 블록 헬퍼
# ═══════════════════════════════════════════════════════════

def _heading2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


# ═══════════════════════════════════════════════════════════
# 파이프라인 연동 헬퍼
# ═══════════════════════════════════════════════════════════

def _fetch_trends_safe() -> dict:
    """Bearer Token 없으면 빈 dict 반환."""
    try:
        from twitter_fetcher import fetch_trends
        return fetch_trends()
    except Exception as e:
        print(f"  ⚠️  트렌드 수집 실패: {e}")
        return {"timeline": [], "trending": []}


def _generate_script_safe(topic: str) -> dict:
    """API 키 없으면 빈 dict 반환."""
    if not topic:
        return {}
    try:
        from content_fetcher import fetch_topic_context
        from script_generator import generate_rich_script
        news_ctx = fetch_topic_context(topic)
        return generate_rich_script(topic=topic, context={"news": news_ctx})
    except Exception as e:
        print(f"  ⚠️  스크립트 생성 실패: {e}")
        return {}


if __name__ == "__main__":
    main()
