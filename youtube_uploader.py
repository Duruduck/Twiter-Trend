"""
youtube_uploader.py
YouTube Data API v3로 Shorts MP4 업로드

인증 방식: OAuth 2.0 (최초 1회 브라우저 인증 → token.json 저장)

필요:
  1. Google Cloud Console에서 프로젝트 생성
  2. YouTube Data API v3 활성화
  3. OAuth 2.0 클라이언트 ID 생성 → client_secrets.json 다운로드
  4. pip install google-auth google-auth-oauthlib google-api-python-client

실행 흐름:
  최초: 브라우저 열림 → Google 로그인 → 허용 → token.json 저장
  이후: token.json 자동 사용 (만료 시 자동 갱신)
"""
import json
import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path("config/youtube_token.json")
SECRETS_PATH = Path(
    os.environ.get("YOUTUBE_CLIENT_SECRETS", "config/client_secrets.json")
)


# ─── 공개 API ────────────────────────────────────────────────

def upload_shorts(
    video_path: Path,
    title: str,
    description: str = "",
    tags: list | None = None,
    privacy: str = "public",
) -> dict:
    """
    Shorts MP4를 YouTube에 업로드.

    Args:
        video_path:  업로드할 MP4 파일
        title:       영상 제목 (100자 이내)
        description: 설명 (선택)
        tags:        태그 리스트 (선택)
        privacy:     "public" / "unlisted" / "private"

    Returns:
        {"id": "video_id", "url": "https://youtube.com/shorts/{id}", "title": title}
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise ImportError(
            "google-api-python-client 패키지가 없습니다.\n"
            "pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    youtube = _get_youtube_client()

    # Shorts 조건: 제목에 #Shorts 포함, 60초 이내
    if "#Shorts" not in title and "#shorts" not in title:
        title = f"{title} #Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description or _default_description(title),
            "tags": (tags or []) + ["Shorts", "쇼츠"],
            "categoryId": "22",      # People & Blogs
            "defaultLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,   # 5MB 청크
    )

    print(f"  → 업로드 시작: {video_path.name}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  → 업로드 중... {pct}%", end="\r")

    video_id = response["id"]
    url = f"https://youtube.com/shorts/{video_id}"
    print(f"\n  ✓ 업로드 완료: {url}")

    return {"id": video_id, "url": url, "title": title}


# ─── 인증 ─────────────────────────────────────────────────────

def _get_youtube_client():
    """OAuth2 인증 후 YouTube API 클라이언트 반환."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google 라이브러리가 없습니다.\n"
            "pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    creds = None

    # 저장된 토큰 로드
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # 토큰 없거나 만료 → 재인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRETS_PATH.exists():
                raise FileNotFoundError(
                    f"client_secrets.json 없음: {SECRETS_PATH}\n"
                    "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고\n"
                    f"'{SECRETS_PATH}'에 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(SECRETS_PATH), SCOPES
            )
            print("\n  브라우저가 열립니다. Google 계정으로 로그인 후 허용해주세요.")
            creds = flow.run_local_server(port=0)

        # 토큰 저장
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        print(f"  인증 토큰 저장: {TOKEN_PATH}")

    return build("youtube", "v3", credentials=creds)


def _default_description(title: str) -> str:
    return (
        f"{title}\n\n"
        "─────────────────────\n"
        "자동 생성된 Shorts 콘텐츠입니다.\n"
        "#Shorts #쇼츠 #AI생성"
    )
