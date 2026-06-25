---
id: SPEC-LOTTO-131
version: 1.0.0
status: completed
created: 2026-06-25
updated: 2026-06-25
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-131: 번호 합계 끝자리(일의 자리) 분석

## 개요 (Overview)

6개 당첨 번호 합계의 일의 자리(0~9) 분포를 분석하여
`/stats/sum-last-digit` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-SLD-001 — 끝자리 계산

**THE SYSTEM SHALL** 각 회차의 6개 번호 합계에서 `sum % 10`으로 일의 자리를 계산한다.

### REQ-SLD-002 — 0~9 분포

**THE SYSTEM SHALL** 끝자리 0~9 각각의 출현 횟수와 비율을 반환한다.

### REQ-SLD-003 — 홀짝 비율

**THE SYSTEM SHALL** 홀수 끝자리(1,3,5,7,9)와 짝수 끝자리(0,2,4,6,8)의 회차 수와 비율을 반환한다.

### REQ-SLD-004 — 요약 통계

**THE SYSTEM SHALL** 평균 합계, 최빈 끝자리, 최소 빈도 끝자리를 반환한다.

### REQ-SLD-005 — 최근 20회 상세

**THE SYSTEM SHALL** 최근 20회차의 번호, 합계, 끝자리를 반환한다.

### REQ-SLD-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_sum_last_digit_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/sum-last-digit` 라우트 추가 |
| `lotto/web/templates/sum_last_digit.html` | 요약 카드 + 끝자리 분포표 + 최근 20회 |
| `lotto/web/templates/base.html` | 네비게이션 '합계 끝자리' 링크 추가 |
| `tests/test_sum_last_digit.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3263 → 3273개
- 커밋: `e155f3c`
