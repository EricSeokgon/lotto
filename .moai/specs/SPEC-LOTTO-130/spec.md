---
id: SPEC-LOTTO-130
version: 1.0.0
status: completed
created: 2026-06-25
updated: 2026-06-25
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-130: 번호 범위(최대-최소) 분포 분석

## 개요 (Overview)

6개 당첨 번호의 최대값과 최소값의 차이(Range)를 구간별로 분석하여
`/stats/number-range` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-NR-001 — 범위 계산

**THE SYSTEM SHALL** 각 회차의 6개 번호에서 max - min 값을 범위로 계산한다.

### REQ-NR-002 — 구간 분포

**THE SYSTEM SHALL** 범위를 7개 구간(5~14, 15~19, 20~24, 25~29, 30~34, 35~39, 40~44)으로 분류하여 분포를 반환한다.

### REQ-NR-003 — 요약 통계

**THE SYSTEM SHALL** 평균 범위, 최소/최대 범위 및 해당 회차 번호를 반환한다.

### REQ-NR-004 — 최소/최대 번호 빈도

**THE SYSTEM SHALL** 각 회차에서 최소 번호·최대 번호로 가장 많이 등장한 번호 TOP 10을 반환한다.

### REQ-NR-005 — 최근 20회 상세

**THE SYSTEM SHALL** 최근 20회차의 당첨 번호와 각 회차의 범위 값을 반환한다.

### REQ-NR-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_number_range_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/number-range` 라우트 추가 |
| `lotto/web/templates/number_range.html` | 요약 카드 + 구간 분포 + 최소/최대 번호 TOP10 + 최근 20회 |
| `lotto/web/templates/base.html` | 네비게이션 '번호 범위' 링크 추가 |
| `tests/test_number_range.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3253 → 3263개
- 커밋: `a337000`
