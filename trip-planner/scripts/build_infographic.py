# -*- coding: utf-8 -*-
"""한 장짜리 인포그래픽 만들기. AI 그림이 아니라 데이터로 HTML 을 그린 뒤 Playwright 로 PNG 를 찍는다.
그래서 글자와 지도가 데이터와 어긋나지 않는다.

크기 두 가지: 폰 세로(1080x1920), A4 세로(1588x2246, 약 190dpi)
지도는 좌표로 그린 개략도다(축척과 길은 정확하지 않다). map: false 인 곳과 공항은 빼고 그린다.

쓰는 법: python build_infographic.py <여행.yaml> <나갈 폴더> [--html-only]
  → <폴더>/infographic-phone.png, infographic-a4.png (그리고 같은 이름 .html)
"""
from __future__ import annotations

import html
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_trip  # noqa: E402
import trip_model as tm  # noqa: E402

SIZES = {"phone": (540, 960, 2), "a4": (794, 1123, 2)}
esc = html.escape


def map_svg(data: dict, w: int, h: int, only_day: int | None = None, note: bool = True) -> str:
    """좌표 개략도. 날짜별 색 선과 번호 점, 숙소는 검은 네모.
    only_day 를 주면 그날 장소와 숙소만 그날 범위에 맞춰 크게 그린다(멀리 떨어진 날 때문에 다른 날이 뭉개지지 않게)."""
    pts = []
    for d in tm.days(data):
        if only_day is not None and d["index"] != only_day:
            continue
        for it in d["items"]:
            p = it["place_data"]
            if p.get("lat") is None or p.get("map", True) is False or p.get("kind") in ("공항", "숙소"):
                continue
            pts.append((d, it, p))
    hotels = [p for p in tm.places(data).values() if p.get("kind") == "숙소" and p.get("lat") is not None]
    # 하루 지도는 그날 장소에만 맞춘다. 숙소가 멀면 가장자리에 방향만 표시한다.
    allp = [p for _, _, p in pts] if (only_day is not None and len(pts) >= 2) else [p for _, _, p in pts] + hotels
    if not allp:
        return ""
    lat0 = sum(p["lat"] for p in allp) / len(allp)
    k = math.cos(math.radians(lat0))
    xs = [p["lon"] * k for p in allp]
    ys = [-p["lat"] for p in allp]
    pad = 16
    legend = 16 if only_day is not None else 0      # 하루 지도 아래 숙소 안내 한 줄 자리
    ph = h - legend
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx = (w - 2 * pad) / ((maxx - minx) or 1e-6)
    sy = (ph - 2 * pad) / ((maxy - miny) or 1e-6)
    s = min(sx, sy)
    ox = pad + ((w - 2 * pad) - (maxx - minx) * s) / 2
    oy = pad + ((ph - 2 * pad) - (maxy - miny) * s) / 2

    def xy(p):
        return ox + (p["lon"] * k - minx) * s, oy + (-p["lat"] - miny) * s

    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">',
           f'<rect width="{w}" height="{h}" rx="10" fill="#f1f0ea"/>']
    for d in tm.days(data):
        if only_day is not None and d["index"] != only_day:
            continue
        line = [xy(p) for dd, _, p in pts if dd["index"] == d["index"]]
        if len(line) >= 2:
            out.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in line)}" fill="none" '
                       f'stroke="{d["color"]}" stroke-width="2.5" stroke-linejoin="round" stroke-opacity=".85"/>')
    # 번호 점: 같은 곳(화면에서 6px 안)은 한 점에 "1,5" 처럼 모은다
    groups: list[list] = []
    for d, it, p in pts:
        if it["no"] is None:
            continue
        x, y = xy(p)
        # 같은 장소(같은 id)를 그날 두 번 가면 한 점에 "1,5". 다른 장소는 가까워도 묶지 않고 아래에서 밀어낸다.
        for g in groups:
            if g[0] is d and g[4] == it.get("place"):
                g[3].append(it["no"])
                break
        else:
            groups.append([d, x, y, [it["no"]], it.get("place")])
    # 다른 곳인데 가까워 겹치는 점은 조금씩 밀어낸다(개략도라 몇 px 어긋나도 된다). 선은 원래 자리를 따른다.
    for _ in range(30):
        moved = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i], groups[j]
                dx, dy = b[1] - a[1], b[2] - a[2]
                dist = math.hypot(dx, dy)
                if dist < 17:
                    if dist < 0.01:
                        dx, dy, dist = 1.0, 0.0, 1.0
                    push = (17 - dist) / 2 + 0.5
                    ux, uy = dx / dist, dy / dist
                    a[1], a[2] = a[1] - ux * push, a[2] - uy * push
                    b[1], b[2] = b[1] + ux * push, b[2] + uy * push
                    moved = True
        for g in groups:
            g[1] = min(max(g[1], 9), w - 9)
            g[2] = min(max(g[2], 9), ph - 9)
        if not moved:
            break
    dots = [(g[1], g[2]) for g in groups]

    # 숙소: 그날 지도 안에 있고 번호 점과 안 겹치면 네모로 그린다. 밖이거나 겹치면 아래 줄에 글자로 방향만.
    legend_text = []
    for p in hotels:
        x, y = xy(p)
        inside = 8 <= x <= w - 8 and 8 <= y <= ph - 8
        crowded = any(abs(x - dx) < 18 and abs(y - dy) < 18 for dx, dy in dots)
        if inside and not crowded:
            lx = x - 34 if x > w / 2 else x + 10
            out.append(f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" fill="#111"/>'
                       f'<text x="{lx:.1f}" y="{y+4:.1f}" font-size="11" font-weight="700" fill="#111">숙소</text>')
        elif only_day is not None:
            if inside:
                near = min(groups, key=lambda g: (g[1] - x) ** 2 + (g[2] - y) ** 2)
                legend_text.append(f"■ 숙소는 {','.join(map(str, near[3]))}번 근처")
            else:
                ang = math.degrees(math.atan2(-(y - ph / 2), x - w / 2)) % 360
                arrow = "→↗↑↖←↙↓↘"[int(((ang + 22.5) % 360) // 45)]
                legend_text.append(f"■ 숙소는 지도 밖 {arrow} 방향")
        else:
            out.append(f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" fill="#111"/>')

    for d, x, y, nos, _pid in groups:
        label = ",".join(map(str, nos))
        if len(nos) == 1:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{d["color"]}" stroke="#fff" stroke-width="1.5"/>')
        else:
            bw = 7 + 6.2 * len(label)
            out.append(f'<rect x="{x-bw/2:.1f}" y="{y-8:.1f}" width="{bw:.1f}" height="16" rx="8" fill="{d["color"]}" stroke="#fff" stroke-width="1.5"/>')
        out.append(f'<text x="{x:.1f}" y="{y+3.5:.1f}" font-size="9.5" font-weight="700" fill="#fff" text-anchor="middle">{label}</text>')
    if legend_text:
        out.append(f'<text x="10" y="{h-6}" font-size="10.5" font-weight="700" fill="#333">{html.escape(" ".join(legend_text))}</text>')
    if note:
        out.append(f'<text x="{w-10}" y="{h-10}" font-size="10" fill="#777" text-anchor="end">좌표로 그린 개략도, 거리와 길은 정확하지 않음</text>')
    out.append("</svg>")
    return "".join(out)


# 장소 종류 아이콘: 흰 선으로 그린 아주 단순한 그림(24x24 기준). 사진 대신 쓴다.
ICON_PATHS = {
    "식사": '<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M16 3c-2 1-3 4-3 7h3v11" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
    "쇼핑": '<path d="M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "숙소": '<path d="M3 18V7M3 13h18v5M21 18v-3M7 11a2 2 0 1 0 0-.01M11 10h7a3 3 0 0 1 3 3" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
    "역": '<path d="M7 4h10a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM5 11h14M8 20l2-3M16 20l-2-3" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
    "공항": '<path d="M3 13l18-6-6 14-3-6-6-2z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "공원": '<path d="M12 3l6 9h-4l4 6H6l4-6H6zM12 18v3" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "동물원": '<circle cx="7" cy="9" r="1.8" fill="#fff"/><circle cx="12" cy="6.5" r="1.8" fill="#fff"/><circle cx="17" cy="9" r="1.8" fill="#fff"/><path d="M8 16c0-3 2-5 4-5s4 2 4 5-2 3-4 3-4 0-4-3z" fill="#fff"/>',
    "절": '<path d="M3 9l9-5 9 5M5 9h14M7 9v10M17 9v10M4 19h16M10 19v-5h4v5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "전망대": '<path d="M12 2v3M9 21l3-16 3 16M8 15h8M10 10h4" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
    "온천": '<path d="M4 17c2 2 14 2 16 0M8 13c-1-2 1-3 0-5M12 13c-1-2 1-3 0-5M16 13c-1-2 1-3 0-5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
    "공연": '<path d="M4 6h16v12H4zM4 10h16M9 6v4M15 6v4" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "기본": '<circle cx="12" cy="10" r="3" fill="none" stroke="#fff" stroke-width="1.8"/><path d="M12 21s-6-6-6-11a6 6 0 0 1 12 0c0 5-6 11-6 11z" fill="none" stroke="#fff" stroke-width="1.8"/>',
}
ICON_ALIAS = {"식당": "식사", "카페": "식사", "시장": "쇼핑", "기차": "역", "지하철": "역", "코인로커": "역", "교통": "역",
              "신사": "절", "탑": "전망대", "스튜디오": "공연", "테마파크": "공연"}


def icon_svg(p: dict, color: str, size: int = 22) -> str:
    key = p.get("icon") or p.get("kind") or "기본"
    key = ICON_ALIAS.get(key, key)
    path = ICON_PATHS.get(key, ICON_PATHS["기본"])
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="-3 -3 30 30" xmlns="http://www.w3.org/2000/svg">'
            f'<circle cx="12" cy="12" r="14.5" fill="{color}"/>{path}</svg>')


def page(data: dict, size: str, findings: list[dict], map_uri: str | None = None) -> str:
    """포스터 짜임새: 노을빛 머리(큰 제목, 기간, 사람, 숙소 칩) → 날짜마다 DAY 띠(점 타임라인 + 그날 지도)
    → 아래 띠(귀국, 먹을 곳, 살 곳, 주의). 사진 대신 장소 종류 아이콘."""
    w, h, _ = SIZES[size]
    trip = data.get("trip") or {}
    places = tm.places(data)
    dep = tm.single(data, "departure")
    days = tm.days(data)
    phone = size == "phone"
    who = ", ".join(f"{t.get('label')}({t.get('age')}세)" for t in tm.travelers(data))
    start, end = tm.to_date(trip.get("start")), tm.to_date(trip.get("end"))
    period = f"{start.year}. {start.month}. {start.day}({tm.weekday_ko(start)}) ~ {end.month}. {end.day}({tm.weekday_ko(end)})" if start and end else ""
    hotel = places.get((data.get("emergency") or {}).get("hotel"), {})
    errs = sum(1 for f in findings if f["level"] == check_trip.ERROR)

    # 폰: 2칸 카드 안에서 시간표 아래 지도. A4: 2칸 카드 안에서 시간표 오른쪽에 좁은 지도
    map_w = 228 if phone else 132
    map_h = 96 if phone else 176

    blocks = []
    for d in days:
        rows = []
        for it in d["items"]:
            p = it["place_data"]
            if it["no"] is None and p.get("kind") != "공항":
                continue
            r = p.get("reservation") or {}
            flag = f'<span class="flag">예약 {esc(str(r.get("slot", "")))}</span>' if r.get("timed") else ""
            sub = it.get("what", "")
            rows.append(f'<li><span class="t">{esc(str(it.get("time")))}</span><span class="dot"></span>'
                        f'<span class="body"><span class="row">{icon_svg(p, d["color"], 18)}<b>{esc(p.get("name", ""))}</b>{flag}</span>'
                        f'<em>{esc(sub)}</em></span></li>')
        # 날짜 수가 홀수면 마지막 날 칸을 가로 전체로(오른쪽 빈칸이 안 생기게). 넓은 칸은 시간표 옆에 지도.
        wide = len(days) % 2 == 1 and d["index"] == len(days) - 1
        if map_uri:
            mini = ""  # 진짜 지도 한 장이 위에 있으니 날짜별 개략도는 뺀다
        elif wide:
            mini = map_svg(data, 210 if phone else 300, map_h + (24 if phone else 0), only_day=d["index"], note=False)
        else:
            mini = map_svg(data, map_w, map_h, only_day=d["index"], note=False)
        blocks.append(
            f'<section class="day{" wide" if wide else ""}" style="--c:{d["color"]}">'
            f'<div class="dh"><span class="badge">DAY {d["index"] + 1}</span><span class="date">{d["date"].month}월 {d["date"].day}일 ({tm.weekday_ko(d["date"])})</span>'
            f'<span class="ttl">{esc(str(d.get("title", "")))}</span></div>'
            f'<div class="dbody"><ul class="tl">{"".join(rows)}</ul>{f'<div class="mini">{mini}</div>' if mini else ""}</div></section>')

    def chips(kind):
        seen, out = set(), []
        for d in days:
            for it in d["items"]:
                p = it["place_data"]
                if p.get("kind") == kind and p.get("name") not in seen:
                    seen.add(p.get("name"))
                    out.append(f'<span class="chip">{icon_svg(p, d["color"], 16)}{esc(p["name"])}<i>{esc(d["label"].split(" ")[0])}</i></span>')
        return "".join(out)

    warn = []
    for d in days:
        for it in d["items"]:
            if it.get("note") and any(x in it["note"] for x in ("휴무", "쉰다", "불가", "공휴일")):
                warn.append(f'{d["label"]} {it["place_data"].get("name", "")}: {it["note"]}')
            if it.get("alt") and "불가" in it["alt"]:
                warn.append(f'{d["label"]}: {it["alt"].split(". ")[-1]}')
            # 장소 메모 속 키 제한, 나이 제한도 주의 칸에 (예: 마리오카트 107cm)
            pn = it["place_data"].get("note") or ""
            for sent in pn.split(". "):
                if any(x in sent for x in ("cm", "세 미만", "세 이상")):
                    line = f'{d["label"]} {it["place_data"].get("name", "")}: {sent.strip().rstrip(".")}'
                    if line not in warn:
                        warn.append(line)
    warn = warn[:4]

    fs = 1.0 if phone else 1.06
    css = f"""
*{{box-sizing:border-box}}
body{{margin:0;width:{w}px;min-height:0;overflow:hidden;background:#f6f4ef;color:#1d2433;
font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;font-size:{12*fs:.1f}px}}
.top{{position:relative;padding:{20 if phone else 30}px {18 if phone else 30}px {16 if phone else 22}px;color:#fff;overflow:hidden;
background:linear-gradient(180deg,#1b2a5c 0%,#3b3f8f 45%,#c86f7e 85%,#f2a66b 100%)}}
.top svg.city{{position:absolute;left:0;right:0;bottom:0;width:100%;height:{46 if phone else 70}px;opacity:.55}}
.top .kick{{font-size:{13*fs:.1f}px;font-weight:700;letter-spacing:.02em;opacity:.95}}
.top h1{{margin:2px 0 10px;font-family:"Jua","Malgun Gothic",sans-serif;font-weight:400;font-size:{40 if phone else 52}px;line-height:1.05;letter-spacing:0;
text-shadow:0 2px 0 rgba(0,0,0,.25)}}
.pills{{display:flex;flex-wrap:wrap;gap:6px;position:relative}}
.pill{{background:rgba(255,255,255,.95);color:#1d2433;border-radius:999px;padding:4px 11px;font-size:{11.5*fs:.1f}px;font-weight:700}}
.pill b{{color:#3b3f8f;margin-right:5px}}
.note-card{{position:absolute;right:{14 if phone else 26}px;top:{16 if phone else 22}px;background:#fff59d;color:#5b4b00;transform:rotate(4deg);
font-size:{11*fs:.1f}px;font-weight:700;line-height:1.35;padding:7px 10px;border-radius:3px;box-shadow:0 3px 6px rgba(0,0,0,.25);max-width:{120 if phone else 170}px}}
.wrap{{padding:{10 if phone else 18}px {12 if phone else 26}px}}
.days{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:{8 if phone else 12}px}}
.day{{background:#fff;border-radius:12px;border:1.5px solid color-mix(in srgb,var(--c) 35%,#fff);overflow:hidden;min-width:0}}
.dh{{display:flex;flex-wrap:wrap;align-items:center;gap:4px 7px;padding:6px 10px;background:color-mix(in srgb,var(--c) 12%,#fff)}}
.badge,.date{{flex:none;white-space:nowrap}}.badge{{font-family:"Jua","Malgun Gothic",sans-serif;font-weight:400;background:var(--c);color:#fff;font-weight:900;font-size:{13*fs:.1f}px;border-radius:6px;padding:2px 8px;letter-spacing:.02em}}
.date{{font-size:{11*fs:.1f}px;font-weight:700;color:var(--c);border:1.5px solid var(--c);border-radius:999px;padding:0 7px;background:#fff}}
.ttl{{font-size:{(12.5 if phone else 14)*fs:.1f}px;font-weight:800;color:#1d2433;line-height:1.25;min-width:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}.day.wide{{grid-column:1/-1}}.day.wide .dbody{{flex-direction:row;align-items:flex-start}}.day.wide .body em{{display:block}}
.dbody{{display:flex;flex-direction:{'column' if phone else 'row'};gap:{6 if phone else 8}px;padding:6px 10px 8px;align-items:{'stretch' if phone else 'flex-start'}}}
.tl{{list-style:none;margin:0;padding:0;flex:1;min-width:0;position:relative}}
.tl::before{{content:"";position:absolute;left:{38*fs:.0f}px;top:6px;bottom:6px;width:2px;background:color-mix(in srgb,var(--c) 30%,#fff)}}
.tl li{{display:flex;align-items:flex-start;gap:6px;padding:{2 if phone else 3}px 0;position:relative}}
.t{{width:{32*fs:.0f}px;flex:none;font-weight:700;font-variant-numeric:tabular-nums;color:#444;font-size:{11*fs:.1f}px;padding-top:1px}}
.dot{{width:9px;height:9px;border-radius:50%;border:2px solid var(--c);background:#fff;flex:none;margin-top:3px;position:relative;z-index:1}}
.body{{min-width:0;flex:1;display:flex;flex-direction:column;line-height:1.3}}.row{{display:flex;align-items:center;gap:4px;min-width:0}}.row .flag{{flex:none}}
.body b{{font-size:{12*fs:.1f}px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}}
.body em{{display:{'none' if phone else 'block'};font-style:normal;color:#6a6f7c;font-size:{10.2*fs:.1f}px;padding-left:22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ic{{flex:none}}
.flag{{font-size:{9.5*fs:.1f}px;background:#1d2433;color:#fff;border-radius:4px;padding:0 4px;font-weight:700}}
.realmap{{margin-bottom:{8 if phone else 12}px;border-radius:12px;overflow:hidden;border:1px solid #e3e1da}}.realmap img{{display:block;width:100%}}.mini{{flex:none;border-radius:8px;overflow:hidden}}.mini svg{{display:block}}
.bottom{{display:grid;align-items:start;grid-template-columns:{'1fr 1.4fr' if phone else '1.1fr 1fr 1fr'};gap:{8 if phone else 12}px;margin-top:{8 if phone else 12}px}}
.panel{{background:#fff;border-radius:12px;padding:8px 10px;min-width:0}}
.panel h4{{margin:0 0 5px;font-size:{12.5*fs:.1f}px;font-weight:800;display:flex;align-items:center;gap:5px}}
.chip{{display:inline-flex;align-items:center;gap:4px;border:1px solid #e3e1da;border-radius:999px;padding:2px 8px 2px 3px;margin:0 4px 4px 0;font-size:{10.8*fs:.1f}px;font-weight:600;white-space:nowrap}}
.chip i{{font-style:normal;color:#8a8f9c;font-weight:500}}
.go{{background:#1d2433;color:#fff}}
.go .big{{font-size:{19*fs:.1f}px;font-weight:900;line-height:1.2}}
.go .sub{{opacity:.85;font-size:{11*fs:.1f}px}}
.warn{{background:#fff4dc}}
.warn p{{margin:0 0 3px;font-size:{10.6*fs:.1f}px;line-height:1.4}}
.picks{{display:grid;grid-template-columns:{'1fr' if phone else '1fr 1fr'};gap:{8 if phone else 12}px;margin-top:{8 if phone else 12}px}}
.pk ul{{list-style:none;margin:0;padding:0}}.pk li{{display:flex;gap:6px;align-items:flex-start;padding:3px 0;border-top:1px dashed #ece9e1}}.pk li:first-child{{border-top:0}}
.pk li div{{min-width:0;line-height:1.3}}.pk b{{font-size:{12*fs:.1f}px}}.pk .ar{{color:#8a8f9c;font-size:{10*fs:.1f}px;margin-left:5px}}
.pk em{{display:block;font-style:normal;color:#3d4250;font-size:{10.5*fs:.1f}px}}.pk small{{display:block;color:#8a8f9c;font-size:{9.6*fs:.1f}px}}
.pk h4{{font-family:"Jua","Malgun Gothic",sans-serif;font-weight:400;font-size:{14*fs:.1f}px}}
.foot{{display:flex;justify-content:space-between;color:#8a8f9c;font-size:{9.8*fs:.1f}px;margin-top:{6 if phone else 10}px}}
"""
    city = ('<svg class="city" viewBox="0 0 400 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"><path fill="#141c3d" d="'
            'M0 60V38h14v-8h10v12h8V24h12v18h6V30h10v30h4V18h6v-6h2v6h6v42h6V34h14v26h8V28h10v8h8v24h6V20h4l3-12 3 12h4v40h8V36h12v24h6V30h10v30h8V40h14v20h6V26h12v34h8V34h10v26h6V22h8v38h10V36h14v24h6V30h10v30h8V40h12v20h10V32h12v28z"/></svg>')
    tagline = trip.get("tagline") or f"{trip.get('destination', '')} {tm.to_date(trip.get('end')) and (tm.to_date(trip.get('end')) - start).days + 1}일 여행"
    top = (f'<header class="top">{city}<div class="kick">{esc(str(trip.get("kicker", "가족과 함께하는")))}</div>'
           f'<h1>{esc(str(trip.get("title", "")))}</h1>'
           f'<div class="pills"><span class="pill"><b>여행기간</b>{esc(period)}</span><span class="pill"><b>여행멤버</b>{esc(who)}</span>'
           + (f'<span class="pill"><b>숙소</b>{esc(hotel.get("name", ""))}</span>' if hotel else "")
           + f'</div><div class="note-card">{esc(str(tagline))}</div></header>')
    dep_name = places.get(dep.get("place"), {}).get("name", "")
    bottom = (f'<div class="panel go"{' style="grid-column:1/-1"' if (phone and not warn) else ""}><div class="sub">{"귀국" if places.get(dep.get("place"), {}).get("kind") == "공항" and str(trip.get("currency", "")).upper() not in ("KRW", "") else "돌아가는 길"}</div><div class="big">{esc(str(dep.get("date", ""))[5:].replace("-", "/"))} {esc(str(dep.get("time", "")))} 출발</div>'
              f'<div class="sub">{esc(dep_name)}에 {esc(str(dep.get("arrive_by", "")))}까지</div></div>'
              + ("" if phone else "".join(f'<div class="panel"><h4>{t}</h4>{c}</div>' for t, c in (("먹을 곳", chips("식사")), ("살 곳", chips("쇼핑"))) if c))
              + (f'<div class="panel warn" style="grid-column:{"auto" if phone else "1/-1"}"><h4>주의</h4>{"".join(f"<p>{esc(x)}</p>" for x in warn)}</div>' if warn else ""))
    # 고객 그림에는 사실 확인일만. 형식 검사·독립 대조 기록은 데이터 trip.audits 와 시트 검사 탭에만 둔다(10/10 기획팀장)
    foot = (f'<div class="foot"><span>사실 확인 {esc(str(trip.get("checked", "")))} · 가기 전 다시 확인 · {"지도 © OpenStreetMap contributors" if map_uri else "지도는 좌표로 그린 개략도"}</span>'
            '</div>')
    realmap = (f'<div class="realmap"><img src="{map_uri}" alt="일정 지도"></div>' if map_uri else "")
    # 추천 칸: picks(맛집 / 요즘 뜨는 곳). 일정 밖 보너스 정보라 출처 확인일을 같이 적는다.
    picks = data.get("picks") or []
    pick_html = ""
    if picks:
        def plist(kind, title, icon_kind, color):
            items = [p for p in picks if p.get("type") == kind][:3]
            if not items:
                return ""
            li = "".join(
                f'<li>{icon_svg({"kind": icon_kind}, color, 18)}<div><b>{esc(str(p.get("name", "")))}</b>'
                f'<span class="ar">{esc(str(p.get("area", "")))}</span>'
                f'<em>{esc(str(p.get("why", "")))}</em>'
                + (f'<small>{esc(str(p.get("hours", "")))}</small>' if p.get("hours") else "")
                + '</div></li>' for p in items)
            return f'<div class="panel pk"><h4>{title}</h4><ul>{li}</ul></div>'
        pick_html = ('<div class="picks">' + plist("맛집", "추천 맛집", "식사", "#F57C00")
                     + plist("요즘", "요즘 뜨는 곳", "쇼핑", "#9C27B0") + '</div>')
        dates = sorted(str(p.get("checked")) for p in picks if p.get("checked"))
        if dates:
            foot = foot.replace(" · 가기 전 다시 확인", f" · 추천 칸 확인 {esc(dates[0])} · 가기 전 다시 확인")
    body = f'{top}<div class="wrap">{realmap}<div class="days">{"".join(blocks)}</div>{pick_html}<div class="bottom">{bottom}</div>{foot}</div>'
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jua&display=swap"><style>{css}</style></head><body>{body}</body></html>'


def render(data: dict, out_dir: str | Path, html_only: bool = False) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    findings = check_trip.check(data)
    made = []
    pages = {}
    # 진짜 지도(오픈스트리트맵) 한 장. 인터넷이 안 되거나 실패하면 날짜별 개략도로 돌아간다.
    map_uris = {}
    if not html_only:
        import base64
        try:
            import real_map
            for size, (mw, mh) in {"phone": (516, 380), "a4": (742, 440)}.items():
                png = real_map.render(data, mw, mh)
                map_uris[size] = "data:image/png;base64," + base64.b64encode(png).decode()
        except Exception as e:  # noqa: BLE001
            print(f"진짜 지도를 못 그려 개략도로 대신함: {e}", file=sys.stderr)
            map_uris = {}
    for size in SIZES:
        hp = out_dir / f"infographic-{size}.html"
        hp.write_text(page(data, size, findings, map_uris.get(size)), encoding="utf-8")
        pages[size] = hp
        made.append(hp)
    if html_only:
        return made
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for size, hp in pages.items():
            w, h, scale = SIZES[size]
            cap = int(h * 1.6)  # 지도가 들어가면 세로로 길어진다. 폰판은 길게 내려 보는 한 장
            pg = b.new_page(viewport={"width": w, "height": cap}, device_scale_factor=scale)
            pg.goto(hp.resolve().as_uri(), wait_until="networkidle")
            pg.evaluate("document.fonts.ready.then(() => 1)")  # 제목 글꼴(Jua)이 다 받아진 뒤 찍기
            pg.wait_for_timeout(300)
            png = out_dir / f"infographic-{size}.png"
            # 높이는 내용에 맞춘다(남는 아래 빈칸 없이)
            hh = min(pg.evaluate("document.body.scrollHeight"), cap)
            pg.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": w, "height": hh})
            made.append(png)
            pg.close()
        b.close()
    return made


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    for p in render(tm.load(args[0]), args[1], "--html-only" in argv):
        print(f"인포그래픽 → {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
