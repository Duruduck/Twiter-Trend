"""
pipeline.py
트위터 트렌드 수집 → 주제 선택 → 트윗/쇼츠 제작 → 최종 확인 → 업로드

실행:
  python pipeline.py

환경변수 (필수):
  ANTHROPIC_API_KEY
  TWITTER_BEARER_TOKEN

환경변수 (선택):
  TWITTER_API_KEY / SECRET / ACCESS_TOKEN / ACCESS_SECRET  → 트윗 게시
  BING_IMAGE_KEY                                           → 이미지 자동 수집
  PEXELS_API_KEY                                           → 영상/이미지 폴백
  YOUTUBE_CLIENT_SECRETS                                   → 쇼츠 업로드 (추후)
"""
import os
import sys
from pathlib import Path

from content_fetcher import fetch_content
from image_fetcher import fetch_image
from script_generator import generate_script
from tts_generator import generate_tts
from twitter_fetcher import fetch_trends
from twitter_poster import generate_tweet_drafts, post_tweet
from video_assembler import assemble_video
from youtube_uploader import upload_shorts

OUTPUT_DIR = Path("output")


# ─── 메인 파이프라인 ─────────────────────────────────────────

def run():
    OUTPUT_DIR.mkdir(exist_ok=True)
    _print_banner()

    # ── STEP 1: 트렌드 수집 ──────────────────────────────────
    trends = _step_collect_trends()

    # ── STEP 2: 주제 선택 ────────────────────────────────────
    topic = _step_pick_topic(trends)

    # ── STEP 3: 제작 방식 선택 ───────────────────────────────
    action = _step_pick_action()   # "tweet" / "shorts" / "both"

    # ── STEP 4: AI 생성 ──────────────────────────────────────
    script, tweet_drafts, image_path, tts_path, video_path = \
        _step_generate(topic, action)

    # ── STEP 5: 최종 확인 + 수정 루프 ────────────────────────
    script, tweet_drafts, chosen_tweet = \
        _step_review(topic, action, script, tweet_drafts, image_path)

    # ── STEP 6: 업로드 ───────────────────────────────────────
    _step_upload(action, chosen_tweet, video_path, topic)


# ─── STEP 1: 트렌드 수집 ─────────────────────────────────────

def _step_collect_trends() -> dict:
    print("\n" + "─" * 52)
    print(" [1/6] 트렌드 수집 중...")
    print("─" * 52)

    while True:
        try:
            trends = fetch_trends()
            _print_trends(trends)
            return trends
        except ValueError as e:
            _err(str(e))
            sys.exit(1)
        except Exception as e:
            _err(f"수집 실패: {e}")
            if _ask("다시 시도할까요? (y/n): ") == "y":
                continue
            sys.exit(1)


def _print_trends(trends: dict):
    tl  = trends.get("timeline", [])
    ktr = trends.get("trending", [])

    print("\n  [ 내 팔로워 타임라인 Top 3 ]")
    if tl:
        for t in tl:
            print(f"   {t['rank']}. {t['topic']:<28}  RT {t['rt_count']:,}")
    else:
        print("   (타임라인 데이터 없음)")

    print("\n  [ 대한민국 전체 트렌딩 Top 3 ]")
    if ktr:
        for t in ktr:
            vol = f"{t['tweet_volume']:,}" if t.get("tweet_volume") else "—"
            print(f"   {t['rank'] + len(tl)}. {t['topic']:<28}  트윗 {vol}")
    else:
        print("   (트렌딩 데이터 없음)")


# ─── STEP 2: 주제 선택 ───────────────────────────────────────

def _step_pick_topic(trends: dict) -> str:
    tl  = trends.get("timeline", [])
    ktr = trends.get("trending", [])
    all_topics = [t["topic"] for t in tl] + [t["topic"] for t in ktr]

    print("\n" + "─" * 52)
    print(" [2/6] 주제를 선택하세요")
    print("─" * 52)
    print("  번호 입력 → 해당 주제 선택")
    print("  d         → 직접 입력")
    print("  r         → 트렌드 다시 수집")
    print()

    while True:
        raw = _ask("  선택: ").strip().lower()

        if raw == "r":
            return None  # 재수집은 run()에서 처리하지 않고 직접 루프
        if raw == "d":
            topic = _ask("  주제 직접 입력: ").strip()
            if topic:
                print(f"\n  ✓ 선택된 주제: {topic}")
                return topic
            continue

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(all_topics):
                topic = all_topics[idx]
                print(f"\n  ✓ 선택된 주제: {topic}")
                return topic
        except ValueError:
            pass

        print("  올바른 번호 또는 d/r을 입력하세요.")


# ─── STEP 3: 제작 방식 선택 ──────────────────────────────────

def _step_pick_action() -> str:
    print("\n" + "─" * 52)
    print(" [3/6] 무엇을 만들까요?")
    print("─" * 52)
    print("  1. 트윗만 작성")
    print("  2. 쇼츠만 제작")
    print("  3. 트윗 + 쇼츠 둘 다")
    print()

    while True:
        raw = _ask("  선택 (1/2/3): ").strip()
        if raw == "1": return "tweet"
        if raw == "2": return "shorts"
        if raw == "3": return "both"
        print("  1, 2, 3 중 하나를 입력하세요.")


# ─── STEP 4: AI 생성 ─────────────────────────────────────────

def _step_generate(topic: str, action: str):
    print("\n" + "─" * 52)
    print(" [4/6] AI 콘텐츠 생성 중...")
    print("─" * 52)

    content = {"title": topic, "text": topic, "source": "direct"}

    # 스크립트 생성 (트윗/쇼츠 모두 필요)
    print("  → 스크립트 생성 중...")
    script = generate_script(content)

    # 트윗 초안
    tweet_drafts = None
    if action in ("tweet", "both"):
        print("  → 트윗 초안 생성 중...")
        tweet_drafts = generate_tweet_drafts(topic, script)

    # 쇼츠 제작 (이미지 + TTS + 영상)
    image_path = tts_path = video_path = None
    if action in ("shorts", "both"):
        print("  → 이미지 수집 중...")
        image_path = fetch_image(
            keywords=script.get("keywords", []),
            output_dir=OUTPUT_DIR,
            pexels_key=os.environ.get("PEXELS_API_KEY", ""),
        )

        print("  → TTS 음성 생성 중...")
        tts_path = generate_tts(script, OUTPUT_DIR)

        print("  → 영상 조립 중...")
        video_path = assemble_video(
            script=script,
            tts_path=tts_path,
            output_path=OUTPUT_DIR / "shorts.mp4",
            image_path=image_path,
            pexels_key=os.environ.get("PEXELS_API_KEY", ""),
        )

    print("  ✓ 생성 완료!")
    return script, tweet_drafts, image_path, tts_path, video_path


# ─── STEP 5: 최종 확인 + 수정 루프 ──────────────────────────

def _step_review(topic, action, script, tweet_drafts, image_path):
    chosen_tweet = None

    while True:
        print("\n" + "─" * 52)
        print(" [5/6] 최종 확인")
        print("─" * 52)

        # 스크립트 출력
        print("\n  [ 쇼츠 스크립트 ]")
        print(f"  Hook  : {script['hook']}")
        for i, b in enumerate(script.get('body', []), 1):
            print(f"  Body {i}: {b}")
        print(f"  Closer: {script['closer']}")

        # 트윗 초안 출력
        if tweet_drafts:
            print("\n  [ 트윗 초안 ]")
            items = [
                ("1", "정보형",   tweet_drafts.get("info", "")),
                ("2", "공감형",   tweet_drafts.get("emotion", "")),
                ("3", "해시태그형", tweet_drafts.get("hashtag", "")),
            ]
            for num, label, text in items:
                print(f"  [{num}] {label}")
                print(f"      {text}")
                print(f"      ({len(text)}자)")

        # 이미지/영상 경로
        if action in ("shorts", "both"):
            mp4 = OUTPUT_DIR / "shorts.mp4"
            print(f"\n  [ 쇼츠 영상 ]")
            print(f"  파일: {mp4} ({'존재' if mp4.exists() else '없음'})")
            if image_path:
                print(f"  사진: {image_path}")

        # 선택지 출력
        print("\n  ─────────────────────────────────")
        if tweet_drafts:
            print("  tw1 / tw2 / tw3  — 트윗 버전 선택")
        print("  s:훅 수정내용   — 스크립트 hook 수정 (예: s:더 강렬하게)")
        print("  t:수정내용      — 트윗 재생성 (예: t:더 재미있게)")
        print("  ok              — 이대로 업로드 진행")
        print("  q               — 종료")
        print()

        raw = _ask("  입력: ").strip().lower()

        if raw == "ok":
            # 트윗 버전 미선택 시 자동으로 공감형(2번) 선택
            if tweet_drafts and chosen_tweet is None:
                chosen_tweet = tweet_drafts.get("emotion", "")
                print(f"  (트윗 버전 미선택 → 공감형 자동 선택)")
            break

        elif raw == "q":
            print("  종료합니다.")
            sys.exit(0)

        elif tweet_drafts and raw in ("tw1", "tw2", "tw3"):
            key = {"tw1": "info", "tw2": "emotion", "tw3": "hashtag"}[raw]
            chosen_tweet = tweet_drafts[key]
            print(f"  ✓ 트윗 선택: {chosen_tweet}")

        elif raw.startswith("s:"):
            instruction = raw[2:].strip()
            print(f"  → 스크립트 재생성 중 ({instruction})...")
            content = {
                "title": topic,
                "text": f"{topic}. 지시사항: {instruction}",
                "source": "direct",
            }
            script = generate_script(content)
            if tweet_drafts:
                tweet_drafts = generate_tweet_drafts(topic, script)
            print("  ✓ 재생성 완료")

        elif raw.startswith("t:"):
            if not tweet_drafts:
                print("  트윗 모드가 아닙니다.")
                continue
            instruction = raw[2:].strip()
            print(f"  → 트윗 재생성 중 ({instruction})...")
            # 기존 스크립트에 지시사항 반영
            modified_script = dict(script)
            modified_script["hook"] = f"{script['hook']} ({instruction})"
            tweet_drafts = generate_tweet_drafts(topic, modified_script)
            print("  ✓ 재생성 완료")

        else:
            print("  올바른 명령을 입력하세요.")

    return script, tweet_drafts, chosen_tweet


# ─── STEP 6: 업로드 ──────────────────────────────────────────

def _step_upload(action: str, chosen_tweet: str | None, video_path: Path | None, topic: str):
    print("\n" + "─" * 52)
    print(" [6/6] 업로드")
    print("─" * 52)

    # 트윗 게시
    if action in ("tweet", "both") and chosen_tweet:
        print(f"\n  트윗 게시 예정:\n  {chosen_tweet}\n")
        if _ask("  트윗 게시할까요? (y/n): ").strip().lower() == "y":
            try:
                result = post_tweet(chosen_tweet)
                print(f"  ✓ 트윗 게시 완료: {result['url']}")
            except Exception as e:
                _err(f"트윗 게시 실패: {e}")
        else:
            print("  트윗 게시 건너뜀.")

    # 쇼츠 업로드 (YouTube Data API v3)
    if action in ("shorts", "both") and video_path and video_path.exists():
        print(f"\n  쇼츠 파일: {video_path}")
        secrets = Path(os.environ.get("YOUTUBE_CLIENT_SECRETS", "config/client_secrets.json"))
        if not secrets.exists():
            print("  ℹ️  client_secrets.json 없음 → 로컬 저장만")
            print(f"  ✓ 쇼츠 저장 완료: {video_path.resolve()}")
        else:
            if _ask("  YouTube에 업로드할까요? (y/n): ").strip().lower() == "y":
                privacy = _ask("  공개 범위 (public/unlisted/private) [기본: public]: ").strip()
                if privacy not in ("public", "unlisted", "private"):
                    privacy = "public"
                try:
                    result = upload_shorts(
                        video_path=video_path,
                        title=topic,
                        tags=script.get("keywords", []),
                        privacy=privacy,
                    )
                    print(f"  ✓ YouTube 업로드 완료: {result['url']}")
                except Exception as e:
                    _err(f"YouTube 업로드 실패: {e}")
                    print(f"  파일은 로컬에 저장됨: {video_path.resolve()}")
            else:
                print(f"  업로드 건너뜀. 파일: {video_path.resolve()}")

    print("\n  ✅ 파이프라인 완료!")


# ─── 유틸 ────────────────────────────────────────────────────

def _ask(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n  중단됨.")
        sys.exit(0)


def _err(msg: str):
    print(f"\n  ⚠️  {msg}")


def _print_banner():
    print("\n" + "=" * 52)
    print("  Shorts & Tweet 자동화 파이프라인")
    print("=" * 52)


if __name__ == "__main__":
    run()
