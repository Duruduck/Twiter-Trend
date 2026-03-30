"""
pipeline.py
트위터 트렌드 수집 → 주제 선택 → 트윗/쇼츠 제작 → 최종 확인 → 업로드

실행:
  python pipeline.py
  python pipeline.py --url "https://blog.naver.com/..."
  python pipeline.py --url "https://x.com/..."
  python pipeline.py --topic "주제 직접 입력"
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 없으면 환경변수 직접 설정 필요

from content_fetcher import fetch_content, fetch_topic_context
from image_fetcher import fetch_image
from script_generator import generate_script, generate_rich_script
from tts_generator import generate_tts
from twitter_fetcher import fetch_trends, fetch_tweet_context
from twitter_poster import generate_tweet_drafts, post_tweet
from video_assembler import assemble_video
from youtube_uploader import upload_shorts

OUTPUT_DIR = Path("output")


def run():
    import argparse
    parser = argparse.ArgumentParser(description="Shorts & Tweet 자동화 파이프라인")
    parser.add_argument("--url",   type=str, default="", help="URL 직접 입력 (블로그/뉴스/X)")
    parser.add_argument("--topic", type=str, default="", help="주제 직접 입력")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    _print_banner()

    if args.url:
        print("\n" + "─" * 52)
        print(" [1/6] URL 콘텐츠 수집 중...")
        print("─" * 52)

        TWITTER_DOMAINS = ("twitter.com", "x.com", "t.co")
        is_twitter = any(d in args.url for d in TWITTER_DOMAINS)

        if is_twitter:
            print(f"  URL: {args.url}")
            print()
            print("  트위터 API 없이 동작하려면 트윗 내용을 붙여넣어 주세요.")
            print("  (입력 후 빈 줄에서 Enter)")
            print()
            lines = []
            while True:
                try:
                    line = input("  > ")
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if line == "" and lines:
                    break
                lines.append(line)
            tweet_text = " ".join(lines).strip()
            if not tweet_text:
                _err("트윗 내용이 없습니다.")
                sys.exit(1)

            import re as _re
            words = _re.findall(r"[가-힣A-Za-z]{2,}", tweet_text)
            stopwords = {"RT","the","and","for","that","this","있다","없다","한다","됩니다","합니다","입니다","것이","이번","오늘","지금","https","http","com","www"}
            keywords = [w for w in words if w not in stopwords][:5]
            topic = " ".join(keywords[:3]) if keywords else tweet_text[:30]

            content = {
                "title":  topic,
                "text":   tweet_text,
                "source": args.url,
                "twitter_context": {
                    "original":     {"text": tweet_text},
                    "quote_tweets": [],
                    "related":      [],
                    "summary": {
                        "topic":          topic,
                        "combined_text":  f"[원본 트윗]\n{tweet_text}",
                        "sentiment_hint": "",
                    },
                },
            }
            print(f"\n  ✓ 주제: {topic}")

        else:
            # 일반 URL (네이버 블로그, 뉴스 등) → 자동 크롤링
            print(f"  → URL 본문 수집 중: {args.url}")
            try:
                content   = fetch_content(args.url)
                body_text = content.get("text", "")
                title     = content.get("title", "")
                import re as _re
                # 본문 앞 500자에서 키워드 추출 (제목보다 본문이 더 정확)
                source_text = body_text[:500] if body_text else title
                words = _re.findall(r"[가-힣]{2,}", source_text)
                stopwords = {"있다","없다","한다","됩니다","합니다","입니다","것이","이번","오늘",
                             "지금","그리고","하지만","그래서","때문","이후","이전","관련","블로그",
                             "네이버","포스팅","내용","글쓴","작성","공유","댓글","좋아요","구독"}
                keywords = []
                seen = set()
                for w in words:
                    if w not in stopwords and w not in seen:
                        keywords.append(w)
                        seen.add(w)
                    if len(keywords) >= 4:
                        break
                topic = " ".join(keywords) if keywords else title
                content["title"] = topic
                print(f"  ✓ 제목: {title}")
                print(f"  ✓ 본문: {len(body_text)}자 수집")
                print(f"  ✓ 추출 키워드: {topic}")
            except Exception as e:
                _err(f"URL 수집 실패: {e}")
                sys.exit(1)

    elif args.topic:
        topic   = args.topic
        content = {"title": topic, "text": topic, "source": "direct"}
        print(f"\n  → 주제: {topic}")

    else:
        trends  = _step_collect_trends()
        topic   = _step_pick_topic(trends)
        content = {"title": topic, "text": topic, "source": "trend"}

    action = _step_pick_action()

    script, tweet_drafts, image_path, tts_path, video_path = \
        _step_generate(topic, action, content)

    script, tweet_drafts, chosen_tweet = \
        _step_review(topic, action, script, tweet_drafts, image_path)

    _step_upload(action, chosen_tweet, video_path, topic)


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
            _err(str(e)); sys.exit(1)
        except Exception as e:
            _err(f"수집 실패: {e}")
            if _ask("다시 시도할까요? (y/n): ") == "y": continue
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
            vol = f"{t['tweet_volume']:,}" if t.get("tweet_volume") else "─"
            print(f"   {t['rank'] + len(tl)}. {t['topic']:<28}  트윗 {vol}")
    else:
        print("   (트렌딩 데이터 없음)")


def _step_pick_topic(trends: dict) -> str:
    tl  = trends.get("timeline", [])
    ktr = trends.get("trending", [])
    all_topics = [t["topic"] for t in tl] + [t["topic"] for t in ktr]
    print("\n" + "─" * 52)
    print(" [2/6] 주제를 선택하세요")
    print("─" * 52)
    print("  번호 입력 → 해당 주제 선택 / d → 직접 입력 / r → 다시 수집")
    print()
    while True:
        raw = _ask("  선택: ").strip().lower()
        if raw == "r":
            return _step_pick_topic(_step_collect_trends())
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


def _step_pick_action() -> str:
    print("\n" + "─" * 52)
    print(" [3/6] 무엇을 만들까요?")
    print("─" * 52)
    print("  1. 트윗만 작성 / 2. 쇼츠만 제작 / 3. 트윗 + 쇼츠 둘 다")
    print()
    while True:
        raw = _ask("  선택 (1/2/3): ").strip()
        if raw == "1": return "tweet"
        if raw == "2": return "shorts"
        if raw == "3": return "both"
        print("  1, 2, 3 중 하나를 입력하세요.")


def _step_generate(topic: str, action: str, content: dict | None = None):
    print("\n" + "─" * 52)
    print(" [4/6] AI 콘텐츠 생성 중...")
    print("─" * 52)

    if content is None:
        content = {"title": topic, "text": topic, "source": "direct"}

    twitter_ctx = content.get("twitter_context")
    if not twitter_ctx:
        try:
            print("  → 트위터 관련 트윗 수집 중...")
            from twitter_fetcher import _fetch_related_tweets, _extract_keywords, _headers
            h  = _headers()
            kw = _extract_keywords(topic)
            related = _fetch_related_tweets(kw, "", h, max_results=10)
            if related:
                twitter_ctx = {
                    "quote_tweets": [],
                    "related":      related,
                    "summary": {
                        "sentiment_hint": "",
                        "combined_text":  "\n".join(f"- {t['text']}" for t in related[:5]),
                    },
                }
        except Exception as e:
            print(f"  ⚠️  트위터 수집 생략: {e}")

    print("  → 뉴스/웹 검색 중...")
    news_ctx = fetch_topic_context(topic)
    sources  = news_ctx.get("sources_used", [])

    print("  → 스크립트 생성 중...")
    if twitter_ctx or news_ctx.get("news") or news_ctx.get("web"):
        script = generate_rich_script(
            topic=topic,
            context={"twitter": twitter_ctx, "news": news_ctx},
        )
        print(f"  → 종합 스크립트 완료 (소스: {', '.join(sources) if sources else '트위터만'})")
    else:
        script = generate_script(content)

    tweet_drafts = None
    if action in ("tweet", "both"):
        print("  → 트윗 초안 생성 중...")
        tweet_drafts = generate_tweet_drafts(topic, script)

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


def _step_review(topic, action, script, tweet_drafts, image_path):
    chosen_tweet = None
    while True:
        print("\n" + "─" * 52)
        print(" [5/6] 최종 확인")
        print("─" * 52)
        print("\n  [ 쇼츠 스크립트 ]")
        print(f"  Hook  : {script['hook']}")
        for i, b in enumerate(script.get('body', []), 1):
            print(f"  Body {i}: {b}")
        print(f"  Closer: {script['closer']}")
        if tweet_drafts:
            print("\n  [ 트윗 초안 ]")
            for num, label, key in [("1","정보형","info"),("2","공감형","emotion"),("3","해시태그형","hashtag")]:
                text = tweet_drafts.get(key, "")
                print(f"  [{num}] {label}  ({len(text)}자)")
                print(f"      {text}")
        if action in ("shorts", "both"):
            mp4 = OUTPUT_DIR / "shorts.mp4"
            print(f"\n  [ 쇼츠 영상 ] {mp4} ({('존재' if mp4.exists() else '없음')})")
            if image_path:
                print(f"  사진: {image_path}")
        print("\n  ─────────────────────────────────")
        if tweet_drafts:
            print("  tw1/tw2/tw3  — 트윗 버전 선택")
        print("  s:내용  — 스크립트 재생성  (예: s:더 강렬하게)")
        print("  t:내용  — 트윗 재생성      (예: t:더 재미있게)")
        print("  ok      — 업로드 진행 / q — 종료")
        print()
        raw = _ask("  입력: ").strip().lower()
        if raw == "ok":
            if tweet_drafts and chosen_tweet is None:
                chosen_tweet = tweet_drafts.get("emotion", "")
                print("  (트윗 버전 미선택 → 공감형 자동 선택)")
            break
        elif raw == "q":
            print("  종료합니다."); sys.exit(0)
        elif tweet_drafts and raw in ("tw1", "tw2", "tw3"):
            key = {"tw1": "info", "tw2": "emotion", "tw3": "hashtag"}[raw]
            chosen_tweet = tweet_drafts[key]
            print(f"  ✓ 트윗 선택: {chosen_tweet}")
        elif raw.startswith("s:"):
            inst = raw[2:].strip()
            print(f"  → 스크립트 재생성 중 ({inst})...")
            script = generate_script({"title": topic, "text": f"{topic}. {inst}", "source": "direct"})
            if tweet_drafts:
                tweet_drafts = generate_tweet_drafts(topic, script)
            print("  ✓ 재생성 완료")
        elif raw.startswith("t:"):
            if not tweet_drafts:
                print("  트윗 모드가 아닙니다."); continue
            inst = raw[2:].strip()
            print(f"  → 트윗 재생성 중 ({inst})...")
            ms = dict(script)
            ms["hook"] = f"{script['hook']} ({inst})"
            tweet_drafts = generate_tweet_drafts(topic, ms)
            print("  ✓ 재생성 완료")
        else:
            print("  올바른 명령을 입력하세요.")
    return script, tweet_drafts, chosen_tweet


def _step_upload(action: str, chosen_tweet, video_path, topic: str):
    print("\n" + "─" * 52)
    print(" [6/6] 업로드")
    print("─" * 52)
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
    if action in ("shorts", "both") and video_path and video_path.exists():
        print(f"\n  쇼츠 파일: {video_path}")
        secrets = Path(os.environ.get("YOUTUBE_CLIENT_SECRETS", "config/client_secrets.json"))
        if not secrets.exists():
            print("  ℹ️  client_secrets.json 없음 → 로컬 저장만")
            print(f"  ✓ 쇼츠 저장 완료: {video_path.resolve()}")
        else:
            if _ask("  YouTube에 업로드할까요? (y/n): ").strip().lower() == "y":
                privacy = _ask("  공개 범위 (public/unlisted/private) [기본: public]: ").strip()
                if privacy not in ("public", "unlisted", "private"): privacy = "public"
                try:
                    result = upload_shorts(video_path=video_path, title=topic, privacy=privacy)
                    print(f"  ✓ YouTube 업로드 완료: {result['url']}")
                except Exception as e:
                    _err(f"YouTube 업로드 실패: {e}")
            else:
                print(f"  업로드 건너뜀. 파일: {video_path.resolve()}")
    print("\n  ✅ 파이프라인 완료!")


def _ask(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n  중단됨."); sys.exit(0)

def _err(msg: str):
    print(f"\n  ⚠️  {msg}")

def _print_banner():
    print("\n" + "=" * 52)
    print("  Shorts & Tweet 자동화 파이프라인")
    print("=" * 52)

if __name__ == "__main__":
    run()
