"""임시: postsSearch 응답 항목의 필드를 확인한다."""
import json
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def search(keyword, scope, order="reg_date", page=1, n=40):
    params = {"l": "DF", "m": "postsSearch", "v": "1.0", "szKeyword": keyword, "nPageNo": page, "nListCnt": n,
              "szOrder": order, "szTerm": "", "nUseFiltering": 1, "isMobile": 0, "isHashSearch": 0, "tab": "post",
              "szSearchScope": scope}
    url = "https://sch.sooplive.com/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.sooplive.com/", "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


for kw, scope, order in [("양도끼", "nickname", "reg_date"), ("yangdoki", "id", "reg_date"), ("양도끼", "nickname", "")]:
    print("=" * 100)
    print("CASE", kw, scope, order)
    data = search(kw, scope, order)
    items = data.get("DATA") or []
    print("TOTAL", data.get("TOTAL_CNT"), "got", len(items))
    if not items:
        continue
    print("KEYS", sorted(items[0].keys()))
    if order == "reg_date" and scope == "nickname":
        for it in items[:2]:
            print("RAW", json.dumps(it, ensure_ascii=False)[:3000])
    for it in items:
        short = {k: str(v)[:40] for k, v in it.items() if not isinstance(v, (list, dict)) and k.lower() not in ("contents", "content", "summary")}
        print("   ", json.dumps(short, ensure_ascii=False)[:600])
