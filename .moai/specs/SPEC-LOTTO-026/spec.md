---
id: SPEC-LOTTO-026
version: 0.1.0
status: Planned
created: 2026-05-29
updated: 2026-05-29
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-026: 번호 트렌드 히트맵 분석

## HISTORY

- 2026-05-29 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 분석 / 시각화 |
| 영향 범위 | API, 웹 페이지 (`/analyze`) |
| 의존 SPEC | SPEC-LOTTO-001(수집), SPEC-LOTTO-002(분석) |

## 배경 및 목적

기존 `/analyze` 페이지는 전체 누적 빈도 통계와 패턴 분석을 제공하지만,
시간 흐름에 따른 번호 출현 변화(트렌드)는 보여주지 못한다.
사용자는 "최근 들어 자주 나오는 번호(핫넘버)"와 "오랫동안 안 나온 번호(콜드넘버)",
그리고 연도/분기별 출현 빈도의 변화 흐름을 한눈에 파악하고 싶어 한다.

본 SPEC은 기존에 수집된 회차 데이터(CSV)를 기반으로
연도/분기별 번호 출현 빈도 행렬(히트맵)과 핫/콜드 번호 트렌드를 계산하여
API로 제공하고, `/analyze` 페이지에 새 "트렌드" 탭으로 시각화한다.
새 데이터 저장이나 DB 도입 없이 기존 CSV에서 즉시 계산하는 것을 원칙으로 한다.

## 요구사항 (EARS)

### REQ-TREND-001: 기간별 출현 행렬 API (Ubiquitous)

`GET /api/trend-heatmap?period=yearly|quarterly` 요청 시,
시스템은 SHALL 번호(1~45)를 행으로, 기간 목록(연도 또는 분기)을 열로 하는
출현 빈도 행렬을 반환한다.

- 응답 구조: `{ "period": "yearly", "periods": [...], "numbers": [1..45], "matrix": [[...], ...] }`
  - `periods`: 기간 라벨 목록 (예: `["2023", "2024", "2025"]` 또는 `["2024-Q1", "2024-Q2"]`)
  - `matrix[i][j]`: 번호 `numbers[i]`가 기간 `periods[j]`에 출현한 횟수
- `period` 파라미터 기본값은 `yearly`.

### REQ-TREND-002: period 파라미터 검증 (Unwanted Behavior)

IF `period` 값이 `yearly` 또는 `quarterly`가 아니면,
THEN 시스템은 SHALL HTTP 400과 함께 허용 값 안내 메시지를 반환한다.

### REQ-TREND-003: 핫/콜드 번호 API (Event-Driven)

WHEN `GET /api/hot-cold?recent_n=20` 요청이 들어오면,
시스템은 SHALL 최근 N회차의 번호별 출현 빈도와 전체 평균 출현 빈도를 비교하여
핫넘버(상위 10개)와 콜드넘버(하위 10개)를 반환한다.

- 응답 구조: `{ "recent_n": 20, "hot": [{number, recent_count, avg_count, diff}, ...], "cold": [...] }`
- `recent_n` 기본값은 `20`, 최소 1.
- `diff`는 `recent_count` 비율과 전체 평균 비율의 차이(양수=핫, 음수=콜드).

### REQ-TREND-004: recent_n 경계 처리 (State-Driven)

WHILE 전체 회차 수가 `recent_n`보다 적은 상태에서는,
시스템은 SHALL 존재하는 전체 회차를 대상으로 계산하며 오류를 발생시키지 않는다.

### REQ-TREND-005: 빈 데이터 처리 (Unwanted Behavior)

IF 수집된 회차 데이터가 전혀 없으면,
THEN 시스템은 SHALL HTTP 404가 아닌, 빈 결과(`periods: []`, `matrix: []`, `hot: []`, `cold: []`)를
HTTP 200으로 반환한다.

### REQ-TREND-006: 트렌드 탭 UI (Where Feature Exists)

WHERE `/analyze` 페이지가 제공되는 경우,
시스템은 SHALL "트렌드" 탭을 추가하고 다음을 표시한다.
- Chart.js 기반 히트맵 색상 테이블 (번호별 × 기간별 출현 강도를 색 농도로 표현)
- 핫넘버/콜드넘버 카드 (번호, 최근 출현 횟수, 평균 대비 증감)
- 기간 단위(연도/분기) 토글

### REQ-TREND-007: 로딩·빈 상태 표시 (Event-Driven)

WHEN 트렌드 탭에서 데이터가 비어 있는 응답을 받으면,
시스템은 SHALL "분석할 데이터가 없습니다" 빈 상태 메시지를 표시한다.

## Exclusions (What NOT to Build)

- 트렌드 계산 결과를 별도 파일/DB에 저장하지 않는다 (기존 CSV에서 매 요청 시 계산).
- 미래 회차 번호 예측 기능은 포함하지 않는다 (출현 빈도 집계만 제공).
- 히트맵 이미지 파일(PNG 등) 내보내기 기능은 포함하지 않는다.
- 핫/콜드 임계값을 사용자가 커스터마이징하는 설정 기능은 포함하지 않는다 (상위/하위 10개 고정).

## 제약 조건 (Constraints)

- 언어/런타임: Python 3.11
- 저장소: DB 사용 안 함. 데이터 소스는 기존 회차 CSV.
- 새 파일 저장 불필요 (읽기 전용 계산).
- 프론트엔드: Jinja2 템플릿 + Chart.js (기존 `/analyze` 자산 재사용).
- 응답 형식: JSON (REST API), HTML (페이지 탭).
