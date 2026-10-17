# -*- coding: utf-8 -*-
"""시트 xlsx 만들기. 드라이브에 올리면 구글 시트로 열린다.

탭: 요약, 일정, 장소, 준비물, 예약, 교통, 예산, 비상, 대안, 검사 결과

쓰는 법: python build_xlsx.py <여행.yaml> <나갈 파일.xlsx>
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_trip  # noqa: E402
import trip_model as tm  # noqa: E402

HEAD_FILL = PatternFill("solid", fgColor="1F2937")
HEAD_FONT = Font(bold=True, color="FFFFFF")
WRAP = Alignment(wrap_text=True, vertical="top")


def _sheet(wb, title, header, rows, widths=None, fills=None):
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.fill, c.font, c.alignment = HEAD_FILL, HEAD_FONT, Alignment(vertical="center")
    for i, r in enumerate(rows):
        ws.append(["" if v is None else v for v in r])
        if fills and fills[i]:
            for c in ws[ws.max_row]:
                c.fill = PatternFill("solid", fgColor=fills[i])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
    for i, w in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    return ws


def _light(hex_rgb: str) -> str:
    """날짜 색을 옅게 (시트 줄 바탕)"""
    h = hex_rgb.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "".join(f"{int(v + (255 - v) * 0.8):02X}" for v in (r, g, b))


def build(data: dict, findings: list[dict] | None = None) -> Workbook:
    if findings is None:
        findings = check_trip.check(data)
    trip = data.get("trip") or {}
    places = tm.places(data)
    days = tm.days(data)
    arr, dep = tm.single(data, "arrival"), tm.single(data, "departure")
    wb = Workbook()
    wb.remove(wb.active)

    who = ", ".join(f"{t.get('label')}({t.get('age')}세{', ' + t['notes'] if t.get('notes') else ''})" for t in tm.travelers(data))
    hol = ", ".join(f"{tm.day_label(d)} {n}" for d, n in tm.holidays(data).items())
    rows = [["여행", trip.get("title")], ["어디", trip.get("destination")],
            ["기간", f"{trip.get('start')} ~ {trip.get('end')}"], ["누구", who],
            ["도착", f"{arr.get('date')} {arr.get('time')} {places.get(arr.get('place'), {}).get('name', '')}"],
            [tm.return_words(data)[0], f"{dep.get('date')} {dep.get('time')} 출발, {tm.return_words(data)[1]}에 {dep.get('arrive_by')}까지 도착 ({places.get(dep.get('place'), {}).get('name', '')})"],
            ["공휴일", hol], ["사실 확인일", trip.get("checked")], ["독립 대조", "; ".join(str(a) for a in (trip.get("audits") or [])) or "없음"], ["J 검사(형식)", check_trip.summary(findings)]]
    rows += [[f"{d['label']}", d.get("title")] for d in days]
    _sheet(wb, "요약", ["항목", "내용"], rows, [14, 80])

    rows, fills = [], []
    for d in days:
        for it in d["items"]:
            p = it["place_data"]
            go = it.get("go") or {}
            mins = tm.go_minutes(go)
            move = f"{go.get('mode', '')} {'/'.join(map(str, mins))}분{' (추정)' if go.get('estimated') else ''}" if mins else ""
            rows.append([d["label"], it.get("time"), tm.fmt_min(it["end"]), it["no"] or "", p.get("name", it.get("place")),
                         it.get("what"), move, it.get("note"), tm.maps_link(p)])
            fills.append(_light(d["color"]))
    _sheet(wb, "일정", ["날짜", "시작", "끝", "번호", "장소", "할 일", "오는 길", "주의", "길찾기"], rows,
           [10, 7, 7, 6, 24, 30, 22, 36, 30], fills)

    rows = []
    for pid, p in places.items():
        hours = p.get("hours")
        r = p.get("reservation") or {}
        rows.append([p.get("name", pid), p.get("local"), p.get("kind"), f"{hours[0]}~{hours[1]}" if hours else ("늘 열림" if p.get("open_air") else ""),
                     ",".join(p.get("closed") or []) + (" (공휴일이면 다음 날)" if p.get("holiday_shift") else ""),
                     p.get("min_age") or "", r.get("status", ""), p.get("checked"), p.get("source") or tm.maps_search(p), p.get("note")])
    _sheet(wb, "장소", ["이름", "현지어", "종류", "영업", "휴무 요일", "나이 제한", "예약", "확인일", "출처", "메모"], rows,
           [24, 24, 8, 12, 18, 9, 9, 11, 30, 30])

    order = {"D-30": 0, "D-14": 1, "D-7": 2, "D-3": 3, "D-1": 4, "당일": 5}
    cl = sorted(data.get("checklist") or [], key=lambda c: order.get(c.get("when"), 9))
    _sheet(wb, "준비물", ["언제", "할 일", "끝"], [[c.get("when"), c.get("item"), "✔" if c.get("done") else ""] for c in cl], [8, 50, 6])

    rows = []
    for pid, p in places.items():
        r = p.get("reservation")
        if r:
            kind = "시간 지정" if r.get("timed") else ("필요" if r.get("required") else "권장")
            rows.append([p.get("name", pid), kind, r.get("slot", ""), r.get("status", ""), r.get("note", "")])
    _sheet(wb, "예약", ["장소", "종류", "시각", "상태", "메모"], rows, [26, 10, 8, 8, 40])

    rows = []
    for d in days:
        prev = None
        for it in d["items"]:
            go = it.get("go")
            if go and prev:
                mins = tm.go_minutes(go)
                rows.append([d["label"], prev["place_data"].get("name"), it["place_data"].get("name"), go.get("mode"),
                             go.get("depart") or tm.fmt_min(prev["end"]), "/".join(map(str, mins)),
                             "추정" if go.get("estimated") else ""])
            prev = it
    _sheet(wb, "교통", ["날짜", "출발", "도착", "수단", "떠나는 시각", "걸리는 분", "비고"], rows, [10, 24, 24, 16, 10, 10, 8])

    b = data.get("budget") or []
    rows = [[x.get("category"), x.get("item"), x.get("amount"), trip.get("currency", ""), "✔" if x.get("paid") else ""] for x in b]
    ws = _sheet(wb, "예산", ["분류", "항목", "금액", "통화", "결제"], rows, [10, 30, 12, 6, 6])
    if rows:
        ws.append(["합계", "", f"=SUM(C2:C{len(rows) + 1})", trip.get("currency", ""), ""])
        ws[f"A{ws.max_row}"].font = Font(bold=True)

    e = data.get("emergency") or {}
    h = places.get(e.get("hotel"), {})
    emb = e.get("embassy") or {}
    rows = [["숙소", h.get("name")], ["숙소 주소(현지어)", h.get("address_local")], ["숙소 전화", h.get("phone")],
            ["경찰", e.get("police")], ["구급", e.get("ambulance")], ["대사관", emb.get("name")],
            ["대사관 전화", emb.get("phone")], ["대사관 주소", emb.get("address_local")], ["영사콜센터", e.get("consular_call")]]
    _sheet(wb, "비상", ["항목", "내용"], rows, [18, 60])

    rows = [[d["label"], it.get("time"), it["place_data"].get("name"), it.get("alt")] for d in days for it in d["items"] if it.get("alt")]
    _sheet(wb, "대안", ["날짜", "시각", "장소", "다른 안 (비, 휴무, 지연)"], rows, [10, 7, 24, 60])

    rows = [[f["level"], f["rule"], f["where"], f["msg"]] for f in findings] or [["", "", "", "오류와 경고 없음"]]
    fills = ["FECACA" if f["level"] == check_trip.ERROR else "FEF3C7" for f in findings] or [None]
    _sheet(wb, "검사 결과", ["수준", "규칙", "어디", "내용"], rows, [8, 14, 34, 70], fills)
    return wb


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    build(tm.load(argv[1])).save(argv[2])
    print(f"시트 xlsx → {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
