"""SOOP에서 키워드가 제목에 들어간 최근 클립·캐치를 모아 docs/data.json에 저장한다."""

import html
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_PATH = ROOT / "docs" / "data.json"

API_URL = "https://sch.sooplive.com/api.php"
KST = timezone(timedelta(hours=9))
PAGE_SIZE = 40
# 7일치 채우기처럼 오래 넘길 때와 평소 실행 때 넘길 수 있는 최대 페이지 수
MAX_BACKFILL_PAGES = 50
MAX_NORMAL_PAGES = 10
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# 응답 필드 이름을 정확히 모르므로 후보를 순서대로 시도한다.
FIELDS = {
    "id": ["title_no", "vod_no", "no", "id"],
    "title": ["title_name", "title", "file_title", "subject"],
    "streamer_id": ["user_id", "bj_id", "station_user_id", "broad_user_id"],
    "streamer_nick": ["user_nick", "bj_nick", "nickname", "nick"],
    "thumbnail": ["thumbnail_path", "ucc_thumb", "thumb", "thumbnail", "thumbnail_url"],
    "date": ["reg_date", "regdate", "reg_datetime", "create_date"],
    "views": ["view_cnt", "read_cnt", "count_view"],
    "url": ["url", "vod_url", "link"],
    "duration": ["duration", "vod_duration"],
}
# 클립·캐치의 원본 방송(다시보기) 스트리머가 기록된 칸. 업로더(user_id)와 함께 제외 검사에 쓴다.
ORIGIN_ID_FIELDS = ["original_bj", "original_reg_user_id"]
ORIGIN_NICK_FIELD = "original_user_nick"


def pick(item, field):
    for key in FIELDS[field]:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def find_items(data):
    """응답 JSON 안에서 영상 목록으로 보이는 리스트를 찾는다."""
    if isinstance(data, list):
        if data and all(isinstance(x, dict) for x in data) and any(pick(x, "title") for x in data):
            return data
        for x in data:
            found = find_items(x)
            if found:
                return found
    elif isinstance(data, dict):
        for value in data.values():
            found = find_items(value)
            if found:
                return found
    return []


def search(keyword, file_type, page=1):
    params = {
        "l": "DF",
        "m": "vodSearch",
        "w": "webk",
        "isMobile": "0",
        "szType": "json",
        "c": "UTF-8",
        "v": "5.0",
        # 사이트는 검색어를 한 번 인코딩한 값을 다시 인코딩해서 보낸다.
        "szKeyword": urllib.parse.quote(keyword),
        "nPageNo": str(page),
        "nListCnt": str(PAGE_SIZE),
        "szOrder": "reg_date",
        "szSearchScope": "all",
        "szContentAttr": "all",
        "nIncludeTranslationMatch": "1",
        "szFileType": file_type,
        "szTerm": "1year",
        "tab": "vod",
        "location": "total_search",
        "isHashSearch": "0",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.sooplive.com/",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def to_https(url):
    if not url:
        return None
    url = str(url)
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def format_duration(value):
    """초(또는 밀리초) 숫자나 "HH:MM:SS" 문자열을 "M:SS" 형태로 바꾼다."""
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if ":" in text:
        parts = [int(p) for p in text.split(":") if p.isdigit()]
        seconds = 0
        for p in parts:
            seconds = seconds * 60 + p
    else:
        try:
            seconds = int(float(text))
        except ValueError:
            return ""
        if seconds >= 36000:  # 10시간이 넘으면 밀리초로 본다.
            seconds //= 1000
    if seconds <= 0:
        return ""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def normalize(item, file_type, keyword):
    vod_id = pick(item, "id")
    title = pick(item, "title")
    if vod_id is None or not title:
        return None
    url = to_https(pick(item, "url"))
    if not url or not url.startswith("http"):
        url = f"https://vod.sooplive.com/player/{vod_id}"
        if file_type == "CATCH":
            url += "/catch"
    return {
        "id": str(vod_id),
        "type": file_type,
        "title": html.unescape(str(title)).strip(),
        "streamer_id": str(pick(item, "streamer_id") or ""),
        "streamer_nick": html.unescape(str(pick(item, "streamer_nick") or "")),
        "thumbnail": to_https(pick(item, "thumbnail")),
        "date": str(pick(item, "date") or ""),
        "views": pick(item, "views"),
        "duration": format_duration(pick(item, "duration")),
        "url": url,
        "keywords": [keyword],
        "origin_ids": sorted({str(item[k]) for k in ORIGIN_ID_FIELDS if item.get(k)}),
        "origin_nick": html.unescape(str(item.get(ORIGIN_NICK_FIELD) or "")),
    }


def related_ids(entry):
    """업로더와 원본 방송 스트리머 ID를 모두 소문자로 돌려준다."""
    ids = {entry.get("streamer_id", "")} | set(entry.get("origin_ids", []))
    return {i.lower() for i in ids if i}


def main():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    keywords = [str(k) for k in config.get("keywords") or []]
    exclude_words = [str(w).lower() for w in config.get("exclude_words") or []]
    exclude_streamers = {str(s).lower() for s in config.get("exclude_streamers") or []}
    types = [str(t).upper() for t in config.get("types") or ["CLIP", "CATCH"]]
    max_items = int(config.get("max_items") or 2000)
    backfill_days = int(config.get("backfill_days") or 0)

    saved = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {}
    existing = saved.get("items", [])
    progress = saved.get("progress", {})
    items = {(it["type"], it["id"]): it for it in existing}

    successes = 0
    new_count = 0
    now = datetime.now(KST).replace(tzinfo=None)
    for keyword in keywords:
        for file_type in types:
            key_name = f"{keyword}|{file_type}"
            prog = progress.get(key_name, {})
            backfilling = prog.get("backfill_days", 0) < backfill_days
            if backfilling or not prog.get("newest"):
                # 처음이거나 채우기 기간이 늘었으면 그 기간 끝까지 넘긴다.
                cutoff = (now - timedelta(days=backfill_days)).strftime(DATE_FORMAT)
                max_pages = MAX_BACKFILL_PAGES
            else:
                # 평소에는 지난번에 본 가장 최근 영상(여유 1시간)까지만 넘긴다.
                newest = datetime.strptime(prog["newest"], DATE_FORMAT)
                cutoff = (newest - timedelta(hours=1)).strftime(DATE_FORMAT)
                max_pages = MAX_NORMAL_PAGES

            reached_end = False
            failed = False
            for page in range(1, max_pages + 1):
                try:
                    data = search(keyword, file_type, page)
                except Exception as error:
                    print(f"[실패] '{keyword}' {file_type} {page}페이지: {error}", file=sys.stderr)
                    failed = True
                    break
                successes += 1
                raw_items = find_items(data)
                print(f"[성공] '{keyword}' {file_type} {page}페이지: {len(raw_items)}개 받음")
                if not raw_items:
                    if page == 1:
                        print(f"       응답 앞부분: {json.dumps(data, ensure_ascii=False)[:500]}")
                    reached_end = True
                    break

                dates = [str(pick(raw, "date") or "") for raw in raw_items]
                dates = [d for d in dates if d]
                if dates and max(dates) > prog.get("newest", ""):
                    prog["newest"] = max(dates)

                for raw in raw_items:
                    entry = normalize(raw, file_type, keyword)
                    if entry is None:
                        continue
                    title_lower = entry["title"].lower()
                    if keyword.lower() not in title_lower:
                        continue
                    if any(word in title_lower for word in exclude_words):
                        continue
                    if related_ids(entry) & exclude_streamers:
                        continue
                    key = (entry["type"], entry["id"])
                    if key in items:
                        merged = sorted(set(items[key].get("keywords", [])) | {keyword})
                        items[key].update(entry, keywords=merged)
                    else:
                        items[key] = entry
                        new_count += 1

                time.sleep(1.5)
                if (dates and min(dates) < cutoff) or len(raw_items) < PAGE_SIZE:
                    reached_end = True
                    break

            if reached_end and not failed and backfilling:
                prog["backfill_days"] = backfill_days
                print(f"       최근 {backfill_days}일치 채우기 완료")
            progress[key_name] = prog

    if successes == 0:
        print("모든 요청이 실패했어요. SOOP 쪽 주소나 형식이 바뀌었을 수 있어요.", file=sys.stderr)
        sys.exit(1)

    # 설정에서 빠진 키워드·제외 대상을 기존 데이터에도 반영한다.
    result = []
    for it in items.values():
        it["keywords"] = [k for k in it.get("keywords", []) if k in keywords]
        if not it["keywords"] or it["type"] not in types:
            continue
        if related_ids(it) & exclude_streamers:
            continue
        if any(word in it["title"].lower() for word in exclude_words):
            continue
        result.append(it)
    result.sort(key=lambda it: (it.get("date", ""), it["id"]), reverse=True)
    result = result[:max_items]

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "keywords": keywords,
                "progress": progress,
                "items": result,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"새 영상 {new_count}개, 총 {len(result)}개 저장")


if __name__ == "__main__":
    main()
