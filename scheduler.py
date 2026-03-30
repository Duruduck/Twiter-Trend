"""
scheduler.py
매일 오후 11시 자동 실행 스케줄러

실행:
  python scheduler.py

환경변수:
  ARCHIVE_TIME  — 실행 시간 (HH:MM, 기본: 23:00)

대안 (cron 사용 시):
  0 23 * * * cd /path/to/project && python notion_archiver.py
"""
import os
import time
from datetime import datetime


def run_scheduler():
    archive_time = os.environ.get("ARCHIVE_TIME", "23:00")
    print(f"🕒 스케줄러 시작 — 매일 {archive_time}에 Notion 아카이브 실행")
    print("중단: Ctrl+C\n")

    while True:
        now = datetime.now().strftime("%H:%M")
        if now == archive_time:
            print(f"\n[🔔 {datetime.now().strftime('%Y-%m-%d %H:%M')}] Notion 아카이브 실행 중...")
            try:
                from notion_archiver import main
                main()
            except Exception as e:
                print(f"  ⚠️  실패: {e}")
            time.sleep(61)  # 1분 대기 (중복 실행 방지)
        else:
            time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
