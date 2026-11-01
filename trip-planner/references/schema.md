# 여행 데이터 파일 칸

YAML(또는 같은 모양의 JSON). 본보기: `examples/tokyo-family.yaml`. 시각은 따옴표로 `"09:30"` (따옴표가 없으면 YAML 이 숫자로 읽을 수 있다).

## trip
| 칸 | 뜻 |
|---|---|
| title, destination | 제목, 어디 |
| start, end | 시작일, 끝나는 날 (YYYY-MM-DD) |
| currency | 예산 통화 (예: JPY) |
| checked | 이 파일의 사실을 마지막으로 확인한 날 |
| audits | (선택) 다른 사람이 원문과 대조한 기록 목록. 시트 요약에만 나온다(고객 그림·웹앱에는 싣지 않음). 형식 검사(J 검사)와는 다른 것 |
| stale_days | 장소 확인일이 여행 시작보다 이만큼 넘게 오래되면 경고 (기본 30) |

## travelers (목록)
`label`(어른 1, 아이 1), `age`, `notes`(못 먹는 것, 거동). 이름은 적지 않는다.

## holidays (목록)
`date`, `name`. 그 나라 공휴일. 휴무와 `holiday_shift` 계산에 쓴다.

## arrival, departure (하나씩)
`date`, `time`, `place`(장소 id), `note`. departure 에는 `arrive_by`(공항에 몇 시까지), `buffer_min`(공항 여유 최소, 기본 30).

## places (id: 장소)
| 칸 | 뜻 |
|---|---|
| name, local | 한국어 이름, 현지어 이름 |
| kind | 숙소, 공항, 교통, 관광, 식사, 쇼핑 |
| lat, lon | 좌표 |
| hours | `["10:00", "20:00"]` 여는 시각, 닫는 시각 |
| open_air | 늘 열린 곳(공원, 시장 거리). 영업시간 경고를 안 낸다 |
| closed | 휴무 요일 목록 `[월, 화]` |
| holiday_shift | true 면 휴무 요일이 공휴일일 때 열고 다음 날 쉰다 |
| closed_holidays | true 면 공휴일에 쉰다 |
| min_age | 이 나이 미만 입장 불가 |
| reservation | `{timed: true, status: 완료, slot: "10:30"}` 시간 지정 입장권, `{required: true, status: 미완료}` 예약 필요 |
| address_local, phone | 숙소면 택시용 현지어 주소와 전화 |
| map | false 면 지도와 인포그래픽에서 뺀다(다른 안으로만 남긴 곳) |
| icon | 아이콘 종류(사람 말): 숙소, 역, 지하철, 기차, 코인로커, 식당, 쇼핑, 시장, 공원, 동물원, 절, 신사, 전망대, 탑, 온천, 공연, 스튜디오, 테마파크. 없으면 kind 로 고른다. 지도 KML 은 구글 내 지도 아이콘 번호로, 인포그래픽은 같은 종류의 그림으로 나온다 |
| base | true 면 지도의 "숙소·기준역" 층에 넣는다(숙소 근처 기준역 등) |
| checked, source | 확인한 날짜, 출처 주소(운영 기관 공식 페이지 우선) |
| coord_note | (선택) 좌표를 무엇과 대조했는지(예: 위키데이터 Q… 와 58m). 못 했으면 "근사 좌표, 가기 전 확인" |
| note | 메모 |

## days (목록)
`date`, `title`, `items`(목록):

| 칸 | 뜻 |
|---|---|
| time | 그 장소에 있는 시각 |
| stay | 머무는 분 |
| place | 장소 id |
| what, note, alt | 할 일, 주의, 다른 안(비, 휴무, 지연) |
| go | 앞 항목에서 오는 길 `{mode: 전철, minutes: 30}`. 여러 안은 `minutes: [60, 75, 90]`, 추정이면 `estimated: true`, 앞 일정 끝이 아니라 정한 시각에 떠나면 `depart: "12:30"` |

번호는 그날 지도에 찍히는 곳(숙소와 map: false 는 빼고)에 1부터 자동으로 붙는다.

## picks (목록, 선택) — 추천 칸

일정에 넣지 않은 보너스 정보. 인포그래픽에 "추천 맛집 / 요즘 뜨는 곳" 칸으로 나온다(각 3곳까지).

| 칸 | 뜻 |
|---|---|
| type | `맛집` 또는 `요즘` |
| name, area, why | 이름, 동네, 추천 이유 한 줄 |
| hours | 영업시간·휴무 한 줄(선택) |
| source | **우리가 직접 열어 맞는지 본 주소만.** 없으면 검사 오류 |
| checked | 그 확인 날짜. 없으면 오류, 여행 시작보다 60일 넘게 오래되면 경고 |

다른 AI(예: 제미나이)에게 후보를 뽑게 해도 된다. 다만 그쪽이 단 출처를 그대로 쓰면 안 된다. 2026-10-09 시험에서 출처 주소가 엉뚱한 페이지인 경우가 많았다.

## checklist, budget, tips, emergency
- checklist: `{when: D-30 | D-14 | D-7 | D-3 | D-1 | 당일, item, done}`
- budget: `{category, item, amount, paid}`
- tips: `{title, body, source}` 판단 근거를 숫자로 (예: 캐리어 크기와 그 이유)
- emergency: `hotel`(장소 id), `police`, `ambulance`, `embassy: {name, phone, address_local}`, `consular_call`
