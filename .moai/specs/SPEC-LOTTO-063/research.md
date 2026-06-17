---
id: SPEC-LOTTO-063
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-063 연구 노트 (Last Digit Sum Analysis)

## 코드베이스 분석 (기존 패턴 확인)

"통계 분석(stats)" 계열은 일관된 패턴을 따른다. 가장 가까운 선행 사례는
SPEC-LOTTO-060(홀짝)·SPEC-LOTTO-061(고저)·SPEC-LOTTO-062(연속 패턴)이다.
본 SPEC도 동일하게 `get_<topic>_stats` 함수 + str-키 캐시 + 3계층 라우트
(`/api/stats/...`, `/stats/...`, 템플릿)를 적용한다.

### 선행 기능 충돌 점검 — SPEC-LOTTO-055 (중요)

코드베이스에는 이미 SPEC-LOTTO-055에서 구현한 "끝자리 분포" 분석이 존재하며
라우트 `/stats/last-digit`, 네비 "끝자리 분포"를 사용한다. 신규 함수/라우트/
템플릿/테스트 명이 충돌하지 않음을 grep으로 확인했다.

기존(SPEC-055, 수정 금지):

- 라우트 `/stats/last-digit`, active_tab `last_digit`
- 네비 "끝자리 분포" → `/stats/last-digit` (base.html desktop_nav_items 및
  nav_items 양쪽에 존재)

신규(SPEC-063, 본 SPEC):

- `get_last_digit_sum_stats(draws)` — 신규, 회차별 끝자리 합계(0~54) 통계
- 라우트 `/stats/last-digit-sum` (api.py, pages.py)
- 템플릿 `last_digit_sum.html`
- 네비 "끝합 분석" → `/stats/last-digit-sum`
- 테스트 `tests/test_last_digit_sum_analysis.py`

→ 함수명·라우트·템플릿·네비 라벨·테스트 파일명이 모두 다르므로 충돌 없이
공존한다. 두 기능은 서로 다른 질문에 답한다: SPEC-055는 "어떤 끝자리(0~9)가
자주 나오는가", SPEC-063은 "회차당 끝자리 총합이 얼마이고 저/중/고 구간 분포가
어떠한가". 본 SPEC은 SPEC-055 코드를 일절 건드리지 않는다(REQ-LDS-014).

### SPEC-049(합계 분석)와의 구분

SPEC-049는 본번호 자체의 합(예: 3+11+18+25+33+40 = 130)을 다루고, 본 SPEC은
끝자리의 합(3+1+8+5+3+0 = 20)을 다룬다. 서로 다른 지표이며 병합/혼동하지 않는다.

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은
  `get_last_digit_sum_stats(draws)`
  - 참고: `get_odd_even_stats`(line 3857), `get_high_low_stats`(line 4019)
- 모듈 레벨 캐시 (data.py 확인):
  - `_odd_even_cache`(line 113), `_high_low_cache`(line 118) — 모두
    `dict[str, Any] = {}` str-키 캐시. 신규
    `_last_digit_sum_cache: dict[str, Any] = {}`도 동일 형태이며
    `str(len(draws))`를 키로 사용 (REQ-LDS-016). `_high_low_cache`(line 118)
    다음 줄에 추가하는 것이 가장 자연스럽다.
- `invalidate_cache()` (data.py:126~)에서 모든 캐시 무효화:
  - line 153 `_odd_even_cache.clear()`, line 154 `_high_low_cache.clear()`가
    순차 등록되어 있다. 신규 `_last_digit_sum_cache.clear()` 라인을 line 154
    다음에 추가한다.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로
    invalidate_cache() 상단 global 선언 목록에 넣을 필요 없음
    (`_odd_even_cache`/`_high_low_cache`와 동일).

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/odd-even")`(line 715),
    `@router.get("/stats/high-low")`(line 729)
- 본 SPEC: `@router.get("/stats/last-digit-sum")` → 항상 200, 데이터 부재도
  정상 응답. 반환은 `get_last_digit_sum_stats(wd.get_draws())` 결과 dict를
  그대로 JSON 직렬화. `get_high_low`(line 729~) 핸들러 시그니처
  `async def ... -> dict[str, Any]:`를 동일하게 복제
- 주의: 기존 `/stats/last-digit`(SPEC-055)과 경로가 다르므로 라우트 충돌 없음

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/odd-even")`(line 771),
  `@router.get("/stats/high-low")`(line 790)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/last-digit-sum")` → `last_digit_sum.html`
  렌더링, `active_tab` = `"last_digit_sum"`
  - `stats_high_low_page`(line 790~)를 복제·각색
- 주의: 기존 `/stats/last-digit`(SPEC-055, active_tab `last_digit`)와 라우트·
  active_tab·템플릿이 모두 다르므로 충돌 없음

### 템플릿 — `lotto/web/templates/`

- 기존 stats 계열: `odd_even.html`(SPEC-060), `high_low.html`(SPEC-061),
  `consecutive_pattern.html`(SPEC-062), `decade.html`, `prime.html`,
  `gap.html`, `ac.html`, `sum_range.html` 등
- 본 SPEC: `last_digit_sum.html` 신규 — 요약 카드(평균/최소/최대 합계 +
  저·중·고 구간 회차 수와 비율) + 끝자리 합계 분포 표(최빈 상위 20개:
  합계값, 회차 수, 비율). `high_low.html`을 복제하여 라벨/표 구성만 변경
- 분포 표는 빈도 내림차순(동률 시 합계값 오름차순)으로 최대 20행
  (LDS-33). 정렬은 파이썬 데이터 계층 또는 템플릿 직전 핸들러에서 수행하고
  템플릿은 단순 순회만 하도록 한다(서버 렌더링 전용, JS 미사용)
- 서버 렌더링 전용 (JavaScript 미사용)

### 네비게이션 — `lotto/web/templates/base.html`

- 네비게이션 항목은 **두 곳**에 정의되어 있다:
  - desktop_nav_items (line 74)
  - nav_items (line 128, 모바일/기본)
- 두 리스트 모두 `('/stats/consecutive-pattern', 'consecutive_pattern',
  '연속 패턴')` 다음에 `('/stats/last-digit-sum', 'last_digit_sum',
  '끝합 분석')` 튜플을 추가한다 (REQ-LDS-010 / 비기능 요구사항). 한 곳만
  수정하면 한쪽 레이아웃에서 링크가 누락된다.
- active_tab 라벨 분기(line 101 부근,
  `{% elif active_tab == 'consecutive_pattern' %}연속 패턴`) 바로 다음에
  `{% elif active_tab == 'last_digit_sum' %}끝합 분석` 분기를 추가한다.
- 기존 "끝자리 분포"(`last_digit`, `/stats/last-digit`, SPEC-055) 항목은
  유지하며, "끝합 분석" 항목을 추가로 둔다. 두 라벨이 시각적으로 유사
  ("끝자리 분포" vs "끝합 분석")하므로 라벨을 명확히 구분한다.

### 테스트 — `tests/test_last_digit_sum_analysis.py`

- 신규 테스트 파일 생성 (최소 20개)
- `mypy.ini` override 목록에 `test_last_digit_sum_analysis` 등록 필수
  - 기존에 `test_odd_even_analysis`, `test_high_low_analysis`,
    `test_consecutive_pattern_analysis` 등이 동일 방식으로 등록되어 있음
    (저장소 사전 mypy 부채 회피 목적)
  - 주의: 기존 SPEC-055 끝자리 분포 테스트와 파일명이 다르므로 별도 등록 —
    혼동 금지
- 데이터/API/페이지 계층별 테스트 분리 권장 (odd_even/high_low SPEC 구조 참고)

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호 각각의 (n % 10)을 더한다.

| 회차 | 본번호 | 끝자리 | 끝자리 합 | 구간 |
|------|--------|--------|-----------|------|
| D1 | [3,11,18,25,33,40]  | 3,1,8,5,3,0 | 20 | 중 (15~29) |
| D2 | [1,2,5,6,10,20]     | 1,2,5,6,0,0 | 14 | 저 (<15) |
| D3 | [9,19,29,39,40,44]  | 9,9,9,9,0,4 | 40 | 고 (≥30) |
| D4 | [7,8,17,18,27,28]   | 7,8,7,8,7,8 | 45 | 고 (≥30) |

last_digit_sum 모음: [20, 14, 40, 45]

- avg_sum = (20+14+40+45)/4 = 119/4 = 29.75
- min_sum = 14, max_sum = 45
- sum_distribution = {20:1, 14:1, 40:1, 45:1} (합 4 ✓, 출현값만)
- most_common_sum = 14 (전부 1회 동률 → 가장 작은 값)
- low_sum_count = 1 (D2), mid_sum_count = 1 (D1), high_sum_count = 2 (D3,D4)
- low+mid+high = 1+1+2 = 4 = total_draws ✓
- low_sum_pct = 25.0, mid_sum_pct = 25.0, high_sum_pct = 50.0

이 수치는 acceptance.md의 LDS-07~LDS-18에 그대로 반영됨. 저(D2)·중(D1)·고
(D3,D4) 세 구간을 모두 포함하고, 끝자리 0 처리(D2,D3의 10/20/40)와 동일 끝자리
반복(D4)을 커버한다. 동률 최빈값(작은 값 우선)은 별도 경계 픽스처(LDS-25)로
검증한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any, Sequence


def _last_digit_sum(main_numbers: Sequence[int]) -> int:
    return sum(n % 10 for n in main_numbers)
```

- `n % 10`은 O(1), 결정적, 부작용 없음. 0으로 끝나는 번호는 0을 기여
  (REQ-LDS-012).
- `match/case` 미사용 → Python 3.9 호환.
- `zip(strict=...)` 미사용 → B905 경고 회피 (단순 합산).

회차 루프에서 합계를 모으고 구간을 분류한다:

```
LOW_MAX = 15   # noqa: PLR2004  (< 15 → 저)
MID_MAX = 30   # noqa: PLR2004  (15 ≤ s ≤ 29 → 중, s ≥ 30 → 고)

sums: list[int] = []
dist: dict[int, int] = {}
low = mid = high = 0
for draw in draws:
    main = list(draw.numbers)  # 본번호 6개 (보너스 제외)
    if len(main) < 6:          # noqa: PLR2004
        continue               # REQ-LDS-015 skip
    s = _last_digit_sum(main)
    sums.append(s)
    dist[s] = dist.get(s, 0) + 1
    if s < LOW_MAX:
        low += 1
    elif s < MID_MAX:          # 15 ≤ s ≤ 29
        mid += 1
    else:                      # s ≥ 30
        high += 1
```

- 구간 경계: `s < 15` 저, `15 ≤ s < 30` 중(즉 15~29), `s ≥ 30` 고
  (REQ-LDS-007). LDS-24가 경계값 15/29/30을 검증.

빈 데이터(total_draws == 0)는 division-by-zero 방지를 위해 조기 반환한다:

```
if not sums:
    return {
        "total_draws": 0, "avg_sum": 0, "min_sum": 0, "max_sum": 0,
        "sum_distribution": {}, "most_common_sum": 0,
        "low_sum_count": 0, "mid_sum_count": 0, "high_sum_count": 0,
        "low_sum_pct": 0, "mid_sum_pct": 0, "high_sum_pct": 0,
    }  # REQ-LDS-013
```

최빈값(동률 시 작은 값 우선)은 sum_distribution을 (합계값 오름차순) 순회하여
첫 최댓값 채택:

```
most_common = min(dist, key=lambda k: (-dist[k], k))
```

- `(-count, value)` 키로 최소를 취하면 빈도 내림차순 + 값 오름차순 → 동률 시
  가장 작은 합계값을 채택 (REQ-LDS-006).

페이지 표(top-20)는 동일 정렬을 적용하여 상위 20개만 슬라이스:

```
top20 = sorted(dist.items(), key=lambda kv: (-kv[1], kv[0]))[:20]  # noqa: PLR2004
```

- 빈도 내림차순, 동률 시 합계값 오름차순, 최대 20행 (LDS-33).
- API는 `sum_distribution` 전체를 반환하고, 페이지 핸들러에서만 top-20을
  구성하여 템플릿에 전달한다.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 구간 분류는 if/elif/else 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 단순 합산으로 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고). 커밋 시 게이트 우회는
  GIT_BIN 변수 패턴 참고.

## 위험 요소 및 완화

- 위험: SPEC-055 끝자리 분포 기능과의 혼동(같은 "끝자리" 도메인) →
  함수명/라우트/템플릿/네비 라벨/테스트 파일명을 모두 구별하고 REQ-LDS-014로
  SPEC-055 코드 무수정 명시.
- 위험: SPEC-049 본번호 합계와의 혼동 → 끝자리 합(n % 10)만 다룸을 용어
  정의와 Exclusions에 명시.
- 위험: 구간 경계 오류(15/29/30 분류) → LDS-24 경계 단위 검증 + if/elif/else
  명확한 비교(`< 15`, `< 30`, else).
- 위험: 6개 미만 본번호 회차 → REQ-LDS-015로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg, *_pct) → REQ-LDS-013 빈 구조 조기 반환.
- 위험: sum_distribution을 전 구간 0-채움(다른 stats SPEC 관례와 반대) →
  본 SPEC은 출현값만 포함(REQ-LDS-005, Exclusions 명시). 구현 시 0-채움 금지.
- 위험: 동률 최빈값을 큰 값으로 잘못 채택 → `(-count, value)` 정렬 키로
  REQ-LDS-006의 "작은 값 우선" 보장.
- 위험: base.html 네비게이션 한 곳만 수정 → 두 리스트(desktop_nav_items,
  nav_items)와 active_tab 라벨 분기까지 모두 갱신.
- 위험: 기존 코어 모듈 침범 → REQ-LDS-014로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `sum_distribution` 키 타입: int(합계값)로 명시. JSON 직렬화 시 키가 문자열로
  변환될 수 있으므로(JSON object key는 string), API 테스트에서는 문자열/정수
  키 허용 여부를 명확히 할 것. 데이터 계층은 int 키 dict를 반환하고, API
  계층의 직렬화 변환은 FastAPI 기본 동작에 위임 (odd_even/high_low SPEC과 동일).
- 반환 타입 표기: 기존 stats 계열과 일관되게 `dict[str, Any]` 사용 권장.
- top-20 슬라이스 위치: 페이지 핸들러(pages.py)에서 구성하여 템플릿에 전달할지,
  데이터 계층에 별도 헬퍼를 둘지 결정. 데이터 계층은 전체 sum_distribution을
  반환하고 페이지 핸들러에서 top-20을 구성하는 편이 API/페이지 책임 분리에
  부합 (LDS-29는 API가 전체 분포 반환, LDS-33은 페이지가 top-20 표시).
- 본번호 접근자: `draw.numbers`가 6개 본번호 리스트인지, 보너스가 별도
  필드인지 기존 stats 함수(get_high_low_stats line 4019)의 본번호 추출
  방식을 동일하게 따른다.
