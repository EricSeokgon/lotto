---
id: SPEC-LOTTO-120
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-120: 계절별 번호 출현 분석

## 개요 (Overview)

봄(3~5월)·여름(6~8월)·가을(9~11월)·겨울(12~2월) 시즌별로 로또 당첨 번호의 출현 빈도와
상위 10개 번호를 분석하여 `/stats/seasonal` 페이지로 제공한다.
모든 시즌에 공통으로 Top10에 포함된 번호도 함께 표시한다.

## EARS 요구사항 (Requirements)

### REQ-SE-001 — 계절 분류

**THE SYSTEM SHALL** 각 회차의 추첨일 월(month)을 기준으로
봄(3~5월), 여름(6~8월), 가을(9~11월), 겨울(12~2월) 4개 시즌으로 분류한다.

### REQ-SE-002 — 시즌별 번호 빈도

**THE SYSTEM SHALL** 각 시즌별로 1~45 번호의 출현 횟수를 집계하고
출현율(출현 수 / 해당 시즌 회차 수 × 100)을 계산한다.

### REQ-SE-003 — Top 10 반환

**THE SYSTEM SHALL** 각 시즌별로 출현 횟수 내림차순 상위 10개 번호를 반환한다.

### REQ-SE-004 — 시즌별 회차 수

**THE SYSTEM SHALL** 각 시즌에 속하는 회차 수(`draws`)를 함께 반환한다.

### REQ-SE-005 — 공통 번호 표시

**THE SYSTEM SHALL** 페이지에서 4개 시즌 모두의 Top10에 포함된 번호를 별도로 표시한다.

### REQ-SE-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_seasonal_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/seasonal` 라우트 추가 |
| `lotto/web/templates/seasonal.html` | 4개 시즌 카드 + 공통 번호 섹션 |
| `lotto/web/templates/base.html` | 네비게이션 '계절별 분석' 링크 추가 |
| `tests/test_seasonal.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3152 → 3162개
- 커밋: `2e1c8c9`
