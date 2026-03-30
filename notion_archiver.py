"""
notion_archiver.py
매일 오후 11시 — 오늘의 트렌드/스크립트/트윗 결과를 Notion에 자동 아카이빙

페이지 구조:
  TwiterTrend (부모 페이지)
  └── 2025-03-30           ← 날짜 제목으로 매일 새 페이지 생성
      ├── 📊 오늘의 트렌드
      │   ├── 타임라인 Top 3
      │   └── 대한민국 트렌딩 Top 3
      ├── 📝 선택된 주제 & 스크립트
      │   ├── hook / body / closer
      │   └── 키워드 / 분위기
      ├── 🐦 트윗 초안
      │   ├── 정보형
      │   ├── 공감형
      │   └── 해시태그형
      └── 🎬 쇼츠 영상
          └── YouTube 링크 (업로드된 경우)

필요:
  NOTION_TOKEN    — Notion Integration Token
  NOTION_PARENT_PAGE_ID — 부모 페이지 ID (TwiterTrend)

설치:
  pip install notion-client

사용법:
  # 직접 실행 (테스트)
  python notion_archiver.py --test

  # 파이프라인에서 자동 호출
  from notion_archiver import archive_daily
  archive_daily(trends, topic, script, tweet_drafts, youtube_url)
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from notion_client import Client

PARENT_PAGE_ID = os.environ.get(
    "NOTION_PARENT_PAGE_ID", "3336d03a-ed91-80e4-82a4-cb1c02f0d9e1"
)


# ─── 공개 API ────────────────────────────────────────────────

def archive_daily(
    trends: dict | None = None,
    topic: str = "",
    script: dict | None = None,
    tweet_drafts: dict | None = None,
    youtube_url: str = "",
    video_path: str = "",
) -> str:
    """
    오늘 날짜 Notion 페이지 생성 후 데이터 채우기.

    반환: 생성된 Notion 페이지 URL
    """
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise ValueError(
            "NOTION_TOKEN 환경변수가 없습니다.\n"
            "Notion Integration Token을 설정해주세요.\n"
            "발급: https://www.notion.so/profile/integrations"
        )

    notion = Client(auth=token)
    today  = datetime.now().strftime("%Y-%m-%d")
    weekday = _weekday_ko()

    print(f"  → Notion 페이지 생성 중: {today}...")

    # 1. 날짜 제목으로 새 페이지 생성
    page = notion.pages.create(
        parent={"page_id": PARENT_PAGE_ID},
        properties={
            "title": {
                "title": [{"type": "text", "text": {"content": f"{today} ({weekday})"}}]
            }
        },
        icon={"type": "emoji", "emoji": "📅"},
    )
    page_id  = page["id"]
    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"

    # 2. 콘텐츠 블록 추가
    blocks = []

    # 트렌드 섹션
    blocks += _build_trends_section(trends)

    # 주제 & 스크립트 섹션
    if topic or script:
        blocks += _build_script_section(topic, script)

    # 트윗 초안 섹션
    if tweet_drafts:
        blocks += _build_tweet_section(tweet_drafts)

    # 쇼츠 영상 섹션
    blocks += _build_video_section(youtube_url, video_path)

    # 블록 추가 (한 번에 최대 100개)
    for i in range(0, len(blocks), 100):
        notion.blocks.children.append(
            block_id=page_id,
            children=blocks[i:i+100],
        )

    print(f"  ✓ Notion 아카이빙 완료: {page_url}")
    return page_url


# ─── 섹션 빌더 ───────────────────────────────────────────────

def _build_trends_section(trends: dict | None) -> list:
    blocks = [
        _heading2("📊 오늘의 트렌드"),
    ]

    if not trends:
        blocks.append(_paragraph("트렌드 데이터 없음"))
        return blocks

    tl  = trends.get("timeline", [])
    ktr = trends.get("trending", [])

    if tl:
        blocks.append(_heading3("🐦 타임라인 Top 3"))
        for t in tl:
            rt  = f"{t.get('rt_count', 0):,}"
            cnt = t.get("tweet_count", 0)
            blocks.append(_bullet(f"{t['rank']}. {t['topic']}  —  RT {rt} | 트윗 {cnt}개"))

    if ktr:
        blocks.append(_heading3("📈 대한민국 트렌딩 Top 3"))
        for t in ktr:
            vol = f"{t.get('tweet_volume', 0):,}" if t.get("tweet_volume") else "—"
            blocks.append(_bullet(f"{t['rank']}. {t['topic']}  —  트윗 {vol}"))

    return blocks


def _build_script_section(topic: str, script: dict | None) -> list:
    blocks = [_heading2("📝 선택된 주제 & 스크립트")]

    if topic:
        blocks.append(_paragraph(f"주제: {topic}"))

    if not script:
        return blocks

    blocks.append(_heading3("스크립트"))
    blocks.append(_bullet(f"Hook: {script.get('hook', '')}"))

    for i, b in enumerate(script.get("body", []), 1):
        blocks.append(_bullet(f"Body {i}: {b}"))

    blocks.append(_bullet(f"Closer: {script.get('closer', '')}"))
    blocks.append(_paragraph(
        f"키워드: {', '.join(script.get('keywords', []))}  |  분위기: {script.get('mood', '')}"
    ))

    return blocks


def _build_tweet_section(tweet_drafts: dict) -> list:
    blocks = [_heading2("🐦 트윗 초안")]

    labels = {"info": "정보형", "emotion": "공감형", "hashtag": "해시태그형"}
    for key, label in labels.items():
        text = tweet_drafts.get(key, "")
        if text:
            blocks.append(_heading3(label))
            blocks.append(_paragraph(text))

    return blocks


def _build_video_section(youtube_url: str, video_path: str) -> list:
    blocks = [_heading2("🎬 쇼츠 영상")]

    if youtube_url:
        blocks.append(_paragraph(f"YouTube: {youtube_url}"))
    elif video_path:
        blocks.append(_paragraph(f"로컬 파일: {video_path}"))
    else:
        blocks.append(_paragraph("영상 없음 (트윗만 생성된 경우)"))

    return blocks


# ─── 블록 헬퍼 ───────────────────────────────────────────────

def _heading2(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _heading3(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


# ─── 유틸 ────────────────────────────────────────────────────

def _weekday_ko() -> str:
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[datetime.now().weekday()]


# ─── CLI 테스트 ───────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Notion 아카이빙 테스트")
    parser.add_argument("--test", action="store_true", help="더미 데이터로 테스트 실행")
    args = parser.parse_args()

    if args.test:
        dummy_trends = {
            "timeline": [
                {"rank": 1, "topic": "서인영 유튜브 복귀", "rt_count": 4200, "tweet_count": 12},
                {"rank": 2, "topic": "갤럭시 S25 언팩",   "rt_count": 3800, "tweet_count": 8},
                {"rank": 3, "topic": "손흥민 해트트릭",   "rt_count": 3100, "tweet_count": 15},
            ],
            "trending": [
                {"rank": 1, "topic": "이재명 판결",    "tweet_volume": 85000},
                {"rank": 2, "topic": "설 연휴 기차표", "tweet_volume": 62000},
                {"rank": 3, "topic": "AI 일자리 대체", "tweet_volume": 41000},
            ],
        }
        dummy_script = {
            "hook":     "서인영이 돌아왔다. 그것도 유튜브로.",
            "body":     ["10년 공백을 깨고 첫 영상 100만뷰", "팬들 반응 둘로 갈렸다"],
            "closer":   "여러분은 어떻게 생각하세요?",
            "keywords": ["서인영", "유튜브복귀", "레전드"],
            "mood":     "dramatic",
        }
        dummy_tweets = {
            "info":    "서인영 유튜브 복귀, 첫 영상 100만뷰 돌파. 역시 레전드.",
            "emotion": "서인영 언니 돌아왔다!! 진짜 기다렸어 🔥",
            "hashtag": "서인영이 돌아왔다 #서인영 #유튜브복귀 #레전드",
        }

        url = archive_daily(
            trends=dummy_trends,
            topic="서인영 유튜브 복귀",
            script=dummy_script,
            tweet_drafts=dummy_tweets,
            youtube_url="",
        )
        print(f"\n✅ 테스트 완료: {url}")
    else:
        print("--test 옵션으로 실행하세요.")
