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
from yt_dlp.jsinterp import js_number_to_string

_TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


def _syndication_token(twid):
    return js_number_to_string((int(twid) / 1e15) * math.pi, 36).replace("0", "").replace(".", "")


def _syndication_extract(twid):
    token = _syndication_token(twid)
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={twid}&token={token}"
    req = urllib.request.Request(url, headers={"User-Agent": "Googlebot"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return jsonlib.loads(resp.read())


def _graphql_extract(twid):
    """Extrae texto completo de note_tweets via GraphQL"""
    try:
        guest_url = "https://api.x.com/1.1/guest/activate.json"
        guest_req = urllib.request.Request(guest_url, data=b"", headers={"Authorization": f"Bearer {_TWITTER_BEARER}"})
        with urllib.request.urlopen(guest_req, timeout=10) as resp:
            guest_token = jsonlib.loads(resp.read())["guest_token"]

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
            data = jsonlib.loads(resp.read())

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


def _extract_media_from_syndication(data):
    media = []
    photos = data.get("photos") or []
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

    return media


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

    data = _syndication_extract(twid)
    if not data or "text" not in data:
        raise HTTPException(404, "Tweet no encontrado o privado.")

    user = data.get("user") or {}
    text = data.get("text", "")
    date_raw = data.get("created_at")
    date_str = None
    if date_raw:
        try:
            dt = datetime.strptime(date_raw, "%a %b %d %H:%M:%S %z %Y")
            date_str = dt.isoformat()
        except (ValueError, TypeError):
            pass

    views = None
    views_raw = data.get("views")
    if isinstance(views_raw, dict):
        views = views_raw.get("count")

    media = _extract_media_from_syndication(data)

    if len(text) >= 270:
        full = _graphql_extract(twid)
        if full and len(full.get("text", "")) > len(text):
            text = full["text"]
            if not user.get("name"):
                user["name"] = full.get("user_name", "")
            if not user.get("screen_name"):
                user["screen_name"] = full.get("user_handle", "")

    if not text and not media:
        raise HTTPException(404, "No se encontraron videos ni imágenes en este tweet.")

    return {
        "tweet": {
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
        },
        "media": media,
        "tweet_url": url,
    }
