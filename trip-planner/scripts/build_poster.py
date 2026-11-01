# -*- coding: utf-8 -*-
"""가로 한 장 그림(포스터) 2판 — 도쿄 본보기 짜임 + Canva 비교에서 가져온 것(따뜻한 색, 날마다 가로 사진줄,
일러스트풍 지도, 꽉 찬 화면). 사실(글자·숫자·지도 위치)은 데이터에서만 넣는다.

머리(분위기 그림 배경, 큰 제목, 알약, 메모지) → 왼쪽 날짜 카드(가로 사진줄 + 시간표) → 오른쪽 지도(날짜 색 동선,
사진 번호와 같은 번호 핀, 이름표) → 아래 사진 띠 → 출처 줄.

쓰는 법: python build_poster.py <여행.yaml> <나갈 폴더>
사진: 장소 photo 키, trip.header_photo, strips[].items[].photo → <yaml 폴더>/<trip.photo_dir>/<키>.jpg
출처: 같은 폴더 photos.json. 쓴 사진만 출처 줄에 적는다. AI 그림은 맨 위 분위기 그림에만 쓴다.
1판과 달라진 것(2026-10-11, 두 검사원 audit + Canva 비교): 지도 핀 번호 = 카드 사진 번호, 장소 사진은 한 번만(지도는 이름표),
"예시 숙소" 자리표시 빼기, 나이 대신 인원 구성, 글자 크게·회색 진하게, 시각 고정폭 숫자, 낱말 안 끊기.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from collections import Counter
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_trip  # noqa: E402
import trip_model as tm  # noqa: E402
from build_infographic import icon_svg  # noqa: E402

W = 1600
LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"


class Photos:
    def __init__(self, folder: Path):
        self.folder = folder
        mp = folder / "photos.json"
        self.meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
        self.used: list[str] = []

    def uri(self, key: str | None) -> str | None:
        if not key:
            return None
        f = self.folder / f"{key}.jpg"
        if not f.exists():
            return None
        if key not in self.used:
            self.used.append(key)
        return "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode()

    def credits(self) -> tuple[str, str]:
        srcs, parts = [], []
        for k in self.used:
            m = self.meta.get(k) or {}
            s = m.get("source", "")
            if s and s not in srcs:
                srcs.append(s)
            if m and "AI" not in s:
                a = re.sub(r"\s+", " ", m.get("artist", "작가 미상")).split(" This photo")[0].strip()
                parts.append(f"{a} ({m.get('license', '')})")
        return " · ".join(srcs), ", ".join(parts)

    def credit_text(self) -> str:
        """쓴 사진의 출처를 곳마다 묶는다. 관광공사(공공누리 1유형)는 출처 표시만, 위키미디어는 작가(라이선스)."""
        groups: dict[str, list[str]] = {}
        for k in self.used:
            m = self.meta.get(k) or {}
            s = m.get("source", "")
            if not s or "AI" in s:
                continue
            a = re.sub(r"\s+", " ", m.get("artist", "작가 미상")).split(" This photo")[0].strip()
            part = a if "관광공사" in s else f"{a} ({m.get('license', '')})"
            groups.setdefault(s, [])
            if part not in groups[s]:
                groups[s].append(part)
        order = sorted(groups, key=lambda x: 0 if "관광공사" in x else 1)
        return " · ".join(f"{s} — {', '.join(groups[s])}" for s in order)

    def is_ai(self, key: str | None) -> bool:
        return bool(key) and "AI" in (self.meta.get(key) or {}).get("source", "")


def go_text(go: dict | None) -> str:
    if not go:
        return ""
    mins = tm.go_minutes(go)
    if not mins:
        return ""
    m = f"{min(mins)}~{max(mins)}분" if len(set(mins)) > 1 else f"{mins[0]}분"
    return f"{go.get('mode', '')} {m}"


def who_text(data: dict) -> str:
    """나이 대신 인원 구성(취향 노트 ⑥). label 의 숫자 앞부분으로 센다: 어른 1, 어른 2 → 어른 2."""
    c = Counter(re.sub(r"\s*\d+$", "", str(t.get("label", ""))) for t in tm.travelers(data))
    return " · ".join(f"{k} {n}" for k, n in c.items())


def page(data: dict, yaml_dir: Path, findings: list[dict]) -> tuple[str, dict]:
    trip = data.get("trip") or {}
    ph = Photos(yaml_dir / str(trip.get("photo_dir", "photos")))
    places = tm.places(data)
    days = tm.days(data)
    start, end = tm.to_date(trip.get("start")), tm.to_date(trip.get("end"))
    period = f"{start.year}. {start.month}. {start.day}({tm.weekday_ko(start)}) ~ {end.month}. {end.day}({tm.weekday_ko(end)})"
    hotel = places.get((data.get("emergency") or {}).get("hotel"), {})
    hotel_name = re.sub(r"^예시\s*숙소\s*", "", hotel.get("name", "")).strip("() ") if hotel else ""

    cards, mdays = [], []
    for d in days:
        rows, spots, num = [], [], {}
        dep = data.get("departure") or {}
        if dep.get("time") and str(tm.to_date(dep.get("date"))) == str(d["date"]):
            dp = places.get(dep.get("place"), {})
            d = dict(d, items=list(d["items"]) + [{"time": dep["time"], "place": dep.get("place"), "place_data": dp,
                                                   "what": "비행기 출발 (예시 시각)" if dp.get("kind") == "공항" else "출발 (예시 시각)"}])
        for it in d["items"]:
            p = it["place_data"]
            if p.get("photo") and len(spots) < 3 and it.get("place") not in num:
                num[it.get("place")] = len(spots) + 1
                spots.append((p.get("photo"), p.get("name", ""), it.get("what", "")))
        for it in d["items"]:
            p = it["place_data"]
            go = go_text(it.get("go"))
            n = num.get(it.get("place"))
            mark = f'<i class="no">{n}</i>' if n else '<span class="dot"></span>'
            rows.append(
                f'<li class="{"meal" if p.get("kind") == "식사" else ""}"><span class="t">{esc(str(it.get("time")))}</span>{mark}'
                f'<div class="b"><div class="n">{icon_svg(p, d["color"], 18)}{esc(re.sub(r"^예시 숙소", "숙소", p.get("name", "")))}'
                + (f'<span class="go">{esc(go)}</span>' if go else "")
                + f'</div><div class="w">{esc(str(it.get("what", "")))}'
                + (f' · {esc(str(it["note"]))}' if it.get("note") else "")
                + '</div></div></li>')
        photos = "".join(
            f'<figure><img src="{ph.uri(k)}"><figcaption><i class="no">{i + 1}</i>{esc(nm)}</figcaption></figure>'
            for i, (k, nm, _) in enumerate(spots) if ph.uri(k)) + "".join(
            f'<figure><img src="{ph.uri(x.get("photo"))}"><figcaption><span class="xdot"></span>{esc(x.get("name", ""))}</figcaption></figure>'
            for x in (d.get("photos") or [])[:max(0, 3 - len(spots))] if ph.uri(x.get("photo")))
        nph = min(3, len(spots) + len(d.get("photos") or []))
        cards.append(
            f'<section class="day" style="--c:{d["color"]}"><div class="dh"><span class="badge">DAY {d["index"] + 1}</span>'
            f'<span class="date">{d["date"].month}월 {d["date"].day}일 ({tm.weekday_ko(d["date"])})</span>'
            f'<div class="tt"><b>{esc(str(d.get("title", "")))}</b><span>{esc(str(d.get("subtitle", "")))}</span></div></div>'
            + (f'<div class="db"><div class="ph" style="grid-template-columns:repeat({max(nph, 1)},1fr)">{photos}</div>' if photos else '<div class="db" style="grid-template-columns:1fr">')
            + f'<ul class="tl">{"".join(rows)}</ul></div></section>')

        pts, line, seen = [], [], set()
        for it in d["items"]:
            p = it["place_data"]
            if p.get("lat") is None:
                continue
            line.append([p["lat"], p["lon"]])
            key = it.get("place")
            if key in seen or p.get("kind") in ("공항", "숙소"):
                continue
            seen.add(key)
            pts.append({"lat": p["lat"], "lon": p["lon"], "no": num.get(key), "name": p.get("name", "") if num.get(key) else "",
                        "ico": icon_svg(p, d["color"], 22)})
        mdays.append({"color": d["color"], "day": d["index"] + 1,
                      "label": f"DAY {d['index'] + 1} ({d['date'].month}/{d['date'].day})", "points": pts, "line": line})

    airports = [{"lat": p["lat"], "lon": p["lon"], "name": p.get("name", ""), "kind": p.get("kind")} for p in places.values()
                if p.get("kind") in ("공항", "교통") and p.get("lat") is not None]
    hotels = [{"lat": p["lat"], "lon": p["lon"]} for p in places.values() if p.get("kind") == "숙소" and p.get("lat") is not None]
    mapdata = {"days": mdays, "hotels": hotels, "airports": airports}

    strips = []
    for s in data.get("strips") or []:
        its = "".join(f'<figure><img src="{ph.uri(x.get("photo"))}" style="object-position:{x.get("pos", "center")}"><figcaption><b>{esc(x.get("name", ""))}</b><span>{esc(x.get("sub", ""))}</span></figcaption></figure>'
                      for x in s.get("items") or [] if ph.uri(x.get("photo"))).replace('"><figcaption>', '"><figcaption>')
        strips.append(f'<div class="strip"><h4>{icon_svg({"kind": s.get("icon", "기본")}, "#E8590C", 20)}{esc(s.get("title", ""))}</h4><div class="row">{its}</div></div>')

    head_img = ph.uri(trip.get("header_photo"))
    src_line, artists = ph.credits()
    foot = (f'<div class="foot"><div>사진: {esc(ph.credit_text())} {' · 맨 위 배경은 AI 그림(분위기용)' if ph.is_ai(trip.get('header_photo')) else ''} · 지도 © OpenStreetMap contributors</div>'
            f'<div>사실 확인 {esc(str(trip.get("checked", "")))} · 영업시간·운영은 가기 전에 다시 확인</div></div>')
    nc = trip.get("note_card") or [trip.get("tagline", "")]
    note_lines = "<br>".join(esc(str(x)) for x in (nc if isinstance(nc, list) else [nc]))
    kicker = trip.get("poster_kicker") or trip.get("kicker", "")
    title = trip.get("poster_title") or trip.get("title", "")

    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jua&family=Gaegu:wght@700&display=swap">
<link rel="stylesheet" href="{LEAFLET_CSS}">
<style>
*{{box-sizing:border-box}}
body{{margin:0;width:{W}px;background:#fbf4e8;color:#2a2a33;font-family:"Malgun Gothic","Noto Sans KR",sans-serif;font-size:14px;word-break:keep-all}}
.top{{position:relative;height:196px;overflow:hidden}}
.top .bg{{position:absolute;inset:0;background:url({head_img}) center 62%/cover}}
.top .fade{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(251,244,232,.9) 0%,rgba(251,244,232,.55) 42%,rgba(251,244,232,0) 70%)}}
.top .in{{position:relative;padding:20px 30px}}
.kick{{font-family:"Jua";font-size:27px;color:#c2410c}}
h1{{margin:0 0 12px;font-family:"Jua";font-weight:400;font-size:66px;line-height:1;color:#7c2d12;text-shadow:0 3px 0 rgba(255,255,255,.85)}}
.pills{{display:flex;gap:8px}}
.pill{{display:flex;gap:8px;align-items:center;background:#fff;border-radius:999px;padding:7px 16px;font-size:15.5px;font-weight:700;box-shadow:0 2px 6px rgba(124,45,18,.15)}}
.pill b{{color:#c2410c}}
.memo{{position:absolute;right:28px;top:22px;width:220px;background:#fff6b3;transform:rotate(3deg);padding:12px 16px;font-family:"Gaegu";font-size:22px;line-height:1.3;color:#4a3b00;box-shadow:0 5px 12px rgba(0,0,0,.2)}}
.main{{display:grid;grid-template-columns:930px 1fr;gap:16px;padding:16px 18px 0}}
.day{{background:#fff;border-radius:16px;border:2px solid color-mix(in srgb,var(--c) 35%,#fff);margin-bottom:14px;overflow:hidden;box-shadow:0 2px 8px rgba(124,45,18,.06)}}
.dh{{display:flex;align-items:center;gap:10px;padding:9px 16px;background:color-mix(in srgb,var(--c) 12%,#fff)}}
.badge{{font-family:"Jua";font-size:27px;color:#fff;background:var(--c);border-radius:10px;padding:2px 14px}}
.date{{font-weight:800;color:var(--c);border:2px solid var(--c);border-radius:999px;padding:2px 11px;background:#fff;font-size:15px;white-space:nowrap}}
.tt b{{display:block;font-family:"Jua";font-weight:400;font-size:25px;color:var(--c);line-height:1.1}}.tt span{{font-size:13.5px;color:#4b4b55}}
.db{{display:grid;grid-template-columns:462px 1fr;gap:14px;padding:12px 16px 14px;align-items:start}}
.ph{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.ph figure{{margin:0}}.ph img{{width:100%;height:150px;object-fit:cover;border-radius:10px;display:block}}
.ph figcaption{{display:flex;align-items:center;gap:5px;margin-top:5px;font-weight:800;font-size:13.5px;line-height:1.25}}
i.no{{font-style:normal;flex:none;width:21px;height:21px;border-radius:50%;background:var(--c);color:#fff;font-size:12px;font-weight:800;display:inline-flex;align-items:center;justify-content:center}}
.xdot{{flex:none;width:12px;height:12px;border-radius:50%;border:3px solid var(--c);background:#fff}}
.tl{{list-style:none;margin:0;padding:0;position:relative}}
.tl::before{{content:"";position:absolute;left:61px;top:10px;bottom:10px;width:2px;background:color-mix(in srgb,var(--c) 40%,#fff)}}
.tl li{{display:flex;gap:9px;padding:3px 0;align-items:flex-start}}
.t{{width:44px;flex:none;font-weight:800;font-size:14.5px;text-align:right;font-variant-numeric:tabular-nums;padding-top:1px}}
.tl .dot{{width:13px;height:13px;margin:4px 4px 0;flex:none;border-radius:50%;border:3px solid var(--c);background:#fff;position:relative;z-index:1}}
.tl .meal .dot{{background:var(--c)}}
.tl i.no{{position:relative;z-index:1;margin-top:1px}}
.n{{font-weight:800;font-size:15.5px;display:flex;align-items:center;gap:5px;flex-wrap:wrap}}.n .ic{{flex:none}}.go{{font-weight:600;font-size:12.5px;color:#5b5f6b;margin-left:8px}}
.w{{color:#3f434d;font-size:13.5px;margin-top:1px}}
.right{{display:flex;flex-direction:column;gap:14px;margin-bottom:14px;min-width:0}}
.mapcard{{flex:1;min-height:460px;background:#fff;border-radius:16px;overflow:hidden;display:flex;flex-direction:column;border:2px solid #f0dcc0}}
.mh{{display:flex;align-items:center;justify-content:space-between;padding:11px 16px}}
.mh b{{font-family:"Jua";font-weight:400;font-size:26px;color:#7c2d12}}
.lg{{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px;font-weight:800;justify-content:flex-end}}.lg i{{display:inline-block;width:13px;height:13px;border-radius:50%;margin-right:4px;vertical-align:-1px}}
#m{{flex:1;position:relative;background:#cfe6ee}}
.leaflet-tile-pane{{filter:sepia(.32) saturate(1.35) hue-rotate(-6deg) brightness(1.04) contrast(.95)}}
.pin{{width:28px;height:28px;border-radius:50%;color:#fff;font:800 14px/28px "Malgun Gothic";text-align:center;border:3px solid #fff;box-shadow:0 2px 5px rgba(0,0,0,.4)}}
.apt{{position:absolute;z-index:720;background:#7c2d12;color:#fff;border-radius:7px;padding:3px 9px;font:800 13px "Malgun Gothic";white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.4)}}.apt.far{{background:#fff;color:#7c2d12;border:2px solid #7c2d12;font-size:13px}}.aptdot{{width:12px;height:12px;border-radius:50%;background:#7c2d12;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)}}
.kico svg{{display:block;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}}.pdot{{width:14px;height:14px;border-radius:50%;border:3px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)}}
.lab{{position:absolute;z-index:700;background:#fff;border:2.5px solid var(--c);border-radius:999px;padding:4px 11px 4px 5px;font-weight:800;font-size:14px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.18);display:flex;align-items:center;gap:6px}}
.lab small{{color:var(--c);font-size:11.5px}}
svg.lk{{position:absolute;inset:0;z-index:650;pointer-events:none}}
.bottom{{display:grid;grid-template-columns:1.25fr .95fr .7fr;gap:14px;padding:0 18px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.pair .row img{{height:84px}}.pair .row figcaption span{{display:none}}.strip{{background:#fff;border-radius:16px;padding:10px 14px 12px;border:2px solid #f0dcc0}}
.strip h4{{margin:0 0 8px;display:flex;align-items:center;gap:7px;font-family:"Jua";font-weight:400;font-size:21px;color:#c2410c}}
.row{{display:flex;gap:9px}}.row figure{{margin:0;flex:1;min-width:0}}.row img{{width:100%;height:96px;object-fit:cover;border-radius:10px;display:block}}
.row figcaption{{text-align:center;margin-top:4px}}.row figcaption b{{display:block;font-size:14.5px}}.row figcaption span{{font-size:12.5px;color:#4b4b55}}
.foot{{padding:10px 20px 14px;color:#5b5f6b;font-size:11.5px;line-height:1.55}}
</style></head><body>
<header class="top"><div class="bg"></div><div class="fade"></div><div class="in">
<div class="kick">{esc(str(kicker))}</div><h1>{esc(str(title))}</h1>
<div class="pills"><span class="pill"><b>여행기간</b>{esc(period)}</span><span class="pill"><b>함께 가는 사람</b>{esc(who_text(data))}</span>
{f'<span class="pill"><b>숙소</b>{esc(hotel_name)}</span>' if hotel_name else ""}</div></div>
<div class="memo">{note_lines}</div></header>
<div class="main"><div class="days">{"".join(cards)}</div>
<div class="right"><div class="mapcard"><div class="mh"><b>{esc(str(trip.get("destination", "")))} 동선 한눈에</b><div class="lg">{"".join(f'<span><i style="background:{x["color"]}"></i>{esc(x["label"])}</span>' for x in mdays)}<span>★ 숙소</span>{''.join(f'<span>{x}</span>' for x in dict.fromkeys(('✈ 공항' if a.get('kind') == '공항' else '갈색 이름표 = 기차역') for a in airports))}<span>숫자 = 사진 장소</span></div></div><div id="m"></div></div>{strips[0] if strips else ""}{('<div class="pair">' + "".join(strips[1:]) + '</div>') if len(strips) > 2 else "".join(strips[1:])}</div></div>
{foot}
<script src="{LEAFLET_JS}"></script>
<script>
const D={json.dumps(mapdata, ensure_ascii=False)};
function go(){{
const el=document.getElementById('m');
const map=L.map(el,{{zoomControl:false,attributionControl:true,zoomSnap:0.25}});
const tiles=L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:18,attribution:'© OpenStreetMap contributors'}}).addTo(map);
const all=[];const labs=[];
D.days.forEach(d=>{{if(d.line.length>1)L.polyline(d.line,{{color:d.color,weight:4,opacity:.85,dashArray:'2 8',lineCap:'round'}}).addTo(map);
 d.points.forEach(p=>{{all.push([p.lat,p.lon]);
  const html=p.no?`<div class="pin" style="background:${{d.color}}">${{p.no}}</div>`:`<div class="kico">${{p.ico}}</div>`;
  const sz=p.no?28:22;
  L.marker([p.lat,p.lon],{{icon:L.divIcon({{className:'',html,iconSize:[sz,sz],iconAnchor:[sz/2,sz/2]}}),zIndexOffset:p.no?500:0}}).addTo(map);
  if(p.no)labs.push({{...p,color:d.color,day:d.day}});}})}});
D.hotels.forEach(h=>{{all.push([h.lat,h.lon]);L.marker([h.lat,h.lon],{{zIndexOffset:1000,icon:L.divIcon({{className:'',html:'<div style="font-size:36px;line-height:36px;color:#f59f00;text-shadow:0 0 3px #7c2d12">★</div>',iconSize:[36,36],iconAnchor:[18,18]}})}}).addTo(map)}});
const apts=D.airports.map(a=>({{...a}}));
apts.forEach(a=>{{L.marker([a.lat,a.lon],{{icon:L.divIcon({{className:'',html:'<div class="aptdot"></div>',iconSize:[12,12],iconAnchor:[12/2,12/2]}})}}).addTo(map)}});
const H=el.clientHeight,Wd=el.clientWidth;
map.fitBounds(all,{{padding:[34,34]}});
// 가까운 공항·역은 함께 보이게 다시 맞추고, 먼 공항은 가장자리에 화살표 이름표만
const near=apts.filter(a=>map.getBounds().pad(0.25).contains([a.lat,a.lon]));
if(near.length){{map.fitBounds(all.concat(near.map(a=>[a.lat,a.lon])),{{padding:[34,34]}})}}
// 핀이 숙소 별·서로와 겹치면 화면에서 조금 밀어낸다(동선 선은 원래 자리)
const ms=[];map.eachLayer(l=>{{if(l instanceof L.Marker&&l.options.zIndexOffset===500)ms.push(l)}});
const hp=D.hotels.map(h=>map.latLngToContainerPoint([h.lat,h.lon]));
const ps=ms.map(m=>map.latLngToContainerPoint(m.getLatLng()));
for(let k=0;k<60;k++){{let mv=false;for(let i=0;i<ps.length;i++){{for(let j=i+1;j<ps.length;j++){{const dx=ps[j].x-ps[i].x,dy=ps[j].y-ps[i].y;let dd=Math.hypot(dx,dy);
 if(dd<30){{if(dd<.01){{ps[j].x+=1;dd=1}}const pu=(30-dd)/2+.5,ux=(ps[j].x-ps[i].x)/dd,uy=(ps[j].y-ps[i].y)/dd;ps[i].x-=ux*pu;ps[i].y-=uy*pu;ps[j].x+=ux*pu;ps[j].y+=uy*pu;mv=true}}}}
 hp.forEach(h=>{{let dx=ps[i].x-h.x,dy=ps[i].y-h.y;let dd=Math.hypot(dx,dy);if(dd<32){{if(dd<.01){{dx=1;dd=1}}const pu=32-dd+.5;ps[i].x+=dx/dd*pu;ps[i].y+=dy/dd*pu;mv=true}}}})}}if(!mv)break}}
ms.forEach((m,i)=>m.setLatLng(map.containerPointToLatLng(ps[i])));
// 이름표는 핀 바로 옆(오른쪽 → 왼쪽 → 위 → 아래 순으로 빈자리), 다른 이름표·핀과 안 겹치게
const boxes=ps.map(p=>({{x:p.x-16,y:p.y-16,w:32,h:32}})).concat(hp.map(p=>({{x:p.x-18,y:p.y-18,w:36,h:36}})));
const hit=(r)=>boxes.some(b=>r.x<b.x+b.w&&r.x+r.w>b.x&&r.y<b.y+b.h&&r.y+r.h>b.y)||r.x<4||r.y<4||r.x+r.w>Wd-4||r.y+r.h>H-22;
apts.forEach(a=>{{const q=map.latLngToContainerPoint([a.lat,a.lon]);const out=q.x<0||q.y<0||q.x>Wd||q.y>H;
 const d=document.createElement('div');d.className='apt';
 let arrow='';if(out){{const ang=Math.atan2(q.y-H/2,q.x-Wd/2)*180/Math.PI;arrow=' '+['→','↘','↓','↙','←','↖','↑','↗'][((Math.round(ang/45)%8)+8)%8]}}
 const km=D.hotels.length?Math.round(map.distance([D.hotels[0].lat,D.hotels[0].lon],[a.lat,a.lon])/1000):0;if(out||a.kind==='공항')d.classList.add('far');d.textContent=(a.kind==='교통'?'':'✈ ')+a.name+(out?arrow+(km?' 약 '+km+'km':''):'');el.appendChild(d);
 const w=d.offsetWidth,h=d.offsetHeight;let r=null;
 if(out){{const h0=hp.length?hp[0]:{{x:Wd/2,y:H/2}};const dx=q.x-h0.x,dy=q.y-h0.y;let t=1;if(dx>0)t=Math.min(t,(Wd-6-h0.x)/dx);if(dx<0)t=Math.min(t,(6-h0.x)/dx);if(dy>0)t=Math.min(t,(H-24-h0.y)/dy);if(dy<0)t=Math.min(t,(6-h0.y)/dy);const ex=h0.x+dx*t,ey=h0.y+dy*t;r={{x:Math.max(6,Math.min(Wd-6-w,ex-w/2)),y:Math.max(6,Math.min(H-24-h,ey-h-6)),w,h}}}}
 else{{const c=[[12,-h/2],[-12-w,-h/2],[-w/2,-12-h],[-w/2,12]];for(let s=0;s<20&&!r;s++){{for(const [ox,oy] of c){{const e=s*10;const t={{x:q.x+ox+(ox>0?e:ox<=-12-w?-e:0),y:q.y+oy+(oy<=-12-h?-e:oy>=12?e:0),w,h}};if(!hit(t)){{r=t;break}}}}}}
  if(!r)r={{x:Math.max(6,Math.min(Wd-6-w,q.x+12)),y:Math.max(6,Math.min(H-24-h,q.y-h/2)),w,h}}}}
 boxes.push(r);d.style.left=r.x+'px';d.style.top=r.y+'px'}});
const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','lk');svg.setAttribute('width',Wd);svg.setAttribute('height',H);
ms.forEach((m,i)=>{{const c=labs[i];const p=ps[i];const d=document.createElement('div');d.className='lab';d.style.setProperty('--c',c.color);
 d.innerHTML=`<i class="no" style="background:${{c.color}}">${{c.no}}</i>${{c.name}}<small>DAY${{c.day}}</small>`;el.appendChild(d);
 const w=d.offsetWidth,h=d.offsetHeight;
 const cand=[[18,-h/2],[-18-w,-h/2],[-w/2,-18-h],[-w/2,18],[18,-18-h],[18,18],[-18-w,-18-h],[-18-w,18]];let r=null;
 for(let step=0;step<24&&!r;step++){{for(const [ox,oy] of cand){{const extra=step*12;const t={{x:p.x+ox+(ox>0?extra:ox<=-18-w?-extra:0),y:p.y+oy+(oy<=-18-h?-extra:oy>=18?extra:0),w,h}};if(!hit(t)){{r=t;break}}}}}}
 if(!r){{const inb=t=>t.x>=4&&t.y>=4&&t.x+t.w<=Wd-4&&t.y+t.h<=H-22;for(const [ox,oy] of cand){{const t={{x:p.x+ox,y:p.y+oy,w,h}};if(inb(t)){{r=t;break}}}}}}
 if(!r)r={{x:Math.max(4,Math.min(Wd-w-4,p.x+18)),y:Math.max(4,Math.min(H-h-22,p.y-h/2)),w,h}};
 boxes.push(r);d.style.left=r.x+'px';d.style.top=r.y+'px';
 const cx=Math.max(r.x,Math.min(p.x,r.x+w)),cy=Math.max(r.y,Math.min(p.y,r.y+h));
 if(Math.hypot(cx-p.x,cy-p.y)>20){{const ln=document.createElementNS(svg.namespaceURI,'line');ln.setAttribute('x1',p.x);ln.setAttribute('y1',p.y);ln.setAttribute('x2',cx);ln.setAttribute('y2',cy);
 ln.setAttribute('stroke',c.color);ln.setAttribute('stroke-width','2');svg.appendChild(ln)}}}});
el.appendChild(svg);
let pending=0;tiles.on('tileloadstart',()=>pending++);tiles.on('tileload',()=>pending--);tiles.on('tileerror',()=>pending--);
window.mapReady=()=>pending<=0;
}}
window.addEventListener('load',go);
</script></body></html>"""
    return html, mapdata


def render(data: dict, yaml_dir: Path, out_dir: Path, name: str = "poster") -> Path:
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    html, _ = page(data, yaml_dir, check_trip.check(data))
    hp = out_dir / f"{name}.html"
    hp.write_text(html, encoding="utf-8")
    png = out_dir / f"{name}.png"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": 1400}, device_scale_factor=2,
                        user_agent="trip-planner-skill/0.1 (personal travel sheet)")
        pg.goto(hp.resolve().as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready.then(()=>1)")
        try:
            pg.wait_for_function("window.mapReady && window.mapReady()", timeout=25000)
        except Exception:  # noqa: BLE001
            pass
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(png), full_page=True)
        b.close()
    return png


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    yp = Path(argv[1])
    print("한 장 그림 →", render(tm.load(yp), yp.parent, Path(argv[2]), argv[3] if len(argv) == 4 else "poster"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
