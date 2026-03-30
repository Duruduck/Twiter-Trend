"""
script_generator.py
콘텐츠 dict → YouTube Shorts 스크립트 JSON 생성

LLM 우선순위:
  1. Google Gemini API (GEMINI_API_KEY) — 무료, gemini-2.0-flash
  2. Anthropic Claude  (ANTHROPIC_API_KEY) — 폴백
"""
import json
import os
import re

_SIMPLE_PROMPT = """당신은 한국어 YouTube Shorts 스크립트 전문 작가입니다.
아래 콘텐츠를 바탕으로 15~20초 분량의 Shorts 스크립트를 작성하세요.

[콘텐츠]
제목: {title}
내용: {text}

[작성 규칙]
- hook: 첫 3초 안에 시청자를 잡는 강렬한 첫 문장
- body: 핵심 내용 2~3문장
- closer: 구독/좋아요 유도 한 문장
- keywords: 영상 검색용 키워드 3~5개
- mood: upbeat / calm / dramatic / funny

JSON만 출력:
{{"hook":"...","body":["...","...","..."],"closer":"...","keywords":["..."],"mood":"..."}}"""

_RICH_PROMPT = """당신은 한국어 YouTube Shorts 스크립트 전문 작가입니다.
아래 수집된 데이터를 종합 분석해서 15~20초 분량의 임팩트 있는 Shorts 스크립트를 작성하세요.

[주제]
{topic}

{twitter_section}

{news_section}

{web_section}

[작성 규칙]
- hook: 시청자가 스크롤을 멈출 만한 강렬한 첫 문장 (감정 유발 우선)
- body: 뉴스 팩트 + 트위터 반응을 조합한 2~3문장
- closer: 시청자 의견을 묻거나 공유를 유도하는 문장
- keywords: 검색/해시태그용 키워드 3~5개
- mood: upbeat / calm / dramatic / funny

JSON만 출력:
{{"hook":"...","body":["...","...","..."],"closer":"...","keywords":["..."],"mood":"..."}}"""


def generate_script(content: dict) -> dict:
    prompt = _SIMPLE_PROMPT.format(
        title=content.get("title", ""),
        text=content.get("text", "")[:2000],
    )
    return _call_llm(prompt) or _fallback_script(content)


def generate_rich_script(topic: str, context: dict) -> dict:
    twitter_section = _format_twitter_section(context.get("twitter"))
    news_context    = context.get("news", {})
    news_section    = _format_news_section(news_context.get("news", []))
    web_section     = _format_web_section(news_context.get("web", []))
    prompt = _RICH_PROMPT.format(
        topic=topic,
        twitter_section=twitter_section,
        news_section=news_section,
        web_section=web_section,
    )
    result = _call_llm(prompt, max_tokens=768)
    if not result:
        result = generate_script({"title": topic, "text": news_context.get("combined_text", topic)})
    return result


def _call_llm(prompt: str, max_tokens: int = 512) -> dict | None:
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        result = _call_gemini(prompt, gemini_key, max_tokens)
        if result: return result

    claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if claude_key:
        result = _call_claude(prompt, claude_key, max_tokens)
        if result: return result

    print("  ⚠️  LLM API 키 없음 — 폴백 스크립트 사용")
    return None


def _call_gemini(prompt: str, api_key: str, max_tokens: int) -> dict | None:
    import requests, time
    for attempt in range(3):
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
                },
                timeout=30,
            )
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  → Gemini 요청 한도 초과, {wait}초 대기 후 재시도...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return _parse_json(raw)
        except Exception as e:
            if "429" in str(e):
                wait = 10 * (attempt + 1)
                print(f"  → Gemini 요청 한도 초과, {wait}초 대기 후 재시도...")
                time.sleep(wait)
                continue
            print(f"  ⚠️  Gemini 실패: {e}")
            return None
    print("  ⚠️  Gemini 재시도 횟수 초과")
    return None


def _call_claude(prompt: str, api_key: str, max_tokens: int) -> dict | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(msg.content[0].text.strip())
    except Exception as e:
        print(f"  ⚠️  Claude 실패: {e}")
        return None


def _parse_json(raw: str) -> dict | None:
    try:
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        match = re.search(r"\{[\s\S]+\}", raw)
        if not match: return None
        script = json.loads(match.group())
        script.setdefault("hook",     "")
        script.setdefault("body",     [])
        script.setdefault("closer",   "구독하고 다음 영상도 기대해주세요!")
        script.setdefault("keywords", [])
        script.setdefault("mood",     "upbeat")
        if isinstance(script["body"], str):
            script["body"] = [script["body"]]
        return script
    except Exception:
        return None


def _format_twitter_section(twitter) -> str:
    if not twitter: return ""
    parts = ["[트위터 반응]"]
    original = twitter.get("original", {})
    if original.get("text"): parts.append(f"원본 트윗: {original['text'][:200]}")
    for q in twitter.get("quote_tweets", [])[:5]: parts.append(f"  인용: {q['text'][:100]}")
    for r in twitter.get("related", [])[:5]:      parts.append(f"  관련: {r['text'][:100]}")
    hint = twitter.get("summary", {}).get("sentiment_hint", "")
    if hint: parts.append(f"전체 분위기: {hint}")
    return "\n".join(parts)


def _format_news_section(news) -> str:
    if not news: return ""
    parts = ["[뉴스]"]
    for i, n in enumerate(news[:5], 1):
        parts.append(f"{i}. {n['title']}")
        if n.get("description"): parts.append(f"   {n['description'][:150]}")
    return "\n".join(parts)


def _format_web_section(web) -> str:
    if not web: return ""
    parts = ["[웹 검색 결과]"]
    for i, w in enumerate(web[:3], 1):
        parts.append(f"{i}. {w['title']}")
        if w.get("snippet"): parts.append(f"   {w['snippet'][:150]}")
    return "\n".join(parts)


def _fallback_script(content: dict) -> dict:
    title = content.get("title", "")
    text  = content.get("text", "")
    hook  = f"{title[:30]}... 알고 계셨나요?" if title else "오늘의 핵심 정보!"
    sentences = [s.strip() for s in re.split(r"[.!?。]", text) if len(s.strip()) > 10]
    return {
        "hook":     hook,
        "body":     sentences[:3] or [text[:100]],
        "closer":   "구독하고 다음 영상도 기대해주세요!",
        "keywords": re.findall(r"[가-힣A-Za-z]{2,}", title)[:5],
        "mood":     "upbeat",
    }
