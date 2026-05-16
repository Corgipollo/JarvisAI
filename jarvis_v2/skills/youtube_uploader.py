"""youtube_uploader.py - YouTube Data API v3 con resumable uploads.

Sube videos sin GUI. Soporta:
  - OAuth 2.0 flow (primera vez abre browser para consent)
  - Token refresh automatico
  - Resumable uploads (reanuda si la red falla a mitad)
  - Set descripcion, titulo, miniatura, tags, categoria, privacy

Setup (UNA SOLA VEZ):
  1. Google Cloud Console -> nuevo proyecto
  2. Enable YouTube Data API v3
  3. Credentials -> OAuth client ID -> Desktop app
  4. Download JSON -> guardar como jarvis_v2/skills/client_secret.json
  5. python -m jarvis_v2.skills.youtube_uploader login  (autoriza una vez)

Uso desde el grafo:
  from jarvis_v2.skills.youtube_uploader import YouTubeUploader
  yt = YouTubeUploader()
  video_id = yt.upload("path/to/video.mp4", title="...", description="...",
                       thumbnail="path/to/thumb.jpg", privacy="private")
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "jarvis_v2" / "skills"
CLIENT_SECRET = SKILLS_DIR / "client_secret.json"
TOKEN_FILE = SKILLS_DIR / "youtube_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


class YouTubeUploader:
    def __init__(self):
        self.service = None

    def _credentials(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            except Exception:
                creds = None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CLIENT_SECRET.exists():
                    raise FileNotFoundError(
                        f"Falta {CLIENT_SECRET}. "
                        "Setup en https://console.cloud.google.com -> YouTube Data API v3 "
                        "-> OAuth client (Desktop) -> Download JSON -> renombrar a "
                        "client_secret.json"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRET), SCOPES)
                creds = flow.run_local_server(port=0)
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _build(self):
        if self.service is not None:
            return self.service
        from googleapiclient.discovery import build
        creds = self._credentials()
        self.service = build("youtube", "v3", credentials=creds)
        return self.service

    def upload(self, video_path: str, title: str, description: str = "",
               tags: list[str] | None = None, category_id: str = "22",
               privacy: str = "private", thumbnail: str | None = None,
               progress_callback=None) -> dict:
        """Sube video con resumable upload. Devuelve {video_id, url}.

        category_id: 22=People & Blogs, 27=Education, 28=Tech, 24=Entertainment
        privacy: private | unlisted | public
        """
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError

        if not Path(video_path).exists():
            return {"error": f"video not found: {video_path}"}

        svc = self._build()
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": (tags or [])[:500],
                "categoryId": category_id,
            },
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
        req = svc.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            try:
                status, response = req.next_chunk()
                if status and progress_callback:
                    progress_callback(status.progress() * 100)
            except HttpError as e:
                # Retry on 5xx, abort on 4xx
                if e.resp.status in (500, 502, 503, 504):
                    continue
                return {"error": f"http_{e.resp.status}: {e}"}
            except Exception as e:
                return {"error": str(e)}

        video_id = response["id"]
        result = {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "status": response.get("status", {}),
        }
        # Set thumbnail
        if thumbnail and Path(thumbnail).exists():
            try:
                svc.thumbnails().set(videoId=video_id,
                                     media_body=MediaFileUpload(thumbnail)).execute()
                result["thumbnail_set"] = True
            except Exception as e:
                result["thumbnail_error"] = str(e)
        return result

    def update_metadata(self, video_id: str, title: str | None = None,
                         description: str | None = None,
                         tags: list[str] | None = None) -> dict:
        svc = self._build()
        snippet = svc.videos().list(part="snippet", id=video_id).execute()
        if not snippet.get("items"):
            return {"error": "video not found"}
        body = snippet["items"][0]["snippet"]
        if title:
            body["title"] = title[:100]
        if description is not None:
            body["description"] = description[:5000]
        if tags is not None:
            body["tags"] = tags[:500]
        resp = svc.videos().update(part="snippet",
                                    body={"id": video_id, "snippet": body}).execute()
        return {"ok": True, "id": resp.get("id")}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        yt = YouTubeUploader()
        try:
            yt._build()
            print("OK login successful, token saved")
        except Exception as e:
            print(f"FAIL: {e}")
    elif len(sys.argv) > 1 and sys.argv[1] == "upload":
        yt = YouTubeUploader()
        path = sys.argv[2]
        title = sys.argv[3] if len(sys.argv) > 3 else Path(path).stem
        result = yt.upload(path, title=title,
                           description="Subido via Jarvis v2", privacy="private",
                           progress_callback=lambda p: print(f"  {p:.0f}%"))
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python -m jarvis_v2.skills.youtube_uploader {login|upload <file> [title]}")
