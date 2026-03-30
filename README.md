# Twiter-Trend Shorts Maker

트위터 트렌드 수집 → 뉴스/웹 종합 분석 → YouTube Shorts 자동 제작 + 트윗 게시

## 파일 구조

```
├── pipeline.py          # 전체 파이프라인 (트렌드 수집 → 제작 → 업로드)
├── main.py              # 단독 실행 (URL/주제 → 쇼츠)
├── content_fetcher.py   # URL 본문 추출 + 뉴스/웹 검색
├── script_generator.py  # 단순/종합 스크립트 생성
├── image_fetcher.py     # 이미지 자동 수집
├── tts_generator.py     # 한국어 TTS (edge-tts, 무료)
├── video_assembler.py   # FFmpeg → 1080x1920 MP4
├── twitter_fetcher.py   # 트렌드 수집 + URL 컨텍스트 수집
├── twitter_poster.py    # 트윗 초안 생성 + 게시
├── youtube_uploader.py  # YouTube Shorts 업로드
├── requirements.txt
├── .env.example
└── config/
    ├── client_secrets.json  ← 직접 넣어야 함
    └── youtube_token.json   ← 자동 생성
```

## 쇼츠 레이아웃 (1080x1920)

```
┌─────────────────┐
│   검정 바        │  3.7cm — 제목(24pt) 중앙
├─────────────────┤
│    사진 영역     │  8.6cm — 자동 수집 이미지
├─────────────────┤
│   검정 바        │  3.7cm — 자막(18pt) 중앙
└─────────────────┘
```

## 설치

```bash
pip install -r requirements.txt
# FFmpeg: brew install ffmpeg / apt install ffmpeg
cp .env.example .env
# .env 파일에 API 키 입력
```

## API 키

| 키 | 용도 | 무료 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 스크립트/트윗 생성 (필수) | 유료 |
| `TWITTER_BEARER_TOKEN` | 트렌드 수집 (필수) | 무료 |
| `NAVER_CLIENT_ID/SECRET` | 한국 뉴스 검색 | 무료 |
| `BING_SEARCH_KEY` | 웹 검색 | 월 1,000건 무료 |
| `BING_IMAGE_KEY` | 이미지 수집 | 월 1,000건 무료 |
| `PEXELS_API_KEY` | 영상/이미지 폴백 | 무료 |
| `client_secrets.json` | YouTube 업로드 | 무료 |

## 실행

```bash
# 전체 파이프라인
python pipeline.py

# URL로 수집
python pipeline.py --url "https://x.com/someone/status/123"

# 주제 직접 입력
python pipeline.py --topic "서인영 유튜브 복귀"

# 단독 쇼츠 제작
python main.py --topic "서인영 유튜브 복귀"
python main.py --url "https://n.news.naver.com/article/..."
```

## 파이프라인 흐름

```
[1] 트렌드 수집 — 타임라인 Top 3 + 대한민국 트렌딩 Top 3
[2] 주제 선택  — 번호 / d: 직접입력 / r: 다시수집
[3] 제작 방식  — 1: 트윗 / 2: 쇼츠 / 3: 둘 다
[4] AI 생성   — 트위터+뉴스+웹 종합 → 스크립트 + 트윗 + 이미지 + TTS + 영상
[5] 최종 확인  — tw1/tw2/tw3 선택, s:/t: 재생성, ok 업로드
[6] 업로드     — 트윗 게시 + YouTube Shorts 업로드
```
