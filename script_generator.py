"""
script_generator.py
콘텐츠 dict → YouTube Shorts 스크립트 JSON 생성 (Claude API 사용)
출력: {hook, body, closer, keywords, mood}
"""
import json
import os
import re

import anthropic


PROMPT_TEMPLATE = """당신은 한국어 YouTube Shorts 스크립트 전문 작가입니다.
아래 콘텐츠를 바탕으로 15~20초 분량의 Shorts 스크립트를 작성하세요.

[콘텐츠]
제목: {title}
내용: {text}

[작성 규칙]
- hook: 첫 3초 안에 시청자를 잡는 강렬한 첫 문장 (의문문 또는 충격적 사실)
- body: 핵심 내용 2~3문장 (간결하고 임팩트 있게)
- closer: 구독/좋아요 유도 또는 행동 촉구 한 문장
- keywords: 영상 검색용 키워드 3~5개
- mood: 영상 분위기 (예: upbeat, calm, dramatic, funny)

[출력 형식 - JSON만 출력, 다른 텍스트 없이]
{{"hook":"...","body":["...","...","..."],"closer":"...","keywords":["..."],"mood":"..."}}"""


def generate_script(content: dict) -> dict:
    """
    content: {title, text, source}
    반환: {hook, body, closer, keywords, mood}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "실행 전: export ANTHROPIC_API_KEY='your-key-here'"
        )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = PROMPT_TEMPLATE.format(
        title=content.get("title", ""),
        text=content.get("text", "")[:2000],
    )

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # 마크다운 코드블록 제거
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)

        # JSON 파싱
        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            script = json.loads(match.group())
        else:
            raise ValueError("JSON을 파싱할 수 없습니다.")

        # 필수 필드 검증 + 기본값
        script.setdefault("hook", content["title"])
        script.setdefault("body", [content["text"][:100]])
        script.setdefault("closer", "구독하고 다음 영상도 기대해주세요!")
        script.setdefault("keywords", [])
        script.setdefault("mood", "upbeat")

        if isinstance(script["body"], str):
            script["body"] = [script["body"]]

        return script

    except Exception as e:
        print(f"  ⚠️  스크립트 생성 실패: {e} — 규칙 기반 폴백 사용")
        return _fallback_script(content)


def _fallback_script(content: dict) -> dict:
    """API 실패시 규칙 기반 기본 스크립트."""
    title = content.get("title", "")
    text = content.get("text", "")

    hook = f"{title[:30]}... 알고 계셨나요?" if title else "오늘의 핵심 정보!"
    sentences = [s.strip() for s in re.split(r"[.!?。]", text) if len(s.strip()) > 10]
    body = sentences[:3] if sentences else [text[:100]]

    return {
        "hook": hook,
        "body": body,
        "closer": "구독하고 다음 영상도 기대해주세요!",
        "keywords": re.findall(r"[가-힣A-Za-z]{2,}", title)[:5],
        "mood": "upbeat",
    }
