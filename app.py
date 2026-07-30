from datetime import datetime
import json as jsonlib
import math
from pathlib import Path
import re
import urllib.request

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import yt_dlp
from yt_dlp.jsinterp import js_number_to_string


def _syndication_token(twid):
    return js_number_to_string((int(twid) / 1e15) * math.pi, 36).replace("0", "").replace(".", "")


def _syndication_extract(twid):
    token = _syndication_token(twid)
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={twid}&token={token}"
    req = urllib.request.Request(url, headers={"User-Agent": "Googlebot"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = jsonlib.loads(resp.read())

    user = data.get("user", {})
    photos = data.get("photos") or []
    text = data.get("text", "")
    date_str = data.get("created_at")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
            date_str = dt.isoformat()
        except ValueError:
            pass

    media = []
    for p in photos:
        media.append({
            "type": "image",
            "url": p.get("url", ""),
            "thumbnail": p.get("url", ""),
            "width": p.get("width"),
            "height": p.get("height"),
        })

    video_data = data.get("video")
    if video_data and video_data.get("variants"):
        for v in video_data.get("variants", []):
            if v.get("content_type", "").startswith("video/") and v.get("url"):
                is_hls = ".m3u8" in v.get("url", "")
                media.append({
                    "type": "video",
                    "url": v["url"],
                    "format": "mp4" if not is_hls else "hls",
                    "thumbnail": video_data.get("posterImageUrl", ""),
                    "width": video_data.get("width"),
                    "height": video_data.get("height"),
                })
                break

    views_raw = data.get("views")
    views = views_raw.get("count") if isinstance(views_raw, dict) else None

    return {
        "text": text,
        "author": {
            "name": user.get("name", ""),
            "handle": user.get("screen_name", ""),
            "url": f"https://x.com/{user.get('screen_name', '')}" if user.get("screen_name") else "",
        },
        "date": date_str,
        "stats": {
            "likes": data.get("favorite_count"),
            "retweets": data.get("retweet_count"),
            "replies": data.get("reply_count"),
            "views": views,
        },
        "media": media,
    }


_original_raise_no_formats = yt_dlp.extractor.common.InfoExtractor.raise_no_formats


def _patched_raise_no_formats(self, msg, *args, **kwargs):
    if "no video could be found" in str(msg).lower():
        return
    _original_raise_no_formats(self, msg, *args, **kwargs)


def _ytdlp_extract(url):
    yt_dlp.extractor.common.InfoExtractor.raise_no_formats = _patched_raise_no_formats
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": False}) as ydl:
            return ydl.extract_info(url, download=False)
    finally:
        yt_dlp.extractor.common.InfoExtractor.raise_no_formats = _original_raise_no_formats


HTML = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")

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

    status_id = re.search(r'/status/(\d+)', url)
    if not status_id:
        raise HTTPException(400, "URL inválida.")
    twid = status_id.group(1)

    info = None
    yt_error = None
    try:
        info = _ytdlp_extract(url)
    except Exception as e:
        yt_error = str(e)

    if info:
        tweet = _extract_tweet_meta_from_info(info)
        media = _extract_media_from_info(info)
        return {"tweet": tweet, "media": media, "tweet_url": url}

    if not yt_error:
        raise HTTPException(404, "No se pudo acceder al tweet.")

    if "not found" in yt_error.lower() or "deleted" in yt_error.lower():
        raise HTTPException(404, "Tweet no encontrado. Puede estar eliminado o ser privado.")
    if "nsfw" in yt_error.lower():
        raise HTTPException(404, "Tweet con contenido restringido. Requiere autenticación.")

    try:
        synd = _syndication_extract(twid)
        if synd["media"] or synd["text"]:
            return {"tweet": {"text": synd["text"], "author": synd["author"], "date": synd["date"], "stats": synd["stats"]}, "media": synd["media"], "tweet_url": url}
    except Exception:
        pass

    raise HTTPException(422, f"No se pudo acceder al tweet: {yt_error}")


def _extract_tweet_meta_from_info(info):
    ts = info.get("timestamp")
    date_str = None
    if ts:
        try:
            date_str = datetime.utcfromtimestamp(ts).isoformat()
        except (TypeError, ValueError):
            pass
    return {
        "text": info.get("description", ""),
        "author": {
            "name": info.get("uploader", ""),
            "handle": info.get("uploader_id", ""),
            "url": info.get("uploader_url", ""),
        },
        "date": date_str,
        "stats": {
            "likes": info.get("like_count"),
            "retweets": info.get("repost_count"),
            "replies": info.get("comment_count"),
            "views": info.get("view_count"),
        },
    }


def _extract_media_from_info(info):
    entries = info.get("entries") or [info]
    results = []

    for entry in entries:
        formats = entry.get("formats", [])
        thumbnail = entry.get("thumbnail", "")
        title = entry.get("title", "")

        videos = [f for f in formats if f.get("vcodec") != "none"]
        if videos:
            mp4_videos = [f for f in videos if "m3u8" not in (f.get("url", "") or "")]
            best = max(mp4_videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0)) if mp4_videos else max(videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
            results.append({
                "type": "video",
                "url": best["url"],
                "format": "mp4" if best in mp4_videos else "hls",
                "thumbnail": thumbnail,
                "width": best.get("width"),
                "height": best.get("height"),
                "title": title,
                "duration": entry.get("duration"),
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

    return results
