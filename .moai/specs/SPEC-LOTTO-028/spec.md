---
id: SPEC-LOTTO-028
version: 0.1.0
status: Planned
created: 2026-05-29
updated: 2026-05-29
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-028: 번호 조합 분석기

## HISTORY

- 2026-05-29 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 분석 / 추천 |
| 영향 범위 | API (`POST /api/analyze-combination`), 웹 페이지 (`/recommend`) |
| 의존 SPEC | SPEC-LOTTO-002(분석), SPEC-LOTTO-026(트렌드 분석) |
| 신규 모듈 | `lotto/analyzer.py` 확장 또는 조합 분석 헬퍼 |

## 배경 및 목적

현재 `/recommend` 페이지는 전략별로 시스템이 생성한 추천 번호만 제공한다.
사용자가 직접 떠올린 번호 조합(예: 생일, 기념일 등)이 통계적으로
어떤 특성을 가지는지 확인할 방법이 없다.

본 SPEC은 사용자가 입력한 6개 번호 조합에 대해 과거 당첨 데이터 기반의
다각도 통계(합계, 홀짝, 번호대 분포, 연속성, 출현 빈도, 동반 빈도,
과거 유사 회차)를 즉시 분석하여 제공한다. 이를 통해 사용자는 자신의 조합이
"균형형(balanced)", "과열형(hot)", "냉각형(cold)" 중 어디에 속하는지
객관적으로 판단할 수 있다.

조합을 저장하거나 추천하지는 않으며, 단순히 입력된 조합의 통계적 특성을
즉석에서 보여주는 읽기 전용 분석 도구이다.

## 요구사항 (EARS)

### REQ-CMB-001: 조합 분석 API (Event-Driven)

WHEN 클라이언트가 `POST /api/analyze-combination`에 6개 번호를 담은
`{"numbers": [3, 7, 14, 22, 35, 42]}` 형식의 body를 전송하면,
시스템은 다음 항목을 포함한 JSON 응답을 반환해야 한다(SHALL):

- `sum`: 6개 번호의 합계 (정수)
- `odd_count`: 홀수 개수 (정수)
- `even_count`: 짝수 개수 (정수)
- `range_distribution`: 번호대별 개수 객체.
  키는 `"1-10"`, `"11-20"`, `"21-30"`, `"31-40"`, `"41-45"`, 값은 각 구간 개수
- `consecutive_count`: 연속 번호 쌍 수 (예: 3,4가 있으면 1쌍, 3,4,5는 2쌍)
- `frequency_score`: 각 번호의 전체 회차 누적 출현 빈도 평균 (실수)
- `recent_score`: 각 번호의 최근 20회 출현 빈도 평균 (실수)
- `companion_score`: 6개 번호로 만들 수 있는 15개 쌍 중,
  과거 함께 출현한 동반 빈도의 평균 (실수)
- `historical_match`: 과거 회차 중 이 조합과 5개 이상 일치한 회차 목록 (최대 5건)
- `verdict`: `"balanced"` | `"hot"` | `"cold"` 중 하나

### REQ-CMB-002: 입력 검증 (Unwanted Behavior)

IF 입력 번호가 정확히 6개가 아니거나, 1~45 범위를 벗어나거나,
중복된 번호를 포함하면, THEN 시스템은 HTTP 422(Unprocessable Entity)
응답을 반환해야 한다(SHALL).

- 번호 개수가 6개가 아님 → 422
- 번호 중 하나라도 1 미만 또는 45 초과 → 422
- 중복 번호 존재 → 422
- `numbers` 키 누락 또는 리스트가 아님 → 422

### REQ-CMB-003: 데이터 부재 시 기본값 (State-Driven)

WHILE 당첨 데이터가 없거나 비어 있는 상태에서,
시스템은 다음과 같이 안전한 기본값을 반환해야 한다(SHALL):

- `frequency_score` = 0.0
- `recent_score` = 0.0
- `companion_score` = 0.0
- `historical_match` = `[]`
- `sum`, `odd_count`, `even_count`, `range_distribution`,
  `consecutive_count`는 입력값만으로 계산 가능하므로 정상 계산
- `verdict`는 빈도 점수가 모두 0이므로 `"cold"`로 판정

### REQ-CMB-004: 판정 기준 (Ubiquitous)

시스템은 `frequency_score`(전체 빈도 점수)를 기준으로
`verdict`를 결정해야 한다(SHALL):

- 전체 번호의 평균 출현 빈도 대비 입력 조합의 `frequency_score`가
  현저히 높으면 `"hot"`
- 현저히 낮으면 `"cold"`
- 평균 범위 내이면 `"balanced"`
- 판정 임계값은 전체 번호 평균 빈도의 ±15% 편차를 기준으로 한다

### REQ-CMB-005: 조합 분석 웹 섹션 (Event-Driven)

WHEN 사용자가 `/recommend` 페이지에 접속하면,
시스템은 "조합 분석" 섹션을 표시해야 한다(SHALL).

- 6개 번호를 입력하는 폼(입력 필드 6개 또는 단일 입력) 제공
- WHEN 사용자가 번호를 입력하고 분석 버튼을 누르면,
  시스템은 `POST /api/analyze-combination`을 호출하여
  결과를 분석 결과 카드 형태로 표시해야 한다(SHALL)
- 결과 카드에는 합계, 홀짝 비율, 번호대 분포, 연속 쌍 수,
  빈도 점수, 동반 점수, 과거 유사 회차, 판정(verdict)을 시각적으로 표시

### REQ-CMB-006: 입력 오류 사용자 피드백 (Unwanted Behavior)

IF 사용자가 웹 폼에서 잘못된 조합(6개 미만, 범위 초과, 중복)을 입력하면,
THEN 시스템은 분석을 수행하지 않고 사용자에게 명확한 오류 메시지를
표시해야 한다(SHALL).

## Exclusions (What NOT to Build)

- 조합 저장 기능 없음 (입력은 즉석 분석만, 영속화하지 않음)
- 7번째 번호(보너스) 분석 미포함 (6개 본번호만 분석)
- 조합 추천/생성 기능 없음 (기존 `/api/recommendations`가 담당)
- 조합 간 비교 기능 없음 (한 번에 하나의 조합만 분석)
- 당첨 확률 계산 없음 (통계적 특성만 제공, 확률 예측은 하지 않음)
- 인증/권한 기능 없음

## 기술적 제약

- Python 3.11, FastAPI + Jinja2
- CSV/JSON 파일 저장소 사용 (DB 미사용)
- 기존 `lotto/analyzer.py`의 빈도/동반 분석 로직 재사용
- 응답 시간: 단일 조합 분석은 P95 기준 500ms 이내
- 테스트 커버리지 85% 이상 유지
