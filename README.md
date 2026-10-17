# 파워J 여행 일정 — 일정 파일 하나로 한 장 그림·인스타 넘김·폰 웹앱·지도·시트

![제주 부모님 2박 3일 샘플 — 한 장 그림](docs/jeju-poster.png)

| 인스타 넘김(1080×1350) | | 다른 샘플 |
|---|---|---|
| ![넘김 1](docs/jeju-carousel-1.png) | ![넘김 2](docs/jeju-carousel-2.png) | ![부산](docs/busan-poster.png) |

넘김 그림 속 사진 출처는 [docs/CREDITS.md](docs/CREDITS.md)에 있습니다.

여행 계획은 같은 사실이 여러 곳에 적히면서 틀어집니다. 포스터에는 09:00 도착인데 지도에는 귀국이 두 번 있는 식입니다. 그래서 이 도구는 **모든 사실을 여행 파일(YAML) 하나에 한 번만** 적습니다. 결과물은 전부 그 파일 하나에서 만들어집니다.

- **한 장 그림**: 날짜별 사진·시간표·지도 (가로 PNG)
- **인스타 넘김**: 표지+지도, 날짜마다 한 장, 먹을 것 (1080×1350 PNG)
- **폰 웹앱**: 인터넷 없이 열리는 HTML 한 파일
- **구글 내 지도용 KML**과 **구글 시트용 xlsx**

만들기 전에 **J 검사기**가 먼저 틀린 곳을 잡습니다. 잡는 것은 이렇습니다.

- 영업시간 전 도착, 휴무일 방문, 공휴일 다음 날 휴무
- 나이 제한, 예약 안 한 시간 지정 입장권
- 이동 여유 부족, 같은 사실이 다르게 적힌 곳

## 설치 (처음 한 번, 몇 분)

1. 이 저장소를 받습니다.
2. `trip-planner` 폴더를 Claude Code 스킬 폴더에 복사합니다. 맥·리눅스는 `~/.claude/skills/`, 윈도우는 `C:\Users\<내 이름>\.claude\skills\` 입니다.
3. 파이썬 3.10 이상에서 아래를 한 번 돌립니다. 마지막 줄은 그림을 굽는 브라우저를 받아서 몇백 MB, 몇 분 걸립니다.

```bash
pip install pyyaml openpyxl playwright
playwright install chromium
```

설치가 끝나면 Claude Code 에서 **"부모님이랑 제주 2박 3일 일정 짜줘"** 처럼 말하면 됩니다. 스킬이 모자란 것만 묻고, 여행 파일을 쓰고, 검사한 뒤 결과물을 만듭니다.

## 직접 돌려 보기 (샘플)

윈도우에서 한글이 깨지면 먼저 `set PYTHONIOENCODING=utf-8`(Git Bash 는 `export PYTHONIOENCODING=utf-8`)를 한 줄 넣으세요.

```bash
cd trip-planner
python scripts/check_trip.py examples/parents-jeju.yaml        # J 검사기
python scripts/build_poster.py examples/parents-jeju.yaml out poster
python scripts/build_carousel.py examples/parents-jeju.yaml out
python scripts/build_all.py examples/parents-jeju.yaml out      # 웹앱·지도·시트
```

샘플에는 사진 파일이 들어 있지 않아서, 처음 돌리면 **사진 칸이 빈 그림**이 나옵니다. 정상입니다. 사진은 따로 받습니다.

- **해외**: `fetch_photos.py` 가 위키미디어 공용에서 자유 라이선스 사진만 고릅니다(CC BY·CC BY-SA·CC0·퍼블릭 도메인).
- **국내**: `fetch_kto.py` 가 한국관광공사 관광사진 API(공공누리 제1유형)에서 받습니다. 공공데이터포털에서 받은 키를 환경변수 `DATA_GO_KR_KEY` 에 넣으면 됩니다.

검색 결과가 엉뚱한 장소일 때가 있으니, **받은 사진은 꼭 눈으로 확인하세요.** 사진 작가와 라이선스는 한 장 그림 아래에 자동으로 적힙니다. 넘김은 자리가 좁아 출처를 게시글 본문(캡션)에 따로 적어야 합니다.

## 샘플에 대해

`examples/` 의 여행 넷(제주·부산·오사카·도쿄)은 **지어낸 여행자**와 예시 숙소로 만든 것입니다. 장소·영업시간·요금은 2026-10 공개 자료와 대조했지만 바뀔 수 있으니 **가기 전에 다시 확인하세요.**

## 쓴 것과 표기

- **지도**: © OpenStreetMap contributors, [Leaflet](https://leafletjs.com)(BSD-2)
- **글꼴**: Google Fonts의 Jua·Gaegu, 웹앱의 IBM Plex Sans KR·Mono (모두 SIL OFL)
- **지도 조각**: tile.openstreetmap.org 는 가벼운 개인 사용만 허용합니다. 많이 쓰려면 다른 지도 조각 서비스로 바꾸세요.
- **관광공사 사진**: 공공누리 제1유형(출처 표시). 그림 아래에 "한국관광공사(공공누리 1유형) — 사진가"로 자동으로 적힙니다.
- **샘플 그림 속 사진**: Wikimedia Commons 의 각 작가. 온전한 작가·라이선스·원본 주소는 [docs/CREDITS.md](docs/CREDITS.md)에 있습니다.
- 결과물의 영업시간·가격은 "확인일" 기준입니다.

## 라이선스

**코드만 MIT** 입니다([LICENSE](LICENSE)). 사진은 [docs/CREDITS.md](docs/CREDITS.md)에 적힌 각 사진의 라이선스를 따릅니다.
