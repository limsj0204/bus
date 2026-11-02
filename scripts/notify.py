"""새로 모인 클립·캐치와 게시글을 디스코드 웹후크로 알린다."""

import json
import os
import re
import sys
import time
import urllib.request

WEBHOOK_ENV = "DISCORD_WEBHOOK_URL"
USERNAME = "양도끼 클립 알림"
AVATAR_URL = "https://stimg.sooplive.com/LOGO/ya/yangdoki/yangdoki.jpg"
SITE_URL = "https://limsj0204.github.io/bus/"
TYPE_LABEL = {"CLIP": "클립", "CATCH": "캐치"}
TYPE_COLOR = {"CLIP": 0x2563EB, "CATCH": 0xDB2777}
# 디스코드는 메시지 하나에 임베드를 10개까지 넣을 수 있다.
EMBEDS_PER_MESSAGE = 10
MAX_MESSAGES = 3


def clean_title(title):
    return re.sub(r"^\s*\[(클립|캐치)\]\s*", "", title)


def embed(item):
    origin = item.get("origin_nick") or item.get("streamer_nick") or item.get("streamer_id") or ""
    lines = []
    if item.get("streamer_nick") and item["streamer_nick"] != origin:
        lines.append(f"✂ {item['streamer_nick']}")
    footer = TYPE_LABEL.get(item["type"], item["type"])
    if item.get("duration"):
        footer += f" · {item['duration']}"
    result = {
        "title": clean_title(item["title"])[:256],
        "url": item["url"],
        "color": TYPE_COLOR.get(item["type"], 0x0D9488),
        "author": {"name": origin[:256]} if origin else None,
        "description": "\n".join(lines) or None,
        "footer": {"text": footer},
    }
    if item.get("thumbnail"):
        result["thumbnail"] = {"url": item["thumbnail"]}
    if item.get("date"):
        result["timestamp"] = item["date"].replace(" ", "T") + "+09:00"
    return {k: v for k, v in result.items() if v is not None}


def post(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/limsj0204/bus, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def matches(item, only_origins):
    if not only_origins:
        return True
    names = {item.get("origin_nick", ""), item.get("streamer_nick", ""), item.get("streamer_id", "")}
    names |= set(item.get("origin_ids", []))
    return any(n.lower() in only_origins for n in names if n)


def send(new_items, config):
    """새 영상을 오래된 것부터 디스코드로 보낸다. 실패해도 수집은 계속되도록 예외를 삼킨다."""
    settings = config.get("discord") or {}
    if settings.get("enabled") is False:
        return
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not url:
        print("디스코드 알림: 웹후크 주소가 없어서 건너뜀")
        return
    only_origins = {str(o).lower() for o in settings.get("only_origins") or []}
    types = {str(t).upper() for t in settings.get("types") or ["CLIP", "CATCH"]}
    items = [it for it in new_items if it["type"] in types and matches(it, only_origins)]
    if not items:
        return
    items.sort(key=lambda it: (it.get("date", ""), it["id"]))

    limit = EMBEDS_PER_MESSAGE * MAX_MESSAGES
    sending, skipped = items[:limit], items[limit:]
    try:
        for i in range(0, len(sending), EMBEDS_PER_MESSAGE):
            chunk = sending[i:i + EMBEDS_PER_MESSAGE]
            payload = {"username": USERNAME, "avatar_url": AVATAR_URL, "embeds": [embed(it) for it in chunk]}
            if i == 0:
                payload["content"] = f"새 영상 {len(items)}개"
            post(url, payload)
            time.sleep(1)
        if skipped:
            post(url, {
                "username": USERNAME,
                "avatar_url": AVATAR_URL,
                "content": f"외 {len(skipped)}개는 사이트에서 확인하세요: {SITE_URL}",
            })
        print(f"디스코드 알림: {len(items)}개 보냄")
    except Exception as error:
        print(f"디스코드 알림 실패: {error}", file=sys.stderr)


POST_USERNAME = "양도끼 게시글 알림"
POST_COLOR = 0x0D9488


def post_embed(item):
    station = item.get("station_nick") or item.get("station_id") or ""
    own = item.get("station_id", "").lower() == item.get("author_id", "").lower()
    where = "내 방송국" if own else f"{station} 방송국"
    result = {
        "title": (item.get("title") or "(제목 없음)")[:256],
        "url": item["url"],
        "color": POST_COLOR,
        "author": {"name": f"{item.get('author_nick', '')} → {where}"[:256]},
        "description": (item.get("content") or "")[:300] or None,
        "footer": {"text": "게시글" + (f" · 사진 {item['photos']}장" if item.get("photos") else "")},
    }
    if item.get("thumbnail"):
        result["thumbnail"] = {"url": item["thumbnail"]}
    if item.get("date"):
        result["timestamp"] = item["date"].replace(" ", "T") + "+09:00"
    return {k: v for k, v in result.items() if v is not None}


def send_posts(new_posts, config):
    """새 게시글을 오래된 것부터 디스코드로 보낸다. 실패해도 수집은 계속되도록 예외를 삼킨다."""
    if not new_posts:
        return
    if (config.get("discord") or {}).get("enabled") is False:
        return
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not url:
        print("디스코드 알림: 웹후크 주소가 없어서 건너뜀")
        return
    posts = sorted(new_posts, key=lambda it: (it.get("date", ""), it["id"]))
    limit = EMBEDS_PER_MESSAGE * MAX_MESSAGES
    sending, skipped = posts[:limit], posts[limit:]
    try:
        for i in range(0, len(sending), EMBEDS_PER_MESSAGE):
            chunk = sending[i:i + EMBEDS_PER_MESSAGE]
            payload = {"username": POST_USERNAME, "avatar_url": AVATAR_URL, "embeds": [post_embed(it) for it in chunk]}
            if i == 0:
                payload["content"] = f"새 게시글 {len(posts)}개"
            post(url, payload)
            time.sleep(1)
        if skipped:
            post(url, {
                "username": POST_USERNAME,
                "avatar_url": AVATAR_URL,
                "content": f"외 {len(skipped)}개는 사이트에서 확인하세요: {SITE_URL}",
            })
        print(f"디스코드 알림: 게시글 {len(posts)}개 보냄")
    except Exception as error:
        print(f"디스코드 알림 실패: {error}", file=sys.stderr)
