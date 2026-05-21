# SPEC-LOTTO-006 인수 기준 (Acceptance Criteria)

## REQ-PAGE-001: limit/offset 쿼리 파라미터

### AC-PAGE-001-1: 기본 페이지네이션
- **Given**: 200회차 이상의 데이터가 존재함
- **When**: 클라이언트가 `GET /api/draws`를 파라미터 없이 호출
- **Then**: 응답 본문에 `limit=50`, `offset=0` 필드가 포함되고 `items` 길이가 50 이하

### AC-PAGE-001-2: 커스텀 limit
- **Given**: 데이터가 충분히 존재
- **When**: 클라이언트가 `GET /api/draws?limit=10`을 호출
- **Then**: 응답의 `limit=10`이며 `items` 길이가 10 이하

### AC-PAGE-001-3: offset 적용
- **When**: 클라이언트가 `GET /api/draws?offset=5`를 호출
- **Then**: 응답의 `offset=5`이며 6번째 회차부터 반환

### AC-PAGE-001-4: limit 상한 검증
- **When**: 클라이언트가 `GET /api/draws?limit=999`를 호출
- **Then**: HTTP 422 (FastAPI Query `le=200` 검증)

## REQ-PAGE-002: 페이지네이션 응답 구조

### AC-PAGE-002-1: 응답 키 검증
- **When**: `GET /api/draws` 호출
- **Then**: 응답 JSON에 `total`, `limit`, `offset`, `items` 4개 키가 모두 존재

### AC-PAGE-002-2: total 의미
- **Given**: 데이터 1224회차 존재
- **When**: `GET /api/draws?limit=10`
- **Then**: `total=1224`, `len(items)=10`

## REQ-PAGE-003: 회차 범위 필터

### AC-PAGE-003-1: from_round + to_round
- **When**: `GET /api/draws?from_round=10&to_round=20`
- **Then**: 모든 `items[i].drwNo`가 10 이상 20 이하

### AC-PAGE-003-2: from_round 단독
- **When**: `GET /api/draws?from_round=50`
- **Then**: 모든 `items[i].drwNo >= 50`

### AC-PAGE-003-3: to_round 단독
- **When**: `GET /api/draws?to_round=30`
- **Then**: 모든 `items[i].drwNo <= 30`

## REQ-PAGE-004: 빈 결과 회피

### AC-PAGE-004-1
- **When**: `GET /api/draws?from_round=9999` (데이터 범위 밖)
- **Then**: HTTP 200, `total=0`, `items=[]`

## REQ-FILTER-001: 전략 필터

### AC-FILTER-001-1: 전략 일치
- **When**: `GET /api/recommendations?strategy=고빈도&count=5`
- **Then**: 응답의 모든 항목이 `strategy_label == "고빈도"`

### AC-FILTER-001-2: count과 함께 작동
- **When**: `GET /api/recommendations?strategy=저빈도&count=3`
- **Then**: 응답이 리스트이고, 길이가 3 이하이며, 각 항목의 `strategy_label == "저빈도"`

## REQ-FILTER-002: 무필터 호환성

### AC-FILTER-002-1
- **When**: `GET /api/recommendations` (strategy 파라미터 없음)
- **Then**: 기존과 동일하게 8개 전략 순환 반환 동작 유지

## REQ-FILTER-003: 잘못된 전략 회피

### AC-FILTER-003-1
- **When**: `GET /api/recommendations?strategy=존재하지않는전략`
- **Then**: HTTP 200, 빈 리스트 `[]` 반환 (422나 500이 아님)

## 검증 절차

```bash
cd /home/sklee/moai/lotto
python3.9 -m pytest tests/test_api_pagination.py tests/test_api_strategy_filter.py -v
python3.9 -m pytest tests/ -q --tb=no
```

### 합격 기준
- 신규 12개 테스트 모두 통과
- 기존 348개 테스트 모두 통과 (총 360개)
- 전체 커버리지 ≥ 95%
