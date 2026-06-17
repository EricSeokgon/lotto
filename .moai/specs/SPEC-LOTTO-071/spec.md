---
id: SPEC-LOTTO-071
version: 1.0.0
status: completed
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-071: 번호 중앙값(median) 분포 분석

## HISTORY

- 2026-06-12 (v1.0.0): 구현 완료. 38개 테스트 추가 (1664→1702). commit 6938a2a
- 2026-06-12 (v0.1.0): 최초 작성 (Planned). 회차별 본번호 6개(보너스 제외)의
  **중앙값(median)** 을 정렬된 6개 번호 `[a,b,c,d,e,f]` 의 가운데 두 값 평균
  `(c+d)/2` 로 정의하고, 전체 이력에 대해 9개 구간(`"1-5"`~`"41-45"`)의 분포를
  산출하는 읽기 전용 통계 기능으로 정의. SPEC-065(표준편차)·070(AC값)의
  `data.py` 확장 패턴을 그대로 따른다.

## 개요

각 회차의 당첨번호 6개(보너스 제외)를 오름차순 정렬한 `[a,b,c,d,e,f]` 에서
**중앙값(median)** 을 `(c+d)/2` 로 계산한 뒤, 전체 이력에 대해 중앙값이 어느
구간에 속하는지의 분포를 분석한다. 중앙값은 한 회차 번호 조합의 "중심 위치"를
나타내는 지표로, 번호가 저번호대에 치우쳤는지 고번호대에 치우쳤는지를 한 값으로
요약한다.

### 중앙값(median) 정의와 예시

짝수 개(6개)의 정렬된 데이터에서 중앙값은 가운데 두 값 `c`(3번째), `d`(4번째)의
평균이다. 6개 번호는 모두 정수이므로 `c+d` 는 정수이고, 중앙값은 항상 `X.0`
(c+d 짝수) 또는 `X.5`(c+d 홀수)의 값이 된다. 본 SPEC은 `(c+d)/2.0` 의 부동소수
결과를 그대로 사용하며, 평균·표시는 소수 1~2자리로 반올림한다.

- 최솟값: `(1+2)/2 = 1.5` (3·4번째가 가능한 가장 작은 경우)
- 최댓값: `(44+45)/2 = 44.5` (3·4번째가 가능한 가장 큰 경우)
- 일반적으로 대부분의 중앙값은 **15~35 구간**에 분포한다.

예시: 번호 `[1, 2, 3, 4, 5, 6]` (정렬됨)
- c = 3 (3번째), d = 4 (4번째)
- median = `(3 + 4) / 2 = 3.5` → 구간 `"1-5"`

예시: 번호 `[10, 20, 30, 40, 42, 45]` (정렬됨)
- c = 30, d = 40 → median = `35.0` → 구간 `"31-35"`

### 분포 구간 (9개 버킷, 1.5~44.5 전 구간)

[HARD] 분포 키는 아래 **9개로 고정**한다. 경계값은 모두 `.5` 단위이며 중앙값은
항상 `X.0`/`X.5` 이므로 경계에서의 모호성이 없다. 경계값은 **상위 구간에 포함**
(`>=` 하한, `<` 상한)한다.

| 구간 key | 판정 조건 | 비고 |
|----------|-----------|------|
| `"1-5"`   | `median < 5.5`              | 최솟값 1.5 포함 |
| `"6-10"`  | `5.5 <= median < 10.5`      | |
| `"11-15"` | `10.5 <= median < 15.5`     | |
| `"16-20"` | `15.5 <= median < 20.5`     | |
| `"21-25"` | `20.5 <= median < 25.5`     | 중심(23.0) 포함 구간 |
| `"26-30"` | `25.5 <= median < 30.5`     | |
| `"31-35"` | `30.5 <= median < 35.5`     | |
| `"36-40"` | `35.5 <= median < 40.5`     | |
| `"41-45"` | `median >= 40.5`            | 최댓값 44.5 포함 |

[HARD] 버킷 개수 결정 근거: 요청 명세 본문은 "10 buckets"를 언급하지만 실제로
열거된 구간은 9개이며, 이 9개 구간이 가능한 전 범위(1.5~44.5)를 빠짐없이 덮는다
(`"1-5"` 의 하한 무한대~5.5, `"41-45"` 의 40.5~상한 무한대). 따라서 본 SPEC은
**열거된 9개 구간을 정본**으로 채택한다. AC값(SPEC-070)과 달리 오버플로 버킷이
필요 없다 — 모든 가능한 중앙값이 9개 구간 안에 들어간다 (Agent "Manage Confusion
Actively": 명세 내 수치 불일치를 명시적으로 해소).

### low_median_pct (중심 미만 비율)

`low_median_pct` 는 중앙값이 **23.0 미만**(`median < 23.0`)인 회차의 비율(%)이다.
23.0은 로또 번호 범위 1~45의 산술 중심(`(1+45)/2 = 23`)으로, 번호 조합이 중심보다
낮은 쪽에 치우친 정도를 측정한다. 경계값 `median == 23.0` 은 "낮음"에서 **제외**
한다(strict `<`).

### 응답 구조

```python
{
    "total_draws": int,
    "avg_median": float,        # 전체 회차 중앙값 평균, 2자리 반올림
    "most_common_range": str,   # 가장 자주 등장한 구간 key (예: "21-25")
    "low_median_pct": float,    # median < 23.0 회차 비율(%), 2자리 반올림
    "median_distribution": {
        "1-5":   {"count": int, "pct": float},
        "6-10":  {"count": int, "pct": float},
        "11-15": {"count": int, "pct": float},
        "16-20": {"count": int, "pct": float},
        "21-25": {"count": int, "pct": float},
        "26-30": {"count": int, "pct": float},
        "31-35": {"count": int, "pct": float},
        "36-40": {"count": int, "pct": float},
        "41-45": {"count": int, "pct": float},
    },
}
```

`median_distribution` 은 항상 9개 키를 모두 포함한다(누락 구간은 `count=0`,
`pct=0.0` 으로 zero-fill). 빈 draws → 모든 값 0, 9개 키 존재,
`most_common_range="1-5"`, `avg_median=0.0`, `low_median_pct=0.0`.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·통계 분석 로직을 변경하지 않고
`data.py`의 확장 패턴(SPEC-065·070)을 그대로 따른다. 결과는 메모리에 캐시하며
DB에 영속화하지 않는다.

## 용어 정의

| 용어 | 정의 |
|------|------|
| 중앙값 (median) | 정렬된 6개 본번호 `[a,b,c,d,e,f]` 의 가운데 두 값 평균 `(c+d)/2.0` |
| 구간 (range bucket) | 중앙값이 속하는 9개 고정 키 중 하나 (`"1-5"`~`"41-45"`) |
| 중심 (center) | 번호 범위 1~45의 산술 중심 23.0 |
| low median | 중앙값이 23.0 미만인 상태 (중심보다 낮은 쪽 치우침) |
| 본번호 (main numbers) | `draw.numbers()` 가 반환하는 6개 번호 (보너스 제외) |

## 요구사항 (EARS)

### 기능 요구사항

**REQ-MED-001** [Ubiquitous]
The system SHALL compute, for each historical draw, the median value defined as the
average of the 3rd and 4th smallest of the 6 main numbers (the bonus number
excluded): for sorted numbers `[a,b,c,d,e,f]`, `median = (c + d) / 2.0`.

**REQ-MED-002** [Event-Driven]
WHEN the `/api/stats/median` endpoint is called THEN the system SHALL return a JSON
response containing `total_draws`, `avg_median`, `most_common_range`,
`low_median_pct`, and `median_distribution` — where `median_distribution` is a
nested dict keyed by the 9 string keys `"1-5"`, `"6-10"`, `"11-15"`, `"16-20"`,
`"21-25"`, `"26-30"`, `"31-35"`, `"36-40"`, `"41-45"`, each mapping to `count`
and `pct`.

**REQ-MED-003** [Event-Driven]
WHEN the `/stats/median` page is requested THEN the system SHALL render an HTML page
whose navigation/heading contains the Korean text "중앙값", using the same stats dict.

**REQ-MED-004** [Ubiquitous]
The system SHALL always include all 9 range keys in `median_distribution`
(zero-filled when a range is absent from the data). A draw's median SHALL be assigned
to exactly one bucket using `>=` lower bound and `<` upper bound, where boundary
values fall into the upper bucket.

**REQ-MED-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_median_cache` SHALL be cleared.

**REQ-MED-006** [Ubiquitous]
The system SHALL determine `most_common_range` as the range key with the highest
`count`; on a tie, the range with the smaller lower bound (earlier in the fixed key
order `"1-5"`..`"41-45"`) SHALL win.

**REQ-MED-007** [Ubiquitous]
The system SHALL compute `low_median_pct` as the percentage of draws whose median is
strictly less than 23.0 (`median < 23.0`); the boundary value `median == 23.0` is
excluded from the "low" count.

**REQ-MED-008** [Ubiquitous]
The system SHALL compute `avg_median` as the arithmetic mean of all per-draw medians.

### 비기능 요구사항

**REQ-MED-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 9
keys present (each `count=0`, `pct=0.0`), `most_common_range="1-5"`,
`avg_median=0.0`, and `low_median_pct=0.0` without raising an exception.

**REQ-MED-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in median computation.

**REQ-MED-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, `recommender.py`, or
`simulator.py`. Only `lotto/web/` layer files are extended.

**REQ-MED-NF-004** [Ubiquitous]
Numeric ratio/average fields (`avg_median`, `low_median_pct`, and each bucket `pct`)
SHALL be rounded to 2 decimal places.

**REQ-MED-NF-005** [Ubiquitous]
The implementation SHALL be Python 3.9 compatible (no walrus `:=`,
no `zip(strict=True)`, no `match-case`) and server-rendered only (no client JS).

## 인수 기준

상세 인수 기준은 [acceptance.md](acceptance.md) 참조 (AC-071-001 ~ AC-071-022).

## Exclusions (What NOT to Build)

- 추천 엔진 연동 (중앙값 기반 가중치·필터 추가 금지)
- 중심 임계값(23.0)의 사용자 정의 (커스텀 임계값 설정 UI 금지)
- 중앙값 예측 모델·시계열 추세 분석
- DB 영속화 (메모리 캐시만 사용)
- 윈도(recent_n) 기반 부분 집계
- 보너스 번호를 포함한 7개 조합의 중앙값 계산
- 평균(mean)·최빈값(mode) 등 다른 중심 경향성 지표 — 별도 SPEC 대상
- 중앙값 외 사분위수(Q1/Q3)·IQR 등 분위 통계 — 별도 SPEC 대상

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-065, SPEC-070 패턴이 `data.py`에 존재함
- 중앙값 산출에 `draw.numbers()` (6개 메인 번호) 사용
- 신규 심볼(`get_median_stats`, `_median_cache`, `/api/stats/median`,
  `/stats/median`, `median.html`)은 모두 비중복으로 검증됨 (기존
  `get_median_stats` 부재 확인 완료)
