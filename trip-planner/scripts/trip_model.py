# -*- coding: utf-8 -*-
"""여행 데이터 파일(YAML) 읽기와 공용 도우미.

모든 결과물(인포그래픽, 웹앱, 지도, 시트)과 검사기가 이 모듈로 같은 데이터를 읽는다.
사실은 데이터 파일에 한 번만 적고, 여기서 계산한 값(요일, 끝나는 시각, 번호, 색)을 다 같이 쓴다.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# 날짜별 색: 구글 내 지도(My Maps) 색 팔레트에서 서로 잘 구분되는 것만 골랐다.
# 같은 색을 지도, 웹앱, 인포그래픽이 다 같이 써서 "빨강 = 첫날"이 어디서나 같다.
DAY_COLORS = ["#FF5252", "#0288D1", "#0F9D58", "#9C27B0", "#F57C00", "#0097A7", "#880E4F", "#4E342E"]
BASE_COLOR = "#424242"   # 숙소처럼 날짜에 안 묶인 곳

# 장소 아이콘: 구글 내 지도 아이콘 번호. KML 의 스타일 이름 "icon-<번호>-<색>" 을 내 지도가 읽어 그 아이콘으로 보여 준다.
# 데이터에는 사람 말(icon: 온천)로 적고, 없으면 kind 로 고른다.
# 번호는 만든 사람이 내 지도에서 내보낸 샘플 KML 에서 확인한 것만 쓴다(2026-10-09). 1899 는 내 지도 기본 핀.
# 새 아이콘이 필요하면 내 지도에서 그 아이콘을 고른 뒤 KML 로 내보내 번호를 확인하고 여기에 더한다.
ICON_CODES = {
    "숙소": 1602, "공항": 1504, "기차": 1716, "코인로커": 1716, "지하철": 1719, "역": 1719,
    "식당": 1577, "식사": 1577, "쇼핑": 1684, "시장": 1684,
    "공원": 1720, "동물원": 1743, "절": 1706, "신사": 1706, "전망대": 1715, "탑": 1715,
    "온천": 1811, "공연": 1635, "테마파크": 1635, "스튜디오": 1635,
    "관광": 1899, "교통": 1719, "기본": 1899,
}


def place_icon(p: dict) -> int:
    """장소의 내 지도 아이콘 번호. icon 칸 → kind → 기본 핀 순서."""
    for key in (p.get("icon"), p.get("kind")):
        if key and str(key) in ICON_CODES:
            return ICON_CODES[str(key)]
    return ICON_CODES["기본"]

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class TripError(ValueError):
    """데이터 파일을 읽을 수 없을 때(형식이 틀려 검사도 못 할 때)."""


def load(path: str | Path) -> dict:
    """YAML 또는 JSON 여행 파일을 읽어 dict 로 돌려준다."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise TripError("PyYAML 이 없다: pip install pyyaml")
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise TripError("여행 파일 맨 위가 표(key: value)가 아니다")
    return data


def to_date(v) -> dt.date | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v).strip())
    except ValueError:
        return None


def to_min(t) -> int | None:
    """"HH:MM" → 자정부터 분. 틀린 값이면 None. YAML 이 09:30 을 숫자(570)로 읽는 경우도 받는다."""
    if t is None:
        return None
    if isinstance(t, int) and not isinstance(t, bool):  # YAML 1.1 의 60진수 해석(09:30 → 570)
        return t if 0 <= t < 24 * 60 else None
    m = TIME_RE.match(str(t).strip())
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt_min(m: int | None) -> str:
    if m is None:
        return "?"
    m = int(m)
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def weekday_ko(d: dt.date) -> str:
    return WEEKDAYS[d.weekday()]


def day_label(d: dt.date) -> str:
    return f"{d.month}/{d.day} {weekday_ko(d)}"


def places(data: dict) -> dict:
    return data.get("places") or {}


def place(data: dict, pid: str) -> dict:
    return places(data).get(pid) or {}


def travelers(data: dict) -> list[dict]:
    return data.get("travelers") or []


def holidays(data: dict) -> dict:
    """{date: 이름}"""
    out = {}
    for h in data.get("holidays") or []:
        d = to_date(h.get("date")) if isinstance(h, dict) else to_date(h)
        if d:
            out[d] = (h.get("name") if isinstance(h, dict) else "") or "공휴일"
    return out


def go_minutes(go: dict | None) -> list[int]:
    """이동 시간. 숫자 하나면 [n], 여러 안이면 그대로(작은 것부터)."""
    if not go:
        return []
    v = go.get("minutes")
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return sorted(int(x) for x in v)
    return [int(v)]


def days(data: dict) -> list[dict]:
    """날짜별 일정. 각 날에 date(날짜), label, color, index 를, 각 항목에 start/end(분), no(그날 순서 번호)를 붙여 돌려준다.
    원본 dict 는 바꾸지 않는다."""
    out = []
    for i, day in enumerate(data.get("days") or []):
        d = to_date(day.get("date"))
        items = []
        no = 0
        for it in day.get("items") or []:
            start = to_min(it.get("time"))
            stay = it.get("stay") or 0
            p = place(data, it.get("place"))
            if p.get("map", True) is not False and p.get("kind") != "숙소":
                no += 1
                n = no
            else:
                n = None
            items.append({**it, "start": start, "end": (start + int(stay)) if start is not None else None, "no": n,
                          "place_data": p})
        out.append({**day, "date": d, "label": day_label(d) if d else str(day.get("date")),
                    "color": DAY_COLORS[i % len(DAY_COLORS)], "index": i, "items": items})
    return out


def day_color(data: dict, date: dt.date) -> str:
    for d in days(data):
        if d["date"] == date:
            return d["color"]
    return BASE_COLOR


def maps_link(p: dict) -> str:
    """구글 지도 길찾기 주소 (좌표 기준)."""
    if p.get("lat") is None or p.get("lon") is None:
        return ""
    return f"https://www.google.com/maps/dir/?api=1&destination={p['lat']},{p['lon']}"


def maps_search(p: dict) -> str:
    if p.get("lat") is None or p.get("lon") is None:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}"


def single(data: dict, key: str) -> dict:
    """arrival / departure 는 하나여야 한다. 목록이면 첫 것을 돌려준다(검사기가 따로 잡는다)."""
    v = data.get(key)
    if isinstance(v, list):
        return v[0] if v else {}
    return v or {}


def youngest(data: dict) -> int | None:
    ages = [t.get("age") for t in travelers(data) if isinstance(t.get("age"), (int, float))]
    return min(ages) if ages else None


def return_words(data: dict) -> tuple[str, str]:
    """돌아가는 편의 이름과 도착할 곳. 해외+공항이면 ("귀국", "공항"), 아니면 ("돌아가는 길", 출발 장소 이름)."""
    dep = single(data, "departure")
    p = places(data).get(dep.get("place"), {})
    cur = str((data.get("trip") or {}).get("currency", "")).upper()
    title = "귀국" if p.get("kind") == "공항" and cur not in ("KRW", "") else "돌아가는 길"
    where = "공항" if p.get("kind") == "공항" else (p.get("name") or "출발 장소")
    return title, where
