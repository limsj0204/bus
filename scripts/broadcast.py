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
# 이 기간 안의 영상은 방제가 바뀌었을 수 있어 다시 비교하고, 방제는 REFRESH_EVERY마다 새로 확인한다.
RECHECK_WINDOW = timedelta(hours=6)
REFRESH_EVERY = timedelta(minutes=30)
# 처음 보는 영상이 아는 방제와 다르면 더 빨리 다시 확인한다. (알림이 가기 전에 거르기 위해)
REFRESH_NEW = timedelta(minutes=5)
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


def fetch_titles(item):
    """원본 방송의 현재 방제(생방송 중일 때)와 다시보기 제목을 가져온다."""
    titles = []
    broad_no = item.get("broad_no")
    for bj_id in item.get("origin_ids") or []:
        title = live_title(bj_id, broad_no)
        if title:
            titles.append(html.unescape(title))
            break
    if item.get("org_title_no"):
        title = vod_title(item["org_title_no"])
        if title:
            titles.append(html.unescape(title))
    return titles


def cache_entry(cache, broad_no):
    """방송 번호별로 지금까지 본 방제 목록과 마지막 확인 시각. (예전 형식: 방제 문자열 하나)"""
    entry = cache.get(broad_no)
    if isinstance(entry, str):
        entry = {"titles": [entry], "checked": ""}
        cache[broad_no] = entry
    return entry


def parse_time(text, fallback):
    try:
        return datetime.strptime(text or "", DATE_FORMAT)
    except ValueError:
        return fallback


def mark_unedited(items, cache, now):
    """영상 제목이 원본 방송의 방제(지금까지 본 방제 중 하나)와 같으면 item["unedited"]를 켠다.

    방송 도중 방제가 바뀔 수 있으므로, 최근 영상이 아는 방제와 다르면 그 방송의 방제를
    REFRESH_EVERY마다 다시 확인해 목록에 더한다.
    """
    lookups = 0
    refreshed = set()
    for item in sorted(items, key=lambda it: it.get("date", ""), reverse=True):
        broad_no = item.get("broad_no")
        if not broad_no or item.get("unedited"):
            continue
        age = now - parse_time(item.get("date"), now - GIVE_UP_AFTER)
        if "unedited" in item and age > RECHECK_WINDOW:
            continue

        entry = cache_entry(cache, broad_no)
        titles = entry["titles"] if entry else []
        match = next((t for t in titles if same_title(item["title"], t)), None)
        last_checked = parse_time(entry.get("checked") if entry else "", now - REFRESH_EVERY)
        refresh_after = REFRESH_EVERY if "unedited" in item else REFRESH_NEW
        if not match and broad_no not in refreshed and lookups < MAX_LOOKUPS and (
            not entry or now - last_checked >= refresh_after
        ):
            lookups += 1
            refreshed.add(broad_no)
            try:
                found = fetch_titles(item)
            except Exception as error:
                print(f"방제 확인 실패 {item['type']} {item['id']}: {error}", file=sys.stderr)
                found = []
            entry = entry or {"titles": [], "checked": ""}
            entry["titles"] += [t for t in found if t not in entry["titles"]]
            entry["checked"] = now.strftime(DATE_FORMAT)
            cache[broad_no] = entry
            titles = entry["titles"]
            match = next((t for t in titles if same_title(item["title"], t)), None)

        if match:
            item["broad_title"] = match
            item["unedited"] = True
        elif titles:
            item["broad_title"] = titles[-1]
            item["unedited"] = False
        elif age >= GIVE_UP_AFTER:
            item["unedited"] = False
    # 오래된 방제는 버려서 파일이 너무 커지지 않게 한다.
    while len(cache) > MAX_CACHE:
        cache.pop(next(iter(cache)))
    return lookups
