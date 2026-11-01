"""임시: 원본 방송 제목을 가져올 수 있는 SOOP 주소를 시험한다."""
import json, urllib.parse, urllib.request
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
d = json.load(open("docs/data.json", encoding="utf-8"))
items = [i for i in d["items"] if i.get("broad_no")][:6]

def call(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Referer": "https://www.sooplive.com/"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", "replace")[:700]
    except Exception as e:
        return f"ERR {e}"

for it in items:
    bid = (it.get("origin_ids") or [""])[0]
    print("=" * 80)
    print("CLIP", it["type"], it["id"], "| title:", it["title"][:60], "| origin:", bid, "| broad_no:", it["broad_no"], "| org:", it.get("org_title_no"))
    for host in ["live.sooplive.co.kr", "live.sooplive.com"]:
        print(f"-- live api {host}:", call(f"https://{host}/afreeca/player_live_api.php", {"bid": bid, "type": "live", "player_type": "html5"}))
    if it.get("org_title_no"):
        for url in [f"https://api.m.sooplive.co.kr/station/video/a/view", f"https://api.m.sooplive.com/station/video/a/view"]:
            print(f"-- vod view {url}:", call(url, {"nTitleNo": it["org_title_no"], "nApiLevel": "10", "nPlaylistIdx": "0"}))
    print(f"-- station {bid}:", call(f"https://chapi.sooplive.co.kr/api/{bid}/station"))
