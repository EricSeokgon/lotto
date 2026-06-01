# SPEC-LOTTO-042 구현 계획 (Implementation Plan)

## 개요

TDD(RED→GREEN→REFACTOR)로 데이터 레이어 → API → 페이지 순서로 구현한다.
기존 SPEC-LOTTO-041(range_stats) 패턴을 그대로 따른다.

## 마일스톤 (우선순위 순)

### Priority High — M1: 데이터 레이어

- `number_trend(numbers, recent_n=100, draws=_UNSET)` 구현 (`lotto/web/data.py`)
- `_UNSET` 센티넬 재사용으로 인자 생략 시 `get_draws()` 자동 로드
- 타임라인은 회차 오름차순(시간순), gap은 윈도 위치 인덱스 기반
- 빈/None draws, 잘못된 번호 입력 → 예외 없이 빈 구조
- MX 태그: `# @MX:NOTE`, `# @MX:SPEC: SPEC-LOTTO-042`
- 테스트: `tests/test_number_trend.py` (~8개)

### Priority High — M2: API 엔드포인트

- `GET /api/numbers/trend` 구현 (`lotto/web/routes/api.py`)
- 반복 가능한 `n` Query 파라미터 (`List[int]`), `recent_n` (ge=10, le=500)
- 검증: 1~3개, 각 1~45, 중복 없음 → 위반 시 422
- 데이터 부재에도 200 (data 레이어에 위임)
- 테스트: `tests/test_api_number_trend.py` (~5개)

### Priority Medium — M3: 페이지 + 네비게이션

- `GET /numbers/trend` 페이지 라우트 (`lotto/web/routes/pages.py`)
- `numbers_trend.html` 템플릿 (base.html 확장, `active_tab="numbers_trend"`)
- `base.html` 데스크톱/모바일 네비에 "번호 추이" 링크 추가
- 파라미터 없음 → 폼만, 유효 → 결과 렌더링
- 테스트: `tests/test_numbers_trend_page.py` (~4개)

## 검증 기준

- 전체 테스트 1025 + 17개 이상 통과
- Python 3.9.25 런타임 호환 (Optional/List 런타임 타입)
- 새 외부 의존성 없음
- 기존 테스트 회귀 없음
