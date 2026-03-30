"""
scheduler.py
매일 오후 11시에 트렌드 수집 → Notion 아카이빙 자동 실행

실행:
  python scheduler.py          # 백그라운드 상시 실행
  python scheduler.py --now    # 지금 당장 한 번 실행 (테스트)
"""
import argparse
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import schedule

from content_fetcher import fetch_topic_context
from notion_archiver import archive_daily
from script_generator import generate_rich_script
from twitter_fetcher import fetch_trends

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ─── 메인 작업 ───────────────────────────────────────────────

def daily_archive():
    """매일 오후 11시 자동 실행: 트렌드 수집 → 스크립트 생성 → Notion 아카이빙."""
    logger.info("=" * 52)
    logger.info(f"일별 아카이빙 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 52)

    try:
        # 1. 트렌드 수집
        logger.info("[1/3] 트렌드 수집 중...")
        try:
            trends = fetch_trends()
            tl  = trends.get("timeline", [])
            ktr = trends.get("trending", [])
            logger.info(f"  타임라인 {len(tl)}개 / 트렌딩 {len(ktr)}개 수집")
        except Exception as e:
            logger.warning(f"  트렌드 수집 실패: {e} — 빈 데이터로 진행")
            trends = {"timeline": [], "trending": []}

        # 2. 가장 인기 있는 주제로 스크립트 생성 (선택사항)
        topic  = ""
        script = None
        all_topics = ([t["topic"] for t in trends.get("timeline", [])] +
                      [t["topic"] for t in trends.get("trending", [])])

        if all_topics:
            topic = all_topics[0]
            logger.info(f"[2/3] 스크립트 생성 중: {topic}")
            try:
                news_ctx = fetch_topic_context(topic)
                script   = generate_rich_script(
                    topic=topic,
                    context={"twitter": None, "news": news_ctx},
                )
                logger.info("  스크립트 생성 완료")
            except Exception as e:
                logger.warning(f"  스크립트 생성 실패: {e}")
        else:
            logger.info("[2/3] 주제 없음 — 스크립트 생략")

        # 3. Notion 아카이빙
        logger.info("[3/3] Notion 아카이빙 중...")
        url = archive_daily(
            trends=trends,
            topic=topic,
            script=script,
            tweet_drafts=None,   # 자동 실행 시 트윗 초안 생략 (원하면 추가 가능)
            youtube_url="",
        )
        logger.info(f"  완료: {url}")
        logger.info("=" * 52)
        return url

    except Exception as e:
        logger.error(f"아카이빙 실패: {e}")
        return ""


# ─── 스케줄러 ────────────────────────────────────────────────

def run_scheduler():
    """매일 오후 11시에 daily_archive 실행."""
    run_time = os.environ.get("ARCHIVE_TIME", "23:00")
    schedule.every().day.at(run_time).do(daily_archive)
    logger.info(f"스케줄러 시작 — 매일 {run_time}에 Notion 아카이빙 실행")
    logger.info("종료: Ctrl+C")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ─── CLI ─────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Notion 자동 아카이빙 스케줄러")
    parser.add_argument("--now", action="store_true", help="지금 바로 1회 실행")
    parser.add_argument("--time", type=str, default="", help="실행 시각 (예: 23:00)")
    args = parser.parse_args()

    if args.time:
        os.environ["ARCHIVE_TIME"] = args.time

    if args.now:
        url = daily_archive()
        if url:
            print(f"\n✅ 완료: {url}")
    else:
        run_scheduler()
