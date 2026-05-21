# SPEC-LOTTO-003 Acceptance Criteria

Given-When-Then 시나리오로 각 REQ의 통과 조건을 명시한다.

---

## REQ-BONUS-001 — Statistics 모델 확장

### Scenario 1: 빈 Statistics에 bonus_frequency 존재

- **Given** `from lotto.models import Statistics`
- **When** `stats = Statistics()`
- **Then** `stats.bonus_frequency` 가 존재한다
- **And** `isinstance(stats.bonus_frequency, FrequencyStats)` 가 True 다
- **And** `stats.bonus_frequency.absolute == {}` 이다

### Scenario 2: JSON 직렬화 시 보너스 빈도 포함

- **Given** `stats = Statistics()`
- **When** `data = stats.model_dump()`
- **Then** `"bonus_frequency"` 키가 data에 존재한다

---

## REQ-BONUS-002 — analyzer가 보너스 빈도 채움

### Scenario 1: 3회차 mini 데이터 — 보너스 5, 3, 7 1회씩 등장

- **Given** `mini_draws` (보너스: 5, 3, 7)
- **When** `stats = LottoAnalyzer().analyze(mini_draws)`
- **Then** `stats.bonus_frequency.absolute[5] == 1`
- **And** `stats.bonus_frequency.absolute[3] == 1`
- **And** `stats.bonus_frequency.absolute[7] == 1`
- **And** `stats.bonus_frequency.absolute[1] == 0` (보너스로 등장 안 함)

### Scenario 2: 전체 합계 == 회차 수

- **Given** N 회차 데이터
- **When** `analyze()` 호출
- **Then** `sum(stats.bonus_frequency.absolute.values()) == N`

### Scenario 3: 상대 빈도 합계 ≈ 1.0

- **Given** N 회차 데이터, N ≥ 1
- **When** `analyze()` 호출
- **Then** `abs(sum(stats.bonus_frequency.relative.values()) - 1.0) < 1e-6`

---

## REQ-BONUS-003 — API 응답에 bonus_frequency 포함

### Scenario 1: GET /api/stats 응답 키 검증

- **Given** stats 데이터(보너스 포함)가 존재
- **When** `client.get("/api/stats")` 호출
- **Then** 응답 상태 == 200
- **And** 응답 JSON에 `"bonus_frequency"` 키 존재
- **And** `response.json()["bonus_frequency"]` 는 `{"absolute": {...}, "relative": {...}}` 구조

---

## REQ-BONUS-004 — 보너스 회피 가중치

### Scenario 1: 기본 가중치 0.0에서 동작 회귀 없음

- **Given** `settings.bonus_avoidance_weight == 0.0` (기본)
- **When** `LottoRecommender(stats).compute_scores()` 호출 (보너스 빈도 데이터 존재)
- **Then** 점수 결과가 가중치 분기 없을 때와 동일

### Scenario 2: 양의 가중치에서 보너스 빈도 높은 번호 페널티

- **Given** `settings.bonus_avoidance_weight = 0.5`, 번호 7의 보너스 빈도가 가장 높음
- **When** `compute_scores()` 호출
- **Then** 번호 7의 점수가 가중치 0일 때보다 낮음

---

## REQ-SCRAPER-001 — 파싱 안정성

### Scenario 1: 11개 미만 컬럼

- **Given** `row = ["1130회", "2024.07.27", "7"]`
- **When** `_parse_draw_row(row)` 호출
- **Then** `None` 반환
- **And** 예외 발생 없음
- **And** `logger.warning` 한 번 호출됨

### Scenario 2: 비정수 번호 셀

- **Given** `row = ["1130회", "2024.07.27", "7", "21억", "abc", "19", "21", "25", "27", "28", "40"]`
- **When** `_parse_draw_row(row)` 호출
- **Then** `None` 반환
- **And** 예외 발생 없음

### Scenario 3: 잘못된 날짜 형식

- **Given** `row = ["1130회", "2024-07-27", ...]`
- **When** `_parse_draw_row(row)` 호출
- **Then** `None` 반환
- **And** 예외 발생 없음

### Scenario 4: 비정수 보너스

- **Given** 보너스 셀이 `"X"` 인 행
- **When** `_parse_draw_row(row)` 호출
- **Then** `None` 반환

### Scenario 5: 비정수 회차

- **Given** 회차 셀이 `"없음"` 인 행
- **When** `_parse_draw_row(row)` 호출
- **Then** `None` 반환

---

## REQ-SCRAPER-002 — scrape_all None 스킵

### Scenario 1: <table> 미발견

- **Given** HTML에 `<table>` 태그 없음
- **When** `scrape_all()` 호출 (mocked HTTP)
- **Then** `[]` 반환
- **And** 예외 발생 없음

### Scenario 2: 유효+무효 행 혼재

- **Given** HTML이 헤더 2행 + 유효 1행 + 무효(짧은) 1행 구성
- **When** `scrape_all()` 호출
- **Then** 결과 길이 == 1 (유효 행만)
- **And** 예외 발생 없음
