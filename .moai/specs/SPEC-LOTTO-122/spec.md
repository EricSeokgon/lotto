---
id: SPEC-LOTTO-122
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-122: 번호 끝자리(일의 자리) 분석

## 개요 (Overview)

당첨 번호 6개의 일의 자리(0~9) 분포와 기대값 대비 비율, 그리고 한 회차에서
커버된 끝자리 종류 수(1~6) 분포를 `/stats/tail-digits` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-TD-001 — 끝자리별 출현 빈도

**THE SYSTEM SHALL** 전체 당첨 번호에서 끝자리(0~9)별 출현 횟수와 비율을 집계한다.

### REQ-TD-002 — 기대값 대비 비율

**THE SYSTEM SHALL** 끝자리별 기대 빈도(해당 끝자리 번호 수 / 45 × 총 번호 수)와
실제 출현 수의 비율(`ratio`)을 함께 반환한다.

### REQ-TD-003 — 커버 종류 수 분포

**THE SYSTEM SHALL** 각 회차에서 6개 번호가 커버한 서로 다른 끝자리 종류 수(1~6)를
집계하여 분포를 반환한다.

### REQ-TD-004 — 요약 통계

**THE SYSTEM SHALL** 최빈 끝자리(`best_tail`), 최빈 끝자리 비율, 최빈 커버 종류 수(`best_cover`),
최빈 커버 비율을 반환한다.

### REQ-TD-005 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_tail_digit_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/tail-digits` 라우트 추가 |
| `lotto/web/templates/tail_digits.html` | 요약 카드 + 끝자리 분포 표 + 커버 수 분포 표 |
| `lotto/web/templates/base.html` | 네비게이션 '끝자리 분석' 링크 추가 |
| `tests/test_tail_digits.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3173 → 3183개
- 커밋: `cec16ca`
