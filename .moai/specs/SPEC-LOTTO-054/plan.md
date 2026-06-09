---
id: SPEC-LOTTO-054
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-054 구현 계획

## 기술 접근

기존 `lotto/web/data.py`의 읽기 전용 분석 함수 패턴(예: `run_backtest`,
`get_cooccurrence_matrix`)을 그대로 따른다. 핵심은 전체 추첨 이력에서 번호별
전체 빈도를 1회 계산하고, 각 윈도우 W에 대해 최근 W회차의 빈도를 계산한 뒤
회차당 정규화된 추세 델타를 산출하는 것이다.

```
get_rolling_frequency(draws, windows=(10, 20, 50, 100))
  → 전체 이력에서 freq_total[1..45] 1회 계산 (REQ-RW-022)
  → 각 W에 대해 (W ≤ total_draws인 경우만):
       최근 W회차에서 freq_window[1..45] 계산
       delta[n] = freq_window[n]/W - freq_total[n]/total_draws
       trend[n] = "상승"(>+0.02) / "하락"(<-0.02) / "보합"
       rising  = delta 내림차순 top 5 (동률 번호 오름차순)
       falling = delta 오름차순 bottom 5 (동률 번호 오름차순)
       → RollingResult
  ↓ 모듈 레벨 캐시 (windows 튜플 키)
```

- "최근 W회차"는 `draws` 리스트의 정렬 순서를 따른다. 데이터 레이어의 기존
  정렬 규약(최신 회차 식별 방식)을 그대로 사용하며, 별도 정렬 변경은 하지 않는다.
- freq/delta/trend 맵은 1~45 전 번호를 포함한다 (REQ-RW-007) — 윈도우에 없는
  번호는 freq 0, delta는 음수/0.
- 임계값 +0.02 / -0.02는 모듈 상수로 하드코딩 (REQ-RW-005, REQ-RW-017).
- W > total_draws인 윈도우는 결과에서 생략 (REQ-RW-012, REQ-RW-021).

### 데이터 레이어 (`lotto/web/data.py`)

- `_ROLLING_WINDOWS = (10, 20, 50, 100)`, `_TREND_UP = 0.02`,
  `_TREND_DOWN = -0.02`, `_TOP_RISING = 5` 등 상수 정의.
- `_rolling_cache: dict[tuple[int, ...], dict[int, Any]]` 모듈 레벨 변수 추가
  (windows 튜플로 키, `_backtest_cache`와 동일한 dict-keyed 패턴).
- `get_rolling_frequency(draws, windows=(10, 20, 50, 100))` — 전체 빈도 1회
  계산 후 윈도우별 RollingResult 산출, windows 튜플 키로 캐시.
- `invalidate_cache()`에 `_rolling_cache.clear()` 추가 (REQ-RW-015).

### 웹 페이지 레이어 (`lotto/web/routes/pages.py`)

- `GET /stats/rolling` 라우트 추가.
  - `w` Query 파라미터 없음 → 기본 윈도우 (10, 20, 50, 100) 전체 표.
  - `w=W` (지원 윈도우 중 하나) → 해당 윈도우만 포커스 표 (REQ-RW-009).
  - `from lotto.web import data as wd` 동적 import (monkeypatch 호환).
- 신규 템플릿 `stats_rolling.html` (서버사이드 렌더, JS 없음). 윈도우를 나란히
  또는 스택으로 비교하는 표, 추세 분류(상승/하락/보합) 표시.

### API 레이어 (`lotto/web/routes/api.py`)

- `GET /api/stats/rolling` 라우트 추가.
  - `windows=10,20,50,100` 파싱 → 요청 윈도우의 RollingResult JSON.
  - `windows` 없으면 기본 윈도우 사용 (REQ-RW-011).
  - `from lotto.web import data as wd` 동적 import (monkeypatch 호환).

## 마일스톤 (우선순위 기반)

### Milestone 1 (Priority High): 데이터 레이어

- `get_rolling_frequency` 구현 (전체 빈도 1회 + 윈도우별 빈도/델타/추세/상승·하락).
- 모듈 캐시(windows 튜플 키) + `invalidate_cache` 통합.
- 단위 테스트: 윈도우 빈도 정확성, 델타 정규화 계산, 임계값 분류
  (상승/하락/보합 경계), rising/falling top 5 정렬, 1~45 전 번호 커버, 보너스
  제외, 부족 윈도우 스킵, 빈 데이터, 캐시 재사용/무효화.

### Milestone 2 (Priority High): API 엔드포인트

- `GET /api/stats/rolling` (windows 파싱, 기본 윈도우 폴백).
- 단위 테스트: 다중 윈도우 응답, 기본 윈도우, 부족 윈도우 스킵, 데이터 부재 200 응답.

### Milestone 3 (Priority Medium): 웹 페이지

- `GET /stats/rolling` + `stats_rolling.html`.
- 단위 테스트: 기본 뷰(전체 윈도우), `w=W` 단일 윈도우 뷰, 빈 상태 렌더.

### Milestone 4 (Priority Low): 품질 검증

- 전체 pytest 스위트 통과, 신규 함수 커버리지 90%+.
- mypy 통과, ruff clean.
- @MX 태그 추가 (신규 공개 함수 NOTE/ANCHOR).

## 기술적 위험 및 완화

- **위험: 윈도우 "최근 W회차" 방향 혼동** — 정렬이 최신→과거인지 과거→최신인지에
  따라 슬라이스가 달라짐. 완화: 데이터 레이어의 기존 정렬 규약을 명시적으로 따르고
  단위 테스트로 "최근 W회차" 선택을 검증.
- **위험: 부동소수 경계 처리** — 델타가 정확히 +0.02/-0.02일 때 분류. 완화:
  REQ-RW-005에 따라 경계값은 "보합"(엄격 부등호 > / <)으로 처리하고 테스트로 고정.
- **위험: 부족 윈도우 에러** — 가용 회차 < W일 때 0 나눗셈/스킵 누락. 완화:
  W > total_draws 윈도우를 결과에서 생략하고, 빈 데이터 시 빈 매핑 반환 + 테스트.
- **위험: 캐시 무효화 누락** — 신규 데이터 적재 시 stale 결과. 완화:
  `invalidate_cache()`에 명시적으로 `_rolling_cache.clear()` 추가.
- **위험: Python 3.9 호환** — `zip(strict=...)` 등 3.10+ 문법 회피. 완화:
  인덱스 기반 루프 사용, 신규 외부 의존성 없음.

## 의존성

- 선행: 없음 (기존 `DrawResult`, `get_draws`, `invalidate_cache` 재사용).
- 관련: SPEC-LOTTO-038(`/stats` 전체 통계), SPEC-LOTTO-042(`/numbers/trend`
  장기 추세). 본 SPEC은 여러 최근 윈도우 간 빈도 비교에 초점을 두어 차별화된다.
