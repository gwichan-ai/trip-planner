# -*- coding: utf-8 -*-
"""한 번에: 검사 → 결과물 4개.

쓰는 법: python build_all.py <여행.yaml> <나갈 폴더> [--force]
검사에 오류가 있으면 만들지 않고 멈춘다(종료코드 1). 고친 뒤 다시 돌린다.
--force 를 주면 오류가 있어도 만든다(시트 '검사 결과' 탭과 웹앱 '처음' 탭에 오류가 그대로 보인다).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_infographic  # noqa: E402
import build_kml  # noqa: E402
import build_webapp  # noqa: E402
import build_xlsx  # noqa: E402
import check_trip  # noqa: E402
import trip_model as tm  # noqa: E402


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    data = tm.load(args[0])
    out = Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    findings = check_trip.check(data)
    for f in findings:
        print(f"[{f['level']}] {f['rule']:<13} {f['where']}: {f['msg']}")
    print("검사:", check_trip.summary(findings))
    if any(f["level"] == check_trip.ERROR for f in findings) and "--force" not in argv:
        print("오류가 있어 만들지 않았다. 데이터 파일을 고친 뒤 다시 돌린다(그래도 만들려면 --force).")
        return 1
    stem = Path(args[0]).stem
    (out / f"{stem}.kml").write_text(build_kml.build(data), encoding="utf-8")
    # 층별 KML: 내 지도가 파일 하나를 층 하나로만 가져올 때 쓰는 것 (숙소·기준역, 날짜별)
    layers_dir = out / f"{stem}-layers"
    layers_dir.mkdir(exist_ok=True)
    for name, kml in build_kml.build_layers(data).items():
        (layers_dir / name).write_text(kml, encoding="utf-8")
    build_xlsx.build(data, findings).save(out / f"{stem}.xlsx")
    (out / f"{stem}.html").write_text(build_webapp.build(data, findings), encoding="utf-8")
    # 아티팩트로 올릴 본문 (claude.ai Artifact 도구가 있으면 이 파일을 올린다. SKILL.md 5단계)
    (out / f"{stem}.artifact.html").write_text(build_webapp.build(data, findings, mode="artifact"), encoding="utf-8")
    pngs = build_infographic.render(data, out, "--html-only" in argv)
    print(f"만듦: {out / (stem + '.kml')}, {out / (stem + '.xlsx')}, {out / (stem + '.html')}, " + ", ".join(str(p) for p in pngs if p.suffix == ".png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
