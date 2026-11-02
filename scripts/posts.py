"""SOOP 통합검색 게시글 탭에서 정해 둔 작성자가 새로 쓴 글을 모아 docs/posts.json에 저장한다.

처음 실행한 시각을 기준으로 삼아, 그 뒤에 올라온 글만 모으고 알린다.
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import notify

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_PATH = ROOT / "docs" / "posts.json"

API_URL = "https://sch.sooplive.com/api.php"
KST = timezone(timedelta(hours=9))
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
PAGE_SIZE = 40
# 한 번 실행할 때 넘겨 볼 최대 페이지 수 (10분 사이에 40개 넘게 쓰는 일은 거의 없다)
MAX_PAGES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def search(nickname, page):
    """게시글 탭에서 '검색 범위: 닉네임'으로 최신순 검색한다."""
    params = {
        "l": "DF",
        "m": "postsSearch",
        "v": "1.0",
        "szKeyword": nickname,
        "nPageNo": str(page),
        "nListCnt": str(PAGE_SIZE),
        "szOrder": "reg_date",
        "szTerm": "",
        "nUseFiltering": "1",
        "isMobile": "0",
        "isHashSearch": "0",
        "tab": "post",
        "szSearchScope": "nickname",
    }
    request = urllib.request.Request(
        API_URL + "?" + urllib.parse.urlencode(params),
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.sooplive.com/",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(data, dict) or str(data.get("RESULT")) != "1":
        raise ValueError(f"예상과 다른 응답: {json.dumps(data, ensure_ascii=False)[:300]}")
    return data.get("DATA") or []


def clean(text):
    text = html.unescape(str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def to_https(url):
    url = str(url or "")
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def normalize(raw):
    post_id = raw.get("title_no")
    if not post_id:
        return None
    station_id = str(raw.get("station_user_id") or "")
    url = to_https(raw.get("url"))
    if not url.startswith("http"):
        url = f"https://www.sooplive.com/station/{station_id}/post/{post_id}"
    return {
        "id": str(post_id),
        "type": "POST",
        "title": clean(raw.get("title")),
        "content": clean(raw.get("content"))[:300],
        "date": str(raw.get("reg_date") or ""),
        "url": url,
        "author_id": str(raw.get("user_id") or ""),
        "author_nick": clean(raw.get("user_nick")),
        # 글이 올라간 방송국(게시판 주인)
        "station_id": station_id,
        "station_nick": clean(raw.get("station_user_nick")),
        "thumbnail": to_https(raw.get("thumbnail")) or None,
        "photos": int(raw.get("photo_cnt") or 0),
        "views": raw.get("view_cnt"),
        "likes": raw.get("recomm_cnt"),
        "comments": raw.get("memo_cnt"),
    }


def main():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    settings = config.get("posts") or {}
    if settings.get("enabled") is False:
        print("게시글 수집: 꺼져 있어서 건너뜀")
        return
    authors = [str(a).strip() for a in settings.get("authors") or [] if str(a).strip()]
    author_ids = {str(a).strip().lower() for a in settings.get("author_ids") or [] if str(a).strip()}
    max_items = int(settings.get("max_items") or 500)
    backfill_hours = float(settings.get("backfill_hours") or 0)

    saved = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {}
    since = saved.get("since", {})
    backfilled = saved.get("backfilled", {})
    items = {it["id"]: it for it in saved.get("items", [])}
    now_dt = datetime.now(KST)
    now = now_dt.strftime(DATE_FORMAT)

    successes = 0
    to_notify = []
    for nickname in authors:
        if nickname not in since:
            # 처음 보는 작성자는 지금부터 올라오는 글만 모은다.
            since[nickname] = now
            print(f"[게시글] '{nickname}': 지금({now})부터 새 글을 모아요")
        # backfill_hours를 늘리면 한 번만 그만큼 앞선 글까지 채운다.
        backfilling = backfill_hours > float(backfilled.get(nickname) or 0)
        if backfilling:
            earlier = (now_dt - timedelta(hours=backfill_hours)).strftime(DATE_FORMAT)
            since[nickname] = min(since[nickname], earlier)
            print(f"[게시글] '{nickname}': 최근 {backfill_hours:g}시간치({since[nickname]}부터)를 한 번 채워요")
        start = since[nickname]
        seen_ids = set()
        fetched = False
        for page in range(1, MAX_PAGES + 1):
            try:
                raw_items = search(nickname, page)
            except Exception as error:
                print(f"[게시글 실패] '{nickname}' {page}페이지: {error}", file=sys.stderr)
                break
            successes += 1
            fetched = True
            page_ids = {str(r.get("title_no")) for r in raw_items}
            if not raw_items or page_ids <= seen_ids:
                break
            seen_ids |= page_ids

            dates = []
            for raw in raw_items:
                post = normalize(raw)
                if post is None:
                    continue
                dates.append(post["date"])
                # 닉네임 검색은 비슷한 닉네임도 섞일 수 있어 작성자를 한 번 더 확인한다.
                if post["author_nick"] != nickname:
                    continue
                if author_ids and post["author_id"].lower() not in author_ids:
                    continue
                if post["date"] < start:
                    continue
                if post["id"] in items:
                    items[post["id"]].update(post)
                else:
                    items[post["id"]] = post
                    to_notify.append(post)
            print(f"[게시글] '{nickname}' {page}페이지: {len(raw_items)}개 받음")
            if not dates or min(dates) < start:
                break
            time.sleep(1.5)
        if backfilling and fetched:
            backfilled[nickname] = backfill_hours

    if authors and successes == 0:
        print("게시글 요청이 모두 실패했어요. SOOP 쪽 주소나 형식이 바뀌었을 수 있어요.", file=sys.stderr)
        sys.exit(1)

    # 설정에서 빠진 작성자의 글은 지운다.
    since = {k: v for k, v in since.items() if k in authors}
    backfilled = {k: v for k, v in backfilled.items() if k in authors}
    result = [it for it in items.values() if it["author_nick"] in since]
    result.sort(key=lambda it: (it.get("date", ""), it["id"]), reverse=True)
    result = result[:max_items]

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "authors": authors,
                "since": since,
                "backfilled": backfilled,
                "items": result,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"새 글 {len(to_notify)}개, 총 {len(result)}개 저장")

    kept = {it["id"] for it in result}
    if settings.get("discord", True):
        notify.send_posts([it for it in to_notify if it["id"] in kept], config)


if __name__ == "__main__":
    main()
