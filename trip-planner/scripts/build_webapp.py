# -*- coding: utf-8 -*-
"""웹앱 HTML 한 파일 만들기. 인터넷 없이 폰에서 열린다(길찾기 링크만 인터넷).

화면 틀은 옆 파일 `webapp_template.html` 이다(디자인은 거기서 고친다). 이 스크립트는 데이터만 넣는다.
탭 순서 = 여행 순서: 처음 → 준비 → 일정 → 현지 정보 → 이동 → 비상
- 처음 열면 큰 표지(여행 이름, 날짜별 경로, 핵심 네 칸, 시작 버튼)
- 폰 날짜가 여행 날이면 그날 일정을 자동으로 펼치고, 다음 일정까지 남은 시간을 보여 준다
- 준비물 체크는 폰(브라우저)에 남는다
- 장소마다 구글 지도 길찾기 링크, 택시 기사에게 보여 줄 숙소 현지어 주소 화면

쓰는 법: python build_webapp.py <여행.yaml> <나갈 파일.html>
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_trip  # noqa: E402
import trip_model as tm  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "webapp_template.html"


def _dur(m: int) -> str:
    if not m:
        return ""
    h, mm = divmod(int(m), 60)
    return (f"{h}시간" if h else "") + (f" {mm}분" if mm else "") if h else f"{mm}분"


def payload(data: dict, findings: list[dict]) -> dict:
    """웹앱이 쓰는 값만 뽑는다(계산은 여기서, 화면은 JS 가 그리기만)."""
    places = tm.places(data)
    trip = data.get("trip") or {}
    arr, dep = tm.single(data, "arrival"), tm.single(data, "departure")
    days = []
    for d in tm.days(data):
        items, prev = [], None
        for it in d["items"]:
            p = it["place_data"]
            go = it.get("go") or {}
            mins = tm.go_minutes(go)
            hours = p.get("hours")
            r = p.get("reservation") or {}
            items.append({
                "time": it.get("time"), "end": tm.fmt_min(it["end"]), "start_min": it["start"], "end_min": it["end"],
                "dur": _dur(it.get("stay") or 0), "no": it["no"], "name": p.get("name", it.get("place")),
                "local": p.get("local", ""), "what": it.get("what", ""), "note": it.get("note", ""), "alt": it.get("alt", ""),
                "go": (f"{go.get('mode', '')} {'/'.join(map(str, mins))}분" + (" (추정)" if go.get("estimated") else "")) if mins else "",
                "from": prev["place_data"].get("name") if prev else "",
                "depart": go.get("depart") or (tm.fmt_min(prev["end"]) if prev else ""),
                "hours": f"{hours[0]}~{hours[1]}" if hours else "", "map": tm.maps_link(p), "kind": p.get("kind", ""),
                "key": bool(r.get("timed")) or p.get("kind") in ("공항",), "slot": r.get("slot", ""),
            })
            prev = it
        days.append({"date": d["date"].isoformat() if d["date"] else "", "label": d["label"], "title": d.get("title", ""),
                     "color": d["color"], "n": d["index"] + 1, "items": items})
    pl = []
    for pid, p in places.items():
        r = p.get("reservation") or {}
        hours = p.get("hours")
        pl.append({"name": p.get("name", pid), "local": p.get("local", ""), "kind": p.get("kind", ""),
                   "hours": f"{hours[0]}~{hours[1]}" if hours else ("늘 열림" if p.get("open_air") else "확인 필요"),
                   "closed": ",".join(p.get("closed") or []) + (" (공휴일이면 다음 날)" if p.get("holiday_shift") else ""),
                   "min_age": p.get("min_age"), "res": r.get("status", ""), "res_kind": "시간 지정" if r.get("timed") else ("필요" if r.get("required") else ("권장" if r else "")),
                   "slot": r.get("slot", ""), "checked": str(p.get("checked", "")), "map": tm.maps_link(p), "note": p.get("note", "")})
    e = data.get("emergency") or {}
    h = places.get(e.get("hotel"), {})
    start, end = tm.to_date(trip.get("start")), tm.to_date(trip.get("end"))
    nights = (end - start).days if start and end else 0
    return {
        "title": trip.get("title", "여행"), "dest": trip.get("destination", ""), "start": str(trip.get("start")), "end": str(trip.get("end")),
        "period": f"{start.month}.{start.day}({tm.weekday_ko(start)}) – {end.month}.{end.day}({tm.weekday_ko(end)})" if start and end else "",
        "nights": f"{nights}박 {nights + 1}일" if nights else "",
        "checked": str(trip.get("checked", "")),
        "audits": len(trip.get("audits") or []), "check_ok": not any(f["level"] == check_trip.ERROR for f in findings),
        "who": [f"{t.get('label')} {t.get('age')}세" + (f" ({t['notes']})" if t.get("notes") else "") for t in tm.travelers(data)],
        "who_short": f"{len(tm.travelers(data))}명",
        "arrival": {"date": str(arr.get("date", "")), "time": arr.get("time", ""), "place": places.get(arr.get("place"), {}).get("name", ""), "note": arr.get("note", "")},
        "departure": {"date": str(dep.get("date", "")), "time": dep.get("time", ""), "by": dep.get("arrive_by", ""),
                      "place": places.get(dep.get("place"), {}).get("name", ""), "note": dep.get("note", ""),
                      "title": tm.return_words(data)[0], "where": tm.return_words(data)[1]},
        "holidays": [f"{tm.day_label(d)} {n}" for d, n in tm.holidays(data).items()],
        "days": days, "places": pl,
        "checklist": [{"id": f"c{i}", "when": c.get("when", ""), "item": c.get("item", ""), "done": bool(c.get("done"))}
                      for i, c in enumerate(data.get("checklist") or [])],
        "tips": data.get("tips") or [],
        "emergency": {"hotel": h.get("name", ""), "hotel_local": h.get("local", ""), "address": h.get("address_local", ""), "phone": h.get("phone", ""),
                      "police": e.get("police", ""), "ambulance": e.get("ambulance", ""), "embassy": e.get("embassy") or {},
                      "consular": e.get("consular_call", "")},
        "check": {"summary": check_trip.summary(findings), "items": findings,
                  "errors": sum(1 for f in findings if f["level"] == check_trip.ERROR)},
        "key": f"trip-{trip.get('title', '')}-{trip.get('start')}",
    }


FILE_HEAD = ('<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n')


def build(data: dict, findings: list[dict] | None = None, mode: str = "file") -> str:
    """mode="file": 폰에 넣어 여는 HTML 한 파일(인터넷 없이 열림, 글꼴만 온라인일 때 받음).
    mode="artifact": claude.ai 아티팩트로 올릴 본문(문서 뼈대는 아티팩트가 씌운다). 열면 준비물 체크를 함께 본다."""
    if findings is None:
        findings = check_trip.check(data)
    raw = json.dumps(payload(data, findings), ensure_ascii=False, default=str).replace("</", "<\\/")
    title = html.escape(str((data.get("trip") or {}).get("title", "여행")))
    body = TEMPLATE.read_text(encoding="utf-8").replace("__TITLE__", title).replace("__DATA__", raw)
    return body if mode == "artifact" else FILE_HEAD + body + "\n</html>\n"


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    mode = "artifact" if "--artifact" in argv else "file"
    Path(args[1]).write_text(build(tm.load(args[0]), mode=mode), encoding="utf-8")
    print(f"웹앱 HTML ({mode}) → {args[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
