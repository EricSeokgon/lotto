---
id: SPEC-LOTTO-132
version: 1.0.0
status: completed
created: 2026-06-25
updated: 2026-06-25
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-132: 연속 번호 패턴 분석

## 개요 (Overview)

6개 당첨 번호 중 연속된 번호(예: 7-8, 15-16-17)가 포함되는 패턴을 분석하여
`/stats/consecutive` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-CN-001 — 연속 런 탐지

**THE SYSTEM SHALL** 각 회차의 정렬된 6개 번호에서 연속된 숫자 구간(run)을 탐지한다.

### REQ-CN-002 — 연속 쌍 수 분포

**THE SYSTEM SHALL** 회차별 연속 쌍(pair) 수(0, 1, 2, …)의 분포를 반환한다.

### REQ-CN-003 — 최장 연속 길이 분포

**THE SYSTEM SHALL** 회차별 최장 연속 구간의 길이(1=없음, 2, 3, 4, 5, 6)의 분포를 반환한다.

### REQ-CN-004 — 자주 나온 연속 쌍 TOP 20

**THE SYSTEM SHALL** 전체 기간 동안 연속 쌍으로 가장 많이 출현한 번호 쌍 TOP 20을 반환한다.

### REQ-CN-005 — 요약 통계

**THE SYSTEM SHALL** 연속 번호가 포함된 회차 수·비율 및 없는 회차 수·비율을 반환한다.

### REQ-CN-006 — 최근 20회 상세

**THE SYSTEM SHALL** 최근 20회차의 번호와 연속 구간 정보를 반환한다.

### REQ-CN-007 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_consecutive_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/consecutive` 라우트 추가 |
| `lotto/web/templates/consecutive.html` | 요약 카드 + 쌍 수 분포 + 최장 길이 분포 + TOP 20 쌍 + 최근 20회 |
| `lotto/web/templates/base.html` | 네비게이션 '연속 번호' 링크 추가 |
| `tests/test_consecutive.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3273 → 3283개
- 커밋: `63d6070`
