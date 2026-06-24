---
id: SPEC-LOTTO-124
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-124: 소수 번호 분석

## 개요 (Overview)

1~45 중 소수(2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43 — 14개)의
당첨 출현 패턴을 분석하여 `/stats/prime-numbers` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-PM-001 — 회차별 소수 개수 분포

**THE SYSTEM SHALL** 각 회차에서 6개 번호 중 소수가 0~6개 포함되는 분포를 집계한다.

### REQ-PM-002 — 개별 소수 출현 빈도

**THE SYSTEM SHALL** 각 소수(2~43)가 당첨 번호로 출현한 횟수와 비율을 반환한다.

### REQ-PM-003 — 전체 소수 출현율

**THE SYSTEM SHALL** 전체 당첨 번호 중 소수의 비율과 기대값(14/45 ≈ 31.11%)을 함께 반환한다.

### REQ-PM-004 — 요약 통계

**THE SYSTEM SHALL** 최빈 소수 개수, 최빈 소수 개수 비율, 누적 소수 출현 수를 반환한다.

### REQ-PM-005 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `PRIMES_1_45` 상수 + `get_prime_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/prime-numbers` 라우트 추가 |
| `lotto/web/templates/prime_numbers.html` | 요약 카드 + 소수 개수 분포 표 + 개별 소수 빈도 표 |
| `lotto/web/templates/base.html` | 네비게이션 '소수 분석' 링크 추가 |
| `tests/test_prime_numbers.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3193 → 3203개
- 커밋: `4d394e3`
