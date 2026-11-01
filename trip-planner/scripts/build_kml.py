# -*- coding: utf-8 -*-
"""지도 KML 만들기 (구글 내 지도 > 가져오기).

날짜마다 층 하나, 날짜마다 서로 다른 색, 장소 이름 앞 순서 번호, 날짜별 동선 선.
메모에는 시각, 할 일, 확인한 날짜를 넣는다. 숙소는 회색 '기준' 층에 따로.

쓰는 법: python build_kml.py <여행.yaml> <나갈 파일.kml>
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trip_model as tm  # noqa: E402


def kml_color(hex_rgb: str, alpha: str = "ff") -> str:
    """#RRGGBB → KML aabbggrr"""
    h = hex_rgb.lstrip("#")
    return f"{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".lower()


MYMAPS_HREF = "https://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png"


class Styles:
    """구글 내 지도가 내보내는 모양 그대로 스타일을 만든다. 점: "icon-<아이콘 번호>-<색>", 선: "line-<색>-4000".
    내 지도로 가져오면 스타일 이름을 읽어 그 아이콘과 색으로 보여 준다(다른 지도 앱은 색 점으로 보인다)."""

    def __init__(self):
        self.done: dict[str, str] = {}

    def icon(self, code: int, color: str) -> str:
        sid = f"icon-{code}-{color.lstrip('#').upper()}"
        if sid not in self.done:
            c = kml_color(color)
            parts = []
            for kind, scale, label in (("normal", 1, 0), ("highlight", 1, 1)):
                parts.append(f'<Style id="{sid}-{kind}"><IconStyle><color>{c}</color><scale>{scale}</scale>'
                             f'<Icon><href>{MYMAPS_HREF}</href></Icon></IconStyle><LabelStyle><scale>{label}</scale></LabelStyle></Style>')
            parts.append(f'<StyleMap id="{sid}"><Pair><key>normal</key><styleUrl>#{sid}-normal</styleUrl></Pair>'
                         f'<Pair><key>highlight</key><styleUrl>#{sid}-highlight</styleUrl></Pair></StyleMap>')
            self.done[sid] = "".join(parts)
        return sid

    def line(self, color: str) -> str:
        sid = f"line-{color.lstrip('#').upper()}-4000"
        if sid not in self.done:
            self.done[sid] = f'<Style id="{sid}"><LineStyle><color>{kml_color(color)}</color><width>4</width></LineStyle></Style>'
        return sid


def _desc(lines: list[str]) -> str:
    return "<![CDATA[" + "<br>".join(escape(x) for x in lines if x) + "]]>"


def build(data: dict) -> str:
    trip = data.get("trip") or {}
    st = Styles()
    out = []
    days = tm.days(data)

    # 기준 층: 숙소
    # 기준 층: 숙소와 기준역(base: true). 이름은 샘플 지도와 같게 "숙소·기준역"
    base = [(pid, p) for pid, p in tm.places(data).items()
            if (p.get("kind") == "숙소" or p.get("base")) and p.get("lat") is not None]
    if base:
        out.append("<Folder><name>숙소·기준역</name>")
        for pid, p in base:
            desc = _desc([p.get("address_local"), p.get("phone"), f"확인 {p.get('checked')}", tm.maps_search(p)])
            out.append(f"<Placemark><name>{escape(p.get('name', pid))}</name><styleUrl>#{st.icon(tm.place_icon(p), tm.BASE_COLOR)}</styleUrl>"
                       f"<description>{desc}</description>"
                       f"<Point><coordinates>{p['lon']},{p['lat']},0</coordinates></Point></Placemark>")
        out.append("</Folder>")

    for d in days:
        # 층 이름: "10/10 토 · 아키하바라" (날짜, 요일, 지역) — 샘플 지도 모양
        out.append(f"<Folder><name>{escape(d['label'])} · {escape(str(d.get('title', '')))}</name>")
        line = []
        for it in d["items"]:
            p = it["place_data"]
            if p.get("lat") is None:
                continue
            if p.get("map", True) is not False:
                line.append(f"{p['lon']},{p['lat']},0")
            if it["no"] is None:
                continue
            hours = p.get("hours")
            lines = [f"{it.get('time')}~{tm.fmt_min(it['end'])}  {it.get('what', '')}",
                     it.get("note"), f"다른 안: {it['alt']}" if it.get("alt") else "",
                     f"영업 {hours[0]}~{hours[1]}" if hours else "",
                     f"휴무 {','.join(p['closed'])}요일" if p.get("closed") else "",
                     f"확인 {p.get('checked')}", tm.maps_link(p)]
            out.append(f"<Placemark><name>{it['no']}. {escape(p.get('name', it.get('place')))}</name>"
                       f"<styleUrl>#{st.icon(tm.place_icon(p), d['color'])}</styleUrl><description>{_desc(lines)}</description>"
                       f"<Point><coordinates>{p['lon']},{p['lat']},0</coordinates></Point></Placemark>")
        if len(line) >= 2:
            out.append(f"<Placemark><name>{escape(d['label'])} 동선</name><styleUrl>#{st.line(d['color'])}</styleUrl>"
                       f"<LineString><tessellate>1</tessellate><coordinates>{' '.join(line)}</coordinates></LineString></Placemark>")
        out.append("</Folder>")
    head = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
            f"<name>{escape(str(trip.get('title', '여행')))}</name>"] + list(st.done.values())
    return "\n".join(head + out + ["</Document></kml>"])


def build_layers(data: dict) -> dict[str, str]:
    """층마다 KML 한 파일씩. 구글 내 지도는 가져오기 한 번에 층 하나만 만들 때가 있어서(7번 지도 키트 실측 10/9),
    "숙소·기준역" 과 날짜별 층을 따로 가져올 수 있게 한다. {파일 이름: KML}"""
    import re
    import xml.etree.ElementTree as ET
    full = build(data)
    ns = "http://www.opengis.net/kml/2.2"
    ET.register_namespace("", ns)
    root = ET.fromstring(full.encode("utf-8"))
    doc = root.find(f"{{{ns}}}Document")
    styles = [ET.tostring(e, encoding="unicode") for e in doc if e.tag in (f"{{{ns}}}Style", f"{{{ns}}}StyleMap")]
    out = {}
    for i, folder in enumerate(doc.findall(f"{{{ns}}}Folder")):
        name = folder.find(f"{{{ns}}}name").text or f"layer{i}"
        body = "".join(ET.tostring(p, encoding="unicode") for p in folder.findall(f"{{{ns}}}Placemark"))
        kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
               f"<name>{escape(name)}</name>" + "".join(styles) + body + "</Document></kml>\n")
        safe = re.sub(r"[\\/:*?\"<>|·]+", "", name).replace(" ", "_").strip("_")
        out[f"{i:02d}_{safe}.kml"] = kml
    return out


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    Path(argv[2]).write_text(build(tm.load(argv[1])), encoding="utf-8")
    print(f"지도 KML → {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
