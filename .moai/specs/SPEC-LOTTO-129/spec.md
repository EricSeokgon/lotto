---
id: SPEC-LOTTO-129
version: 1.0.0
status: completed
created: 2026-06-25
updated: 2026-06-25
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-129: 번호 중앙값 분포 분석

## 개요 (Overview)

정렬된 6개 당첨 번호의 중앙값(3번째·4번째 번호의 평균)을 구간별로 분석하여
`/stats/median` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-MD-001 — 중앙값 계산

**THE SYSTEM SHALL** 각 회차의 정렬된 6개 번호 중 3번째와 4번째 번호의 평균을 중앙값으로 계산한다.

### REQ-MD-002 — 구간 분포

**THE SYSTEM SHALL** 중앙값을 7개 구간(~9, 10~14, 15~19, 20~24, 25~29, 30~34, 35~)으로 나누어 분포를 반환한다.

### REQ-MD-003 — 중심값(23) 기준 편향 분석

**THE SYSTEM SHALL** 중앙값이 23보다 작은(저편향) / 같은(균형) / 큰(고편향) 회차 수와 비율을 반환한다.

### REQ-MD-004 — 요약 통계

**THE SYSTEM SHALL** 평균 중앙값, 최소/최대 중앙값 및 해당 회차 번호를 반환한다.

### REQ-MD-005 — 최근 20회 상세

**THE SYSTEM SHALL** 최근 20회차의 당첨 번호와 각 회차의 중앙값을 반환한다.

### REQ-MD-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_median_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/median` 라우트 추가 |
| `lotto/web/templates/median.html` | 요약 카드 + 중심값 분포 + 구간 분포표 + 최근 20회 |
| `lotto/web/templates/base.html` | 네비게이션 '중앙값' 링크 추가 |
| `tests/test_median.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3243 → 3253개
- 커밋: `399c234`
