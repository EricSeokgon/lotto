---
id: SPEC-LOTTO-127
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-127: 배수(Multiple) 분석

## 개요 (Overview)

3의 배수(15개), 5의 배수(9개), 7의 배수(6개)가 당첨 번호에 포함되는 패턴을
분석하여 `/stats/multiples` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-ML-001 — 회차별 배수 개수 분포

**THE SYSTEM SHALL** 각 배수 유형(3/5/7)에 대해 회차당 포함 개수(0~6)의 분포를 반환한다.

### REQ-ML-002 — 실제 출현율 vs 기대값

**THE SYSTEM SHALL** 각 배수 유형의 실제 출현율과 기대값(count_in_range/45 × 100%)을 반환한다.

### REQ-ML-003 — 개별 번호 빈도

**THE SYSTEM SHALL** 각 배수 집합 내 개별 번호의 출현 횟수와 비율을 반환한다.

### REQ-ML-004 — 요약 통계

**THE SYSTEM SHALL** 각 배수 유형의 최빈 개수와 비율을 반환한다.

### REQ-ML-005 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `MULTIPLES_3/5/7` 상수 + `get_multiples_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/multiples` 라우트 추가 |
| `lotto/web/templates/multiples.html` | 비교 카드 + 3개 유형 상세 분포표 + 개별 빈도 |
| `lotto/web/templates/base.html` | 네비게이션 '배수 분석' 링크 추가 |
| `tests/test_multiples.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3223 → 3233개
- 커밋: `3ddbf6a`
