"""클립·캐치의 원본 방송 제목(방제)을 찾아, 제목을 고치지 않고 딴 영상을 표시한다."""

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
LIVE_API = "https://live.sooplive.co.kr/afreeca/player_live_api.php"
VOD_API = "https://api.m.sooplive.co.kr/station/video/a/view"
# 한 번 실행할 때 SOOP에 물어보는 최대 횟수 (같은 방송은 저장해 둔 방제를 다시 쓴다)
MAX_LOOKUPS = 40
# 이 기간이 지나도 방제를 못 찾으면 더 묻지 않는다.
GIVE_UP_AFTER = timedelta(days=1)
MAX_CACHE = 3000
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def post(url, data):
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        headers={"User-Agent": USER_AGENT, "Referer": "https://www.sooplive.com/"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def vod_title(title_no):
    """원본 다시보기 번호로 다시보기 제목을 가져온다."""
    data = post(VOD_API, {"nTitleNo": title_no, "nApiLevel": "10", "nPlaylistIdx": "0"}).get("data") or {}
    return data.get("full_title") or data.get("title")


def live_title(bj_id, broad_no):
    """스트리머가 아직 그 방송을 하고 있으면 현재 방제를 가져온다."""
    channel = post(LIVE_API, {"bid": bj_id, "type": "live", "player_type": "html5"}).get("CHANNEL") or {}
    if channel.get("RESULT") == 1 and str(channel.get("BNO")) == str(broad_no):
        return channel.get("TITLE")
    return None


def normalize(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"^\s*\[(클립|캐치)\]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def same_title(clip_title, broad_title):
    clip, broad = normalize(clip_title), normalize(broad_title)
    if not clip or not broad:
        return False
    # 클립 제목 길이 제한 때문에 방제 앞부분만 남은 경우도 같은 것으로 본다.
    return clip == broad or (len(clip) >= 10 and broad.startswith(clip))


def find_title(item, cache):
    broad_no = item.get("broad_no")
    if broad_no and broad_no in cache:
        return cache[broad_no]
    title = None
    if item.get("org_title_no"):
        title = vod_title(item["org_title_no"])
    if not title and broad_no:
        for bj_id in item.get("origin_ids") or []:
            title = live_title(bj_id, broad_no)
            if title:
                break
    if title and broad_no:
        cache[broad_no] = html.unescape(title)
    return cache.get(broad_no) if broad_no else title


def mark_unedited(items, cache, now):
    """아직 확인하지 않은 영상의 방제를 찾아 item["unedited"]를 채운다."""
    lookups = 0
    for item in sorted(items, key=lambda it: it.get("date", ""), reverse=True):
        if "unedited" in item or not item.get("broad_no"):
            continue
        cached = item["broad_no"] in cache
        if not cached and lookups >= MAX_LOOKUPS:
            continue
        try:
            title = find_title(item, cache)
        except Exception as error:
            print(f"방제 확인 실패 {item['type']} {item['id']}: {error}", file=sys.stderr)
            title = None
        if not cached:
            lookups += 1
        if title:
            item["broad_title"] = title
            item["unedited"] = same_title(item["title"], title)
            continue
        try:
            age = now - datetime.strptime(item.get("date", ""), DATE_FORMAT)
        except ValueError:
            age = GIVE_UP_AFTER
        if age >= GIVE_UP_AFTER:
            item["unedited"] = False
    # 오래된 방제는 버려서 파일이 너무 커지지 않게 한다.
    while len(cache) > MAX_CACHE:
        cache.pop(next(iter(cache)))
    return lookups
