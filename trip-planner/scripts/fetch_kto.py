# -*- coding: utf-8 -*-
"""국내 장소 사진을 한국관광공사 관광사진 정보 API(공공누리 제1유형)에서 받는다.
쓰는 법: python fetch_kto.py <목록.json> <사진 폴더>
목록.json: [{"key": "seongsan", "q": "성산일출봉", "pick": 1}, ...]  (pick: 검색 결과 몇 번째를 쓸지, 기본 1)
키: 공공데이터포털(data.go.kr)에서 "한국관광공사_관광사진 정보_GW" 활용신청 뒤 받은 일반 인증키를
    환경변수 DATA_GO_KR_KEY 에 넣는다. 키는 파일에 적지 않는다.
사진 폴더에 <key>.jpg 를 쓰고 photos.json 에 출처를 더한다(있던 항목은 덮어씀).
국내만 해당. 해외는 fetch_photos.py(위키미디어). 받은 사진은 꼭 눈으로 장소를 확인한다
(검색 1위가 옆 장소 사진이거나 세로 사진일 때가 있다 — pick 으로 고른다).
출처 표시: 한 장 그림 아래에 "한국관광공사(공공누리 1유형) — 사진가"로 자동으로 적힌다.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://apis.data.go.kr/B551011/PhotoGalleryService1/gallerySearchList1"
SOURCE = "한국관광공사(공공누리 1유형)"
IMG_HOST_SUFFIX = ".visitkorea.or.kr"


def search(key: str, q: str, rows: int) -> list[dict]:
    qs = urllib.parse.urlencode([("serviceKey", key), ("numOfRows", str(rows)), ("pageNo", "1"),
                                 ("MobileOS", "ETC"), ("MobileApp", "trip-planner"), ("_type", "json"),
                                 ("arrange", "A"), ("keyword", q)])
    with urllib.request.urlopen(f"{BASE}?{qs}", timeout=30) as r:
        doc = json.loads(r.read().decode("utf-8"))
    items = (((doc.get("response") or {}).get("body") or {}).get("items") or {})
    it = items.get("item") if isinstance(items, dict) else None
    return [] if it is None else (it if isinstance(it, list) else [it])


def main(list_path: str, out_dir: str) -> None:
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        raise SystemExit("환경변수 DATA_GO_KR_KEY 가 없습니다(공공데이터포털 일반 인증키).")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta_p = out / "photos.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    for job in json.loads(Path(list_path).read_text(encoding="utf-8")):
        k, q, pick = job["key"], job["q"], int(job.get("pick", 1))
        try:
            items = search(key, q, max(pick, 5))
        except Exception as e:  # noqa: BLE001
            print(f"{k}\t못 받음 ({q}) {type(e).__name__}")
            continue
        if len(items) < pick:
            print(f"{k}\t못 찾음 ({q})")
            continue
        it = items[pick - 1]
        url = it.get("galWebImageUrl", "")
        if not urllib.parse.urlparse(url).hostname or not urllib.parse.urlparse(url).hostname.endswith(IMG_HOST_SUFFIX):
            print(f"{k}\t사진 주소 이상 ({url})")
            continue
        with urllib.request.urlopen(url, timeout=60) as r:
            (out / f"{k}.jpg").write_bytes(r.read())
        meta[k] = {"title": it.get("galTitle", ""), "page": url, "artist": it.get("galPhotographer") or "한국관광공사",
                   "license": "공공누리 제1유형", "source": SOURCE, "taken": it.get("galPhotographyMonth", ""),
                   "where": it.get("galPhotographyLocation", "")}
        print(f"{k}\t{it.get('galTitle')}\t{it.get('galPhotographyMonth')}\t{it.get('galPhotographyLocation')}")
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
