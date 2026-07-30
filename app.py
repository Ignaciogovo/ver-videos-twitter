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

_TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

_original_raise_no_formats = yt_dlp.extractor.common.InfoExtractor.raise_no_formats


def _patched_raise_no_formats(self, msg, *args, **kwargs):
    msg_lower = str(msg).lower()
    if "no video" in msg_lower or "no formats" in msg_lower:
        return
    _original_raise_no_formats(self, msg, *args, **kwargs)


def _ytdlp_extract(url):
    yt_dlp.extractor.common.InfoExtractor.raise_no_formats = _patched_raise_no_formats
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            return ydl.extract_info(url, download=False)
    finally:
        yt_dlp.extractor.common.InfoExtractor.raise_no_formats = _original_raise_no_formats


def _guest_token():
    url = "https://api.x.com/1.1/guest/activate.json"
    req = urllib.request.Request(url, data=b"", headers={"Authorization": f"Bearer {_TWITTER_BEARER}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return jsonlib.loads(resp.read())["guest_token"]


def _graphql_tweet(twid, guest_token):
    endpoint = "2ICDjqPd81tulZcYrtpTuQ/TweetResultByRestId"
    url = f"https://x.com/i/api/graphql/{endpoint}"
    body = jsonlib.dumps({
        "variables": {"tweetId": twid, "withCommunity": False, "includePromotedContent": False, "withVoice": False},
        "features": {
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_media_download_video_enabled": False,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        },
        "fieldToggles": {"withArticleRichContentState": False},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {_TWITTER_BEARER}",
        "x-guest-token": guest_token,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return jsonlib.loads(resp.read())


def _extract_full_text(twid):
    try:
        token = _guest_token()
        data = _graphql_tweet(twid, token)
        result = data.get("data", {}).get("tweetResult", {}).get("result", {})

        if result.get("__typename") in ("TweetUnavailable", "TweetTombstone"):
            return None

        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet", {})

        legacy = result.get("legacy") or {}
        note = result.get("note_tweet", {}).get("note_tweet_results", {}).get("result", {})
        text = note.get("text") or legacy.get("full_text", "")

        user_data = result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
        if not user_data:
            user_data = legacy.get("user", {}) if isinstance(legacy.get("user"), dict) else {}

        return {
            "text": text,
            "user_name": user_data.get("name", ""),
            "user_handle": user_data.get("screen_name", ""),
            "date": legacy.get("created_at", ""),
            "likes": legacy.get("favorite_count"),
            "retweets": legacy.get("retweet_count"),
            "replies": legacy.get("reply_count"),
        }
    except Exception:
        return None


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

    media = []
    tweet_text = ""
    user_name = ""
    user_handle = ""
    date_str = None
    likes = None
    retweets = None
    replies = None

    try:
        info = _ytdlp_extract(url)
        entries = info.get("entries") or [info]
        for entry in entries:
            formats = entry.get("formats", [])
            thumbnail = entry.get("thumbnail", "")
            title = entry.get("title", "")
            videos = [f for f in formats if f.get("vcodec") != "none"]
            if videos:
                mp4_videos = [f for f in videos if "m3u8" not in (f.get("url", "") or "")]
                best = max(mp4_videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0)) if mp4_videos else max(videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
                media.append({
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
                media.append({"type": "image", "url": thumbnail, "thumbnail": thumbnail, "title": title})
        tweet_text = info.get("description", "") or ""
        user_name = info.get("uploader", "") or ""
        user_handle = info.get("uploader_id", "") or ""
        ts = info.get("timestamp")
        if ts:
            try:
                date_str = datetime.utcfromtimestamp(ts).isoformat()
            except (TypeError, ValueError):
                pass
        likes = info.get("like_count")
        retweets = info.get("repost_count")
        replies = info.get("comment_count")
    except Exception:
        pass

    if len(tweet_text) >= 270 or not tweet_text:
        full = _extract_full_text(twid)
        if full:
            if len(full.get("text", "")) > len(tweet_text):
                tweet_text = full["text"]
            if not user_name and full.get("user_name"):
                user_name = full["user_name"]
            if not user_handle and full.get("user_handle"):
                user_handle = full["user_handle"]
            if not likes and full.get("likes") is not None:
                likes = full["likes"]
            if not retweets and full.get("retweets") is not None:
                retweets = full["retweets"]
            if not replies and full.get("replies") is not None:
                replies = full["replies"]
            date_raw = full.get("date", "")
            if date_raw and not date_str:
                try:
                    dt = datetime.strptime(date_raw, "%a %b %d %H:%M:%S %z %Y")
                    date_str = dt.isoformat()
                except (ValueError, TypeError):
                    pass

    if not tweet_text and not media:
        raise HTTPException(404, "No se encontraron videos ni imágenes en este tweet.")

    return {
        "tweet": {
            "text": tweet_text,
            "author": {
                "name": user_name,
                "handle": user_handle,
                "url": f"https://x.com/{user_handle}" if user_handle else "",
            },
            "date": date_str,
            "stats": {"likes": likes, "retweets": retweets, "replies": replies, "views": None},
        },
        "media": media,
        "tweet_url": url,
    }