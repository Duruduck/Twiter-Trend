"""
twitter_fetcher.py
Twitter API v2로 트렌드 수집

1. 내 팔로워 타임라인 Top 3 (홈 타임라인 최근 100개 분석)
2. 대한민국 전체 트렌딩 Top 3 (Trends API)

필요: TWITTER_BEARER_TOKEN (읽기 전용, 무료)
"""
import os
import re
from collections import Counter
from datetime import datetime, timezone

import requests

BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}

# 한국 트렌딩 WOEID (Yahoo Where On Earth ID)
# 23424868 = 대한민국
KR_WOEID = 23424868


# ─── 공개 API ────────────────────────────────────────────────

def fetch_trends() -> dict:
    """
    반환:
    {
      "timeline": [
        {"rank":1, "topic":"서인영 유튜브 복귀", "rt_count":4200, "tweet_count":12},
        ...
      ],
      "trending": [
        {"rank":1, "topic":"이재명 판결", "tweet_volume":85000},
        ...
      ]
    }
    """
    token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not token:
        raise ValueError(
            "TWITTER_BEARER_TOKEN 환경변수가 없습니다.\n"
            "export TWITTER_BEARER_TOKEN='your-token'"
        )
    headers = {"Authorization": f"Bearer {token}"}

    print("  → 타임라인 분석 중...")
    timeline = _fetch_timeline_trends(headers)

    print("  → 대한민국 트렌딩 수집 중...")
    trending = _fetch_kr_trending(headers)

    return {"timeline": timeline, "trending": trending}


# ─── 타임라인 트렌드 ─────────────────────────────────────────

def _fetch_timeline_trends(headers: dict) -> list:
    """
    홈 타임라인 최근 100개 트윗 분석 →
    RT 수 기준 상위 3개 주제 추출
    """
    try:
        # 내 user_id 먼저 조회
        me_resp = requests.get(
            "https://api.twitter.com/2/users/me",
            headers=headers,
            timeout=10,
        )
        me_resp.raise_for_status()
        user_id = me_resp.json()["data"]["id"]

        # 홈 타임라인 (최근 100개)
        tl_resp = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/timelines/reverse_chronological",
            headers=headers,
            params={
                "max_results": 100,
                "tweet.fields": "public_metrics,entities,referenced_tweets",
                "expansions": "referenced_tweets.id",
            },
            timeout=15,
        )
        tl_resp.raise_for_status()
        tweets = tl_resp.json().get("data", [])

        return _extract_topics_from_tweets(tweets)

    except Exception as e:
        print(f"  ⚠️  타임라인 수집 실패: {e}")
        return []


def _extract_topics_from_tweets(tweets: list) -> list:
    """
    트윗 리스트 → RT 수 기준 상위 3개 주제.
    해시태그 우선, 없으면 명사구 추출.
    """
    topic_stats: dict[str, dict] = {}

    for tweet in tweets:
        metrics = tweet.get("public_metrics", {})
        rt_count = metrics.get("retweet_count", 0)
        like_count = metrics.get("like_count", 0)
        score = rt_count * 3 + like_count  # RT 가중치 3배

        # 해시태그 수집
        entities = tweet.get("entities", {})
        hashtags = [h["tag"] for h in entities.get("hashtags", [])]

        # 해시태그 없으면 텍스트에서 키워드 추출
        if not hashtags:
            text = tweet.get("text", "")
            hashtags = _extract_keywords(text)

        for tag in hashtags:
            tag = tag.strip("#").strip()
            if len(tag) < 2:
                continue
            if tag not in topic_stats:
                topic_stats[tag] = {"rt_count": 0, "score": 0, "tweet_count": 0}
            topic_stats[tag]["rt_count"] += rt_count
            topic_stats[tag]["score"] += score
            topic_stats[tag]["tweet_count"] += 1

    # score 기준 정렬, 상위 3개
    sorted_topics = sorted(
        topic_stats.items(), key=lambda x: x[1]["score"], reverse=True
    )[:3]

    return [
        {
            "rank": i + 1,
            "topic": topic,
            "rt_count": stats["rt_count"],
            "tweet_count": stats["tweet_count"],
        }
        for i, (topic, stats) in enumerate(sorted_topics)
    ]


def _extract_keywords(text: str) -> list:
    """트윗 텍스트에서 의미있는 키워드 추출 (2글자 이상 한글/영문)."""
    # URL, 멘션 제거
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"RT\s+", "", text)

    # 2글자 이상 단어 추출
    words = re.findall(r"[가-힣A-Za-z]{2,}", text)
    # 불용어 제거
    stopwords = {"RT", "the", "and", "for", "that", "this", "있다", "없다", "한다",
                 "됩니다", "합니다", "입니다", "것이", "이번", "오늘", "지금"}
    return [w for w in words if w not in stopwords][:3]


# ─── 대한민국 트렌딩 ─────────────────────────────────────────

def _fetch_kr_trending(headers: dict) -> list:
    """
    Twitter v1.1 Trends API (Bearer Token으로 접근 가능).
    WOEID 23424868 = 대한민국
    """
    try:
        resp = requests.get(
            f"https://api.twitter.com/1.1/trends/place.json",
            headers=headers,
            params={"id": KR_WOEID},
            timeout=10,
        )
        resp.raise_for_status()
        trends = resp.json()[0].get("trends", [])

        # tweet_volume 있는 것 우선, 없으면 순서대로
        valid = [t for t in trends if t.get("tweet_volume")]
        if not valid:
            valid = trends

        result = []
        for i, t in enumerate(valid[:3]):
            result.append({
                "rank": i + 1,
                "topic": t["name"].lstrip("#"),
                "tweet_volume": t.get("tweet_volume", 0),
            })
        return result

    except Exception as e:
        print(f"  ⚠️  트렌딩 수집 실패: {e}")
        return []
