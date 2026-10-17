# -*- coding: utf-8 -*-
"""장소 사진을 위키미디어 공용에서 한 번에 받는다(라이선스 걸러서).
쓰는 법: python fetch_photos.py <목록.json> <나갈 폴더>
목록.json: [{"key": "seongsan", "q": "Seongsan Ilchulbong"}, ...]  ("file": "File:..." 로 콕 집어도 됨)
나갈 폴더에 <key>.jpg 와 photos.json(출처·작가·라이선스·주소)을 쓴다.
받는 라이선스: CC BY, CC BY-SA, CC0, 퍼블릭 도메인. 그 밖(NC, ND, 저작권 표시 없음)은 건너뛴다."""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "trip-planner-skill/0.1 (personal travel sheet)"}
OK = re.compile(r"^(CC BY(-SA)? [\d.]+( [A-Za-z\-]+)?|CC0|Public domain|PD.*)$", re.I)


def fetch(url: str) -> bytes:
    """429(너무 잦음)면 쉬었다가 다시. 위키미디어는 빠르게 여러 번 부르면 막는다."""
    for k in range(5):
        time.sleep(1.0 + k * 15)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == 4:
                raise


def get(params: dict) -> dict:
    return json.loads(fetch(API + "?" + urllib.parse.urlencode({**params, "format": "json"})))


def clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def candidates(item: dict, width: int):
    base = {"action": "query", "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": width}
    if item.get("file"):
        d = get({**base, "titles": item["file"]})
    else:
        d = get({**base, "generator": "search", "gsrsearch": f"{item['q']} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 12})
    pages = sorted((d.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        lic = clean((md.get("LicenseShortName") or {}).get("value", ""))
        if not OK.match(lic) or ii.get("width", 0) < 800 or ii.get("width", 0) < ii.get("height", 1) * 0.9:
            continue  # 라이선스 안 맞음, 작음, 세로 사진
        yield {"title": p["title"], "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"),
               "artist": clean((md.get("Artist") or {}).get("value", ""))[:80] or "작가 미상",
               "license": lic, "source": "Wikimedia Commons"}


def main(argv):
    items = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out = Path(argv[2]); out.mkdir(parents=True, exist_ok=True)
    meta_p = out / "photos.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    for it in items:
        if it["key"] in meta and (out / f"{it['key']}.jpg").exists():
            continue
        got = None
        for c in candidates(it, it.get("width", 640)):
            try:
                (out / f"{it['key']}.jpg").write_bytes(fetch(c["thumb"]))
                got = c
                break
            except Exception as e:  # noqa: BLE001
                print(it["key"], "받기 실패", e)
        if got:
            meta[it["key"]] = {k: v for k, v in got.items() if k != "thumb"}
            print(f"{it['key']}\t{got['license']}\t{got['artist'][:30]}\t{got['title'][:60]}")
        else:
            print(f"{it['key']}\t못 찾음 ({it.get('q') or it.get('file')})")
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
