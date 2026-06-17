---
id: SPEC-LOTTO-053
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-053 구현 계획

## 기술 접근

기존 `lotto/web/data.py`의 읽기 전용 분석 함수 패턴(예: `number_affinity`,
`run_backtest`)을 그대로 따른다. 핵심은 전체 추첨 이력을 1회 순회하며 각 회차의
본번호 6개에서 C(6,2)=15개 쌍을 추출해 동시 출현 행렬을 누적하는 것이다.

```
get_cooccurrence_matrix(draws)
  → 각 draw에 대해 sorted nums의 (i, j), i<j 쌍 15개 누적 → {(i,j): count}
  ↓ 모듈 레벨 캐시 (matrix + total_draws)
get_top_cooccurrences(draws, n=20)   → 행렬에서 count 내림차순 top n + pct
get_number_partners(draws, number, top_k=10) → 행렬에서 number 포함 쌍 추출 + pct
```

- pct는 `count / total_draws × 100` (소수 2자리). total_draws=0이면 0.0.
- top/partner 정렬: count 내림차순, 동률은 쌍/번호 오름차순(결정론적 순서).
- 캐시는 기존 `_draws_cache`/`_backtest_cache`와 동일하게 모듈 레벨 변수로 두고,
  `invalidate_cache()`에 클리어 로직을 추가한다 (REQ-CO-013).

### 데이터 레이어 (`lotto/web/data.py`)

- `_COOCCURRENCE_TOP_N = 20`, `_PARTNER_TOP_K = 10` 등 상수 정의.
- `_cooccurrence_cache` 모듈 레벨 변수 추가 (행렬 + total_draws 보관).
- `get_cooccurrence_matrix(draws)` — 단일 O(D×15) 패스로 행렬 구성, 캐시.
- `get_top_cooccurrences(draws, n=20)` — 행렬 파생, [{pair, count, pct}].
- `get_number_partners(draws, number, top_k=10)` — number 포함 쌍에서 파트너
  추출, [{number, count, pct}].
- `invalidate_cache()`에 `_cooccurrence_cache = None` 추가.

### 웹 페이지 레이어 (`lotto/web/routes/pages.py`)

- `GET /numbers/cooccurrence` 라우트 추가.
  - [HARD] `/numbers/{number}` 동적 라우트보다 **먼저** 등록해야
    "cooccurrence"가 number로 캡처되지 않는다 (affinity/cycle과 동일 주의).
  - `number` Query 파라미터 없음 → 상위 20개 쌍 표.
  - `number=N` (1~45) → 해당 번호의 상위 10개 파트너 표.
  - `from lotto.web import data as wd` 동적 import (monkeypatch 호환).
- 신규 템플릿 `numbers_cooccurrence.html` (서버사이드 렌더, JS 없음).

### API 레이어 (`lotto/web/routes/api.py`)

- `GET /api/numbers/cooccurrence` 라우트 추가.
  - `number` 있으면 → 해당 번호 top_k 파트너.
  - `number` 없으면 → 상위 top 쌍 (기본 20).
  - `from lotto.web import data as wd` 동적 import (monkeypatch 호환).

## 마일스톤 (우선순위 기반)

### Milestone 1 (Priority High): 데이터 레이어

- `get_cooccurrence_matrix`, `get_top_cooccurrences`, `get_number_partners` 구현.
- 모듈 캐시 + `invalidate_cache` 통합.
- 단위 테스트: 행렬 정확성, i<j 단일 집계, 보너스 제외, pct 계산, 빈 데이터,
  캐시 재사용/무효화.

### Milestone 2 (Priority High): API 엔드포인트

- `GET /api/numbers/cooccurrence` (number 유무 분기).
- 단위 테스트: number 유/무, top 파라미터, 데이터 부재 200 응답.

### Milestone 3 (Priority Medium): 웹 페이지

- `GET /numbers/cooccurrence` + `numbers_cooccurrence.html`.
- 라우트 등록 순서 (`/numbers/{number}`보다 먼저) 검증.
- 단위 테스트: 기본 뷰(상위 쌍), number 뷰(파트너), 빈 상태 렌더.

### Milestone 4 (Priority Low): 품질 검증

- 전체 pytest 스위트 통과, 신규 함수 커버리지 90%+.
- mypy 통과, ruff clean.
- @MX 태그 추가 (신규 공개 함수 NOTE/ANCHOR).

## 기술적 위험 및 완화

- **위험: 라우트 캡처 충돌** — `/numbers/cooccurrence`가 `/numbers/{number}`에
  잡힐 수 있음. 완화: affinity/cycle 라우트와 동일하게 동적 라우트보다 먼저 등록.
- **위험: 캐시 무효화 누락** — 신규 데이터 적재 시 stale 행렬. 완화:
  `invalidate_cache()`에 명시적으로 `_cooccurrence_cache` 클리어 추가.
- **위험: 이중 집계** — 쌍 순회 시 (i, j)와 (j, i) 중복. 완화: 정렬된 nums에서
  `for i in range(len): for j in range(i+1, len)` 구조로 i<j 보장 + 테스트.
- **위험: Python 3.9 호환** — `zip(strict=...)` 등 3.10+ 문법 회피. 완화:
  인덱스 기반 중첩 루프 사용, 신규 외부 의존성 없음.

## 의존성

- 선행: 없음 (기존 `DrawResult`, `get_draws`, `invalidate_cache` 재사용).
- 관련: SPEC-LOTTO-044(번호 궁합 — 추천 조합), SPEC-LOTTO-030(번호 상세
  통계 — companion_top5). 본 SPEC은 원시 쌍 행렬에 초점을 두어 차별화된다.
