# -*- coding: utf-8 -*-
"""J 검사기: 결과물을 만들기 전에 여행 데이터의 틀린 곳을 찾는다.

규칙은 실제 여행 계획에서 나온 실수에서 왔다.
  open_before    영업 시작 전 도착 (마감 뒤까지 머무는 것도)
  closed_day     방문 요일이 휴무일
  holiday_shift  공휴일 다음 날 휴무 (휴무일이 공휴일이면 열고 다음 날 쉬는 곳)
  min_age        나이 제한
  reservation    시간 지정 입장권 미예약, 예약 시각과 일정 시각이 다름
  single         도착이나 귀국이 둘
  sane           말이 안 되는 값 (나이 422세, 25:00, 좌표 범위 밖)
  conflict       같은 사실이 다르게 적힘 (메모 속 귀국 시각이 귀국 칸과 다름)
  travel         이동 여유 (앞 일정 끝 + 이동 시간이 다음 시각을 넘음, 공항 여유)
  stale          확인한 날짜가 오래됨, 영업시간 모름
  ref            없는 장소를 가리킴, 여행 기간 밖 날짜

쓰는 법: python check_trip.py <여행.yaml> [--json]
종료코드: 0 오류 없음 (경고는 있을 수 있음), 1 오류 있음, 2 파일을 못 읽음
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trip_model as tm  # noqa: E402

ERROR, WARN = "오류", "경고"
TIME_IN_TEXT = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
DEPART_WORDS = ("귀국", "출국", "집결", "공항 도착", "출발 항공", "비행기")
ARRIVE_WORDS = ("입국", "도착 항공", "현지 도착")


def _f(level, rule, where, msg):
    return {"level": level, "rule": rule, "where": where, "msg": msg}


def _texts(data):
    """(위치, 글) 을 모두 돌려준다: 일정 항목의 what/note/alt, 도착·귀국 메모, 장소 메모, 할 일."""
    for d in tm.days(data):
        for it in d["items"]:
            for k in ("what", "note", "alt"):
                if it.get(k):
                    yield f"{d['label']} {it.get('time')} {k}", str(it[k])
    for key in ("arrival", "departure"):
        v = data.get(key)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, dict) and x.get("note"):
                yield f"{key} note", str(x["note"])
    for pid, p in tm.places(data).items():
        if p.get("note"):
            yield f"장소 {pid} note", str(p["note"])
    for c in data.get("checklist") or []:
        if c.get("item"):
            yield f"할 일 {c.get('when')}", str(c["item"])


def check(data: dict) -> list[dict]:
    out: list[dict] = []
    trip = data.get("trip") or {}
    start, end = tm.to_date(trip.get("start")), tm.to_date(trip.get("end"))
    hol = tm.holidays(data)
    places = tm.places(data)
    young = tm.youngest(data)

    # --- sane: 사람, 날짜, 장소 값 ---
    if not start or not end:
        out.append(_f(ERROR, "sane", "trip", "여행 시작일과 끝나는 날(trip.start, trip.end)이 없거나 날짜가 아니다"))
    elif end < start:
        out.append(_f(ERROR, "sane", "trip", f"끝나는 날 {end} 이 시작일 {start} 보다 앞이다"))
    for t in tm.travelers(data):
        age = t.get("age")
        if age is None:
            out.append(_f(WARN, "sane", f"여행자 {t.get('label')}", "나이가 없어 나이 제한을 볼 수 없다"))
        elif not isinstance(age, (int, float)) or not (0 <= age <= 110):
            out.append(_f(ERROR, "sane", f"여행자 {t.get('label')}", f"나이 {age} 는 말이 안 된다"))
    for pid, p in places.items():
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            out.append(_f(WARN, "sane", f"장소 {pid}", "좌표가 없어 지도와 길찾기를 못 만든다"))
        elif not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
            out.append(_f(ERROR, "sane", f"장소 {pid}", f"좌표 {lat},{lon} 가 범위 밖이다"))
        hours = p.get("hours")
        if hours:
            o, c = (tm.to_min(hours[0]), tm.to_min(hours[1])) if len(hours) == 2 else (None, None)
            if o is None or c is None:
                out.append(_f(ERROR, "sane", f"장소 {pid}", f"영업시간 {hours} 를 읽을 수 없다 (\"10:00\" 꼴 두 개)"))
        if p.get("min_age") is not None and not (0 <= int(p["min_age"]) <= 25):
            out.append(_f(ERROR, "sane", f"장소 {pid}", f"나이 제한 {p['min_age']} 은 말이 안 된다"))
        for wd in p.get("closed") or []:
            if wd not in tm.WEEKDAYS:
                out.append(_f(ERROR, "sane", f"장소 {pid}", f"휴무 요일 '{wd}' 는 월~일 중 하나가 아니다"))

    # --- single: 도착, 귀국은 하나 ---
    for key, name in (("arrival", "도착"), ("departure", "귀국")):
        v = data.get(key)
        if isinstance(v, list) and len(v) > 1:
            times = ", ".join(f"{tm.to_date(x.get('date'))} {x.get('time')}" for x in v if isinstance(x, dict))
            out.append(_f(ERROR, "single", key, f"{name}이 {len(v)}개다 ({times}). 하나로 정하고 나머지는 지운다"))
        elif not v:
            out.append(_f(WARN, "single", key, f"{name} 칸이 없다"))
    dep, arr = tm.single(data, "departure"), tm.single(data, "arrival")
    for key, v in (("arrival", arr), ("departure", dep)):
        if v:
            if tm.to_min(v.get("time")) is None:
                out.append(_f(ERROR, "sane", key, f"시각 '{v.get('time')}' 이 HH:MM 이 아니다"))
            d = tm.to_date(v.get("date"))
            if d and start and end and not (start <= d <= end):
                out.append(_f(ERROR, "ref", key, f"날짜 {d} 가 여행 기간 {start}~{end} 밖이다"))
            if v.get("place") and v["place"] not in places:
                out.append(_f(ERROR, "ref", key, f"없는 장소 '{v['place']}'"))

    # --- 일정 항목 ---
    for d in tm.days(data):
        date = d["date"]
        if date is None:
            out.append(_f(ERROR, "sane", f"일정 {d.get('date')}", "날짜를 읽을 수 없다"))
            continue
        if start and end and not (start <= date <= end):
            out.append(_f(ERROR, "ref", d["label"], f"여행 기간 {start}~{end} 밖의 날짜다"))
        wd = tm.weekday_ko(date)
        prev = None
        for it in d["items"]:
            where = f"{d['label']} {it.get('time')} {it['place_data'].get('name', it.get('place'))}"
            pid = it.get("place")
            if pid not in places:
                out.append(_f(ERROR, "ref", where, f"없는 장소 '{pid}'"))
                prev = it
                continue
            p = places[pid]
            s, e = it["start"], it["end"]
            if s is None:
                out.append(_f(ERROR, "sane", where, f"시각 '{it.get('time')}' 이 HH:MM 이 아니다"))
                prev = it
                continue
            stay = it.get("stay") or 0
            if not (0 <= int(stay) <= 16 * 60):
                out.append(_f(ERROR, "sane", where, f"머무는 시간 {stay}분은 말이 안 된다"))

            # 휴무
            closed = set(p.get("closed") or [])
            prev_day = date - tm.dt.timedelta(days=1)
            if wd in closed:
                if p.get("holiday_shift") and date in hol:
                    pass  # 휴무일이 공휴일이면 연다
                else:
                    out.append(_f(ERROR, "closed_day", where, f"{wd}요일은 휴무다"))
            if p.get("holiday_shift") and prev_day in hol and tm.weekday_ko(prev_day) in closed:
                out.append(_f(ERROR, "holiday_shift", where,
                              f"전날 {tm.day_label(prev_day)}({hol[prev_day]})이 휴무일과 겹친 공휴일이라 이날 쉰다"))
            if date in hol and p.get("closed_holidays"):
                out.append(_f(ERROR, "closed_day", where, f"공휴일({hol[date]}) 휴무다"))

            # 영업시간
            hours = p.get("hours")
            if hours and len(hours) == 2:
                o, c = tm.to_min(hours[0]), tm.to_min(hours[1])
                if o is not None and s < o:
                    out.append(_f(ERROR, "open_before", where, f"{it.get('time')} 도착인데 {hours[0]} 에 연다"))
                if c is not None and e is not None and stay and e > c:
                    out.append(_f(WARN, "open_before", where, f"{tm.fmt_min(e)} 까지 머무는데 {hours[1]} 에 닫는다"))
                if c is not None and s >= c:
                    out.append(_f(ERROR, "open_before", where, f"{it.get('time')} 도착인데 {hours[1]} 에 이미 닫았다"))
            elif p.get("kind") in ("관광", "식사", "쇼핑") and not p.get("open_air"):
                out.append(_f(WARN, "stale", where, "영업시간이 없다. 확인해서 hours 에 적는다"))

            # 나이
            if p.get("min_age") is not None and young is not None and young < int(p["min_age"]):
                out.append(_f(ERROR, "min_age", where, f"{p['min_age']}세 미만 입장 불가인데 가장 어린 여행자가 {young}세다"))

            # 예약
            r = p.get("reservation") or {}
            if r.get("timed") and r.get("status") != "완료":
                out.append(_f(ERROR, "reservation", where, "시간 지정 입장권인데 예약이 끝나지 않았다"))
            elif r.get("required") and r.get("status") != "완료":
                out.append(_f(WARN, "reservation", where, "예약이 필요한데 아직 안 했다"))
            if r.get("slot") and tm.to_min(r["slot"]) is not None:
                slot = tm.to_min(r["slot"])
                if e is not None and not (s <= slot <= max(e, s)):
                    out.append(_f(ERROR, "reservation", where,
                                  f"예약 시각 {r['slot']} 이 이 일정({it.get('time')}~{tm.fmt_min(e)}) 밖이다"))

            # 이동
            go = it.get("go") or {}
            mins = tm.go_minutes(go)
            if prev is not None and prev.get("end") is not None and mins:
                leave = tm.to_min(go.get("depart")) if go.get("depart") else prev["end"]
                if leave is None:
                    out.append(_f(ERROR, "sane", where, f"출발 시각 '{go.get('depart')}' 이 HH:MM 이 아니다"))
                    leave = prev["end"]
                if leave < prev["end"]:
                    out.append(_f(ERROR, "travel", where,
                                  f"{tm.fmt_min(leave)} 에 떠나야 하는데 앞 일정이 {tm.fmt_min(prev['end'])} 에 끝난다"))
                worst = leave + mins[-1]
                if worst > s:
                    est = " (가장 오래 걸리는 경우)" if len(mins) > 1 else ""
                    out.append(_f(ERROR, "travel", where,
                                  f"{tm.fmt_min(leave)} 출발 + {mins[-1]}분{est} = {tm.fmt_min(worst)} 도착이라 {it.get('time')} 에 못 맞춘다"))
            for m in mins:
                if not (0 < m <= 24 * 60):
                    out.append(_f(ERROR, "sane", where, f"이동 {m}분은 말이 안 된다"))
            prev = it

    # 공항 여유
    if dep:
        dd, by = tm.to_date(dep.get("date")), tm.to_min(dep.get("arrive_by"))
        buf = int(dep.get("buffer_min", 30))
        t = tm.to_min(dep.get("time"))
        if by is not None and t is not None and by > t - 60 and places.get(dep.get("place"), {}).get("kind") == "공항":
            out.append(_f(WARN, "travel", "departure", f"공항 도착 {dep.get('arrive_by')} 이 출발 {dep.get('time')} 1시간 전보다 늦다"))
        for d in tm.days(data):
            if d["date"] != dd:
                continue
            for i, it in enumerate(d["items"]):
                if it.get("place") != dep.get("place"):
                    continue
                mins = tm.go_minutes(it.get("go"))
                prev = d["items"][i - 1] if i else None
                go = it.get("go") or {}
                leave = tm.to_min(go.get("depart")) if go.get("depart") else (prev or {}).get("end")
                if leave is None or not mins or by is None:
                    continue
                cases = ", ".join(f"{m}분이면 {by - (leave + m)}분 남음" for m in mins)
                slack = by - (leave + mins[-1])
                if slack < 0:
                    out.append(_f(ERROR, "travel", "공항 이동", f"{tm.fmt_min(leave)} 출발: {cases}. 가장 늦으면 공항 도착 {dep.get('arrive_by')} 에 못 맞춘다"))
                elif slack < buf:
                    out.append(_f(WARN, "travel", "공항 이동", f"{tm.fmt_min(leave)} 출발: {cases}. 가장 늦으면 여유가 {buf}분보다 적다"))

    # --- conflict: 글 속 시각이 칸과 다름 ---
    dep_times = {x for x in (dep.get("time"), dep.get("arrive_by")) if x} if dep else set()
    arr_times = {arr.get("time")} if arr and arr.get("time") else set()
    dep_min = {tm.to_min(x) for x in dep_times}
    arr_min = {tm.to_min(x) for x in arr_times}
    for where, text in _texts(data):
        for m in TIME_IN_TEXT.finditer(text):
            val = int(m.group(1)) * 60 + int(m.group(2))
            around = text[max(0, m.start() - 12): m.end() + 12]
            if dep_min and any(w in around for w in DEPART_WORDS) and val not in dep_min:
                out.append(_f(ERROR, "conflict", where,
                              f"글에 '{around.strip()}' 이라 적혔는데 귀국 칸은 출발 {dep.get('time')}, 공항 도착 {dep.get('arrive_by')} 이다"))
            if arr_min and any(w in around for w in ARRIVE_WORDS) and val not in arr_min:
                out.append(_f(ERROR, "conflict", where, f"글에 '{around.strip()}' 이라 적혔는데 도착 칸은 {arr.get('time')} 이다"))
    for d in tm.days(data):
        for it in d["items"]:
            r = (it["place_data"].get("reservation") or {})
            if not r.get("slot"):
                continue
            for k in ("what", "note"):
                for m in re.finditer(r"([01]?\d|2[0-3]):([0-5]\d)\s*입장", str(it.get(k) or "")):
                    if tm.to_min(f"{m.group(1)}:{m.group(2)}") != tm.to_min(r["slot"]):
                        out.append(_f(ERROR, "conflict", f"{d['label']} {it.get('time')} {k}",
                                      f"글에는 {m.group(0)} 인데 예약 칸은 {r['slot']} 이다"))

    # --- stale: 확인일 ---
    stale_days = int(trip.get("stale_days", 30))
    for pid, p in places.items():
        c = tm.to_date(p.get("checked"))
        if c is None:
            out.append(_f(WARN, "stale", f"장소 {pid}", "확인한 날짜(checked)가 없다"))
        elif start and (start - c).days > stale_days:
            out.append(_f(WARN, "stale", f"장소 {pid}", f"{c} 에 확인한 정보라 여행 시작({start})보다 {(start - c).days}일 오래됐다"))
    # 추천 칸(picks): 출처와 확인일이 꼭 있어야 하고, 오래되면 경고(가게는 일정보다 빨리 바뀐다)
    for i, p in enumerate(data.get("picks") or []):
        where = f"추천 {p.get('name', i + 1)}"
        if p.get("type") not in ("맛집", "요즘"):
            out.append(_f(ERROR, "ref", where, "type 은 맛집 또는 요즘"))
        if not p.get("source"):
            out.append(_f(ERROR, "stale", where, "출처(source)가 없다"))
        c = tm.to_date(p.get("checked"))
        if c is None:
            out.append(_f(ERROR, "stale", where, "확인한 날짜(checked)가 없다"))
        elif start and (start - c).days > min(stale_days, 60):
            out.append(_f(WARN, "stale", where, f"{c} 에 확인한 추천이라 여행 시작보다 {(start - c).days}일 오래됐다"))
    return out


def summary(findings: list[dict]) -> str:
    e = sum(1 for f in findings if f["level"] == ERROR)
    w = sum(1 for f in findings if f["level"] == WARN)
    return f"오류 {e}, 경고 {w}"


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    try:
        data = tm.load(args[0])
    except (OSError, tm.TripError, ValueError) as e:
        print(f"여행 파일을 못 읽음: {e}", file=sys.stderr)
        return 2
    findings = check(data)
    if "--json" in argv:
        print(json.dumps(findings, ensure_ascii=False, indent=1))
    else:
        for f in findings:
            print(f"[{f['level']}] {f['rule']:<13} {f['where']}: {f['msg']}")
        print(summary(findings))
    return 1 if any(f["level"] == ERROR for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
