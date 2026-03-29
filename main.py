"""
shorts-maker / main.py
사용법:
  python main.py --topic "서인영 유튜브 복귀"
  python main.py --url "https://n.news.naver.com/article/..."
  python main.py --topic "..." --bing-key "YOUR_KEY"
  python main.py --topic "..." --dry-run
"""
import argparse
import os
import sys
from pathlib import Path

from content_fetcher import fetch_content
from image_fetcher import fetch_image
from script_generator import generate_script
from tts_generator import generate_tts
from video_assembler import assemble_video


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts 자동 제작")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url",        type=str, help="블로그/뉴스 URL")
    group.add_argument("--topic",      type=str, help="직접 주제 입력")
    parser.add_argument("--bing-key",  type=str, default=os.environ.get("BING_IMAGE_KEY", ""),
                        help="Bing Image Search API 키 (권장, 월 1,000건 무료)")
    parser.add_argument("--google-key",type=str, default=os.environ.get("GOOGLE_CSE_KEY", ""),
                        help="Google Custom Search API 키")
    parser.add_argument("--google-cse",type=str, default=os.environ.get("GOOGLE_CSE_ID", ""),
                        help="Google CSE ID")
    parser.add_argument("--pexels-key",type=str, default=os.environ.get("PEXELS_API_KEY", ""),
                        help="Pexels API 키 (이미지/영상 폴백)")
    parser.add_argument("--output",    type=str, default="output/shorts.mp4")
    parser.add_argument("--dry-run",   action="store_true", help="스크립트만 확인, 영상 미생성")
    args = parser.parse_args()

    # 환경변수 덮어쓰기 (--key 옵션 우선)
    if args.bing_key:
        os.environ["BING_IMAGE_KEY"] = args.bing_key
    if args.google_key:
        os.environ["GOOGLE_CSE_KEY"] = args.google_key
    if args.google_cse:
        os.environ["GOOGLE_CSE_ID"] = args.google_cse

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # ── STEP 1: 콘텐츠 수집 ──────────────────────────────────
    print("\n[1/5] 콘텐츠 수집 중...")
    if args.url:
        content = fetch_content(args.url)
        print(f"  → 제목: {content['title']}")
        print(f"  → 본문: {len(content['text'])}자 수집")
    else:
        content = {"title": args.topic, "text": args.topic, "source": "direct"}
        print(f"  → 주제: {args.topic}")

    # ── STEP 2: 스크립트 생성 ────────────────────────────────
    print("\n[2/5] AI 스크립트 생성 중...")
    script = generate_script(content)
    print(f"  → Hook    : {script['hook']}")
    print(f"  → Body    : {' / '.join(script['body'])}")
    print(f"  → Closer  : {script['closer']}")
    print(f"  → 키워드  : {', '.join(script['keywords'])}")
    print(f"  → 분위기  : {script['mood']}")

    if args.dry_run:
        print("\n[dry-run] 스크립트 확인 완료. 영상 생성 생략.")
        return

    # ── STEP 3: 이미지 수집 ──────────────────────────────────
    print("\n[3/5] 이미지 수집 중...")
    image_path = fetch_image(
        keywords=script.get("keywords", []),
        output_dir=output_dir,
        source_url=content.get("source", ""),
        pexels_key=args.pexels_key,
    )
    if image_path:
        print(f"  → 이미지: {image_path}")
    else:
        print("  → 이미지 없음 — 색상 배경 사용")

    # ── STEP 4: TTS 음성 생성 ────────────────────────────────
    print("\n[4/5] 음성(TTS) 생성 중...")
    tts_path = generate_tts(script, output_dir)
    print(f"  → 음성: {tts_path}")

    # ── STEP 5: 영상 조립 ────────────────────────────────────
    print("\n[5/5] 영상 조립 중 (FFmpeg)...")
    video_path = assemble_video(
        script=script,
        tts_path=tts_path,
        output_path=Path(args.output),
        image_path=image_path,
        pexels_key=args.pexels_key,
    )
    print(f"\n✅ 완성! → {video_path}")


if __name__ == "__main__":
    main()
