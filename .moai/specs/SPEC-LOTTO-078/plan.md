# SPEC-LOTTO-078 구현 계획

## 목표

각 회차 본번호 6개에서 3개 이상 연속 묶음(triple run) 수(0~2)를 집계하고,
전체 회차 분포 통계를 API/웹 페이지로 제공한다.

## 구현 단위

### 1. 데이터 계층 (`lotto/web/data.py`)
- 모듈 상수 `_TRIPLE_RUN_KEYS = ["0", "1", "2"]` 추가
- 모듈 캐시 `_triple_run_cache: dict[str, Any] = {}` 추가
- 헬퍼 `_count_triple_runs(numbers)`: 정렬 후 연속 길이 3 이상 묶음 수 반환
- 헬퍼 `_max_run_length(numbers)`: 정렬 후 최대 연속 길이 반환
- `get_triple_run_stats(draws)`: 분포/평균/최빈/포함비율 집계, 캐시 보관
- `invalidate_cache()`에 `_triple_run_cache.clear()` 추가

### 2. API 계층 (`lotto/web/routes/api.py`)
- `GET /stats/triple_run` 엔드포인트 → `get_triple_run_stats(get_draws())`

### 3. 페이지 계층 (`lotto/web/routes/pages.py`)
- `GET /stats/triple-run` → `triple_run.html` 렌더 (active_tab="triple_run")

### 4. 템플릿 (`lotto/web/templates/triple_run.html`)
- 다크모드 Tailwind, mult4.html 패턴 준수
- 요약 카드 4개 + 분포 테이블 3행(0/1/2 그룹)

### 5. 네비게이션 (`lotto/web/templates/base.html`)
- "3연속" 링크 추가 (/stats/triple-run)

## 알고리즘

- `_count_triple_runs`: 정렬 → 인접 차 +1 누적, 끊길 때 run_len>=3 이면 묶음 +1, 마지막 run 처리
- `_max_run_length`: 정렬 → 인접 차 +1 누적하며 최댓값 추적
- 동률 최빈 처리: `_TRIPLE_RUN_KEYS` 순서대로 최댓값 키 탐색 → 작은 값 우선

## 캐시 키
- `str(len(draws))` (기존 패턴 동일), `invalidate_cache()`로 무효화

## 제약
- Python 3.9 호환 (walrus/zip strict/match 미사용)
- 기존 함수 수정 금지, 보너스 번호 제외(`draw.numbers()` 사용)
