"""
tts_generator.py
스크립트 dict → 한국어 음성 WAV 파일 생성
edge-tts 사용 (무료, API 키 불필요)
"""
import asyncio
import subprocess
from pathlib import Path

import edge_tts

# 한국어 음성 목록 (취향에 따라 변경 가능)
VOICES = {
    "female": "ko-KR-SunHiNeural",   # 밝고 자연스러운 여성
    "male":   "ko-KR-InJoonNeural",  # 자연스러운 남성
}


def generate_tts(script: dict, output_dir: Path, voice: str = "female") -> Path:
    """
    script: {hook, body, closer, ...}
    반환: output_dir/tts.mp3 경로
    """
    text = _build_tts_text(script)
    voice_name = VOICES.get(voice, VOICES["female"])

    mp3_path = output_dir / "tts.mp3"
    wav_path = output_dir / "tts.wav"

    # edge-tts는 비동기 → asyncio로 실행
    asyncio.run(_synthesize(text, voice_name, str(mp3_path)))

    # mp3 → wav 변환 (FFmpeg)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3_path), str(wav_path)],
        capture_output=True, check=True
    )

    return wav_path


def _build_tts_text(script: dict) -> str:
    """스크립트 dict → 읽기용 단일 텍스트."""
    parts = [script.get("hook", "")]
    body = script.get("body", [])
    if isinstance(body, list):
        parts.extend(body)
    else:
        parts.append(str(body))
    parts.append(script.get("closer", ""))
    return " ".join(p for p in parts if p)


async def _synthesize(text: str, voice: str, output_path: str):
    """edge-tts 비동기 합성."""
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)
