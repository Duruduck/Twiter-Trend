"""
video_assembler.py
TTS + 스크립트 + (선택) 이미지 → 최종 Shorts MP4 조립 (FFmpeg)

레이아웃 (9cm x 16cm 기준, 1cm = 120px):
  0px    ┌─────────────┐
         │  검정 바     │  444px
  444px  ├─────────────┤
         │  사진 영역   │  1032px
  1476px ├─────────────┤
         │  검정 바     │  444px
  1920px └─────────────┘
"""
import subprocess
import tempfile
import wave
from pathlib import Path

import requests

WIDTH, HEIGHT    = 1080, 1920
BAR_H            = 444
PHOTO_Y          = BAR_H
PHOTO_H          = HEIGHT - BAR_H * 2
TITLE_SIZE       = 32
CAPTION_SIZE     = 24
TOP_BAR_CY       = BAR_H // 2
BOTTOM_BAR_CY    = PHOTO_Y + PHOTO_H + BAR_H // 2
TITLE_MARGIN_V   = TOP_BAR_CY - TITLE_SIZE // 2
CAPTION_MARGIN_V = HEIGHT - BOTTOM_BAR_CY - CAPTION_SIZE // 2
MOOD_BG = {"upbeat": "f5f0e8", "calm": "e8f0ed", "dramatic": "1a1a2e", "funny": "fff0f5", "default": "f0f0f0"}


def assemble_video(script, tts_path, output_path, image_path=None, pexels_key=""):
    duration = _get_wav_duration(tts_path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stock_video = None
        if image_path is None and pexels_key:
            stock_video = _fetch_pexels_video(script.get("keywords", []), pexels_key, tmp, duration)
        ass_path = output_path.parent / "captions.ass"
        _write_ass_captions(ass_path, script.get("hook",""), script.get("body",[]), script.get("closer",""), duration)
        return _render(script, tts_path, ass_path, output_path, duration, image_path, stock_video)


def _render(script, tts_path, ass_path, output_path, duration, image_path, stock_video):
    mood     = script.get("mood", "default")
    photo_bg = MOOD_BG.get(mood, MOOD_BG["default"])

    # Windows 경로 처리: 백슬래시→슬래시, 드라이브 콜론 이스케이프, 공백 이스케이프
    ass_str = str(ass_path).replace("\\", "/")
    if len(ass_str) >= 2 and ass_str[1] == ":":
        ass_str = ass_str[0] + "\\:" + ass_str[2:]
    ass_str = ass_str.replace(" ", "\\ ")

    if image_path and image_path.exists():
        fg = (
            "color=black:size={W}x{H}:rate=30[canvas];"
            "color={bg}:size={W}x{PH}:rate=30[pbg];"
            "[0:v]scale={W}:{PH}:force_original_aspect_ratio=decrease,"
            "pad={W}:{PH}:(ow-iw)/2:(oh-ih)/2:color={bg}[img];"
            "[pbg][img]overlay=0:0[pf];"
            "[canvas][pf]overlay=0:{PY}[wp];"
            "[wp]ass={ass}[vout]"
        ).format(W=WIDTH, H=HEIGHT, PH=PHOTO_H, PY=PHOTO_Y, bg=photo_bg, ass=ass_str)
        input_flags = ["-loop", "1", "-i", str(image_path), "-i", str(tts_path)]
        audio_map   = "1:a"
    elif stock_video and stock_video.exists():
        fg = (
            "color=black:size={W}x{H}:rate=30[canvas];"
            "[0:v]scale={W}:{PH}:force_original_aspect_ratio=increase,"
            "crop={W}:{PH},setsar=1[vid];"
            "[canvas][vid]overlay=0:{PY}[wp];"
            "[wp]ass={ass}[vout]"
        ).format(W=WIDTH, H=HEIGHT, PH=PHOTO_H, PY=PHOTO_Y, ass=ass_str)
        input_flags = ["-stream_loop", "-1", "-i", str(stock_video), "-i", str(tts_path)]
        audio_map   = "1:a"
    else:
        fg = (
            "color=black:size={W}x{H}:rate=30[canvas];"
            "color={bg}:size={W}x{PH}:rate=30[pa];"
            "[canvas][pa]overlay=0:{PY}[wp];"
            "[wp]ass={ass}[vout]"
        ).format(W=WIDTH, H=HEIGHT, PH=PHOTO_H, PY=PHOTO_Y, bg=photo_bg, ass=ass_str)
        input_flags = ["-i", str(tts_path)]
        audio_map   = "0:a"

    cmd = (["ffmpeg", "-y"] + input_flags + [
        "-filter_complex", fg, "-map", "[vout]", "-map", audio_map,
        "-t", str(duration + 0.5),
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output_path),
    ])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg 오류:\n{result.stderr[-600:]}")
        raise RuntimeError("영상 조립 실패")
    return output_path


def _write_ass_captions(path, hook, body, closer, duration):
    body_text    = "\n".join(body) if isinstance(body, list) else str(body)
    body_end     = min(duration - 3.0, duration * 0.8)
    closer_start = max(body_end, duration - 3.5)
    def ts(sec):
        h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"
    lines = [
        "[Script Info]", "ScriptType: v4.00+",
        f"PlayResX: {WIDTH}", f"PlayResY: {HEIGHT}", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Title,Arial,{TITLE_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,3,0,8,60,60,{TITLE_MARGIN_V},1",
        f"Style: Caption,Arial,{CAPTION_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,3,0,2,60,60,{CAPTION_MARGIN_V},1",
        f"Style: Closer,Arial,{CAPTION_SIZE},&H00FFFF00,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,3,0,2,60,60,{CAPTION_MARGIN_V},1",
        "", "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        f"Dialogue: 0,{ts(0.2)},{ts(duration+0.3)},Title,,0,0,0,,{_wrap(hook, 22)}",
        f"Dialogue: 0,{ts(0.5)},{ts(body_end)},Caption,,0,0,0,,{_wrap(body_text, 28)}",
        f"Dialogue: 0,{ts(closer_start)},{ts(duration+0.3)},Closer,,0,0,0,,{_wrap(closer, 26)}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _wrap(text, max_chars):
    words = text.replace("\n", " ").split()
    lines, cur, cnt = [], [], 0
    for w in words:
        if cnt + len(w) + 1 > max_chars and cur:
            lines.append(" ".join(cur)); cur, cnt = [w], len(w)
        else:
            cur.append(w); cnt += len(w) + 1
    if cur: lines.append(" ".join(cur))
    return r"\N".join(lines)


def _fetch_pexels_video(keywords, api_key, tmp, duration):
    query = " ".join(keywords[:2]) if keywords else "background"
    try:
        resp = requests.get("https://api.pexels.com/videos/search",
                            headers={"Authorization": api_key},
                            params={"query": query, "per_page": 5, "orientation": "portrait"}, timeout=10)
        resp.raise_for_status()
        for v in resp.json().get("videos", []):
            if v.get("duration", 0) >= max(duration - 2, 5):
                hd = next((f for f in v.get("video_files",[]) if f.get("quality") in ("hd","sd")), None)
                if hd:
                    vp = tmp / "stock.mp4"
                    _download_file(hd["link"], vp)
                    print("  → Pexels 스톡 영상 다운로드 완료")
                    return vp
    except Exception as e:
        print(f"  Pexels 오류: {e}")
    return None


def _download_file(url, dest):
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192): f.write(chunk)


def _get_wav_duration(wav_path):
    try:
        with wave.open(str(wav_path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 20.0
