---
id: SPEC-LOTTO-125
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-125: 번호 표준편차 분석

## 개요 (Overview)

6개 당첨 번호의 표준편차(분산도)를 분석하여 번호가 얼마나 넓게 퍼져 있는지를
구간별 분포로 `/stats/std-deviation` 페이지에 제공한다.

## EARS 요구사항 (Requirements)

### REQ-SD-001 — 표준편차 계산

**THE SYSTEM SHALL** 각 회차 6개 번호의 모집단 표준편차(population std dev)를 계산한다.

### REQ-SD-002 — 구간 분포

**THE SYSTEM SHALL** 표준편차를 [0,5), [5,8), [8,11), [11,14), [14,17), [17,∞) 6개 구간으로
분류하여 각 구간별 회차 수와 비율을 반환한다.

### REQ-SD-003 — 극값 정보

**THE SYSTEM SHALL** 최소·최대 표준편차 값과 해당 회차 번호를 반환한다.

### REQ-SD-004 — 최근 20회차

**THE SYSTEM SHALL** 최근 20회차의 번호와 표준편차를 반환한다.

### REQ-SD-005 — 요약 통계

**THE SYSTEM SHALL** 평균 표준편차, 최빈 구간과 비율을 반환한다.

### REQ-SD-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_std_deviation_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/std-deviation` 라우트 추가 |
| `lotto/web/templates/std_deviation.html` | 요약 카드 + 구간 분포 표 + 최근 20회차 표 |
| `lotto/web/templates/base.html` | 네비게이션 '표준편차' 링크 추가 |
| `tests/test_std_deviation.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3203 → 3213개
- 커밋: `abfdb3b`
