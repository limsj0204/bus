"""임시: SOOP 검색 페이지가 게시글 검색을 어떻게 호출하는지 찾는다."""
import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
NICK = "양도끼"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.sooplive.com/"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


# 1) 검색 페이지와 스크립트에서 api.php 호출 방식 찾기
pages = [
    "https://www.sooplive.com/search?szLocation=total_search&szSearchType=post&szKeyword=" + urllib.parse.quote(NICK),
    "https://www.sooplive.co.kr/search?szLocation=total_search&szSearchType=post&szKeyword=" + urllib.parse.quote(NICK),
]
scripts = set()
for p in pages:
    try:
        body = get(p)
    except Exception as e:
        print("PAGE ERROR", p, e)
        continue
    print("PAGE", p, len(body))
    for src in re.findall(r'<script[^>]+src="([^"]+)"', body):
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urllib.parse.urljoin(p, src)
        scripts.add(src)
    for m in re.finditer(r"api\.php|postSearch|Search\b", body):
        pass
print("SCRIPTS", len(scripts))
for s in sorted(scripts):
    print("  ", s)

pat = re.compile(r"(Search|search)[\"']?\s*[:,]|api\.php|szSearchScope|SearchScope|szFileType|nick", re.I)
seen = set()
for s in sorted(scripts):
    try:
        js = get(s)
    except Exception as e:
        print("JS ERROR", s, e)
        continue
    hits = [m.start() for m in re.finditer(r"api\.php|[a-zA-Z]+Search\"|[a-zA-Z]+Search'|szSearchScope|szSearchType", js)]
    if not hits:
        continue
    print("#" * 100)
    print("JS", s, len(js), "hits", len(hits))
    names = sorted(set(re.findall(r"[\"']([a-zA-Z]+Search)[\"']", js)))
    print("SEARCH NAMES", names)
    for h in hits[:80]:
        snippet = js[max(0, h - 200):h + 300].replace("\n", " ")
        key = snippet[150:260]
        if key in seen:
            continue
        seen.add(key)
        print("---", snippet)
