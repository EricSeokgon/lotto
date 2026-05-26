# SPEC-LOTTO-013: 갭분석·앙상블 전략 및 gap_rounds 테스트 커버리지

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-013 |
| 상태 | DONE |
| 작성일 | 2026-05-26 |
| 완료 커밋 | f45ac98 |

## 목적

SPEC-LOTTO-012에서 추가된 갭분석·앙상블 전략 구현 경로와 `analyze_page`의 `gap_rounds` 계산 분기에 대한 테스트 커버리지를 확보한다.

## 요구사항

### REQ-013-001: _gap_scores() 동작 검증
- WHEN `_gap_scores()` 호출 시 THEN 1~45 모든 번호에 대해 점수를 반환해야 한다
- WHEN 음수 스트릭이 있을 때 THEN 정규화된 0.0~1.0 범위의 점수를 반환해야 한다
- WHEN 모든 스트릭이 0일 때 THEN 모든 점수가 0.5여야 한다
- WHEN 모든 스트릭이 양수일 때 THEN gap_raw가 0이므로 span=0 → 0.5여야 한다

### REQ-013-002: 갭분석·앙상블 전략 경로 검증
- WHEN 갭분석 전략으로 추천 시 THEN 유효한 6개 번호 세트를 반환해야 한다
- WHEN 앙상블 전략으로 추천 시 THEN 유효한 6개 번호 세트를 반환해야 한다
- WHEN `recommend(count=10)` 호출 시 THEN 10가지 전략이 한 번씩 순환되어야 한다
- WHEN `recommend(count=20)` 호출 시 THEN 10가지 전략이 각 2회 순환되어야 한다
- WHEN 갭분석 전략 사용 시 THEN candidates는 상위 22개 번호여야 한다
- WHEN 앙상블 전략 사용 시 THEN candidates는 상위 25개 번호여야 한다
- WHEN 갭분석 전략 사용 시 THEN gap 가중치(0.70)로 미출현 번호를 우선해야 한다
- WHEN 앙상블 전략 사용 시 THEN 내부 가중치는 (0.25, 0.25, 0.25, 0.25)여야 한다

### REQ-013-003: analyze_page gap_rounds 계산 분기 검증
- WHEN stats가 None일 때 THEN gap_rounds는 빈 딕셔너리여야 한다
- WHEN consecutive_pattern이 None일 때 THEN gap_rounds는 빈 딕셔너리여야 한다
- WHEN current_streak가 빈 딕셔너리일 때 THEN gap_rounds는 빈 딕셔너리여야 한다
- WHEN streak 값이 음수일 때 THEN gap_rounds에 미출현 회차 수가 채워져야 한다
- WHEN streak 값이 양수일 때 THEN gap_rounds[num] = 0이어야 한다
- WHEN streak 값에 TypeError 발생 시 THEN gap_rounds[num] = 0으로 처리되어야 한다
- WHEN streak 값에 ValueError 발생 시 THEN gap_rounds[num] = 0으로 처리되어야 한다

## 구현 내역

### 신규 테스트 파일

**`tests/test_recommender_strategies.py`** (15 tests)
- `TestGapScores`: `_gap_scores()` 4개 테스트 + 반환값 45개 키 검증 1개
- `TestGapAndEnsembleStrategies`: 갭분석·앙상블 전략 전체 경로 10개 테스트

**`tests/test_pages_gap_rounds.py`** (7 tests)
- `TestAnalyzePageGapRounds`: `analyze_page` gap_rounds 계산 7개 분기 검증

### 주요 수정

ruff 린트 규칙 준수:
- C420: `{k: v for k in range()}` → `dict.fromkeys(range(), v)` 변환
- I001: import 블록 정렬
- F401: 미사용 import 제거

## 커버리지 영향

| 파일 | 이전 | 이후 |
|------|------|------|
| `lotto/recommender.py` | 98% | 98% (신규 경로 커버) |
| `lotto/web/routes/pages.py` | 98% | 98% (gap_rounds 분기 커버) |
| **전체** | 98.37% | 98.37% |

총 테스트 수: 433 → 455 (+22)
