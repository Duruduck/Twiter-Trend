"""
twitter_poster.py
스크립트 → 트윗 초안 생성 + 실제 게시

트윗 생성: Claude API (3가지 버전)
트윗 게시: Twitter API v2 (OAuth 1.0a, 쓰기 권한 필요)

필요 환경변수:
  ANTHROPIC_API_KEY        — 트윗 문안 생성
  TWITTER_API_KEY          — OAuth 1.0a
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_SECRET
"""
import json
import os
import re

import anthropic
import requests
from requests_oauthlib import OAuth1


# ─── 트윗 초안 생성 ──────────────────────────────────────────

def generate_tweet_drafts(topic: str, script: dict) -> dict:
    """
    주제 + 쇼츠 스크립트 기반으로 트윗 3가지 버전 생성.

    반환:
    {
      "info":    "정보 전달형 트윗 (140자)",
      "emotion": "공감/반응 유도형 트윗 (140자)",
      "hashtag": "해시태그 강조형 트윗 (140자)",
    }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _fallback_tweet_drafts(topic, script)

    hook = script.get("hook", topic)
    keywords = script.get("keywords", [])
    hashtags = " ".join(f"#{k}" for k in keywords[:4])

    prompt = f"""다음 주제로 한국어 트위터 포스팅 3가지를 작성하세요.
각 버전은 반드시 140자 이내로 작성하세요.

주제: {topic}
핵심 문장: {hook}
해시태그 후보: {hashtags}

버전 설명:
- info: 사실 중심, 정보 전달 (뉴스 스타일)
- emotion: 감정/공감 유발, 팔로워 반응 유도 (구어체)
- hashtag: 해시태그 3~4개 포함, 검색 최적화용

JSON만 출력 (다른 텍스트 없이):
{{"info":"...","emotion":"...","hashtag":"..."}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            drafts = json.loads(match.group())
            # 140자 초과 시 자동 자르기
            for k in drafts:
                if len(drafts[k]) > 140:
                    drafts[k] = drafts[k][:137] + "..."
            return drafts
    except Exception as e:
        print(f"  ⚠️  트윗 생성 실패: {e}")

    return _fallback_tweet_drafts(topic, script)


def _fallback_tweet_drafts(topic: str, script: dict) -> dict:
    """API 없을 때 규칙 기반 트윗."""
    hook = script.get("hook", topic)
    keywords = script.get("keywords", [])
    hashtags = " ".join(f"#{k}" for k in keywords[:3])

    return {
        "info":    f"{hook}"[:140],
        "emotion": f"{hook} 여러분은 어떻게 생각하세요?"[:140],
        "hashtag": f"{hook} {hashtags}"[:140],
    }


# ─── 트윗 게시 ───────────────────────────────────────────────

def post_tweet(text: str) -> dict:
    """
    트위터에 트윗 게시.

    반환:
    {
      "id":  "tweet_id",
      "url": "https://twitter.com/i/web/status/{id}",
      "text": "게시된 텍스트",
    }
    """
    api_key    = os.environ.get("TWITTER_API_KEY", "")
    api_secret = os.environ.get("TWITTER_API_SECRET", "")
    acc_token  = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    acc_secret = os.environ.get("TWITTER_ACCESS_SECRET", "")

    if not all([api_key, api_secret, acc_token, acc_secret]):
        missing = [k for k, v in {
            "TWITTER_API_KEY": api_key,
            "TWITTER_API_SECRET": api_secret,
            "TWITTER_ACCESS_TOKEN": acc_token,
            "TWITTER_ACCESS_SECRET": acc_secret,
        }.items() if not v]
        raise ValueError(f"트위터 OAuth 키 없음: {', '.join(missing)}")

    auth = OAuth1(api_key, api_secret, acc_token, acc_secret)

    resp = requests.post(
        "https://api.twitter.com/2/tweets",
        auth=auth,
        json={"text": text},
        timeout=15,
    )
    resp.raise_for_status()

    tweet_id = resp.json()["data"]["id"]
    return {
        "id":   tweet_id,
        "url":  f"https://twitter.com/i/web/status/{tweet_id}",
        "text": text,
    }
