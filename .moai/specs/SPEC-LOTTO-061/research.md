---
id: SPEC-LOTTO-061
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-061 연구 노트 (High/Low Ratio Analysis)

## 코드베이스 분석 (기존 패턴 확인)

분석 기능은 일관된 패턴을 따른다. SPEC-LOTTO-061도 동일 패턴으로 구현하며,
가장 가까운 선행 사례는 SPEC-LOTTO-060(홀짝 비율, get_odd_even_stats)이다.
고저 비율은 홀짝과 구조적으로 동일하다(상보적 두 버킷의 합 == 6, 두 번째 버킷
유도, 3:3 균형 케이스). 차이는 분류 기준뿐이다: 패리티(n % 2) 대신 범위 비교
(저 1-22, 고 23-45).

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은 `get_high_low_stats(draws)`
  - 참고: `get_decade_stats`(SPEC-059, line 3689),
    `get_odd_even_stats`(SPEC-060, line 3843)
- 모듈 레벨 캐시 패턴 (data.py 확인):
  - `_decade_cache`(line 108), `_odd_even_cache`(line 113) — 모두
    `dict[str, Any] = {}` str-키 캐시. 본 SPEC의
    `_high_low_cache: dict[str, Any] = {}`도 동일 형태이며
    `str(len(draws))`를 키로 사용 (REQ-HL-016).
  - `_odd_even_cache`(line 113) 다음 줄에 `_high_low_cache`를 추가하는 것이
    가장 자연스럽다.
- `invalidate_cache()` (data.py:116~)에서 모든 캐시 무효화:
  - line 140 `_decade_cache.clear()`, line 141 `_odd_even_cache.clear()`가
    순차 등록되어 있다. 신규 `_high_low_cache.clear()` 라인을 line 141 다음에
    추가해야 함.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로
    invalidate_cache() 상단의 global 선언 목록에 넣을 필요 없음
    (`_decade_cache`/`_odd_even_cache`와 동일).

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/decade")`(line 702),
    `@router.get("/stats/odd-even")`(line 715)
- 본 SPEC: `@router.get("/stats/high-low")` → 항상 200, 데이터 부재도 정상 응답
- 반환은 `get_high_low_stats(...)` 결과 dict를 그대로 JSON 직렬화
  - `get_odd_even`(line 716~724)의 핸들러 시그니처
    `async def get_high_low() -> dict[str, Any]:`를 동일하게 복제

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/decade")`(line 754),
  `@router.get("/stats/odd-even")`(line 771)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/high-low")` → `high_low.html` 렌더링,
  `active_tab` = `"high_low"`
  - `stats_odd_even_page`(line 771~783)를 복제·각색

### 템플릿 — `lotto/web/templates/`

- 기존: `decade.html`(SPEC-059), `odd_even.html`(SPEC-060), `prime.html`,
  `gap.html`, `ac.html`, `last_digit.html`, `sum_range.html`, `stats.html`
- 본 SPEC: `high_low.html` 신규 — 요약 카드(평균 저번호 개수 / 평균 고번호
  개수 / 균형 회차 비율) + 저번호 개수 분포 표(0..6, 회차 수, 비율) +
  균형(3:3) 회차 강조 표시. `odd_even.html`을 복제하여 라벨만 홀짝→고저로 변경
- 서버 렌더링 전용 (JavaScript 미사용)

### 네비게이션 — `lotto/web/templates/base.html`

- 네비게이션 항목은 **두 곳**에 정의되어 있다:
  - desktop_nav_items (line 74)
  - nav_items (line 126, 모바일/기본)
- 두 리스트 모두 `('/stats/odd-even', 'odd_even', '홀짝 분석')` 다음에
  `('/stats/high-low', 'high_low', '고저 분석')` 튜플을 추가해야 함
  (REQ-HL-010 / 비기능 요구사항). 한 곳만 수정하면 한쪽 레이아웃에서 링크가
  누락된다.
- active_tab 라벨 분기(line 98~99 부근, `{% elif active_tab == 'odd_even' %}홀짝 분석`)
  바로 다음에 `{% elif active_tab == 'high_low' %}고저 분석` 분기를 추가해야 한다.

### 테스트 — `tests/test_high_low_analysis.py`

- 신규 테스트 파일 생성 (최소 20개)
- `mypy.ini` override 목록에 `test_high_low_analysis` 등록 필수
  - 기존에 `test_odd_even_analysis`, `test_decade_analysis`,
    `test_prime_analysis` 등이 동일 방식으로 등록되어 있음 (저장소 사전 mypy
    부채 회피 목적)
- 데이터/API/페이지 계층별 테스트 분리 권장 (odd_even/decade SPEC 구조 참고)

## 고저 분류표 (1~45)

본번호는 1~45 범위에 한정되므로 단순 범위 비교(`n <= 22`)로 충분하다.

- 저번호(22개): {1,2,3,...,22}
- 고번호(23개): {23,24,25,...,45}

검증: 22(저) + 23(고) = 45 ✓

홀짝(SPEC-060)과 달리 패리티가 아닌 경계값(22/23) 기준 분할이다. 사전 정의
집합은 불필요 — `n <= 22`로 저번호 판정이 결정적이고 빠르다. 단, high_count는
독립 분류 대신 `6 - low_count`로 유도하여 합 불변식(low + high == 6)을 보장한다
(REQ-HL-012).

경계값 주의: 22는 저(low), 23은 고(high)다. `n <= 22` 또는 `n < 23` 어느 쪽도
동일 결과이나 SPEC 용어("1-22" / "23-45")와 일치하도록 `n <= 22`(또는
`1 <= n <= 22`) 권장. HL-03이 이 경계값을 명시적으로 검증한다.

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호를 저/고로 분류한다.

| 회차 | 본번호 | low | high | 균형(3:3)? |
|------|--------|-----|------|-----------|
| D1 | [1,3,5,7,9,11]       | 6 | 0 | 아니오 |
| D2 | [23,25,27,29,31,33]  | 0 | 6 | 아니오 |
| D3 | [1,2,3,40,42,44]     | 3 | 3 | 예 |
| D4 | [1,3,5,7,40,42]      | 4 | 2 | 아니오 |

low_count 모음: [6, 0, 3, 4]
high_count 모음: [0, 6, 3, 2]

- avg_low = (6+0+3+4)/4 = 3.25
- avg_high = (0+6+3+2)/4 = 2.75
- low_distribution = {0:1, 3:1, 4:1, 6:1}, 나머지 0..6 키(1,2,5)는 0 (합 4 ✓)
- high_distribution = {0:1, 2:1, 3:1, 6:1}, 나머지 0..6 키(1,4,5)는 0 (합 4 ✓)
- low_distribution_pct = {0:25.0, 3:25.0, 4:25.0, 6:25.0}, 나머지 0.0
- high_distribution_pct = {0:25.0, 2:25.0, 3:25.0, 6:25.0}, 나머지 0.0
- most_common_low_count = 0 (0,3,4,6이 각 1회 동률 → 가장 작은 값 0)
- most_common_high_count = 0 (0,2,3,6이 각 1회 동률 → 가장 작은 값 0)
- balanced_count = 1 (D3만 3:3), balanced_pct = 25.0

이 수치는 acceptance.md의 HL-05~HL-16에 그대로 반영됨. low_count 경계값
0(D2)과 6(D1)을 모두 포함하여 분포 범위 양 끝단을 검증하며, 균형 회차(D3)와
비균형 회차(D1/D2/D4)를 함께 커버한다. 동률 최빈값 처리(가장 작은 값 우선)도
픽스처가 동률 상황을 만들어 명시적으로 검증한다. 경계값(22/23)은 HL-03에서
별도 단위 검증한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any, Iterable


def _count_low(main_numbers: Iterable[int]) -> int:
    return sum(1 for n in main_numbers if n <= 22)
```

- `n <= 22` 판정은 O(1), 결정적, 부작용 없음.
- high_count = 6 - low_count로 유도 (REQ-HL-012).
- `zip(strict=...)` 불필요 → B905 경고 회피.
- `match/case` 미사용 → Python 3.9 호환.

분포 딕셔너리는 0..6 키를 0으로 초기화한 뒤 카운트를 누적한다:

```
low_dist = {k: 0 for k in range(7)}
high_dist = {k: 0 for k in range(7)}
# 회차 루프에서 low_dist[low_count] += 1; high_dist[high_count] += 1
```

최빈값(동률 시 작은 값 우선)은 키 0..6 오름차순으로 순회하며 첫 최댓값 채택:

```
most_common_low = max(range(7), key=lambda k: (low_dist[k], -k))
# 또는 키 0..6 오름차순 순회로 첫 최댓값 채택 — 동률 시 작은 값 우선 보장
```

주의: `max(..., key=lambda k: low_dist[k])`는 동률 시 첫 항목(가장 작은 키)을
반환하므로 range(7) 오름차순 순회와 결합하면 REQ-HL-007의 "작은 값 우선"을
충족한다.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 분기는 if/else 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고).

## 위험 요소 및 완화

- 위험: 6개 미만 본번호 회차에서 합(low+high) != 6 → REQ-HL-015로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg_low, avg_high, *_pct, balanced_pct) →
  REQ-HL-013 빈 구조 조기 반환.
- 위험: 분포 키 누락(0..6 일부만 채움) → 0으로 초기화한 7개 키 딕셔너리를
  먼저 만든 뒤 카운트 누적하여 REQ-HL-004/005/006 보장.
- 위험: 동률 최빈값을 큰 값으로 잘못 채택 → range(7) 오름차순 순회로
  REQ-HL-007의 "작은 값 우선" 보장.
- 위험: 경계값 오분류(22를 고, 23을 저로) → `n <= 22` 명시 + HL-03 단위 검증.
- 위험: base.html 네비게이션 한 곳만 수정 → 두 리스트(desktop_nav_items,
  nav_items)와 active_tab 라벨 분기까지 모두 갱신 필요.
- 위험: 기존 코어 모듈 침범 → REQ-HL-014로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `low_distribution`/`high_distribution` 키 타입: int(0..6)로 명시.
  JSON 직렬화 시 키가 문자열로 변환될 수 있으므로(JSON object key는 string),
  API 테스트에서는 문자열/정수 키 허용 여부를 명확히 할 것. 데이터 계층
  (get_high_low_stats)은 int 키 dict를 반환하고, API 계층의 직렬화 변환은
  FastAPI 기본 동작에 위임 (odd_even/decade SPEC과 동일 처리).
- 반환 타입 표기: 기존 odd_even/decade와 일관되게 `dict[str, Any]` 사용 권장.
- 균형 정의: "저==고"는 6개 본번호 기준 정확히 3:3을 의미. low_count == 3 으로
  판정하면 충분(high_count == 3과 동치).
