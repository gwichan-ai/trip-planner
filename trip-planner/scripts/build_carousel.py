# -*- coding: utf-8 -*-
"""인스타 넘김(캐러셀) 1080x1350 다섯 장 — 한 장 그림(build_poster) 3판을 폰 크기로 나눈 것.
1 표지+지도 / 2~4 DAY 마다 한 장 / 5 먹어 볼 것·사 올 것·더 가볼 곳.
글자는 1080 폭에서 가장 작은 것도 26px 이상(폰 390 폭에서 약 9.5pt). 사실·사진·출처 규칙은 build_poster 와 같다.

쓰는 법: python build_carousel.py <여행.yaml> <나갈 폴더>
"""
from __future__ import annotations

import json
import re
import sys
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trip_model as tm  # noqa: E402
from build_infographic import icon_svg  # noqa: E402
from build_poster import Photos, go_text, who_text, LEAFLET_CSS, LEAFLET_JS  # noqa: E402

W, H = 1080, 1350

BASE_CSS = """
*{box-sizing:border-box}html,body{margin:0}
body{width:1080px;height:1350px;overflow:hidden;background:#fbf4e8;color:#2a2a33;font-family:"Malgun Gothic","Noto Sans KR",sans-serif;word-break:keep-all;position:relative}
.jua{font-family:"Jua";font-weight:400}
.foot{position:absolute;left:44px;right:44px;bottom:26px;display:flex;justify-content:space-between;color:#5b5f6b;font-size:24px}
.foot b{color:#c2410c}
i.no{font-style:normal;flex:none;width:44px;height:44px;border-radius:50%;background:var(--c);color:#fff;font-size:26px;font-weight:800;display:inline-flex;align-items:center;justify-content:center}
"""


def page_html(body: str, css: str, extra_head: str = "") -> str:
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jua&family=Gaegu:wght@700&display=swap">'
            f'{extra_head}<style>{BASE_CSS}{css}</style></head><body>{body}</body></html>')


PAGES_BEFORE = 0  # 이 넘김 앞에 따로 붙는 장 수(예: 후킹 표지). trip.pages_before 로 정한다


HANDLE = ""  # 넘김 아래 왼쪽에 찍을 계정 이름. 여행 데이터 trip.handle(예: "@my_account")에서 읽는다


def foot(n: int, total: int, right: str = "") -> str:
    who = f'<b>{esc(HANDLE)}</b> ' if HANDLE else ""
    return f'<div class="foot"><span>{who}{esc(right)}</span><span>{n + PAGES_BEFORE} / {total + PAGES_BEFORE}</span></div>'


def build(data: dict, yaml_dir: Path) -> list[str]:
    trip = data.get("trip") or {}
    global PAGES_BEFORE, HANDLE
    HANDLE = str(trip.get("handle") or "")
    PAGES_BEFORE = int(trip.get("pages_before") or 0)
    ph = Photos(yaml_dir / str(trip.get("photo_dir", "photos")))
    places = tm.places(data)
    days = tm.days(data)
    basics = data.get("basics") or {}
    nb = (1 if (basics.get("transport") or basics.get("lodging")) else 0) + (1 if (basics.get("weather") or basics.get("packing")) else 0)
    total = len(days) + 2 + nb
    start, end = tm.to_date(trip.get("start")), tm.to_date(trip.get("end"))
    period = f"{start.month}. {start.day}({tm.weekday_ko(start)}) ~ {end.month}. {end.day}({tm.weekday_ko(end)})"
    hotel = places.get((data.get("emergency") or {}).get("hotel"), {})
    hotel_name = re.sub(r"^예시\s*숙소\s*", "", hotel.get("name", "")).strip("() ") if hotel else ""
    pages = []

    # ---- 1. 표지 + 지도 ----
    mdays = []
    for d in days:
        num, pts, line, seen = {}, [], [], set()
        for it in d["items"]:
            p = it["place_data"]
            if p.get("photo") and len(num) < 3 and it.get("place") not in num:
                num[it.get("place")] = len(num) + 1
        for it in d["items"]:
            p = it["place_data"]
            if p.get("lat") is None:
                continue
            line.append([p["lat"], p["lon"]])
            if it.get("place") in seen or p.get("kind") in ("공항", "숙소"):
                continue
            seen.add(it.get("place"))
            pts.append({"lat": p["lat"], "lon": p["lon"], "no": num.get(it.get("place")), "name": p.get("name", ""),
                        "ico": icon_svg(p, d["color"], 30)})
        mdays.append({"color": d["color"], "day": d["index"] + 1, "points": pts, "line": line})
    hotels = [{"lat": p["lat"], "lon": p["lon"]} for p in places.values() if p.get("kind") == "숙소" and p.get("lat") is not None]
    airports = [{"lat": p["lat"], "lon": p["lon"], "name": p.get("name", ""), "kind": p.get("kind")} for p in places.values() if p.get("kind") in ("공항", "교통") and p.get("lat") is not None]
    head = ph.uri(trip.get("header_photo"))
    legend = "".join(f'<span><i style="background:{x["color"]}"></i>DAY {x["day"]}</span>' for x in mdays)
    css1 = f"""
.top{{position:relative;height:430px;overflow:hidden}}.top .bg{{position:absolute;inset:0;background:url({head}) center 60%/cover}}
.top .fade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(251,244,232,.15) 0%,rgba(251,244,232,.92) 78%,#fbf4e8 100%)}}
.top .in{{position:absolute;left:52px;right:52px;bottom:28px}}
.kick{{font-size:44px;color:#c2410c}}h1{{margin:0 0 18px;font-size:104px;line-height:1;color:#7c2d12;text-shadow:0 4px 0 rgba(255,255,255,.85)}}
.pills{{display:flex;flex-wrap:wrap;gap:12px}}.pill{{background:#fff;border-radius:999px;padding:10px 22px;font-size:30px;font-weight:700;box-shadow:0 2px 8px rgba(124,45,18,.15)}}.pill b{{color:#c2410c;margin-right:8px}}
.mapbox{{position:absolute;left:44px;right:44px;top:450px;height:790px;border-radius:28px;overflow:hidden;border:3px solid #f0dcc0;background:#cfe6ee}}
#m{{position:absolute;inset:0}}.leaflet-tile-pane{{filter:sepia(.32) saturate(1.35) hue-rotate(-6deg) brightness(1.04) contrast(.95)}}
.leaflet-control-attribution{{font-size:18px!important}}
.lg{{position:absolute;z-index:800;left:20px;right:20px;top:18px;flex-wrap:wrap;background:rgba(255,255,255,.95);border-radius:18px;padding:10px 18px;font-size:26px;font-weight:800;display:flex;gap:18px}}.lg i{{display:inline-block;width:22px;height:22px;border-radius:50%;margin-right:6px;vertical-align:-3px}}
.pin{{width:46px;height:46px;border-radius:50%;color:#fff;font:800 26px/46px "Malgun Gothic";text-align:center;border:4px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.4)}}
.apt{{position:absolute;z-index:720;background:#7c2d12;color:#fff;border-radius:10px;padding:5px 14px;font:800 24px "Malgun Gothic";white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.4)}}.apt.far{{background:#fff;color:#7c2d12;border:2px solid #7c2d12;font-size:24px}}.aptdot{{width:20px;height:20px;border-radius:50%;background:#7c2d12;border:3px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)}}
.kico svg{{display:block;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}}
.lab{{position:absolute;z-index:700;background:#fff;border:3px solid var(--c);border-radius:999px;padding:6px 16px;font-weight:800;font-size:27px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.18)}}
svg.lk{{position:absolute;inset:0;z-index:650;pointer-events:none}}
"""
    js = """<script>
const D=__D__;
function go(){const el=document.getElementById('m');
const map=L.map(el,{zoomControl:false,attributionControl:true,zoomSnap:0.25});
const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(map);
const all=[];const labs=[];const ms=[];
D.days.forEach(d=>{if(d.line.length>1)L.polyline(d.line,{color:d.color,weight:6,opacity:.85,dashArray:'2 12',lineCap:'round'}).addTo(map);
 d.points.forEach(p=>{all.push([p.lat,p.lon]);const sz=p.no?46:30;
  const m=L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',html:p.no?`<div class="pin" style="background:${d.color}">${p.no}</div>`:`<div class="kico">${p.ico}</div>`,iconSize:[sz,sz],iconAnchor:[sz/2,sz/2]}),zIndexOffset:p.no?500:0}).addTo(map);
  if(p.no){ms.push(m);labs.push({...p,color:d.color})}})});
D.hotels.forEach(h=>{all.push([h.lat,h.lon]);L.marker([h.lat,h.lon],{zIndexOffset:1000,icon:L.divIcon({className:'',html:'<div style="font-size:58px;line-height:58px;color:#f59f00;text-shadow:0 0 4px #7c2d12">★</div>',iconSize:[58,58],iconAnchor:[29,29]})}).addTo(map)});
const apts=D.airports.map(a=>({...a}));
apts.forEach(a=>{L.marker([a.lat,a.lon],{icon:L.divIcon({className:'',html:'<div class="aptdot"></div>',iconSize:[20,20],iconAnchor:[20/2,20/2]})}).addTo(map)});
const H=el.clientHeight,Wd=el.clientWidth;
map.fitBounds(all,{paddingTopLeft:[40,110],paddingBottomRight:[40,60]});
// 가까운 공항·역은 함께 보이게 다시 맞추고, 먼 공항은 가장자리에 화살표 이름표만
const near=apts.filter(a=>map.getBounds().pad(0.25).contains([a.lat,a.lon]));
if(near.length){map.fitBounds(all.concat(near.map(a=>[a.lat,a.lon])),{paddingTopLeft:[40,110],paddingBottomRight:[40,60]})}
const hp=D.hotels.map(h=>map.latLngToContainerPoint([h.lat,h.lon]));
const ps=ms.map(m=>map.latLngToContainerPoint(m.getLatLng()));
for(let k=0;k<60;k++){let mv=false;for(let i=0;i<ps.length;i++){for(let j=i+1;j<ps.length;j++){const dx=ps[j].x-ps[i].x,dy=ps[j].y-ps[i].y;let dd=Math.hypot(dx,dy);
 if(dd<48){if(dd<.01){ps[j].x+=1;dd=1}const pu=(48-dd)/2+.5,ux=(ps[j].x-ps[i].x)/dd,uy=(ps[j].y-ps[i].y)/dd;ps[i].x-=ux*pu;ps[i].y-=uy*pu;ps[j].x+=ux*pu;ps[j].y+=uy*pu;mv=true}}
 hp.forEach(h=>{let dx=ps[i].x-h.x,dy=ps[i].y-h.y;let dd=Math.hypot(dx,dy);if(dd<50){if(dd<.01){dx=1;dd=1}const pu=50-dd+.5;ps[i].x+=dx/dd*pu;ps[i].y+=dy/dd*pu;mv=true}})}if(!mv)break}
ms.forEach((m,i)=>m.setLatLng(map.containerPointToLatLng(ps[i])));
const boxes=ps.map(p=>({x:p.x-26,y:p.y-26,w:52,h:52})).concat(hp.map(p=>({x:p.x-30,y:p.y-30,w:60,h:60})));
boxes.push({x:0,y:0,w:Wd,h:100});
const hit=r=>boxes.some(b=>r.x<b.x+b.w&&r.x+r.w>b.x&&r.y<b.y+b.h&&r.y+r.h>b.y)||r.x<6||r.y<6||r.x+r.w>Wd-6||r.y+r.h>H-34;
apts.forEach(a=>{const q=map.latLngToContainerPoint([a.lat,a.lon]);const out=q.x<0||q.y<0||q.x>Wd||q.y>H;
 const d=document.createElement('div');d.className='apt';
 let arrow='';if(out){const ang=Math.atan2(q.y-H/2,q.x-Wd/2)*180/Math.PI;arrow=' '+['→','↘','↓','↙','←','↖','↑','↗'][((Math.round(ang/45)%8)+8)%8]}
 const km=D.hotels.length?Math.round(map.distance([D.hotels[0].lat,D.hotels[0].lon],[a.lat,a.lon])/1000):0;if(out||a.kind==='공항')d.classList.add('far');d.textContent=(a.kind==='교통'?'':'✈ ')+a.name+(out?arrow+(km?' 약 '+km+'km':''):'');el.appendChild(d);
 const w=d.offsetWidth,h=d.offsetHeight;let r=null;
 if(out){const h0=hp.length?hp[0]:{x:Wd/2,y:H/2};const dx=q.x-h0.x,dy=q.y-h0.y;let t=1;if(dx>0)t=Math.min(t,(Wd-8-h0.x)/dx);if(dx<0)t=Math.min(t,(8-h0.x)/dx);if(dy>0)t=Math.min(t,(H-36-h0.y)/dy);if(dy<0)t=Math.min(t,(8-h0.y)/dy);const ex=h0.x+dx*t,ey=h0.y+dy*t;r={x:Math.max(8,Math.min(Wd-8-w,ex-w/2)),y:Math.max(8,Math.min(H-36-h,ey-h-6)),w,h}}
 else{const c=[[20,-h/2],[-20-w,-h/2],[-w/2,-20-h],[-w/2,20]];for(let s=0;s<20&&!r;s++){for(const [ox,oy] of c){const e=s*10;const t={x:q.x+ox+(ox>0?e:ox<=-20-w?-e:0),y:q.y+oy+(oy<=-20-h?-e:oy>=20?e:0),w,h};if(!hit(t)){r=t;break}}}
  if(!r)r={x:Math.max(8,Math.min(Wd-8-w,q.x+20)),y:Math.max(8,Math.min(H-36-h,q.y-h/2)),w,h}}
 boxes.push(r);d.style.left=r.x+'px';d.style.top=r.y+'px'});
const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','lk');svg.setAttribute('width',Wd);svg.setAttribute('height',H);
labs.forEach((c,i)=>{const p=ps[i];const d=document.createElement('div');d.className='lab';d.style.setProperty('--c',c.color);d.textContent=c.name;el.appendChild(d);
 const w=d.offsetWidth,h=d.offsetHeight;const cand=[[28,-h/2],[-28-w,-h/2],[-w/2,-28-h],[-w/2,28],[28,-28-h],[28,28],[-28-w,-28-h],[-28-w,28]];let r=null;
 for(let s=0;s<30&&!r;s++){for(const [ox,oy] of cand){const e=s*12;const t={x:p.x+ox+(ox>0?e:ox<=-28-w?-e:0),y:p.y+oy+(oy<=-28-h?-e:oy>=28?e:0),w,h};if(!hit(t)){r=t;break}}}
 if(!r){const inb=t=>t.x>=6&&t.y>=86&&t.x+t.w<=Wd-6&&t.y+t.h<=H-34;for(const [ox,oy] of cand){const t={x:p.x+ox,y:p.y+oy,w,h};if(inb(t)){r=t;break}}}
 if(!r)r={x:Math.max(6,Math.min(Wd-w-6,p.x+28)),y:Math.max(6,Math.min(H-h-34,p.y-h/2)),w,h};
 boxes.push(r);d.style.left=r.x+'px';d.style.top=r.y+'px';
 const cx=Math.max(r.x,Math.min(p.x,r.x+w)),cy=Math.max(r.y,Math.min(p.y,r.y+h));
 if(Math.hypot(cx-p.x,cy-p.y)>30){const ln=document.createElementNS(svg.namespaceURI,'line');ln.setAttribute('x1',p.x);ln.setAttribute('y1',p.y);ln.setAttribute('x2',cx);ln.setAttribute('y2',cy);ln.setAttribute('stroke',c.color);ln.setAttribute('stroke-width','3');svg.appendChild(ln)}});
el.appendChild(svg);
let pending=0;tiles.on('tileloadstart',()=>pending++);tiles.on('tileload',()=>pending--);tiles.on('tileerror',()=>pending--);window.mapReady=()=>pending<=0;}
window.addEventListener('load',go);
</script>""".replace("__D__", json.dumps({"days": mdays, "hotels": hotels, "airports": airports}, ensure_ascii=False))
    body1 = (f'<div class="top"><div class="bg"></div><div class="fade"></div><div class="in">'
             f'<div class="kick jua">{esc(str(trip.get("poster_kicker") or trip.get("kicker", "")))}</div>'
             f'<h1 class="jua" style="font-size:{min(104, int(104 * 13 / max(len(str(trip.get("poster_title") or trip.get("title", ""))), 1)))}px">{esc(str(trip.get("poster_title") or trip.get("title", "")))}</h1>'
             f'<div class="pills"><span class="pill"><b>기간</b>{esc(period)}</span><span class="pill"><b>함께</b>{esc(who_text(data))}</span>'
             + (f'<span class="pill"><b>숙소</b>{esc(hotel_name)}</span>' if hotel_name else "")
             + f'</div></div></div><div class="mapbox"><div id="m"></div><div class="lg">{legend}<span>★ 숙소</span>{''.join(f'<span>{x}</span>' for x in dict.fromkeys(('✈ 공항' if a.get('kind') == '공항' else '갈색 이름표 = 기차역') for a in airports))}<span>숫자 = 사진 장소</span></div></div>'
             + foot(1, total, ("맨 위 그림은 AI(분위기용) · " if ph.is_ai(trip.get("header_photo")) else "") + "넘겨서 날짜별 일정 →") + f'<script src="{LEAFLET_JS}"></script>' + js)
    pages.append(page_html(body1, css1, f'<link rel="stylesheet" href="{LEAFLET_CSS}">'))

    # ---- v2 기본 먼저: 교통·숙박 / 날씨·준비물 (10/20 "여행의 기본은 교통편, 숙박") ----
    pages.extend(basics_pages(basics, total))

    # ---- 2~4. DAY ----
    css_day = """
.dh{padding:46px 52px 18px;background:color-mix(in srgb,var(--c) 14%,#fbf4e8)}
.dh .row{display:flex;align-items:center;gap:18px}
.badge{font-size:58px;color:#fff;background:var(--c);border-radius:16px;padding:4px 24px}
.date{font-weight:800;color:var(--c);border:3px solid var(--c);border-radius:999px;padding:4px 20px;background:#fff;font-size:32px}
.dh h2{margin:16px 0 4px;font-size:64px;color:var(--c);line-height:1.1}.dh p{margin:0;font-size:30px;color:#3f434d}
.ph{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:26px 52px 10px}
.ph figure{margin:0}.ph img{width:100%;height:250px;object-fit:cover;border-radius:18px;display:block}
.ph figcaption{display:flex;align-items:center;gap:8px;margin-top:10px;font-weight:800;font-size:28px;line-height:1.2}
.tl{list-style:none;margin:10px 52px 0;padding:0;position:relative}
.tl::before{content:"";position:absolute;left:121px;top:20px;bottom:20px;width:4px;background:color-mix(in srgb,var(--c) 40%,#fff)}
.tl li{display:flex;gap:16px;padding:10px 0;align-items:flex-start}
.t{width:96px;flex:none;font-weight:800;font-size:32px;text-align:right;font-variant-numeric:tabular-nums}
.dot{width:26px;height:26px;margin:8px 9px 0;flex:none;border-radius:50%;border:5px solid var(--c);background:#fff;position:relative;z-index:1}
.tl i.no{position:relative;z-index:1}
.n{font-weight:800;font-size:34px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}.go{font-weight:600;font-size:26px;color:#5b5f6b}
.w{color:#3f434d;font-size:28px;margin-top:2px}
.xdot{flex:none;width:22px;height:22px;border-radius:50%;border:5px solid var(--c);background:#fff}
.todo{margin:26px 52px 0;background:#fff;border:3px solid color-mix(in srgb,var(--c) 40%,#fff);border-radius:22px;padding:18px 26px}
.todo h3{margin:0 0 10px;font-size:40px;color:var(--c)}.todo ul{margin:0;padding:0;list-style:none}
.todo li{font-size:28px;padding:6px 0;display:flex;gap:16px}.todo li b{flex:none;width:84px;color:var(--c)}
.dense .dh{padding-top:34px;padding-bottom:12px}.dense .dh h2{font-size:56px;margin-top:10px}.dense .ph{padding-top:18px}.dense .ph img{height:190px}
.dense .tl li{padding:5px 0}.dense .n{font-size:31px}.dense .w{font-size:26px}.dense .t{font-size:30px}
"""
    for d in days:
        num, spots = {}, []
        dep = data.get("departure") or {}
        if dep.get("time") and str(tm.to_date(dep.get("date"))) == str(d["date"]):
            dp = places.get(dep.get("place"), {})
            d = dict(d, items=list(d["items"]) + [{"time": dep["time"], "place": dep.get("place"), "place_data": dp,
                                                   "what": "비행기 출발 (예시 시각)" if dp.get("kind") == "공항" else "출발 (예시 시각)"}])
        for it in d["items"]:
            p = it["place_data"]
            if p.get("photo") and len(spots) < 3 and it.get("place") not in num:
                num[it.get("place")] = len(spots) + 1
                nm = p.get("name", "")
                spots.append((p.get("photo"), nm.rsplit(" ", 1)[0] if len(nm) > 9 and " " in nm else nm))
        photos = "".join(f'<figure><img src="{ph.uri(k)}"><figcaption><i class="no">{i + 1}</i>{esc(n)}</figcaption></figure>'
                         for i, (k, n) in enumerate(spots) if ph.uri(k)) + "".join(
            f'<figure><img src="{ph.uri(x.get("photo"))}"><figcaption><span class="xdot"></span>{esc(x.get("name", ""))}</figcaption></figure>'
            for x in (d.get("photos") or [])[:max(0, 3 - len(spots))] if ph.uri(x.get("photo")))
        nph = min(3, len(spots) + len(d.get("photos") or []))
        extra = ""
        alts = [str(it["alt"]) for it in d["items"] if it.get("alt")]
        if len(d["items"]) <= 3 and alts and d["index"] != len(days) - 1:
            extra = '<div class="todo"><h3 class="jua">이럴 땐</h3><ul>' + "".join(f'<li>{esc(x)}</li>' for x in alts) + '</ul></div>'
        if d["index"] == len(days) - 1 and len(d["items"]) <= 4:
            todo = [c for c in data.get("checklist") or [] if not c.get("done")]
            if todo:
                extra = ('<div class="todo"><h3 class="jua">떠나기 전 챙길 것</h3><ul>'
                         + "".join(f'<li><b>{esc(str(c.get("when", "")))}</b>{esc(str(c.get("item", "")))}</li>' for c in todo) + '</ul></div>')
        rows = []
        for it in d["items"]:
            p = it["place_data"]
            n = num.get(it.get("place"))
            mark = f'<i class="no">{n}</i>' if n else ('<span class="dot" style="background:var(--c)"></span>' if p.get("kind") == "식사" else '<span class="dot"></span>')
            go = go_text(it.get("go"))
            rows.append(f'<li><span class="t">{esc(str(it.get("time")))}</span>{mark}<div><div class="n">{icon_svg(p, d["color"], 34)}'
                        f'{esc(re.sub(r"^예시 숙소", "숙소", p.get("name", "")))}' + (f'<span class="go">{esc(go)}</span>' if go else "")
                        + f'</div><div class="w">{esc(str(it.get("what", "")))}' + (f' · {esc(str(it["note"]))}' if it.get("note") else "") + '</div></div></li>')
        dense = " dense" if len(d["items"]) >= 8 else ""
        body = (f'<div class="pg{dense}" style="--c:{d["color"]}"><div class="dh"><div class="row"><span class="badge jua">DAY {d["index"] + 1}</span>'
                f'<span class="date">{d["date"].month}월 {d["date"].day}일 ({tm.weekday_ko(d["date"])})</span></div>'
                f'<h2 class="jua">{esc(str(d.get("title", "")))}</h2><p>{esc(str(d.get("subtitle", "")))}</p></div>'
                f'<div class="ph" style="grid-template-columns:repeat({max(nph, 1)},1fr)">{photos}</div><ul class="tl">{"".join(rows)}</ul>{extra}</div>'
                + foot(d["index"] + 2 + nb, total, "사진 출처는 게시글 캡션에 · 영업시간은 가기 전에 다시 확인"))
        pages.append(page_html(body, css_day))

    # ---- 5. 먹을 것·살 것·더 ----
    css5 = """
h2{margin:0;padding:52px 52px 6px;font-size:66px;color:#7c2d12}
.sec{padding:14px 52px 4px}.sec h3{margin:0 0 12px;display:flex;align-items:center;gap:10px;font-size:40px;color:#c2410c}
.grid{display:grid;gap:14px}.grid figure{margin:0}.grid img{width:100%;object-fit:cover;border-radius:16px;display:block}
.grid figcaption{text-align:center;margin-top:6px}.grid b{display:block;font-size:30px}.grid span{font-size:24px;color:#4b4b55}
"""
    secs = []
    nstrip = len(data.get("strips") or [])
    heights = {0: 220, 1: 190, 2: 190} if nstrip >= 3 else {0: 350, 1: 340}
    for si, s in enumerate(data.get("strips") or []):
        items = [x for x in s.get("items") or [] if ph.uri(x.get("photo"))]
        figs = "".join(f'<figure><img src="{ph.uri(x.get("photo"))}" style="height:{heights.get(si, 190)}px;object-position:{x.get("pos", "center")}"><figcaption><b>{esc(x.get("name", ""))}</b><span>{esc(x.get("sub", ""))}</span></figcaption></figure>' for x in items)
        secs.append(f'<div class="sec"><h3 class="jua">{icon_svg({"kind": s.get("icon", "기본")}, "#E8590C", 40)}{esc(s.get("title", ""))}</h3>'
                    f'<div class="grid" style="grid-template-columns:repeat({len(items)},1fr)">{figs}</div></div>')
    src_line, _ = ph.credits()
    cta = trip.get("cta")
    cta_html = (f'<div style="position:absolute;left:44px;right:44px;bottom:80px;background:#0f766e;color:#fff;border-radius:24px;'
                f'padding:22px 30px;font-size:36px;font-weight:800;text-align:center">{esc(str(cta))}</div>') if cta else ""
    body5 = (f'<h2 class="jua">여행 가서 이것도</h2>{"".join(secs)}{cta_html}'
             + foot(total, total, "사진 출처·라이선스는 게시글 캡션에"))
    pages.append(page_html(body5, css5))
    return pages


BASICS_CSS = """
.hd{padding:46px 52px 8px}.hd .k{font-size:34px;color:#c2410c}.hd h2{margin:4px 0 0;font-size:72px;line-height:1.05;color:#7c2d12}
.card{margin:18px 44px 0;background:#fff;border-radius:26px;padding:22px 28px;box-shadow:0 2px 10px rgba(124,45,18,.10)}
.card h3{margin:0 0 12px;display:flex;align-items:center;gap:12px;font-size:42px;color:#0f766e}.card h3 .st{font-size:28px;color:#fff;background:#0f766e;border-radius:999px;padding:2px 16px}
.rw{display:flex;gap:14px;font-size:30px;padding:6px 0;align-items:baseline}.rw b{flex:none;width:120px;color:#7c2d12}.rw .s{font-size:22px;color:#8a8f99;margin-left:auto;white-space:nowrap;padding-left:10px}
.area{display:flex;gap:14px;align-items:baseline;font-size:29px;padding:7px 0;border-top:2px dashed #f0dcc0}.area:first-of-type{border-top:0}
.area b{flex:none;width:200px}.tag{flex:none;font-size:24px;font-weight:800;border-radius:999px;padding:2px 14px;background:#fff7e6;color:#c2410c;border:2px solid #f3c98b}.tag.on{background:#0f766e;color:#fff;border-color:#0f766e}
.small{font-size:24px;color:#6b5a4c;margin-top:8px;line-height:1.35}
.temp{display:flex;gap:18px;align-items:center}.temp .big{font-size:84px;font-weight:900;color:#c2410c;line-height:1}.temp .big small{font-size:40px;color:#0369a1}
.temp .t2{font-size:30px;line-height:1.35}
.pk{display:grid;grid-template-columns:1fr 1fr;gap:10px 22px}.pk div{font-size:29px;display:flex;gap:10px;align-items:baseline}.pk div::before{content:"✓";color:#0f766e;font-weight:900}
.pk span{display:block;font-size:23px;color:#6b5a4c}
"""


def basics_pages(b: dict, total: int) -> list[str]:
    """교통·숙박 한 장, 날씨·준비물 한 장. 값은 데이터에 있는 것만 쓴다(지어내지 않음)."""
    out = []
    ck = str(b.get("checked", ""))
    n = 2
    tr, lo = b.get("transport") or {}, b.get("lodging") or {}
    if tr or lo:
        h = f'<div class="hd"><div class="k jua">여행의 기본 ① ②</div><h2 class="jua">교통편부터, 숙소까지</h2></div>'
        if tr:
            h += (f'<div class="card"><h3 class="jua"><span class="st">①</span>{esc(str(tr.get("title", "교통")))}</h3>'
                  + "".join(f'<div class="rw"><b>{esc(str(r.get("label", "")))}</b><span>{esc(str(r.get("when", "")))} · {esc(str(r.get("what", "")))}</span></div>' for r in tr.get("rows") or [])
                  + "".join(f'<div class="rw"><b>{esc(str(f.get("k", "")))}</b><span>{esc(str(f.get("v", "")))}</span></div>' for f in tr.get("facts") or [])
                  + '<div class="small">출처: ' + esc(" · ".join(str(f.get("src")) for f in tr.get("facts") or [] if f.get("src"))) + f' (확인 {esc(ck)})</div></div>')
        if lo:
            h += (f'<div class="card"><h3 class="jua"><span class="st">②</span>숙소 · 예산 {esc(str(lo.get("budget", "")))}</h3>'
                  + "".join(f'<div class="area"><b>{esc(str(a.get("name", "")))}</b><span class="tag{" on" if a.get("name") == lo.get("pick") else ""}">{esc(str(a.get("fit", "")))}</span><span>{esc(str(a.get("note", "")))}</span></div>' for a in lo.get("areas") or [])
                  + (f'<div class="rw" style="margin-top:6px"><b>왜</b><span>{esc(str(lo.get("why", "")))}</span></div>' if lo.get("why") else "")
                  + f'<div class="small">참고 값: {esc(str(lo.get("price_ref", "")))} (확인 {esc(ck)}) · {esc(str(lo.get("note", "")))}</div></div>')
        out.append(page_html(h + foot(n, total, "예약·결제는 직접 · 값은 날짜마다 달라요"), BASICS_CSS))
        n += 1
    we, pk = b.get("weather") or {}, b.get("packing") or []
    if we or pk:
        h = f'<div class="hd"><div class="k jua">여행의 기본 ③ 그리고 짐</div><h2 class="jua">날씨 보고, 맞춰 챙기기</h2></div>'
        if we:
            h += (f'<div class="card"><h3 class="jua"><span class="st">③</span>날씨 ({esc(str(we.get("mode", "")))})</h3>'
                  f'<div class="temp"><div class="big">{esc(str(we.get("high")))}°<small> / {esc(str(we.get("low")))}°</small></div>'
                  f'<div class="t2">낮 최고 / 아침 최저<br>{esc(str(we.get("rain_days", "")))}</div></div>'
                  + ('<div class="rw" style="margin-top:10px;color:#0369a1;font-weight:800">☔ 비 오면 이렇게</div>' if we.get("rain_plan") else "")
                  + "".join(f'<div class="rw"><b>DAY {esc(str(r.get("day")))}</b><span>{esc(str(r.get("text", "")))}</span></div>' for r in we.get("rain_plan") or [])
                  + f'<div class="small">{esc(str(we.get("src", "")))} · {esc(str(we.get("recheck", "")))}</div></div>')
        if pk:
            h += ('<div class="card"><h3 class="jua">🎒 날씨·일정에 맞춘 준비물</h3><div class="pk">'
                  + "".join(f'<div><p style="margin:0">{esc(str(x.get("item", "")))}<span>{esc(str(x.get("why", "")))}</span></p></div>' for x in pk)
                  + '</div></div>')
        out.append(page_html(h + foot(n, total, "넘겨서 날짜별 일정 →"), BASICS_CSS))
    return out


def render(data: dict, yaml_dir: Path, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = build(data, yaml_dir)
    outs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for i, html in enumerate(pages, 1):
            hp = out_dir / f"carousel_{i}.html"
            hp.write_text(html, encoding="utf-8")
            pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1,
                            user_agent="trip-planner-skill/0.1 (personal travel sheet)")
            pg.goto(hp.resolve().as_uri(), wait_until="networkidle")
            pg.evaluate("document.fonts.ready.then(()=>1)")
            if i == 1:
                try:
                    pg.wait_for_function("window.mapReady && window.mapReady()", timeout=25000)
                except Exception:  # noqa: BLE001
                    pass
                pg.wait_for_timeout(1500)
            png = out_dir / f"carousel_{i}.png"
            pg.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": W, "height": H})
            outs.append(png)
            pg.close()
        b.close()
    return outs


if __name__ == "__main__":
    yp = Path(sys.argv[1])
    for p in render(tm.load(yp), yp.parent, Path(sys.argv[2])):
        print("넘김 →", p)
