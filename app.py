from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import yt_dlp

HTML = Path("public/index.html").read_text(encoding="utf-8")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TweetRequest(BaseModel):
    url: str


@app.get("/")
def index():
    return HTMLResponse(HTML)


@app.post("/api/media")
def get_media(req: TweetRequest):
    url = req.url.strip()
    if not re.match(r'https?://(?:www\.|m\.)?(?:twitter|x)\.com/(?:\w+|i)/status/\d+', url):
        raise HTTPException(400, "URL inválida. Ingresa un enlace de tweet de X/Twitter.")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except (yt_dlp.utils.ExtractorError, yt_dlp.utils.DownloadError) as e:
        msg = str(e)
        if "no video could be found" in msg.lower():
            raise HTTPException(404, "No se encontraron videos ni imágenes en este tweet.")
        if "not found" in msg.lower() or "unavailable" in msg.lower() or "deleted" in msg.lower():
            raise HTTPException(404, "Tweet no encontrado. Puede estar eliminado o ser privado.")
        raise HTTPException(422, f"No se pudo acceder al tweet: {msg}")

    entries = info.get("entries") or [info]
    results = []

    for entry in entries:
        formats = entry.get("formats", [])
        thumbnail = entry.get("thumbnail", "")
        title = entry.get("title", "")
        duration = entry.get("duration")

        videos = [f for f in formats if f.get("vcodec") != "none"]
        if videos:
            mp4_videos = [f for f in videos if "m3u8" not in (f.get("url", "") or "")]
            best = None
            if mp4_videos:
                best = max(mp4_videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
            else:
                best = max(videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
            results.append({
                "type": "video",
                "url": best["url"],
                "format": "mp4" if best in mp4_videos else "hls",
                "thumbnail": thumbnail,
                "width": best.get("width"),
                "height": best.get("height"),
                "title": title,
                "duration": duration,
            })
        elif thumbnail:
            results.append({
                "type": "image",
                "url": thumbnail,
                "thumbnail": thumbnail,
                "title": title,
            })
        elif entry.get("url"):
            results.append({
                "type": "image",
                "url": entry["url"],
                "thumbnail": thumbnail or entry["url"],
                "title": title,
            })

    if not results:
        raise HTTPException(404, "No se encontraron videos ni imágenes en este tweet.")

    return {"media": results, "tweet_url": url}
