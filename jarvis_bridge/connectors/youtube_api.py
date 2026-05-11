"""YouTube Data API v3 connector — gratis con cuota 10k unidades/día.

Capacidades:
  - upload_video(path, title, description, tags, privacy)
  - list_my_videos(max_results)
  - get_channel_stats()
  - update_video(video_id, metadata)

Requiere OAuth2 (client_secret.json + token.json). Setup una sola vez.
Google Cloud Console → APIs → Habilitar YouTube Data API v3 → credentials OAuth2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = ROOT / "secrets"
CLIENT_SECRET = SECRETS_DIR / "youtube_client_secret.json"
TOKEN_FILE = SECRETS_DIR / "youtube_token.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _get_service():
    """Obtiene servicio autenticado YouTube."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return None, "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.readonly"]

    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not CLIENT_SECRET.exists():
                return None, f"falta {CLIENT_SECRET} (descargar de Google Cloud Console)"
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    service = build("youtube", "v3", credentials=creds)
    return service, None


def upload_video(path: str, title: str, description: str = "",
                 tags: list = None, privacy: str = "private",
                 category_id: str = "22") -> dict:
    """Sube un video. privacy: private/unlisted/public."""
    service, err = _get_service()
    if err:
        return {"success": False, "error": err}

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return {"success": False, "error": "googleapiclient no instalado"}

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": (tags or [])[:50],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    try:
        request = service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(path, chunksize=-1, resumable=True),
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  upload {status.progress()*100:.0f}%", flush=True)
        return {
            "success": True,
            "video_id": response["id"],
            "url": f"https://youtu.be/{response['id']}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_my_videos(max_results: int = 10) -> dict:
    service, err = _get_service()
    if err:
        return {"success": False, "error": err}
    try:
        channels = service.channels().list(part="contentDetails", mine=True).execute()
        uploads_id = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = service.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads_id, maxResults=max_results,
        ).execute()
        return {
            "success": True,
            "videos": [{
                "id": v["contentDetails"]["videoId"],
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"],
            } for v in items.get("items", [])],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_channel_stats() -> dict:
    service, err = _get_service()
    if err:
        return {"success": False, "error": err}
    try:
        r = service.channels().list(part="statistics,snippet", mine=True).execute()
        item = r["items"][0]
        return {
            "success": True,
            "title": item["snippet"]["title"],
            "subscribers": int(item["statistics"]["subscriberCount"]),
            "views": int(item["statistics"]["viewCount"]),
            "videos": int(item["statistics"]["videoCount"]),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(get_channel_stats(), ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        print(json.dumps(list_my_videos(10), ensure_ascii=False, indent=2))
    else:
        print("Usos: stats | list")
