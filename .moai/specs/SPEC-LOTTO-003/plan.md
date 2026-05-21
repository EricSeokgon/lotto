# SPEC-LOTTO-003 Plan

## 개요

3개 핵심 모듈에 작은 폭의 추가로 SPEC을 달성한다. 모든 외부 함수 시그니처는 변경하지 않는다.

## 모듈별 변경 사항

### 1. `lotto/models.py`
- `Statistics`에 `bonus_frequency: FrequencyStats = Field(default_factory=FrequencyStats)` 추가
- `FrequencyStats` 재사용 (이미 존재)

### 2. `lotto/analyzer.py`
- `compute_bonus_frequency(draws)` private/public 헬퍼 추가
- `analyze()` 마지막에 `bonus_frequency` 채워서 `Statistics(...)` 생성자에 전달

### 3. `lotto/config.py`
- `bonus_avoidance_weight: float = 0.0` 필드 추가
- 환경 변수: `LOTTO_BONUS_AVOIDANCE_WEIGHT`, 잘못된 값 시 명확한 ValueError

### 4. `lotto/recommender.py`
- `compute_scores()`에서 `settings.bonus_avoidance_weight > 0` 일 때 보너스 빈도 정규화 → 페널티 차감
- 가중치 = 0 (기본)이면 분기를 진입하지 않아 기존 점수 그대로

### 5. `lotto/scraper.py`
- 모듈 로거 추가: `logger = logging.getLogger(__name__)`
- `_parse_draw_row` 내 `except (ValueError, IndexError)` 경로에 `logger.warning(...)` 추가
- 행 길이 부족 시에도 `logger.warning(...)` 추가 (현재는 무음 None)

### 6. 신규 테스트
- `tests/test_bonus_stats.py` — REQ-BONUS-001, REQ-BONUS-002
- `tests/test_bonus_api.py` — REQ-BONUS-003
- `tests/test_scraper_edge.py` — REQ-SCRAPER-001, REQ-SCRAPER-002
- `tests/test_bonus_avoidance.py` — REQ-BONUS-004

## TDD 단계

### Phase 1 (RED → GREEN): Statistics + analyzer
1. test_bonus_stats: bonus_frequency 필드 존재 / 정확성
2. models.py 수정
3. analyzer.py 수정

### Phase 2 (RED → GREEN): API 응답
1. test_bonus_api: GET /api/stats 응답에 bonus_frequency 포함
2. (자동) Pydantic이 처리하므로 코드 변경 불필요할 가능성

### Phase 3 (RED → GREEN): 스크래퍼 로깅
1. test_scraper_edge: 5개 엣지 케이스 + scrape_all None 스킵
2. scraper.py에 로깅 추가

### Phase 4 (RED → GREEN): 보너스 회피 가중치
1. test_bonus_avoidance: 기본 0.0에서 회귀 없음 + 가중치 > 0에서 페널티 검증
2. config.py + recommender.py 수정

## 안전성

- 256개 기존 테스트 + 신규 테스트 모두 GREEN 시점에서만 다음 페이즈 진행
- 함수 시그니처 변경 금지
- Python 3.9 호환 (zip(strict=True) 미사용)
- 모든 신규 코드 한국어 주석 (language.yaml: code_comments=ko)
