from datetime import datetime
import json
from pathlib import Path
import re
import urllib.request

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


def _parse_media(item):
    mtype = item.get("type", "")
    if mtype in ("photo", "image"):
        return {
            "type": "image",
            "url": item.get("url", ""),
            "thumbnail": item.get("url", ""),
            "width": item.get("width"),
            "height": item.get("height"),
        }
    if mtype in ("video", "gif"):
        url_val = item.get("url", "")
        return {
            "type": "video",
            "url": url_val,
            "format": "mp4" if ".m3u8" not in url_val else "hls",
            "thumbnail": item.get("thumbnail_url", ""),
            "width": item.get("width"),
            "height": item.get("height"),
            "duration": item.get("duration"),
        }
    return None


def _fxtwitter_extract(twid):
    url = f"https://api.fxtwitter.com/status/{twid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    if data.get("code") != 200:
        return None

    tweet = data.get("tweet", {})
    if not tweet:
        return None

    text = tweet.get("text", "")
    author_data = tweet.get("author", {})
    date_raw = tweet.get("created_at", "")
    date_str = None
    if date_raw:
        try:
            dt = datetime.strptime(date_raw, "%a %b %d %H:%M:%S %z %Y")
            date_str = dt.isoformat()
        except (ValueError, TypeError):
            date_str = date_raw

    media = []
    for item in (tweet.get("media", {}).get("all", []) or []):
        parsed = _parse_media(item)
        if parsed:
            media.append(parsed)

    quote = tweet.get("quote")
    if quote:
        for item in (quote.get("media", {}).get("all", []) or []):
            parsed = _parse_media(item)
            if parsed:
                media.append(parsed)

    return {
        "text": text,
        "author": {
            "name": author_data.get("name", ""),
            "handle": author_data.get("screen_name", ""),
            "url": author_data.get("url", f"https://x.com/{author_data.get('screen_name', '')}"),
        },
        "date": date_str,
        "stats": {
            "likes": tweet.get("likes"),
            "retweets": tweet.get("retweets"),
            "replies": tweet.get("replies"),
            "views": tweet.get("views"),
        },
        "media": media,
    }


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
    m = re.match(r'https?://(?:www\.|m\.)?(?:twitter|x)\.com/(?:\w+|i)/status/(\d+)', url)
    if not m:
        raise HTTPException(400, "URL inválida. Ingresa un enlace de tweet de X/Twitter.")
    twid = m.group(1)

    try:
        result = _fxtwitter_extract(twid)
    except Exception:
        raise HTTPException(422, "No se pudo acceder al tweet.")

    if not result:
        raise HTTPException(404, "Tweet no encontrado. Puede estar eliminado o ser privado.")

    if not result["text"] and not result["media"]:
        raise HTTPException(404, "No se encontraron videos ni imágenes en este tweet.")

    return {
        "tweet": {
            "text": result["text"],
            "author": result["author"],
            "date": result["date"],
            "stats": result["stats"],
        },
        "media": result["media"],
        "tweet_url": url,
    }