---
id: SPEC-LOTTO-119
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-119: 번호 조합 가이드

## 개요 (Overview)

실제 당첨 데이터를 바탕으로 최적 번호 조합 패턴(홀짝 비율, 합계 구간, 연속 번호 쌍, 구간 커버 수, 저/고 비율)을
5가지 카드 레이아웃과 요약 원칙 표로 제공하는 `/stats/combo-guide` 페이지를 구현한다.

## EARS 요구사항 (Requirements)

### REQ-CG-001 — 홀짝 비율 분포

**THE SYSTEM SHALL** 각 회차 6개 번호 중 홀수 개수(0~6)별 분포와 최빈값을 반환한다.

### REQ-CG-002 — 합계 구간 분포

**THE SYSTEM SHALL** 6개 번호 합계를 20단위 구간(~79, 80~99, …, 200~)으로 나누어
구간별 분포와 최빈 구간을 반환한다.

### REQ-CG-003 — 연속 번호 쌍 수 분포

**THE SYSTEM SHALL** 각 회차에서 연속된 번호 쌍(예: 3-4, 7-8) 수를 계산하여 분포를 반환한다.

### REQ-CG-004 — 구간 커버 수 분포

**THE SYSTEM SHALL** 1~9 / 10~19 / 20~29 / 30~39 / 40~45 중 몇 개 구간이 커버되는지
분포와 최빈값을 반환한다.

### REQ-CG-005 — 저/고 비율 분포

**THE SYSTEM SHALL** 1~22(저) vs 23~45(고) 기준으로 저번호 개수(0~6)별 분포를 반환한다.

### REQ-CG-006 — 요약 원칙 표

**THE SYSTEM SHALL** 5가지 지표의 최빈값을 한 곳에 모은 "최적 조합 원칙 요약" 카드를 표시한다.

### REQ-CG-007 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_combo_guide()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/combo-guide` 라우트 추가 |
| `lotto/web/templates/combo_guide.html` | 6개 카드 레이아웃 템플릿 |
| `lotto/web/templates/base.html` | 네비게이션 '조합 가이드' 링크 추가 |
| `tests/test_combo_guide.py` | 12개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +12개
- 누적 테스트: 3140 → 3152개
- 커밋: `fa01f0e`
