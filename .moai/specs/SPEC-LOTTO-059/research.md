---
id: SPEC-LOTTO-059
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-059 연구 노트 (Decade Distribution Analysis)

## 코드베이스 분석 (기존 패턴 확인)

분석 기능은 일관된 패턴을 따른다. SPEC-LOTTO-059도 동일 패턴으로 구현하며,
가장 가까운 선행 사례는 SPEC-LOTTO-057(AC 분석, get_ac_stats)과
SPEC-LOTTO-058(소수/합성수 분석, get_prime_stats)이다. 특히 구간 그룹을
리스트로 반환하고 최댓/최솟 그룹 라벨을 산출하는 구조는 끝자리 분포
(get_last_digit_stats)와 유사하다.

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은 `get_decade_stats(draws)`
  - 참고: `get_last_digit_stats`, `get_gap_stats`(SPEC-056),
    `get_ac_stats`(SPEC-057), `get_prime_stats`(SPEC-058)
- 모듈 레벨 캐시 패턴:
  - `_gap_cache`, `_ac_cache`, `_prime_cache` 등 str-키 캐시와 동일하게
    `_decade_cache: dict[str, Any] = {}`를 추가하고 `str(len(draws))`를 키로
    사용 (REQ-DC-017).
- `invalidate_cache()`에서 모든 캐시 무효화:
  - `_prime_cache.clear()` 등과 동일하게, 신규 `_decade_cache.clear()` 라인을
    invalidate_cache() 본문에 추가해야 함.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로 global 선언
    목록에 넣을 필요 없음 (`_gap_cache`/`_ac_cache`/`_prime_cache`와 동일).

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/sum-range")`, `@router.get("/stats/last-digit")`,
    `@router.get("/stats/gap")`(056), `@router.get("/stats/ac")`(057),
    `@router.get("/stats/prime")`(058)
- 본 SPEC: `@router.get("/stats/decade")` → 항상 200, 데이터 부재도 정상 응답
- 반환은 `get_decade_stats(...)` 결과 dict를 그대로 JSON 직렬화

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/last-digit")`,
  `@router.get("/stats/gap")`(056), `@router.get("/stats/ac")`(057),
  `@router.get("/stats/prime")`(058)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/decade")` → `decade.html` 렌더링

### 템플릿 — `lotto/web/templates/`

- 기존: `last_digit.html`, `gap.html`(056), `ac.html`(057), `prime.html`(058),
  `sum_range.html`, `stats.html`
- 본 SPEC: `decade.html` 신규 — 구간별 요약 표(label, size, avg_count,
  expected_avg, deviation) + 구간별 count 분포 표(0..6, 회차 수) +
  최빈/최소 구간 표시
- 서버 렌더링 전용 (JavaScript 미사용)

### 테스트 — `tests/test_decade_analysis.py`

- 신규 테스트 파일 생성
- `mypy.ini` override 목록에 `test_decade_analysis` 등록 필수
  - 기존에 `test_prime_analysis`, `test_gap_analysis`, `test_ac_analysis`,
    `test_last_digit` 등이 동일 방식으로 등록되어 있음 (저장소 사전 mypy 부채
    회피 목적)
- 데이터/API/페이지 계층별 테스트 분리 권장 (prime/ac SPEC 구조 참고)

## 구간 정의표 (1~45)

본번호는 1~45 범위에 한정되므로, 십의 자리 기준으로 5개 구간에 결정적으로
매핑한다.

| 구간   | 번호 범위 | size | expected_avg = (size/45)*6 |
|--------|-----------|------|-----------------------------|
| 01-09  | 1~9       | 9    | 1.20                        |
| 10-19  | 10~19     | 10   | 1.3333… → 1.33              |
| 20-29  | 20~29     | 10   | 1.3333… → 1.33              |
| 30-39  | 30~39     | 10   | 1.3333… → 1.33              |
| 40-45  | 40~45     | 6    | 0.80                        |

검증: 9 + 10 + 10 + 10 + 6 = 45 ✓, expected_avg 합 = (45/45)*6 = 6.0 ✓

주의: "01-09"는 0~9가 아닌 1~9이다(로또 번호에 0 없음, size 9). "40-45"는
40~49가 아닌 40~45이다(로또 최대 45, size 6). 따라서 단순히 `n // 10`으로
구간을 산출하면 9는 0대, 40~45는 4대로 가지만 라벨/size가 어긋나므로,
경계를 명시적 범위 비교로 매핑하는 것이 안전하다.

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호를 5개 구간으로 분류한다.

| 회차 | 본번호 | 01-09 | 10-19 | 20-29 | 30-39 | 40-45 | 합 |
|------|--------|-------|-------|-------|-------|-------|----|
| D1 | [3,5,12,18,25,33]   | 2 | 2 | 1 | 1 | 0 | 6 |
| D2 | [1,9,11,21,41,45]   | 2 | 1 | 1 | 0 | 2 | 6 |
| D3 | [10,19,20,29,30,39] | 0 | 2 | 2 | 2 | 0 | 6 |
| D4 | [2,4,6,8,40,42]     | 4 | 0 | 0 | 0 | 2 | 6 |

구간별 count 모음 / 평균:

- 01-09: [2,2,0,4] 합 8 → avg 2.0; expected 1.2; dev +0.8
- 10-19: [2,1,2,0] 합 5 → avg 1.25; expected 1.3333; dev -0.0833 → -0.08
- 20-29: [1,1,2,0] 합 4 → avg 1.0; expected 1.3333; dev -0.3333 → -0.33
- 30-39: [1,0,2,0] 합 3 → avg 0.75; expected 1.3333; dev -0.5833 → -0.58
- 40-45: [0,2,0,2] 합 4 → avg 1.0; expected 0.8; dev +0.2

분포 (키 0..6, 나머지 0):

- 01-09 distribution = {0:1, 2:2, 4:1}
- 10-19 distribution = {0:1, 1:1, 2:2}
- 20-29 distribution = {0:1, 1:2, 2:1}
- 30-39 distribution = {0:2, 1:1, 2:1}
- 40-45 distribution = {0:2, 2:2}

각 구간 distribution 값 합 == 4 ✓

- most_frequent_group = "01-09" (avg 2.0 최대)
- least_frequent_group = "30-39" (avg 0.75 최소)

이 수치는 acceptance.md의 DC-06~DC-15에 그대로 반영됨. count 경계값
0(여러 구간)과 4(01-09, D4)를 포함하여 분포 범위를 검증하고, 양/음 편차
(01-09 +0.8, 30-39 -0.58)를 모두 포함한다.

## deviation 반올림 주의 (REQ-DC-007)

deviation은 "반올림한 avg_count - 반올림한 expected_avg"가 아니라 **미반올림
평균에서 미반올림 기댓값을 뺀 뒤 2 decimals로 반올림**한다.

예: 10-19 → 미반올림 1.25 - 1.3333… = -0.08333… → -0.08.
만약 반올림 후 빼면(1.25 - 1.33 = -0.08) 본 픽스처에서는 우연히 같지만,
일반적으로 어긋날 수 있으므로 미반올림 기준 차이를 권장. 구현 시 expected_avg
원값(size/45*6)을 보관하여 deviation 계산에 사용하고, 표시용 expected_avg만
round(…, 2)로 출력한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any, Iterable, List, Tuple

# 고정 구간 정의: (label, lo, hi, size). hi 포함.
_DECADE_GROUPS: Tuple[Tuple[str, int, int, int], ...] = (
    ("01-09", 1, 9, 9),
    ("10-19", 10, 19, 10),
    ("20-29", 20, 29, 10),
    ("30-39", 30, 39, 10),
    ("40-45", 40, 45, 6),
)


def _group_index(n: int) -> int:
    # 명시적 범위 비교 (n // 10 사용 금지: 9, 40-45 경계 어긋남)
    for i, (_label, lo, hi, _size) in enumerate(_DECADE_GROUPS):
        if lo <= n <= hi:
            return i
    return -1  # 1~45 범위 밖 (정상 데이터에서는 발생하지 않음)
```

- 범위 비교 매핑은 결정적, O(5), 부작용 없음.
- `n // 10`을 쓰지 않는 이유: 번호 9는 9//10=0(0대), 40~45는 4//10=4(4대)로
  가서 "01-09"(1~9) / "40-45"(40~45) 라벨·size와 어긋남.
- `match/case` 미사용 → for/if 분기로 Python 3.9 호환.
- `zip(strict=...)` 불필요 → B905 경고 회피.

각 구간 distribution은 0..6 키를 0으로 초기화한 뒤 회차별 count를 누적한다:

```
dist = {k: 0 for k in range(7)}
# 회차 루프에서 dist[group_count] += 1
```

groups 리스트는 _DECADE_GROUPS 순서를 그대로 유지하여 REQ-DC-003의 고정
순서를 보장한다.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 분기는 for/if 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고).

## 위험 요소 및 완화

- 위험: `n // 10` 사용 시 구간 경계 오분류(9→0대, 40-45→4대) → 명시적 범위
  비교(_group_index)로 매핑하여 REQ-DC-013 보장.
- 위험: 6개 미만 본번호 회차에서 다섯 구간 합 != 6 → REQ-DC-016으로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg_count) → REQ-DC-014 빈 구조 조기 반환
  (avg_count=0, deviation=(0 - expected_avg)).
- 위험: 분포 키 누락(0..6 일부만 채움) → 0으로 초기화한 7개 키 딕셔너리를
  먼저 만든 뒤 카운트 누적하여 REQ-DC-008 보장.
- 위험: deviation을 반올림 값끼리 빼서 오차 발생 → 미반올림 평균/기댓값으로
  계산 후 2 decimals 반올림(REQ-DC-007).
- 위험: 동률 최댓/최솟 구간 처리 모호 → 고정 그룹 순서상 앞선 label 우선
  (REQ-DC-009).
- 위험: 기존 코어 모듈 침범 → REQ-DC-015로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `distribution` 키 타입: int(0..6)로 명시. JSON 직렬화 시 키가 문자열로
  변환될 수 있으므로(JSON object key는 string), API 테스트에서는 문자열/정수
  키 허용 여부를 명확히 할 것. 데이터 계층(get_decade_stats)은 int 키 dict를
  반환하고, API 계층의 직렬화 변환은 FastAPI 기본 동작에 위임 (prime/ac SPEC과
  동일 처리).
- 반환 타입 표기: 기존 last_digit/gap/ac/prime과 일관되게 `dict[str, Any]`
  사용 권장. groups 항목 역시 `dict[str, Any]`.
- 구간 정의 표현: 매 호출 재생성을 피하기 위해 모듈 레벨 상수 `_DECADE_GROUPS`
  튜플로 1회 정의 (위 참고).
- most_frequent_group/least_frequent_group 동률 기준: 고정 그룹 순서상 더
  앞선 label 선택으로 결정적 처리.
