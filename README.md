# Twiter-Trend Shorts Maker

트위터 트렌드 수집 → 쇼츠 자동 제작 → 트위터/YouTube 업로드 파이프라인

## 파일 구조

```
shorts-maker/
├── pipeline.py          # 전체 파이프라인 실행 진입점
├── main.py              # 단독 실행 (URL/주제 → 쇼츠)
├── twitter_fetcher.py   # 트위터 트렌드/타임라인 수집
├── twitter_poster.py    # 트윗 초안 생성 + 게시
├── youtube_uploader.py  # YouTube Shorts 업로드
├── content_fetcher.py   # URL → 본문 텍스트 추출
├── script_generator.py  # Claude API → 쇼츠 스크립트
├── image_fetcher.py     # Bing/Google/og:image/Pexels 이미지 수집
├── tts_generator.py     # edge-tts → 한국어 음성
├── video_assembler.py   # FFmpeg → 1080x1920 MP4 조립
├── requirements.txt
├── .env.example
└── config/              # API 키, YouTube 인증 파일 (gitignore됨)
```

## 쇼츠 레이아웃

```
┌─────────────────┐
│   검정 바        │  3.7cm — 제목(24pt) 중앙 배치
├─────────────────┤
│                 │
│    사진 영역     │  8.6cm — 자동 수집 이미지
│                 │
├─────────────────┤
│   검정 바        │  3.7cm — 자막(18pt) 중앙 배치
└─────────────────┘
  1080 x 1920px
```

## 설치

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. FFmpeg 설치
# Mac:   brew install ffmpeg
# Linux: apt install ffmpeg
# Win:   https://ffmpeg.org/download.html

# 3. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

## API 키 발급

| 키 | 용도 | 발급처 | 무료 여부 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | 스크립트/트윗 생성 | [console.anthropic.com](https://console.anthropic.com) | 유료 |
| `TWITTER_BEARER_TOKEN` | 트렌드 수집 | [developer.twitter.com](https://developer.twitter.com) | 무료 |
| `TWITTER_API_KEY` 외 3개 | 트윗 게시 | 동일 | 무료 |
| `BING_IMAGE_KEY` | 이미지 수집 | [Azure Portal](https://portal.azure.com) | 월 1,000건 무료 |
| `PEXELS_API_KEY` | 이미지/영상 폴백 | [pexels.com/api](https://www.pexels.com/api/) | 무료 |
| `client_secrets.json` | YouTube 업로드 | [Google Cloud Console](https://console.cloud.google.com) | 무료 |

## 실행

### 전체 파이프라인 (트렌드 수집 → 선택 → 제작 → 업로드)
```bash
python pipeline.py
```

### 단독 실행 (URL/주제 → 쇼츠만)
```bash
python main.py --topic "서인영 유튜브 복귀"
python main.py --url "https://n.news.naver.com/article/..."
python main.py --topic "..." --dry-run   # 스크립트만 확인
```

## 파이프라인 흐름

```
[1] 트렌드 수집
    타임라인 Top 3 (RT 기준) + 대한민국 트렌딩 Top 3

[2] 주제 선택  ← 직접 선택
    번호 입력 / d: 직접 입력 / r: 다시 수집

[3] 제작 방식  ← 직접 선택
    1: 트윗만 / 2: 쇼츠만 / 3: 둘 다

[4] AI 자동 생성
    스크립트 + 트윗 3가지 + 이미지 수집 + TTS + 영상 조립

[5] 최종 확인  ← 직접 확인/수정
    tw1/tw2/tw3       트윗 버전 선택
    s:더 자극적으로   스크립트 재생성
    t:더 재미있게     트윗만 재생성
    ok                업로드 진행

[6] 업로드     ← 최종 승인 후 실행
    트윗 게시 + YouTube Shorts 업로드
```

## YouTube 인증 (최초 1회)

```bash
# 1. Google Cloud Console에서
#    YouTube Data API v3 활성화
#    OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)
#    client_secrets.json 다운로드

mkdir config
mv ~/Downloads/client_secrets.json config/

# 2. 파이프라인 실행 시 브라우저 자동 열림
#    Google 로그인 → 허용 → config/youtube_token.json 저장
#    이후 자동 사용
```
