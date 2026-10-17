# -*- coding: utf-8 -*-
"""실제 지도(오픈스트리트맵) 위에 날짜 색 동선, 번호 핀, 숙소 별을 찍은 PNG 를 만든다.
Leaflet 페이지를 Playwright 로 열어 지도 조각이 다 뜬 뒤 찍는다. 키나 결제 없음.
지도 아래 오른쪽에 "© OpenStreetMap contributors" 출처를 꼭 남긴다(OSM 이용 조건).

쓰는 법(모듈): png_bytes = render(data, width_px, height_px)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trip_model as tm  # noqa: E402

LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"
TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def points(data: dict) -> dict:
    """지도에 찍을 것: 날짜별 번호 점과 동선, 숙소. 공항과 map:false 는 뺀다(멀어서 지도가 너무 넓어짐)."""
    days = []
    for d in tm.days(data):
        pts, line = [], []
        seen = {}
        for it in d["items"]:
            p = it["place_data"]
            if p.get("lat") is None or p.get("map", True) is False or p.get("kind") == "공항":
                continue
            if p.get("kind") != "숙소":
                line.append([p["lat"], p["lon"]])
            if it["no"] is None:
                continue
            key = it.get("place")
            if key in seen:
                seen[key]["label"] += f",{it['no']}"
                continue
            seen[key] = {"lat": p["lat"], "lon": p["lon"], "label": str(it["no"]), "name": p.get("name", "")}
            pts.append(seen[key])
        days.append({"color": d["color"], "label": d["label"].split(" ")[0], "points": pts, "line": line})
    hotels = [{"lat": p["lat"], "lon": p["lon"], "name": p.get("name", "")}
              for p in tm.places(data).values() if p.get("kind") == "숙소" and p.get("lat") is not None]
    return {"days": days, "hotels": hotels}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="%(css)s">
<style>html,body{margin:0;padding:0}#m{width:%(w)dpx;height:%(h)dpx}
.pin{width:22px;height:22px;border-radius:50%%;color:#fff;font:700 12px/22px "Malgun Gothic",sans-serif;text-align:center;border:2.5px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45)}
.pin.wide{width:auto;padding:0 6px;border-radius:11px}
.home{font-size:30px;line-height:30px;color:#111;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 3px #fff}
.leaflet-control-attribution{font-size:11px}.leaflet-tile-pane{filter:saturate(.35) brightness(1.06) contrast(.92)}
.legend{position:absolute;left:10px;top:10px;z-index:999;background:rgba(255,255,255,.92);border-radius:8px;padding:6px 10px;font:600 12px "Malgun Gothic",sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.25)}
.legend i{display:inline-block;width:12px;height:12px;border-radius:50%%;margin:0 4px -1px 8px}
</style></head><body><div id="m"></div><div class="legend" id="lg"></div>
<script src="%(js)s"></script>
<script>
const D=%(data)s;
const map=L.map('m',{zoomControl:false,attributionControl:true,zoomSnap:0.25});
const tiles=L.tileLayer('%(tiles)s',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(map);
const all=[];
D.days.forEach(d=>{
  if(d.line.length>1)L.polyline(d.line,{color:d.color,weight:2.5,opacity:.9,dashArray:'6 6'}).addTo(map);
  d.points.forEach(p=>{all.push([p.lat,p.lon]);
    L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',html:`<div class="pin${p.label.length>2?' wide':''}" style="background:${d.color}">${p.label}</div>`,iconSize:[22,22],iconAnchor:[11,11]})}).addTo(map)})});
D.hotels.forEach(h=>{all.push([h.lat,h.lon]);L.marker([h.lat,h.lon],{icon:L.divIcon({className:'',html:'<div class="home">★</div>',iconSize:[30,30],iconAnchor:[15,15]}),zIndexOffset:1000}).addTo(map)});
map.fitBounds(all,{padding:[34,34]});
// 겹치는 핀은 화면에서 조금씩 밀어낸다(동선 선은 원래 자리). 숙소 별은 움직이지 않는다.
const ms=[];map.eachLayer(l=>{if(l instanceof L.Marker&&!(l.options.zIndexOffset>0))ms.push(l)});
const hs=[];map.eachLayer(l=>{if(l instanceof L.Marker&&l.options.zIndexOffset>0)hs.push(map.latLngToContainerPoint(l.getLatLng()))});
const ps=ms.map(m=>map.latLngToContainerPoint(m.getLatLng()));
for(let k=0;k<40;k++){let moved=false;
  for(let i=0;i<ps.length;i++){for(let j=i+1;j<ps.length;j++){const dx=ps[j].x-ps[i].x,dy=ps[j].y-ps[i].y;let d=Math.hypot(dx,dy);
    if(d<24){if(d<0.01){ps[j].x+=1;d=1}const push=(24-d)/2+.5,ux=(ps[j].x-ps[i].x)/d,uy=(ps[j].y-ps[i].y)/d;ps[i].x-=ux*push;ps[i].y-=uy*push;ps[j].x+=ux*push;ps[j].y+=uy*push;moved=true}}
    hs.forEach(h=>{let dx=ps[i].x-h.x,dy=ps[i].y-h.y;let d=Math.hypot(dx,dy);if(d<26){if(d<0.01){dx=1;d=1}const push=26-d+.5;ps[i].x+=dx/d*push;ps[i].y+=dy/d*push;moved=true}})}
  if(!moved)break}
ms.forEach((m,i)=>m.setLatLng(map.containerPointToLatLng(ps[i])));
document.getElementById('lg').innerHTML='<span style="font-size:14px">★</span> 숙소'+D.days.map(d=>`<i style="background:${d.color}"></i>${d.label}`).join('');
let pending=0;tiles.on('tileloadstart',()=>pending++);tiles.on('tileload',()=>pending--);tiles.on('tileerror',()=>pending--);
window.mapReady=()=>pending<=0;
</script></body></html>"""


def render(data: dict, w: int, h: int, scale: int = 2) -> bytes:
    from playwright.sync_api import sync_playwright
    html = PAGE % {"css": LEAFLET_CSS, "js": LEAFLET_JS, "tiles": TILES, "w": w, "h": h,
                   "data": json.dumps(points(data), ensure_ascii=False)}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale,
                        user_agent="trip-planner-skill/0.1 (personal travel sheet; contact via github)")
        pg.set_content(html, wait_until="networkidle")
        try:
            pg.wait_for_function("window.mapReady && window.mapReady()", timeout=20000)
        except Exception:  # noqa: BLE001  지도 조각이 늦어도 찍는다(빈 칸이 생길 수 있음)
            pass
        pg.wait_for_timeout(1200)
        png = pg.locator("#m").screenshot()
        b.close()
    return png
