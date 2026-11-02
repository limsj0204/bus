"""임시: SOOP 통합검색 게시글 API가 작성자 닉네임 검색을 어떻게 받는지 확인한다."""
import json
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
NICK = "양도끼"


def call(extra):
    params = {
        "l": "DF", "w": "webk", "isMobile": "0", "szType": "json", "c": "UTF-8", "v": "5.0",
        "szKeyword": urllib.parse.quote(NICK), "nPageNo": "1", "nListCnt": "10",
        "szOrder": "reg_date", "szTerm": "1year", "location": "total_search", "isHashSearch": "0",
    }
    params.update(extra)
    url = "https://sch.sooplive.com/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.sooplive.com/", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return url, r.read().decode("utf-8", errors="replace")


def lists(data, path="$"):
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
        yield path, data
    if isinstance(data, dict):
        for k, v in data.items():
            yield from lists(v, f"{path}.{k}")
    elif isinstance(data, list):
        for i, v in enumerate(data[:3]):
            yield from lists(v, f"{path}[{i}]")


variants = []
for m in ["postSearch", "bbsSearch", "boardSearch"]:
    for scope in ["all", "nick", "user_nick", "nickname", "writer", "user_id", "title"]:
        variants.append({"m": m, "tab": "post", "szSearchScope": scope})
variants.append({"m": "postSearch", "tab": "post", "szSearchScope": "all", "szSearchType": "nick"})
variants.append({"m": "postSearch", "tab": "post", "szSearchScope": "all", "szField": "nick"})

for extra in variants:
    print("=" * 100)
    print("PARAMS", extra)
    try:
        url, body = call(extra)
    except Exception as e:
        print("ERROR", e)
        continue
    try:
        data = json.loads(body)
    except Exception:
        print("NOT JSON", body[:300])
        continue
    if isinstance(data, dict):
        print("TOP KEYS", list(data.keys())[:20], {k: data[k] for k in data if not isinstance(data[k], (list, dict))})
    found = list(lists(data))
    if not found:
        print("NO LIST", body[:400])
    for path, items in found[:2]:
        print("LIST", path, "count", len(items), "keys", sorted(items[0].keys()))
        for it in items[:10]:
            short = {k: (str(v)[:60]) for k, v in it.items() if k in (
                "title_no", "bbs_no", "station_no", "title_name", "title", "user_id", "user_nick", "bj_id", "bj_nick",
                "reg_date", "board_type", "url", "station_user_id", "station_nick", "nickname", "writer_id", "writer_nick")}
            print("   ", json.dumps(short, ensure_ascii=False))
    print("FIRST ITEM RAW", json.dumps(found[0][1][0], ensure_ascii=False)[:1500] if found else "")
