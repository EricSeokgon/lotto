---
id: SPEC-LOTTO-128
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-128: 핫/콜드 번호 분석

## 개요 (Overview)

최근 10회 / 최근 50회 / 전체 기간의 번호 출현 빈도를 비교하여 핫(자주 나오는)·콜드(오래 안 나오는) 번호를
`/stats/hot-cold` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-HC-001 — 상태 분류

**THE SYSTEM SHALL** 각 번호(1~45)를 최근 10회 출현 횟수 기준으로 hot(3회 이상),
warm(1~2회), cold(0회)로 분류한다.

### REQ-HC-002 — 3개 시간창 비교

**THE SYSTEM SHALL** 전체 기간, 최근 50회, 최근 10회 각각의 출현 횟수와 비율을 반환한다.

### REQ-HC-003 — 미출현 기간

**THE SYSTEM SHALL** 각 번호가 마지막으로 출현한 이후 경과 회차를 반환한다.

### REQ-HC-004 — TOP 10 목록

**THE SYSTEM SHALL** 핫 번호 상위 10개, 콜드 번호 상위 10개를 반환한다.

### REQ-HC-005 — 기대값

**THE SYSTEM SHALL** 균등 분포 기대값(6/45 × 100 ≈ 13.33%)을 반환한다.

### REQ-HC-006 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_hot_cold_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/hot-cold` 라우트 추가 |
| `lotto/web/templates/hot_cold.html` | 요약 카드 + 핫/콜드 TOP10 + 전체 번호 그리드 |
| `lotto/web/templates/base.html` | 네비게이션 '핫/콜드' 링크 추가 |
| `tests/test_hot_cold.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3233 → 3243개
- 커밋: `49bb04d`
