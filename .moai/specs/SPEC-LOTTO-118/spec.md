---
id: SPEC-LOTTO-118
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-118: 이월 번호 분석

## 개요 (Overview)

전 회차 당첨 번호 중 다음 회차에도 동일하게 등장하는 번호(이월 번호)의 수를 연속 회차 쌍마다 계산하여,
분포·평균·최빈값과 최근 20회차 상세 이력을 `/stats/carryover` 페이지로 제공한다.

로또 구매자들이 "보통 1~2개 번호가 이월된다"는 경험칙을 실제 데이터로 검증할 수 있다.

## EARS 요구사항 (Requirements)

### REQ-CO-001 — 이월 번호 수 집계

**WHEN** 사용자가 `/stats/carryover` 페이지에 접근하면
**THE SYSTEM SHALL** 연속 회차 쌍(i-1, i)마다 전 회차 번호와 현 회차 번호의 교집합 크기를 계산한다.

### REQ-CO-002 — 분포 반환

**THE SYSTEM SHALL** 이월 번호 수(0~6개)별 회차 쌍 수와 비율을 분포 딕셔너리로 반환한다.

### REQ-CO-003 — 요약 통계

**THE SYSTEM SHALL** 평균 이월 번호 수(`avg_carryover`), 최빈 이월 수(`most_common`),
분석 쌍 수(`total_pairs`)를 함께 반환한다.

### REQ-CO-004 — 최근 20회차 상세

**THE SYSTEM SHALL** 가장 최근 20회차 각각에 대해 이월된 번호 목록과 개수를 반환한다.

### REQ-CO-005 — 빈 데이터 처리

**WHEN** 데이터가 없거나 1회차만 있으면
**THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고 메시지를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_carryover_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/carryover` 라우트 추가 |
| `lotto/web/templates/carryover.html` | 요약 카드 + 분포 표 + 최근 20회차 테이블 |
| `lotto/web/templates/base.html` | 네비게이션 '이월 번호' 링크 추가 |
| `tests/test_carryover.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3130 → 3140개
- 커밋: `1a7f4bf`
