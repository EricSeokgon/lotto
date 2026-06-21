# SPEC-LOTTO-103 인수 기준

보너스 번호 분석 기능의 Given-When-Then 인수 기준이다. 모든 기준은 손계산 가능한 소규모 `DrawResult` 픽스처로 결정적으로 검증한다.

---

## 핵심 함수 검증 (`get_bonus_analysis`)

### AC-BON-001: 보너스 빈도 1~45 전체 키
- **Given** 일부 번호만 보너스로 등장한 추첨 데이터가 주어졌을 때
- **When** `get_bonus_analysis(draws)`를 호출하면
- **Then** `bonus_frequency`는 1~45 모든 45개 키를 포함하고, 미출현 번호는 `0`이어야 한다 (REQ-BON-U02)

### AC-BON-002: 보너스 빈도 정확 집계
- **Given** 보너스 번호가 손계산으로 알려진 픽스처가 주어졌을 때
- **When** 분석을 수행하면
- **Then** 각 번호의 `bonus_frequency` 값이 손계산 결과와 일치해야 한다

### AC-BON-003: 보너스 비율 소수 2자리
- **Given** `total_draws`가 알려진 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** `bonus_percentage[n] == round(bonus_frequency[n] / total_draws * 100, 2)`여야 한다 (REQ-BON-U03)

### AC-BON-004: 보너스 비율 전체 키
- **Given** 추첨 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** `bonus_percentage`도 1~45 모든 키를 포함해야 한다

### AC-BON-005: Top 10 보너스 번호
- **Given** 서로 다른 빈도의 보너스 번호들이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `top_bonus`는 빈도 내림차순 상위 10개이며 각 항목은 `number`, `count`, `percentage`를 포함해야 한다 (REQ-BON-U04)

### AC-BON-006: Top 10 동률 처리
- **Given** 동일 빈도의 보너스 번호가 존재할 때
- **When** `top_bonus`를 산출하면
- **Then** 동률은 더 작은 번호가 먼저 정렬되어야 한다

### AC-BON-007: 최근 보너스 윈도우
- **Given** `total_draws`보다 작은 `recent_n`이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `recent_bonus`는 최근 `recent_n` 회차로만 한정 집계되어야 한다 (REQ-BON-U05)

### AC-BON-008: recent_count 산출
- **Given** 추첨 데이터와 `recent_n`이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `recent_count == min(recent_n, total_draws)`여야 한다

### AC-BON-009: 동시 출현 상위 5개
- **Given** 특정 보너스 번호가 여러 회차에 등장한 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** `cooccurrence[보너스번호]`는 해당 회차들의 본번호 동시출현 상위 5개(`number`, `count`)를 내림차순으로 가져야 한다 (REQ-BON-U06)

### AC-BON-010: 동시 출현 동률 처리
- **Given** 동시출현 횟수가 같은 본번호들이 있을 때
- **When** `cooccurrence`를 산출하면
- **Then** 동률은 더 작은 번호가 먼저 정렬되어야 한다

### AC-BON-011: 동시 출현은 본번호만 집계
- **Given** 보너스 번호가 등장한 회차들이 주어졌을 때
- **When** `cooccurrence`를 계산하면
- **Then** 본번호(`draw.numbers()`)만 집계하고 보너스 번호는 집계에서 제외되어야 한다 (REQ-BON-N02)

### AC-BON-012: 반환 dict 필수 키
- **Given** 임의의 유효 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** 반환 dict는 `total_draws`, `recent_n`, `recent_count`, `bonus_frequency`, `bonus_percentage`, `top_bonus`, `recent_bonus`, `cooccurrence`, `disclaimer` 키를 모두 포함해야 한다 (REQ-BON-U01)

### AC-BON-013: 결정적 결과
- **Given** 동일한 입력 데이터를 두 번 분석할 때
- **When** 두 결과를 비교하면
- **Then** 완전히 동일해야 한다 (난수·시간 의존 금지) (REQ-BON-U08)

### AC-BON-014: hot/cold/normal 판정
- **Given** 평균(100/45 ≈ 2.22%)보다 높은/낮은 비율의 번호가 있을 때
- **When** 상태를 판정하면
- **Then** 평균 초과는 "hot", 미만은 "cold", 그 외는 "normal"로 분류되어야 한다 (REQ-BON-S03)

### AC-BON-015: 면책 고지 포함
- **Given** 분석 결과가 산출되었을 때
- **When** 반환 dict를 확인하면
- **Then** 미래 예측이 아님을 명시한 `disclaimer` 문구가 포함되어야 한다 (REQ-BON-N03)

---

## 경계 및 빈 데이터 검증

### AC-BON-016: 빈 데이터 처리
- **Given** `draws=[]` 또는 `draws=None`이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `total_draws=0`, 모든 `bonus_frequency` 값 `0`, 모든 `bonus_percentage` 값 `0.0`, 빈 `top_bonus`, 빈/0채움 `recent_bonus`, 빈 `cooccurrence`를 반환해야 한다 (에러 없음) (REQ-BON-S01)

### AC-BON-017: recent_n이 전체보다 클 때
- **Given** `recent_n`이 `total_draws`보다 큰 값일 때
- **When** 분석을 수행하면
- **Then** 사용 가능한 전체 회차를 사용하고 `recent_count`를 실제 회차 수로 설정하며 에러를 내지 않아야 한다 (REQ-BON-S02)

### AC-BON-018: 본번호·보너스 분포 분리
- **Given** 본번호와 보너스 번호가 섞여 있는 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** 보너스 빈도에 본번호가 카운트되지 않고, 본번호 분포에 보너스가 카운트되지 않아야 한다 (REQ-BON-N02)

---

## API 동작 검증 (`GET /api/stats/bonus`)

### AC-BON-019: 기본 응답 및 필드
- **Given** 서버가 실행 중일 때
- **When** `GET /api/stats/bonus`를 호출하면
- **Then** HTTP 200과 함께 `bonus_frequency`, `bonus_percentage`, `top_bonus`, `recent_bonus`, `cooccurrence`, `total_draws`, `recent_n` 필드를 포함한 JSON을 반환해야 한다 (REQ-BON-E01)
- **And** `recent_n` 미지정 시 기본값 `50`을 사용해야 한다 (REQ-BON-E02)

### AC-BON-020: recent_n 파라미터 검증
- **Given** 서버가 실행 중일 때
- **When** `recent_n` 쿼리 파라미터를 지정하면
- **Then** 다음 검증 규칙을 따라야 한다 (REQ-BON-N01)
  - `recent_n=0` → HTTP 422
  - `recent_n=501` → HTTP 422
  - `recent_n=1` → HTTP 200 (경계 허용)
  - `recent_n=500` → HTTP 200 (경계 허용)
  - `recent_n=100` → HTTP 200, 최근 100회차 윈도우 반영

---

## 웹 페이지 검증 (`GET /stats/bonus`)

- [x] `GET /stats/bonus` → HTTP 200, `bonus_analysis.html` 렌더링 (top10 강조, recent_n 선택기, 번호별 테이블) (REQ-BON-E03)
- [x] `?recent_n=200` 지정 시 최근 횟수 컬럼·상태 계산에 반영 (REQ-BON-E04)
- [x] 핵심 테이블이 서버 렌더링(클라이언트 JS 비의존)으로 표시 (REQ-BON-N06)
- [x] `base.html` 기반 모든 페이지에 "보너스 분석" 내비게이션 탭 존재 (`/stats/bonus`, tab=`bonus`)

---

## 품질 게이트 (Definition of Done)

- [x] `pytest tests/test_bonus_analysis.py` — 모든 테스트(약 30개) 통과
- [x] `mypy lotto/web/data.py lotto/web/routes/api.py lotto/web/routes/pages.py` — 타입 오류 0건
- [x] ruff 린트 통과 (`# noqa` 최소화)
- [x] Python 3.9 호환성 확인 (`match`/`case`, `zip(strict=True)` 미사용)
- [x] `draw.numbers()`를 메서드로 호출 (property 오용 없음)
- [x] 면책 고지(disclaimer) API 응답·UI 모두 포함
- [x] 기존 경로·탭 키와 충돌 없음 (신규는 `/stats/bonus`, tab=`bonus`)
- [x] 코어 모듈(`lotto/models.py`, `lotto/*.py`) 미수정

---

## 테스트 실행 방법

```bash
# 전체 테스트
pytest tests/test_bonus_analysis.py -v

# 커버리지 포함
pytest tests/test_bonus_analysis.py -v --cov=lotto/web

# 특정 테스트
pytest tests/test_bonus_analysis.py::test_cooccurrence_top_5 -v
```
