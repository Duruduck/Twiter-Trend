"""
twitter_poster.py
트윗 초안 생성 (Gemini 우선, Claude 폴백) + 게시 (Twitter API v2)

LLM 우선순위:
  1. GEMINI_API_KEY   — 무료
  2. ANTHROPIC_API_KEY — 폴백
게시용: TWITTER_API_KEY / API_SECRET / ACCESS_TOKEN / ACCESS_SECRET
"""
import json
import os
import re

import requests


def generate_tweet_drafts(topic: str, script: dict) -> dict:
    hook     = script.get("hook", topic)
    keywords = script.get("keywords", [])
    hashtags = " ".join(f"#{k}" for k in keywords[:4])

    prompt = f"""다음 주제로 한국어 트위터 포스팅 3가지를 작성하세요.
각 버전은 반드시 140자 이내로 작성하세요.

주제: {topic}
핵심 문장: {hook}
해시태그 후보: {hashtags}

- info: 사실 중심, 정보 전달 (뉴스 스타일)
- emotion: 감정/공감 유발, 팔로워 반응 유도 (구어체)
- hashtag: 해시태그 3~4개 포함, 검색 최적화용

JSON만 출력:
{{"info":"...","emotion":"...","hashtag":"..."}}"""

    raw = _call_llm(prompt)
    if raw:
        try:
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            m   = re.search(r"\{[\s\S]+\}", raw)
            if m:
                drafts = json.loads(m.group())
                for k in drafts:
                    if len(drafts[k]) > 140:
                        drafts[k] = drafts[k][:137] + "..."
                return drafts
        except Exception as e:
            print(f"  ⚠️  트윗 파싱 실패: {e}")
    return _fallback(topic, script)


def _call_llm(prompt: str) -> str | None:
    import time
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"maxOutputTokens": 512}},
                    timeout=30,
                )
                if resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f"  → Gemini 요청 한도 초과, {wait}초 대기 후 재시도...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                if "429" in str(e):
                    wait = 10 * (attempt + 1)
                    print(f"  → Gemini 요청 한도 초과, {wait}초 대기 후 재시도...")
                    time.sleep(wait)
                    continue
                print(f"  ⚠️  Gemini 트윗 생성 실패: {e}")
                break

    claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if claude_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=claude_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            print(f"  ⚠️  Claude 트윗 생성 실패: {e}")
    return None


def _fallback(topic: str, script: dict) -> dict:
    hook     = script.get("hook", topic)
    hashtags = " ".join(f"#{k}" for k in script.get("keywords", [])[:3])
    return {
        "info":    hook[:140],
        "emotion": f"{hook} 여러분은 어떻게 생각하세요?"[:140],
        "hashtag": f"{hook} {hashtags}"[:140],
    }


def post_tweet(text: str) -> dict:
    api_key    = os.environ.get("TWITTER_API_KEY", "")
    api_secret = os.environ.get("TWITTER_API_SECRET", "")
    acc_token  = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    acc_secret = os.environ.get("TWITTER_ACCESS_SECRET", "")
    if not all([api_key, api_secret, acc_token, acc_secret]):
        missing = [k for k, v in {
            "TWITTER_API_KEY": api_key, "TWITTER_API_SECRET": api_secret,
            "TWITTER_ACCESS_TOKEN": acc_token, "TWITTER_ACCESS_SECRET": acc_secret,
        }.items() if not v]
        raise ValueError(f"트위터 OAuth 키 없음: {', '.join(missing)}")
    from requests_oauthlib import OAuth1
    auth = OAuth1(api_key, api_secret, acc_token, acc_secret)
    resp = requests.post("https://api.twitter.com/2/tweets", auth=auth, json={"text": text}, timeout=15)
    resp.raise_for_status()
    tweet_id = resp.json()["data"]["id"]
    return {"id": tweet_id, "url": f"https://twitter.com/i/web/status/{tweet_id}", "text": text}
