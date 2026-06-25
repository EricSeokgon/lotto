---
id: SPEC-LOTTO-133
version: 1.0.0
status: completed
created: 2026-06-25
updated: 2026-06-25
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-133: 번호 쌍(pair) 동시 출현 빈도 분석

## 개요 (Overview)

같은 회차에서 두 번호가 함께 당첨된 빈도(C(6,2)=15쌍/회차)를 분석하여
`/stats/pair-frequency` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-PF-001 — 쌍 빈도 계산

**THE SYSTEM SHALL** 각 회차의 6개 번호에서 C(6,2)=15개 쌍을 생성하여 전체 동시 출현 횟수를 집계한다.

### REQ-PF-002 — TOP 20 빈출 쌍

**THE SYSTEM SHALL** 가장 많이 동시 출현한 쌍 TOP 20과 출현 횟수·비율을 반환한다.

### REQ-PF-003 — TOP 20 희귀 쌍

**THE SYSTEM SHALL** 가장 드물게 동시 출현한(출현 횟수 > 0) 쌍 TOP 20을 반환한다.

### REQ-PF-004 — 번호별 파트너 TOP 5

**THE SYSTEM SHALL** 번호 1~45 각각에 대해 가장 자주 함께 나온 번호 TOP 5를 반환한다.

### REQ-PF-005 — 요약 통계

**THE SYSTEM SHALL** 쌍별 기대 출현 횟수, 출현한 쌍 수, 한 번도 안 나온 쌍 수를 반환한다.

### REQ-PF-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_pair_frequency_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/pair-frequency` 라우트 추가 |
| `lotto/web/templates/pair_frequency.html` | 요약 카드 + 빈출/희귀 쌍 TOP20 + 번호별 파트너 |
| `lotto/web/templates/base.html` | 네비게이션 '쌍 빈도' 링크 추가 |
| `tests/test_pair_frequency.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3283 → 3293개
- 커밋: `349a020`
