---
id: SPEC-LOTTO-064
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-064 연구 노트 (Min/Max Number Distribution Analysis)

## 코드베이스 분석 (기존 패턴 확인)

"통계 분석(stats)" 계열은 일관된 패턴을 따른다. 가장 가까운 선행 사례는
SPEC-LOTTO-061(고저)·SPEC-LOTTO-062(연속 패턴)·SPEC-LOTTO-063(끝자리 합계)이다.
본 SPEC도 동일하게 `get_<topic>_stats` 함수 + str-키 캐시 + 3계층 라우트
(`/api/stats/...`, `/stats/...`, 템플릿)를 적용한다.

### 선행 기능 충돌 점검 (중요)

grep 결과 "최솟값·최댓값" 분석 기능(min-max / min_max / get_min_max /
최대최소 라우트·함수·네비)은 코드베이스에 **존재하지 않는다**. 따라서 신규
함수/라우트/템플릿/네비/테스트 명이 충돌하지 않는다.

다만 인접 개념과 명확히 구분한다:

- SPEC-049 합계 분석: 본번호 6개의 총합 (본 SPEC은 최솟/최댓/범위만, 합 아님)
- SPEC-056 간격 분석: 인접 번호 간 gap 분포 (본 SPEC의 range는 max-min 단일값,
  인접 간격 아님)
- SPEC-061 고저 분석: 저(≤22)/고(≥23) 개수 비율 (본 SPEC은 절대 최솟/최댓값)

→ 함수명·라우트·템플릿·네비 라벨·테스트 파일명이 모두 다르며 답하는 질문도
다르다. 본 SPEC은 기존 코드를 일절 건드리지 않는다(REQ-MM-017).

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은 `get_min_max_stats(draws)`
  - 참고: `get_high_low_stats`(line 4026), `get_odd_even_stats`
- 본번호 추출: `get_high_low_stats`(line 4090)는 `draw.numbers()`를 호출하며
  주석에 "정렬된 본번호 6개 (보너스 제외)"라고 명시. 본 SPEC도 동일하게
  `draw.numbers()`로 6개 본번호를 얻는다. 정렬되어 있으므로 `nums[0]`이
  min_num, `nums[-1]`이 max_num이 되지만, 정렬 비의존성을 위해 `min(nums)`/
  `max(nums)`를 쓰는 것이 안전·명확하다(MM-04 정렬 비의존 검증).
- 6개 미만 회차 제외: `get_high_low_stats`(line 4092)는
  `if len(nums) < _HIGH_LOW_PICK: continue` 패턴을 사용. 본 SPEC도
  `if len(nums) < 6: continue`(REQ-MM-018, MM-25).
- 모듈 레벨 캐시 (data.py 확인):
  - `_odd_even_cache`(line 113), `_high_low_cache`(line 118) — 모두
    `dict[str, Any] = {}` str-키 캐시. 신규 `_min_max_cache: dict[str, Any] = {}`도
    동일 형태이며 `str(len(draws))`를 키로 사용(REQ-MM-019).
    `_high_low_cache`(line 118) 다음 줄에 추가하는 것이 자연스럽다.
  - 캐시 키 산출은 `get_high_low_stats`의 `str(len(draws) if draws else 0)`
    (line 4060) 패턴을 그대로 따른다.
- `invalidate_cache()` (data.py:131~)에서 모든 캐시 무효화:
  - line 160 `_high_low_cache.clear()` 부근에 신규 `_min_max_cache.clear()`
    라인을 추가한다.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로
    invalidate_cache() 상단 global 선언 목록에 넣을 필요 없음.

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/high-low")`, `@router.get("/stats/last-digit-sum")`
    (SPEC-063)
- 본 SPEC: `@router.get("/stats/min-max")` → 항상 200, 데이터 부재도 정상 응답.
  반환은 `get_min_max_stats(wd.get_draws())` 결과 dict를 그대로 JSON 직렬화.
  기존 stats 핸들러 시그니처 `async def ... -> dict[str, Any]:`를 복제.
- 주의: 신규 경로이므로 라우트 충돌 없음.

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/high-low")`,
  `@router.get("/stats/last-digit-sum")`
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/min-max")` → `min_max.html` 렌더링,
  `active_tab` = `"min_max"`
  - 기존 stats 페이지 핸들러를 복제·각색
- top-15 표 두 개(최솟값·최댓값)는 페이지 핸들러에서 구성하여 템플릿에
  전달한다(책임 분리: API는 전체 분포 반환, 페이지는 top-15 표시).

### 템플릿 — `lotto/web/templates/`

- 기존 stats 계열: `high_low.html`(SPEC-061),
  `consecutive_pattern.html`(SPEC-062), `last_digit_sum.html`(SPEC-063),
  `sum_range.html`, `gap.html` 등
- 본 SPEC: `min_max.html` 신규 — 요약 카드(평균 최솟값/최댓값/범위 +
  좁음·넓음 구간 회차 수와 비율) + 최솟값 top-15 표 + 최댓값 top-15 표.
  기존 stats 템플릿을 복제하여 라벨/표 구성만 변경.
- 두 표 모두 빈도 내림차순(동률 시 번호 오름차순)으로 최대 15행(MM-38).
  정렬은 페이지 핸들러에서 수행하고 템플릿은 단순 순회만(서버 렌더링 전용,
  JS 미사용).

### 네비게이션 — `lotto/web/templates/base.html`

- 네비게이션 항목은 **두 곳**에 정의되어 있다:
  - desktop_nav_items (line ~74)
  - nav_items (line ~128, 모바일/기본)
- 두 리스트 모두 가장 최근 stats 항목(예: `('/stats/last-digit-sum',
  'last_digit_sum', '끝합 분석')`) 다음에 `('/stats/min-max', 'min_max',
  '최대최소')` 튜플을 추가한다(REQ-MM-013 / 비기능 요구사항). 한 곳만 수정하면
  한쪽 레이아웃에서 링크가 누락된다.
- active_tab 라벨 분기에 `{% elif active_tab == 'min_max' %}최대최소` 분기를
  추가한다.

### 테스트 — `tests/test_min_max_analysis.py`

- 신규 테스트 파일 생성 (최소 20개)
- `mypy.ini` override 목록에 `test_min_max_analysis` 등록 필수
  - 기존에 `test_high_low_analysis`, `test_last_digit_sum_analysis` 등이 동일
    방식으로 등록되어 있음(저장소 사전 mypy 부채 회피 목적).
- 데이터/API/페이지 계층별 테스트 분리 권장 (high_low/last_digit_sum SPEC 구조
  참고).

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호에서 min/max/range를 산출한다.

| 회차 | 본번호 | min | max | range | 구간 |
|------|--------|-----|-----|-------|------|
| D1 | [3,11,18,25,33,40]  | 3  | 40 | 37 | 넓음 (≥30) |
| D2 | [1,2,5,6,10,20]     | 1  | 20 | 19 | 좁음 (<30) |
| D3 | [9,19,29,39,40,44]  | 9  | 44 | 35 | 넓음 (≥30) |
| D4 | [7,8,17,18,27,28]   | 7  | 28 | 21 | 좁음 (<30) |

- min_num 모음: [3,1,9,7] → avg_min = 20/4 = 5.0
- max_num 모음: [40,20,44,28] → avg_max = 132/4 = 33.0
- range_val 모음: [37,19,35,21] → avg_range = 112/4 = 28.0
- min_distribution = {3:1,1:1,9:1,7:1} (합 4 ✓, 출현값만)
- max_distribution = {40:1,20:1,44:1,28:1} (합 4 ✓)
- range_distribution = {37:1,19:1,35:1,21:1} (합 4 ✓)
- most_common_min = 1, most_common_max = 20, most_common_range = 19
  (전부 1회 동률 → 각각 가장 작은 값)
- small_range_count = 2 (D2,D4), large_range_count = 2 (D1,D3)
- small+large = 2+2 = 4 = total_draws ✓
- small_range_pct = 50.0, large_range_pct = 50.0

이 수치는 acceptance.md의 MM-08~MM-22에 그대로 반영됨. 좁음(D2,D4)·넓음(D1,D3)
두 구간을 모두 포함하고, 동률 최빈값(작은 값 우선)을 세 분포 모두에서 검증한다.
빈도 우세 케이스(MM-30)와 경계값 29/30(MM-28)은 별도 픽스처로 검증한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any

SMALL_RANGE_MAX = 30  # noqa: PLR2004  (range < 30 → 좁음, range >= 30 → 넓음)
MAIN_PICK = 6         # noqa: PLR2004  (본번호 6개)


def get_min_max_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    cache_key = str(len(draws) if draws else 0)
    cached = _min_max_cache.get(cache_key)
    if cached is not None:
        return cached

    mins: list[int] = []
    maxs: list[int] = []
    ranges: list[int] = []
    min_dist: dict[int, int] = {}
    max_dist: dict[int, int] = {}
    range_dist: dict[int, int] = {}
    small = large = 0

    for draw in draws or []:
        nums = draw.numbers()          # 정렬된 본번호 6개 (보너스 제외)
        if len(nums) < MAIN_PICK:
            continue                   # REQ-MM-018 skip
        lo = min(nums)
        hi = max(nums)
        rng = hi - lo
        mins.append(lo)
        maxs.append(hi)
        ranges.append(rng)
        min_dist[lo] = min_dist.get(lo, 0) + 1
        max_dist[hi] = max_dist.get(hi, 0) + 1
        range_dist[rng] = range_dist.get(rng, 0) + 1
        if rng < SMALL_RANGE_MAX:
            small += 1
        else:
            large += 1

    total = len(mins)
    if total == 0:
        result = {
            "total_draws": 0, "avg_min": 0, "avg_max": 0, "avg_range": 0,
            "min_distribution": {}, "max_distribution": {},
            "range_distribution": {}, "most_common_min": 0,
            "most_common_max": 0, "most_common_range": 0,
            "small_range_count": 0, "large_range_count": 0,
            "small_range_pct": 0, "large_range_pct": 0,
        }  # REQ-MM-016
        _min_max_cache[cache_key] = result
        return result

    result = {
        "total_draws": total,
        "avg_min": round(sum(mins) / total, 2),
        "avg_max": round(sum(maxs) / total, 2),
        "avg_range": round(sum(ranges) / total, 2),
        "min_distribution": min_dist,
        "max_distribution": max_dist,
        "range_distribution": range_dist,
        "most_common_min": _most_common_smallest_kv(min_dist),
        "most_common_max": _most_common_smallest_kv(max_dist),
        "most_common_range": _most_common_smallest_kv(range_dist),
        "small_range_count": small,
        "large_range_count": large,
        "small_range_pct": round(small / total * 100, 2),
        "large_range_pct": round(large / total * 100, 2),
    }
    _min_max_cache[cache_key] = result
    return result
```

- `min(nums)`/`max(nums)`는 O(n), 결정적, 부작용 없음, 정렬 비의존(MM-04).
- `match/case` 미사용 → Python 3.9 호환. `zip(strict=...)` 미사용.
- 최빈값(동률 시 작은 값 우선)은 distribution을 `(-count, value)` 키로 최소를
  취해 산출:

```
def _most_common_smallest_kv(dist: dict[int, int]) -> int:
    if not dist:
        return 0
    return min(dist, key=lambda k: (-dist[k], k))
```

  - 빈도 내림차순 + 값 오름차순 → 동률 시 가장 작은 값(REQ-MM-007/008/009).
  - 기존 `data.py`에 `max(dist, key=lambda k: (dist[k], -k))` 형태의 동률-작은값
    선택 헬퍼가 있음(예: AC `most_common_ac` line 3563). 동일 의미. 기존
    `_most_common_smallest`(line 3845)가 있다면 재사용 가능 여부를 구현 시
    확인하되, 그 헬퍼가 전 구간 0-채움 분포를 전제한다면(출현값만 담는 본
    SPEC과 다름) 별도 헬퍼를 두거나 `min(... )` 패턴을 인라인으로 적용한다.

- 페이지 top-15 표(최솟값·최댓값)는 동일 정렬을 적용하여 상위 15개만 슬라이스:

```
top_min = sorted(min_dist.items(), key=lambda kv: (-kv[1], kv[0]))[:15]  # noqa: PLR2004
top_max = sorted(max_dist.items(), key=lambda kv: (-kv[1], kv[0]))[:15]  # noqa: PLR2004
```

  - 빈도 내림차순, 동률 시 번호 오름차순, 최대 15행(MM-38).
  - API는 세 분포 전체를 반환하고, 페이지 핸들러에서만 top-15을 구성하여
    템플릿에 전달.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 구간 분류는 if/else 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로 전체
  mypy 차단되므로 게이트 우회 패턴 참고). 커밋 시 게이트 우회는 GIT_BIN 변수
  패턴 참고.

## 위험 요소 및 완화

- 위험: SPEC-049 합계/ SPEC-056 간격/ SPEC-061 고저와의 혼동 → 용어 정의와
  Exclusions에 명확히 구분, REQ-MM-017로 기존 코드 무수정 명시.
- 위험: 구간 경계 오류(29/30 분류) → MM-28 경계 단위 검증 + 명확한 비교
  (`< 30`, else).
- 위험: 6개 미만 본번호 회차 → REQ-MM-018로 skip 처리(MM-25).
- 위험: 빈 데이터 division-by-zero(avg, *_pct) → REQ-MM-016 빈 구조 조기 반환.
- 위험: 세 분포를 전 구간 0-채움(다른 stats SPEC 일부 관례와 반대) → 본 SPEC은
  출현값만 포함(REQ-MM-004/005/006, Exclusions 명시). 구현 시 0-채움 금지.
- 위험: 동률 최빈값을 큰 값으로 잘못 채택 → `(-count, value)` 정렬 키로
  "작은 값 우선" 보장(MM-16~18, MM-29).
- 위험: base.html 네비게이션 한 곳만 수정 → 두 리스트(desktop_nav_items,
  nav_items)와 active_tab 라벨 분기까지 모두 갱신.
- 위험: 기존 코어 모듈 침범 → REQ-MM-017로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- 분포 키 타입: int(번호/범위값)로 명시. JSON 직렬화 시 키가 문자열로 변환될
  수 있으므로 API 테스트에서 문자열/정수 키 허용 여부를 명확히 할 것. 데이터
  계층은 int 키 dict를 반환하고 직렬화 변환은 FastAPI 기본 동작에 위임
  (기존 stats SPEC과 동일).
- 반환 타입 표기: 기존 stats 계열과 일관되게 `dict[str, Any]` 사용 권장.
- avg/pct 빈 케이스 값: 빈 데이터 시 0(정수)로 반환(기존 stats SPEC들이
  avg를 0/0.0으로 반환하는 관례 확인 후 일관되게 적용; 데이터 존재 시에는
  round(...,2)로 float).
- top-15 슬라이스 위치: 페이지 핸들러(pages.py)에서 구성하여 템플릿에 전달
  (API/페이지 책임 분리: MM-34 API 전체 분포 반환, MM-38 페이지 top-15 표시).
- `_most_common_smallest`(line 3845) 재사용 여부: 그 헬퍼가 0-채움 분포 전제면
  본 SPEC(출현값만)과 다르므로 별도 헬퍼 또는 인라인 min(...) 적용.
- 본번호 접근자: `draw.numbers()`가 정렬된 6개 본번호를 반환함을
  `get_high_low_stats`(line 4090)에서 확인. 동일 방식 사용.
