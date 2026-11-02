"""임시: SOOP 게시글 검색(postsSearch)의 작성자 검색 값과 응답 형식을 확인한다."""
import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
NICK = "양도끼"


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.sooplive.com/", "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


# 1) 게시글 필터(검색 범위) 옵션 정의 찾기
js = get("https://www.sooplive.com/_next/static/chunks/app/(main)/layout-460bc5ea9695900e.js")
for word in ["작성자", "닉네임", "제목+내용", "제목", "searchScope:lj", "lj=", "eF="]:
    for m in list(re.finditer(re.escape(word), js))[:6]:
        print(f"[{word}]", js[max(0, m.start() - 250):m.start() + 250].replace("\n", " "))
    print()

# 2) 실제 호출
base = {"l": "DF", "m": "postsSearch", "v": "1.0", "szKeyword": NICK, "nPageNo": 1, "nListCnt": 10,
        "szOrder": "reg_date", "szTerm": "", "nUseFiltering": 1, "isMobile": 0, "isHashSearch": 0, "tab": "post"}
for scope in [None, "all", "title_contents", "title", "contents", "nick", "user_nick", "nickname", "writer", "user_id", "id", "bj"]:
    params = dict(base)
    if scope:
        params["szSearchScope"] = scope
    print("=" * 100)
    print("SCOPE", scope)
    try:
        body = get("https://sch.sooplive.com/api.php", params)
    except Exception as e:
        print("ERROR", e)
        continue
    try:
        data = json.loads(body)
    except Exception:
        print("NOT JSON", repr(body[:300]))
        continue
    if isinstance(data, dict):
        print("TOP", {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} {len(v)}>") for k, v in data.items()})
    items = data.get("data") if isinstance(data, dict) else None
    if isinstance(items, list) and items:
        print("KEYS", sorted(items[0].keys()))
        for it in items[:10]:
            short = {k: str(v)[:50] for k, v in it.items() if not isinstance(v, (list, dict))}
            print("   ", json.dumps(short, ensure_ascii=False)[:700])
        if scope in (None, "all"):
            print("RAW", json.dumps(items[0], ensure_ascii=False)[:2500])
