---
id: SPEC-LOTTO-123
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-123: 번호 간격(Gap) 분석

## 개요 (Overview)

정렬된 당첨 번호 6개 사이의 5개 차이값(gap) 패턴을 분석하여 최솟값 gap 분포,
최댓값 gap 분포, 연속 번호 쌍 수 분포를 `/stats/number-gaps` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-NG-001 — 최솟값 gap 분포

**THE SYSTEM SHALL** 각 회차에서 5개 gap 중 최솟값의 분포를 집계한다.

### REQ-NG-002 — 최댓값 gap 분포

**THE SYSTEM SHALL** 각 회차에서 5개 gap 중 최댓값의 분포를 집계한다.

### REQ-NG-003 — 연속 번호 쌍 수 분포

**THE SYSTEM SHALL** 각 회차에서 gap=1인 쌍(연속 번호) 수(0~5)의 분포를 집계한다.

### REQ-NG-004 — 평균 간격

**THE SYSTEM SHALL** 전체 회차의 평균 간격((n6-n1)/5)을 계산한다.

### REQ-NG-005 — 요약 통계

**THE SYSTEM SHALL** 최빈 최솟값 gap, 최빈 최댓값 gap, 최빈 연속 쌍 수와 각 비율을 반환한다.

### REQ-NG-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_number_gap_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/number-gaps` 라우트 추가 |
| `lotto/web/templates/number_gaps.html` | 3단 레이아웃: 최솟값 gap / 최댓값 gap(상위 15개) / 연속 쌍 수 분포 |
| `lotto/web/templates/base.html` | 네비게이션 '번호 간격' 링크 추가 |
| `tests/test_number_gaps.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3183 → 3193개
- 커밋: `411507a`
