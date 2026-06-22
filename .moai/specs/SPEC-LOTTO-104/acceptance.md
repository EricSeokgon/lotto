# SPEC-LOTTO-104 인수 기준

번호 출현 주기(recency / interval) 분석 기능의 Given-When-Then 인수 기준이다. 모든 기준은 손계산 가능한 소규모 `DrawResult` 픽스처로 결정적으로 검증한다.

## 검증용 기준 픽스처 (손계산)

회차 오름차순 5회차 픽스처(본번호만 표기, 보너스는 분석 무관하므로 임의):

| 회차 idx | drwNo | 본번호 |
|----------|-------|--------|
| 0 | 1 | 1, 2, 3, 4, 5, 6 |
| 1 | 2 | 1, 7, 8, 9, 10, 11 |
| 2 | 3 | 2, 7, 12, 13, 14, 15 |
| 3 | 4 | 1, 16, 17, 18, 19, 20 |
| 4 | 5 | 2, 21, 22, 23, 24, 25 |

`total_draws = 5`, `last_idx = 4`, 가장 최근 회차(idx 4) 본번호 `recent = [2, 21, 22, 23, 24, 25]`.

손계산 결과(핵심 번호):

- 번호 1: 출현 idx [0, 1, 3] → `appearance_count=3`, `last_seen_ago = 4-3 = 1`, gaps=[1-0, 3-1]=[1, 2] → `avg_interval=1.5`, `max_interval=2`, `min_interval=1`.
- 번호 2: 출현 idx [0, 2, 4] → `appearance_count=3`, `last_seen_ago = 4-4 = 0`, gaps=[2-0, 4-2]=[2, 2] → `avg_interval=2.0`, `max_interval=2`, `min_interval=2`.
- 번호 7: 출현 idx [1, 2] → `appearance_count=2`, `last_seen_ago = 4-2 = 2`, gaps=[2-1]=[1] → `avg_interval=1.0`, `max_interval=1`, `min_interval=1`.
- 번호 6: 출현 idx [0] → `appearance_count=1`, `last_seen_ago = 4-0 = 4`, gaps=[] → `avg_interval=None`, `max_interval=None`, `min_interval=None`.
- 번호 30: 미출현 → `appearance_count=0`, `last_seen_ago=None`, `avg/max/min=None`.

연체(overdue) 순위(상위): 미출현 번호(last_seen_ago=None)가 최상단(작은 번호 우선) → 그다음 `last_seen_ago=4`인 단발 출현 번호들 → ... 본번호 1(=1), 2(=0)는 하위.

---

## 핵심 함수 검증 (`get_recency_analysis`)

### AC-REC-001: numbers 1~45 전체 항목
- **Given** 일부 번호만 등장한 추첨 데이터가 주어졌을 때
- **When** `get_recency_analysis(draws)`를 호출하면
- **Then** `numbers`는 1~45 모든 45개 항목을 번호 오름차순으로 포함해야 한다 (REQ-REC-U02)

### AC-REC-002: 항목 필수 키
- **Given** 추첨 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** 각 `numbers` 항목은 `number`, `last_seen_ago`, `avg_interval`, `max_interval`, `min_interval`, `appearance_count` 키를 모두 포함해야 한다 (REQ-REC-U02)

### AC-REC-003: last_seen_ago 정확 계산
- **Given** 기준 픽스처가 주어졌을 때
- **When** 분석을 수행하면
- **Then** 번호 1의 `last_seen_ago == 1`, 번호 7의 `last_seen_ago == 2`여야 한다 (REQ-REC-U03)

### AC-REC-004: 최근 회차 출현 시 0
- **Given** 가장 최근 회차에 등장한 번호가 있을 때
- **When** 분석을 수행하면
- **Then** 그 번호의 `last_seen_ago == 0`이어야 한다 (번호 2 = 0) (REQ-REC-U03)

### AC-REC-005: 미출현 시 None
- **Given** 한 번도 등장하지 않은 번호(예: 30)가 있을 때
- **When** 분석을 수행하면
- **Then** 그 번호의 `last_seen_ago`는 `None`이어야 한다 (REQ-REC-U03)

### AC-REC-006: avg_interval은 연속 간격 평균
- **Given** 번호 1이 idx [0,1,3]에 등장할 때(gaps=[1,2])
- **When** 분석을 수행하면
- **Then** `avg_interval == 1.5`여야 한다(= mean([1,2]), `total_draws/count`가 아님) (REQ-REC-U04)

### AC-REC-007: avg_interval 소수 2자리
- **Given** 간격 평균이 무한소수인 데이터가 주어졌을 때
- **When** 분석을 수행하면
- **Then** `avg_interval == round(mean(gaps), 2)`여야 한다 (REQ-REC-U04)

### AC-REC-008: max/min interval 계산
- **Given** 번호 1(gaps=[1,2])이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `max_interval == 2`, `min_interval == 1`이어야 한다 (REQ-REC-U05)

### AC-REC-009: 1회 출현 시 간격 None
- **Given** 정확히 1회만 등장한 번호(예: 6)가 있을 때
- **When** 분석을 수행하면
- **Then** `avg_interval`, `max_interval`, `min_interval`은 모두 `None`이고 `appearance_count == 1`, `last_seen_ago == 4`여야 한다 (REQ-REC-S02, REQ-REC-U04, REQ-REC-U05)

### AC-REC-010: appearance_count 정확 집계
- **Given** 손계산된 픽스처가 주어졌을 때
- **When** 분석을 수행하면
- **Then** 번호 1·2의 `appearance_count == 3`, 번호 7 == 2여야 한다 (REQ-REC-U06)

### AC-REC-011: appearance_count는 본번호만
- **Given** 보너스로만 등장하고 본번호로는 안 나온 번호가 있을 때
- **When** 분석을 수행하면
- **Then** 그 번호의 `appearance_count`에 보너스 출현이 포함되지 않아야 한다 (REQ-REC-N02)

### AC-REC-012: overdue 정렬 (last_seen_ago 내림차순)
- **Given** 서로 다른 last_seen_ago를 가진 번호들이 있을 때
- **When** `overdue`를 산출하면
- **Then** `last_seen_ago` 내림차순(가장 오래 미출현 우선) 상위 `top_n`이어야 한다 (REQ-REC-U07)

### AC-REC-013: overdue에서 미출현(None) 최우선
- **Given** 미출현 번호와 출현 번호가 섞여 있을 때
- **When** `overdue`를 산출하면
- **Then** `last_seen_ago=None`인 번호가 최상단에 위치해야 한다 (REQ-REC-U07)

### AC-REC-014: overdue 동률 시 작은 번호 우선
- **Given** 동일한 last_seen_ago(또는 동일 미출현)인 번호들이 있을 때
- **When** `overdue`를 산출하면
- **Then** 더 작은 번호가 먼저 정렬되어야 한다 (REQ-REC-U07)

### AC-REC-015: overdue 크기 = top_n
- **Given** `top_n=3`이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `overdue`의 길이는 3이어야 한다 (REQ-REC-U07, REQ-REC-E04)

### AC-REC-016: recent는 최근 회차 본번호
- **Given** 기준 픽스처가 주어졌을 때
- **When** 분석을 수행하면
- **Then** `recent == [2, 21, 22, 23, 24, 25]`(최근 회차 본번호 오름차순)여야 한다 (REQ-REC-U08)

### AC-REC-017: 반환 dict 필수 키 + 결정성
- **Given** 동일한 입력 데이터를 두 번 분석할 때
- **When** 두 결과를 비교하면
- **Then** 반환 dict는 `numbers`, `overdue`, `recent`, `total_draws`, `top_n`, `disclaimer` 키를 모두 포함하고 두 결과가 완전히 동일해야 한다 (REQ-REC-U01, REQ-REC-U09)

### AC-REC-018: 면책 고지 포함
- **Given** 분석 결과가 산출되었을 때
- **When** 반환 dict를 확인하면
- **Then** 미래 예측이 아님(도박사의 오류 경계 포함)을 명시한 `disclaimer` 문구가 포함되어야 한다 (REQ-REC-N03)

---

## 경계 및 빈 데이터 검증

### AC-REC-019: 빈/None 데이터 처리
- **Given** `draws=[]` 또는 `draws=None`이 주어졌을 때
- **When** 분석을 수행하면
- **Then** `total_draws=0`, 45개 항목 모두 `last_seen_ago=None`·`avg_interval=None`·`max_interval=None`·`min_interval=None`·`appearance_count=0`, 빈 `overdue`, 빈 `recent`, `disclaimer` 포함을 반환해야 한다 (에러 없음) (REQ-REC-S01)

---

## API 동작 검증 (`GET /api/stats/recency`)

### AC-REC-020: 기본 응답·필드 및 top_n 검증
- **Given** 서버가 실행 중일 때
- **When** `GET /api/stats/recency`를 호출하면
- **Then** HTTP 200과 함께 `numbers`, `overdue`, `recent`, `total_draws`, `top_n`, `disclaimer` 필드를 포함한 JSON을 반환해야 한다 (REQ-REC-E01)
- **And** `top_n` 미지정 시 기본값 `10`을 사용해야 한다 (REQ-REC-E02)
- **And** 다음 검증 규칙을 따라야 한다 (REQ-REC-N01)
  - `top_n=0` → HTTP 422
  - `top_n=46` → HTTP 422
  - `top_n=1` → HTTP 200 (경계 허용)
  - `top_n=45` → HTTP 200 (경계 허용)

---

## 웹 페이지 검증 (`GET /stats/recency`)

- [ ] `GET /stats/recency` → HTTP 200, `recency_analysis.html` 렌더링 (45번호 테이블: 번호/last_seen_ago/avg_interval/appearance_count, overdue 강조, recent 배지) (REQ-REC-E03)
- [ ] `?top_n=20` 지정 시 overdue 목록 크기에 반영 (REQ-REC-E04)
- [ ] `last_seen_ago > avg_interval * 1.5`인 번호가 시각적으로 overdue 강조 (REQ-REC-S03)
- [ ] 핵심 테이블이 서버 렌더링(클라이언트 JS 비의존)으로 표시 (REQ-REC-N06)
- [ ] `base.html` 기반 모든 페이지에 "주기 분석" 내비게이션 탭 존재 (`/stats/recency`, tab=`recency`)
- [ ] 기존 "당첨 주기"(`/numbers/cycle`, tab=`cycle`) 탭과 별개로 공존 (충돌 없음)

---

## 품질 게이트 (Definition of Done)

- [ ] `pytest tests/test_recency_analysis.py` — 모든 테스트(약 25개) 통과
- [ ] `mypy lotto/web/data.py lotto/web/routes/api.py lotto/web/routes/pages.py` — 타입 오류 0건
- [ ] ruff 린트 통과 (`# noqa` 최소화)
- [ ] Python 3.9 호환성 확인 (`match`/`case`, `zip(strict=True)` 미사용)
- [ ] `draw.numbers()`를 메서드로 호출 (property 오용 없음)
- [ ] `drwNo` 필드 사용 (외부 명세 `draw_no` 매핑 확인)
- [ ] 면책 고지(disclaimer) API 응답·UI 모두 포함
- [ ] 기존 경로·탭 키와 충돌 없음 (신규는 `/stats/recency`, tab=`recency`)
- [ ] SPEC-047 `cycle_analysis` 미수정·미재구현 확인
- [ ] 코어 모듈(`lotto/models.py`, `lotto/*.py`) 미수정

---

## 테스트 실행 방법

```bash
# 전체 테스트
pytest tests/test_recency_analysis.py -v

# 커버리지 포함
pytest tests/test_recency_analysis.py -v --cov=lotto/web

# 특정 테스트
pytest tests/test_recency_analysis.py::test_avg_interval_uses_consecutive_gaps -v
```
