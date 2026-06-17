---
id: SPEC-LOTTO-062
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-062 연구 노트 (Consecutive Number Pattern Analysis)

## 코드베이스 분석 (기존 패턴 확인)

"통계 분석(stats)" 계열은 일관된 패턴을 따른다. 가장 가까운 선행 사례는
SPEC-LOTTO-060(홀짝)·SPEC-LOTTO-061(고저)이다. 본 SPEC도 동일하게
`get_<topic>_stats` 함수 + str-키 캐시 + 3계층 라우트(`/api/stats/...`,
`/stats/...`, 템플릿)를 적용한다.

### 선행 기능 충돌 점검 — SPEC-LOTTO-043 (중요)

코드베이스에는 이미 SPEC-LOTTO-043에서 구현한 연속 번호 분석이 존재한다.
신규 함수/라우트/템플릿/테스트 명이 충돌하지 않음을 grep으로 확인했다.

기존(SPEC-043, 수정 금지):

- `consecutive_pattern(draws, recent_n)` — data.py:2216 (런 길이 분포 2~6,
  most_common_pairs 라벨 순위, consecutive_ratio, recent_n 윈도 지원)
- 헬퍼 `_find_consecutive_runs(nums)` — data.py:2307
- 빈 구조 `_empty_consecutive_pattern()` — data.py:2198
- 라우트 `/patterns/consecutive` — pages.py:853, api.py:826
- 템플릿 `patterns_consecutive.html`
- 네비 "연속 번호" → `/patterns/consecutive` (base.html desktop_nav_items
  line 74, nav_items line 127)
- 테스트 test_consecutive_pattern.py, test_api_consecutive.py,
  test_consecutive_page.py (mypy.ini에 모두 등록됨)

신규(SPEC-062, 본 SPEC):

- `get_consecutive_pattern_stats(draws)` — 신규, 회차별 연속 쌍 개수(0..5) 분포
- 라우트 `/stats/consecutive-pattern` (api.py, pages.py)
- 템플릿 `consecutive_pattern.html`
- 네비 "연속 패턴" → `/stats/consecutive-pattern`
- 테스트 `tests/test_consecutive_pattern_analysis.py`

→ 함수명·라우트·템플릿·네비 라벨·테스트 파일명이 모두 다르므로 충돌 없이
공존한다. 두 기능은 서로 다른 질문에 답한다: SPEC-043은 "연속 런이 얼마나
길게/어떤 쌍으로 나타나는가", SPEC-062는 "회차당 연속 쌍이 몇 개이고 트리플을
포함하는 회차가 얼마나 되는가". 본 SPEC은 SPEC-043 코드를 일절 건드리지 않는다
(REQ-CP-015).

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은
  `get_consecutive_pattern_stats(draws)`
  - 참고: `get_odd_even_stats`(line 3850), `get_high_low_stats`(line 4012)
- 모듈 레벨 캐시 (data.py 확인):
  - `_odd_even_cache`(line 113), `_high_low_cache`(line 118) — 모두
    `dict[str, Any] = {}` str-키 캐시. 신규
    `_consecutive_cache: dict[str, Any] = {}`도 동일 형태이며 `str(len(draws))`
    를 키로 사용 (REQ-CP-017). `_high_low_cache`(line 118) 다음 줄에 추가하는
    것이 가장 자연스럽다.
- `invalidate_cache()` (data.py:121~)에서 모든 캐시 무효화:
  - line 147 `_odd_even_cache.clear()`, line 148 `_high_low_cache.clear()`가
    순차 등록되어 있다. 신규 `_consecutive_cache.clear()` 라인을 line 148 다음에
    추가한다.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로
    invalidate_cache() 상단 global 선언 목록에 넣을 필요 없음
    (`_odd_even_cache`/`_high_low_cache`와 동일).

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/odd-even")`(line 715),
    `@router.get("/stats/high-low")`(line 729)
- 본 SPEC: `@router.get("/stats/consecutive-pattern")` → 항상 200, 데이터
  부재도 정상 응답. 반환은 `get_consecutive_pattern_stats(...)` 결과 dict를
  그대로 JSON 직렬화. `get_high_low`(line 729~) 핸들러 시그니처
  `async def ... -> dict[str, Any]:`를 동일하게 복제
- 주의: 기존 `/patterns/consecutive`(api.py:826, SPEC-043)와 경로가 다르므로
  라우트 충돌 없음

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/odd-even")`(line 771),
  `@router.get("/stats/high-low")`(line 790)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/consecutive-pattern")` →
  `consecutive_pattern.html` 렌더링, `active_tab` = `"consecutive_pattern"`
  - `stats_high_low_page`(line 790~)를 복제·각색
- 주의: 기존 `/patterns/consecutive`(pages.py:853, SPEC-043, active_tab
  `patterns_consecutive`, 템플릿 `patterns_consecutive.html`)와 라우트·
  active_tab·템플릿이 모두 다르므로 충돌 없음

### 템플릿 — `lotto/web/templates/`

- 기존 stats 계열: `odd_even.html`(SPEC-060), `high_low.html`(SPEC-061),
  `decade.html`, `prime.html`, `gap.html`, `ac.html`, `sum_range.html` 등
- 기존 patterns 계열: `patterns_consecutive.html`(SPEC-043) — 별개
- 본 SPEC: `consecutive_pattern.html` 신규 — 요약 카드(평균 연속 쌍 개수 /
  연속 쌍 없는 회차 비율 / 트리플 포함 회차 비율) + 연속 쌍 개수 분포 표
  (0..5, 회차 수, 비율). `high_low.html`을 복제하여 라벨만 변경
- 서버 렌더링 전용 (JavaScript 미사용)

### 네비게이션 — `lotto/web/templates/base.html`

- 네비게이션 항목은 **두 곳**에 정의되어 있다:
  - desktop_nav_items (line 74)
  - nav_items (line 127, 모바일/기본)
- 두 리스트 모두 `('/stats/high-low', 'high_low', '고저 분석')` 다음에
  `('/stats/consecutive-pattern', 'consecutive_pattern', '연속 패턴')` 튜플을
  추가한다 (REQ-CP-011 / 비기능 요구사항). 한 곳만 수정하면 한쪽 레이아웃에서
  링크가 누락된다.
- active_tab 라벨 분기(line 100 부근, `{% elif active_tab == 'high_low' %}고저 분석`)
  바로 다음에 `{% elif active_tab == 'consecutive_pattern' %}연속 패턴` 분기를
  추가한다.
- 기존 "연속 번호"(`patterns_consecutive`, `/patterns/consecutive`, line 74의
  리스트 내) 항목은 유지하며, "연속 패턴" 항목을 추가로 둔다. 두 라벨이 시각적
  으로 유사하므로 라벨을 "연속 번호"(SPEC-043) / "연속 패턴"(SPEC-062)로 명확히
  구분한다.

### 테스트 — `tests/test_consecutive_pattern_analysis.py`

- 신규 테스트 파일 생성 (최소 20개)
- `mypy.ini` override 목록에 `test_consecutive_pattern_analysis` 등록 필수
  - 기존에 `test_odd_even_analysis`, `test_high_low_analysis`,
    `test_decade_analysis` 등이 동일 방식으로 등록되어 있음 (저장소 사전 mypy
    부채 회피 목적)
  - 주의: 기존 `test_consecutive_pattern`(SPEC-043)과 파일명이 다르므로
    별도 등록 — 혼동 금지
- 데이터/API/페이지 계층별 테스트 분리 권장 (odd_even/high_low SPEC 구조 참고)

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호를 오름차순 정렬 후 인접 차가 1인
쌍을 카운트하고, 길이 3+ 런 존재 여부로 트리플을 판정한다.

| 회차 | 본번호(정렬) | 인접차 | 연속 쌍 | 트리플(3+런)? |
|------|-------------|--------|---------|--------------|
| D1 | [3,11,18,25,33,40]   | 8,7,7,8,7  | 0 | 아니오 |
| D2 | [1,2,5,6,10,20]      | 1,3,1,4,10 | 2 | 아니오 (런 길이 모두 2) |
| D3 | [4,5,6,7,30,44]      | 1,1,1,23,14| 3 | 예 (런 [4,5,6,7] 길이 4) |
| D4 | [10,11,12,20,21,35]  | 1,1,8,1,15 | 3 | 예 (런 [10,11,12] 길이 3) |

consecutive_pairs 모음: [0, 2, 3, 3]
has_triple 모음: [False, False, True, True]

- avg_consecutive_pairs = (0+2+3+3)/4 = 2.0
- pair_distribution = {0:1, 1:0, 2:1, 3:2, 4:0, 5:0} (합 4 ✓)
- pair_distribution_pct = {0:25.0, 1:0.0, 2:25.0, 3:50.0, 4:0.0, 5:0.0}
- most_common_pair_count = 3 (키 3이 2회로 유일 최다)
- no_consecutive_count = 1 (D1), no_consecutive_pct = 25.0
- has_triple_count = 2 (D3, D4), has_triple_pct = 50.0
- max_consecutive_count = max(0,2,3,3) = 3

이 수치는 acceptance.md의 CP-07~CP-17에 그대로 반영됨. 연속 쌍 개수 경계값
0(D1)과 중간값(2,3)을 포함하고, 트리플 포함/미포함을 함께 커버한다. 동률
최빈값(작은 값 우선)은 별도 경계 픽스처(CP-24)로 검증하며, 최대치(5쌍)와
연속 쌍 != 트리플 케이스(CP-04: [1,2,4,5,7,8] 3쌍이지만 트리플 없음)도 별도
단위로 검증한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any, Sequence


def _count_consecutive_pairs(sorted_nums: Sequence[int]) -> int:
    return sum(
        1
        for i in range(1, len(sorted_nums))
        if sorted_nums[i] - sorted_nums[i - 1] == 1
    )


def _has_consecutive_triple(sorted_nums: Sequence[int]) -> bool:
    run = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] - sorted_nums[i - 1] == 1:
            run += 1
            if run >= 3:  # noqa: PLR2004
                return True
        else:
            run = 1
    return False
```

- 정렬은 `sorted(main_numbers)` 한 번. `n+1` 판정은 O(1), 결정적, 부작용 없음.
- `zip(strict=...)` 불필요 → B905 경고 회피 (인접 비교는 인덱스 순회).
- `match/case` 미사용 → Python 3.9 호환.
- has_triple는 회차 단위 불리언 — 첫 length>=3 런 발견 시 즉시 True 반환
  (REQ-CP-013: 회차당 1회만 기여).

분포 딕셔너리는 0..5 키를 0으로 초기화한 뒤 카운트를 누적한다:

```
pair_dist = {k: 0 for k in range(6)}  # 0..5
# 회차 루프: pairs = _count_consecutive_pairs(s); pair_dist[pairs] += 1
```

최빈값(동률 시 작은 값 우선)은 키 0..5 오름차순 순회로 첫 최댓값 채택:

```
most_common = max(range(6), key=lambda k: pair_dist[k])
```

주의: `max(..., key=...)`는 동률 시 첫 항목(가장 작은 키)을 반환하므로
range(6) 오름차순과 결합하면 REQ-CP-006의 "작은 값 우선"을 충족한다.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 분기는 if/else 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 인덱스 순회로 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고). 커밋 시 게이트 우회는
  GIT_BIN 변수 패턴 참고.

## 위험 요소 및 완화

- 위험: SPEC-043 기능과의 혼동(같은 "연속" 도메인) → 함수명/라우트/템플릿/네비
  라벨/테스트 파일명을 모두 구별하고 REQ-CP-015로 SPEC-043 코드 무수정 명시.
- 위험: 6개 미만 본번호 회차에서 인접 비교 오류 → REQ-CP-016으로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg, *_pct) → REQ-CP-014 빈 구조 조기 반환.
- 위험: 분포 키 누락(0..5 일부만 채움) → 0으로 초기화한 6개 키 딕셔너리를
  먼저 만든 뒤 카운트 누적하여 REQ-CP-004/005 보장.
- 위험: 동률 최빈값을 큰 값으로 잘못 채택 → range(6) 오름차순 순회로
  REQ-CP-006의 "작은 값 우선" 보장.
- 위험: 트리플을 회차 내 여러 번 카운트 → 회차 단위 불리언으로 1회만 기여
  (REQ-CP-013, CP-23).
- 위험: 연속 쌍 개수와 트리플 혼동(3쌍인데 모두 길이 2 런) → CP-04 단위 검증.
- 위험: base.html 네비게이션 한 곳만 수정 → 두 리스트(desktop_nav_items,
  nav_items)와 active_tab 라벨 분기까지 모두 갱신.
- 위험: 기존 코어 모듈 침범 → REQ-CP-015로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `pair_distribution` 키 타입: int(0..5)로 명시. JSON 직렬화 시 키가 문자열로
  변환될 수 있으므로(JSON object key는 string), API 테스트에서는 문자열/정수
  키 허용 여부를 명확히 할 것. 데이터 계층은 int 키 dict를 반환하고, API
  계층의 직렬화 변환은 FastAPI 기본 동작에 위임 (odd_even/high_low SPEC과 동일).
- 반환 타입 표기: 기존 stats 계열과 일관되게 `dict[str, Any]` 사용 권장.
- 트리플 헬퍼 재사용 여부: SPEC-043의 `_find_consecutive_runs`를 읽기 전용으로
  참고할 수 있으나, REQ-CP-015(무수정)·결합도 최소화를 위해 SPEC-062 전용
  헬퍼(`_has_consecutive_triple`)를 신규 작성하는 것을 권장. SPEC-043 헬퍼를
  호출해도 무방하나 호출 시 그 동작/시그니처에 결합되므로 신규 작성이 안전.
